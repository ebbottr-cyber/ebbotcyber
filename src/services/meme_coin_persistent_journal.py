"""Explicitly opted-in SQLite storage for SYNTHETIC CLOSED SCENARIOS only.

No external data, wallets, trading endpoints, scheduler, API or order routing.
Storage is local research data; SHA-256 chaining detects accidental edits
but is NOT a substitute for signatures or a secure audit log.
"""
from __future__ import annotations

from contextlib import closing
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from src.services.meme_coin_paper_preview import _positive_decimal
from src.services.meme_coin_synthetic_journal import replay_synthetic_journal

_ZERO_HASH = "0" * 64
_MAX_RECORDS = 200
_VERSION = "1"


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "mode": "offline_synthetic_storage_only",
        "status": "blocked", "reason": reason,
        "trade_executed": False, "paper_trading_enabled": False,
        "live_trading_enabled": False, "realized_performance": False,
    }


def _canonical(event: dict[str, Any]) -> str:
    return json.dumps(
        event, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    )


def _file_path(database_path: Any) -> Path:
    if not isinstance(database_path, (str, Path)) or not str(database_path):
        raise ValueError("invalid_path")
    path = Path(database_path)
    if str(database_path).startswith("file:") or path.suffix != ".sqlite3":
        raise ValueError("invalid_path")
    path = path.absolute()
    if path.is_symlink() or not path.parent.is_dir():
        raise ValueError("invalid_path")
    return path


def _equity(value: Any) -> str:
    return str(_positive_decimal(value))


def _schema(db: sqlite3.Connection, equity: str) -> None:
    db.execute(
        "CREATE TABLE IF NOT EXISTS research_meta "
        "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS synthetic_scenarios ("
        "seq INTEGER PRIMARY KEY AUTOINCREMENT, "
        "event_id TEXT NOT NULL UNIQUE, strategy TEXT NOT NULL, "
        "trading_day TEXT NOT NULL, payload TEXT NOT NULL, "
        "previous_sha256 TEXT NOT NULL, entry_sha256 TEXT NOT NULL)"
    )
    db.executemany(
        "INSERT OR IGNORE INTO research_meta(key, value) VALUES (?, ?)",
        [("version", _VERSION), ("equity", equity), ("kill_latched", "0")],
    )


def _load(db: sqlite3.Connection, equity: str) -> tuple[list[dict[str, Any]], str, bool]:
    # A missing or altered metadata value is never silently repaired.
    meta = dict(db.execute("SELECT key, value FROM research_meta"))
    if set(meta) != {"version", "equity", "kill_latched"}:
        raise ValueError("invalid_metadata")
    if meta["version"] != _VERSION or meta["kill_latched"] not in ("0", "1"):
        raise ValueError("invalid_metadata")
    try:
        if Decimal(meta["equity"]) != Decimal(equity):
            raise ValueError("equity_mismatch")
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("invalid_metadata") from exc

    rows = db.execute(
        "SELECT seq, event_id, strategy, trading_day, payload, "
        "previous_sha256, entry_sha256 FROM synthetic_scenarios ORDER BY seq"
    ).fetchall()
    if len(rows) > _MAX_RECORDS:
        raise ValueError("journal_limit_exceeded")
    previous = _ZERO_HASH
    events: list[dict[str, Any]] = []
    for expected_seq, row in enumerate(rows, 1):
        seq, event_id, strategy, day, payload, previous_sha, entry_sha = row
        if seq != expected_seq or previous_sha != previous:
            raise ValueError("journal_integrity_failed")
        try:
            event = json.loads(payload)
            if not isinstance(event, dict) or _canonical(event) != payload:
                raise ValueError("journal_integrity_failed")
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("journal_integrity_failed") from exc
        if (event.get("event_id"), event.get("strategy"), event.get("trading_day")) != (
            event_id, strategy, day
        ):
            raise ValueError("journal_integrity_failed")
        digest = hashlib.sha256((previous + "\n" + payload).encode("utf-8")).hexdigest()
        if digest != entry_sha:
            raise ValueError("journal_integrity_failed")
        events.append(event)
        previous = digest
    replay = replay_synthetic_journal(starting_equity_usd=equity, events=events)
    if replay["status"] != "synthetic_preview_only":
        raise ValueError("journal_replay_failed")
    if any(a["result"] != "synthetic_recorded" for a in replay["audit"]):
        raise ValueError("journal_replay_failed")
    return events, previous, meta["kill_latched"] == "1"


def _snapshot(equity: str, events: list[dict[str, Any]],
              tip: str, killed: bool) -> dict[str, Any]:
    replay = replay_synthetic_journal(starting_equity_usd=equity, events=events)
    return {
        "mode": "offline_synthetic_storage_only",
        "status": "synthetic_storage_snapshot",
        "reason": None,
        "event_count": len(events),
        "audit_tip_sha256": tip,
        "kill_switch_latched": killed,
        "summary": replay["summary"],
        "strategies": replay["strategies"],
        "trade_executed": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "realized_performance": False,
    }


def append_synthetic_scenario(
    *, database_path: Any, starting_equity_usd: Any, event: Any,
    enabled: bool = False,
) -> dict[str, Any]:
    """Atomic append under SQLite BEGIN IMMEDIATE; disabled by default."""
    if enabled is not True:
        return _blocked("offline_storage_disabled")
    try:
        path = _file_path(database_path)
        equity = _equity(starting_equity_usd)
        if not isinstance(event, dict):
            return _blocked("invalid_synthetic_event")
        payload = _canonical(event)
        if len(payload) > 4096:
            return _blocked("invalid_synthetic_event")
    except (ValueError, TypeError, OverflowError):
        return _blocked("invalid_synthetic_inputs")
    try:
        with closing(sqlite3.connect(str(path), timeout=5, isolation_level=None)) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                _schema(db, equity)
                events, tip, killed = _load(db, equity)
                if killed:
                    db.rollback()
                    return _blocked("manual_kill_switch")
                match = next((existing for existing in events
                              if existing["event_id"] == event.get("event_id")), None)
                if match is not None:
                    db.rollback()
                    if _canonical(match) != payload:
                        return _blocked("conflicting_event_id")
                    return {**_snapshot(equity, events, tip, False),
                            "append_result": "duplicate_ignored"}
                if len(events) >= _MAX_RECORDS:
                    db.rollback()
                    return _blocked("journal_limit_exceeded")
                proposed = events + [event]
                result = replay_synthetic_journal(
                    starting_equity_usd=equity, events=proposed,
                )
                if result["status"] != "synthetic_preview_only":
                    db.rollback()
                    return _blocked(result["reason"] or "invalid_synthetic_event")
                final = result["audit"][-1]
                if final["result"] != "synthetic_recorded":
                    db.rollback()
                    return _blocked(final["reason"] or "synthetic_event_rejected")
                digest = hashlib.sha256((tip + "\n" + payload).encode("utf-8")).hexdigest()
                db.execute(
                    "INSERT INTO synthetic_scenarios (event_id, strategy, trading_day, "
                    "payload, previous_sha256, entry_sha256) VALUES (?, ?, ?, ?, ?, ?)",
                    (event["event_id"], event["strategy"], event["trading_day"],
                     payload, tip, digest),
                )
                db.commit()
                return {**_snapshot(equity, proposed, digest, False),
                        "append_result": "synthetic_recorded"}
            except (sqlite3.Error, ValueError, TypeError, KeyError):
                db.rollback()
                raise
    except ValueError as exc:
        # Expose only deterministic local validation reasons, never secrets.
        return _blocked(str(exc))
    except (sqlite3.Error, OSError, TypeError, KeyError):
        return _blocked("synthetic_storage_unavailable")


def read_synthetic_scenarios(
    *, database_path: Any, starting_equity_usd: Any, enabled: bool = False,
) -> dict[str, Any]:
    """Read-only SQLite open; never creates missing databases or records."""
    if enabled is not True:
        return _blocked("offline_storage_disabled")
    try:
        path = _file_path(database_path)
        equity = _equity(starting_equity_usd)
        if not path.is_file():
            return _blocked("synthetic_storage_not_found")
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro",
                                    uri=True, timeout=5)) as db:
            events, tip, killed = _load(db, equity)
            return _snapshot(equity, events, tip, killed)
    except ValueError as exc:
        return _blocked(str(exc))
    except (sqlite3.Error, OSError, TypeError):
        return _blocked("synthetic_storage_unavailable")


def latch_synthetic_kill_switch(
    *, database_path: Any, starting_equity_usd: Any, enabled: bool = False,
) -> dict[str, Any]:
    """Permanently latch OFF in the local research database. No unlock API."""
    if enabled is not True:
        return _blocked("offline_storage_disabled")
    try:
        path = _file_path(database_path)
        equity = _equity(starting_equity_usd)
        if not path.is_file():
            return _blocked("synthetic_storage_not_found")
        with closing(sqlite3.connect(str(path), timeout=5,
                                     isolation_level=None)) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                _load(db, equity)
                db.execute("UPDATE research_meta SET value='1' WHERE key='kill_latched'")
                db.commit()
                return _blocked("manual_kill_switch")
            except (sqlite3.Error, ValueError):
                db.rollback()
                raise
    except ValueError as exc:
        return _blocked(str(exc))
    except (sqlite3.Error, OSError, TypeError):
        return _blocked("synthetic_storage_unavailable")
