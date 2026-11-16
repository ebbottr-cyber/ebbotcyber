"""No real application database is accessed by these rehearsal tests."""
import sqlite3

import pytest

from scripts import sqlite_migration_rehearsal as rehearsal


def _seed_marker(path):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE operator_marker (id INTEGER PRIMARY KEY, payload TEXT)")
        conn.execute("INSERT INTO operator_marker VALUES (1, 'keep-me')")


def _seed_stock_daily(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE stock_daily (id INTEGER PRIMARY KEY, code TEXT, "
            "date TEXT, open REAL, high REAL, low REAL, close REAL, "
            "volume REAL, data_source TEXT)"
        )
        conn.execute(
            "INSERT INTO stock_daily VALUES "
            "(7, 'THYAO.IS', '2026-11-13', 1.0, 2.0, 0.5, 1.5, 900, 'Yahoo Finance')"
        )


def test_rehearsal_runs_real_bootstrap_only_on_disposable_clone(tmp_path):
    source = tmp_path / "marker.sqlite"
    _seed_marker(source)
    with sqlite3.connect(source) as conn:
        before = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    report = rehearsal.rehearse(source)
    assert report["status"] == "isolated_rehearsal_passed"
    assert report["input_verified"] == "ok"
    assert "operator_marker" in report["preexisting_tables_preserved"]
    with sqlite3.connect(source) as conn:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall() == before
        assert conn.execute("SELECT * FROM operator_marker").fetchall() == [(1, "keep-me")]


def test_rehearsal_blocks_deleted_rows_without_touching_original(tmp_path, monkeypatch):
    source = tmp_path / "marker.sqlite"
    _seed_marker(source)

    def delete_from_clone(staged):
        assert staged.resolve() != source.resolve()
        with sqlite3.connect(staged) as db:
            db.execute("DELETE FROM operator_marker")

    monkeypatch.setattr(rehearsal, "_migrate_isolated", delete_from_clone)
    with pytest.raises(RuntimeError, match="row count"):
        rehearsal.rehearse(source)
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT * FROM operator_marker").fetchall() == [(1, "keep-me")]


def test_rehearsal_detects_changed_bist_prices_even_when_count_is_same(tmp_path, monkeypatch):
    source = tmp_path / "prices.sqlite"
    _seed_stock_daily(source)

    def tamper_with_clone(staged):
        with sqlite3.connect(staged) as db:
            db.execute("UPDATE stock_daily SET close = 99 WHERE id = 7")

    monkeypatch.setattr(rehearsal, "_migrate_isolated", tamper_with_clone)
    with pytest.raises(RuntimeError, match="critical 'stock_daily'"):
        rehearsal.rehearse(source)
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT close FROM stock_daily WHERE id=7").fetchone() == (1.5,)


def test_failed_rehearsal_never_mutates_input(tmp_path, monkeypatch):
    source = tmp_path / "marker.sqlite"
    _seed_marker(source)

    def fail_startup(_staged):
        raise RuntimeError("simulated legacy custom-index refusal")

    monkeypatch.setattr(rehearsal, "_migrate_isolated", fail_startup)
    with pytest.raises(RuntimeError, match="legacy custom-index"):
        rehearsal.rehearse(source)
    assert rehearsal.main(["--backup", str(source)]) == 2
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT COUNT(*) FROM operator_marker").fetchone()[0] == 1


def test_corrupt_input_blocks_without_starting_migration(tmp_path, monkeypatch):
    source = tmp_path / "bad.sqlite"
    source.write_bytes(b"not a sqlite database")

    def never_run(_staged):
        raise AssertionError("must not run migration")

    monkeypatch.setattr(rehearsal, "_migrate_isolated", never_run)
    assert rehearsal.main(["--backup", str(source)]) == 2


def test_rehearsal_preserves_operator_index_and_trigger(tmp_path):
    source = tmp_path / "custom_objects.sqlite"
    _seed_marker(source)
    with sqlite3.connect(source) as db:
        db.execute("CREATE INDEX operator_payload_idx ON operator_marker(payload)")
        db.execute(
            "CREATE TRIGGER operator_marker_guard AFTER UPDATE ON operator_marker "
            "BEGIN SELECT 1; END"
        )
    result = rehearsal.rehearse(source)
    assert result["preexisting_indexes_and_triggers_preserved"] == 2
    with sqlite3.connect(source) as db:
        assert db.execute("SELECT * FROM operator_marker").fetchall() == [(1, "keep-me")]


@pytest.mark.parametrize(
    ("object_sql", "drop_sql", "name"),
    [
        ("CREATE INDEX operator_payload_idx ON operator_marker(payload)",
         "DROP INDEX operator_payload_idx", "operator_payload_idx"),
        ("CREATE TRIGGER operator_marker_guard AFTER UPDATE ON operator_marker "
         "BEGIN SELECT 1; END",
         "DROP TRIGGER operator_marker_guard", "operator_marker_guard"),
    ],
)
def test_rehearsal_blocks_dropped_schema_objects_even_if_rows_preserved(
    tmp_path, monkeypatch, object_sql, drop_sql, name
):
    source = tmp_path / "custom.sqlite"
    _seed_marker(source)
    with sqlite3.connect(source) as db:
        db.execute(object_sql)

    def tamper_with_staged_schema(staged):
        assert staged.resolve() != source.resolve()
        with sqlite3.connect(staged) as db:
            db.execute(drop_sql)

    monkeypatch.setattr(rehearsal, "_migrate_isolated", tamper_with_staged_schema)
    with pytest.raises(RuntimeError, match="schema object"):
        rehearsal.rehearse(source)
    with sqlite3.connect(source) as db:
        assert db.execute("SELECT * FROM operator_marker").fetchall() == [(1, "keep-me")]
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE name=?", (name,)
        ).fetchone() == (name,)
