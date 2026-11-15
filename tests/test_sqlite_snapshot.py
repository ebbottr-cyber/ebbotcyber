"""Isolated regression checks; never access the configured application DB."""
import sqlite3

import pytest

from scripts.sqlite_snapshot import create_snapshot, verify_snapshot, main


def _seed(path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE history (id INTEGER PRIMARY KEY, symbol TEXT)")
        db.executemany("INSERT INTO history (symbol) VALUES (?)", [("THYAO.IS",), ("ASELS.IS",)])


def test_snapshot_preserves_committed_wal_rows_without_touching_source(tmp_path):
    source, dest = tmp_path / "source.db", tmp_path / "backup.db"
    with sqlite3.connect(source) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE history (id INTEGER PRIMARY KEY, symbol TEXT)")
        writer.execute("INSERT INTO history (symbol) VALUES ('THYAO.IS')")
        writer.commit()
        report = create_snapshot(source, dest)
        assert report["integrity"] == "ok"
        assert report["tables"] == 1
        with sqlite3.connect(dest) as backup:
            assert backup.execute("SELECT symbol FROM history").fetchall() == [("THYAO.IS",)]
        assert writer.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 1


def test_snapshot_refuses_overwrite_and_preserves_existing_bytes(tmp_path):
    source, dest = tmp_path / "source.db", tmp_path / "already.db"
    _seed(source)
    dest.write_bytes(b"operator-backup")
    with pytest.raises(FileExistsError):
        create_snapshot(source, dest)
    assert dest.read_bytes() == b"operator-backup"


def test_snapshot_refuses_same_file_and_missing_source(tmp_path):
    source = tmp_path / "source.db"
    _seed(source)
    with pytest.raises(ValueError):
        create_snapshot(source, source)
    with pytest.raises(FileNotFoundError):
        create_snapshot(tmp_path / "missing.db", tmp_path / "new.db")
    assert verify_snapshot(source)["tables"] == 1


def test_invalid_db_fails_closed_and_never_publishes_backup(tmp_path):
    source, dest = tmp_path / "bad.db", tmp_path / "never.db"
    source.write_bytes(b"not a sqlite database")
    assert main(["--source", str(source), "--output", str(dest)]) == 2
    assert not dest.exists()
    assert main(["--verify-only", str(source)]) == 2
