"""Crash-recoverable LOCAL offline paper replay state (SQLite, no server API writes).

An immutable, hash-linked input stream and a transactionally updated derived
checkpoint form one SQLite transaction per batch. On recovery the full replay
is recomputed and compared byte-for-byte; this catches torn state/checkpoint
inconsistency. The hash chain is tamper-EVIDENT, not secure against a
privileged DB administrator. No wallet, network or live paper scheduler.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from src.services.meme_coin_paper_mtm import _prevalidate, replay_marked_guarded
from src.services.meme_coin_paper_replay import new_ledgers

GENESIS = "0" * 64
MAX_STORED_STEPS = 2000
MAX_APPEND_BATCH = 100
MAX_STEP_JSON_BYTES = 14000


def _canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _step_hash(seq: int, prev_hash: str, payload: str) -> str:
    return _digest("meme-coin-mtm-v11|" + str(seq) + "|" + prev_hash + "|" + payload)


def _init(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS mtm_steps (
            seq INTEGER PRIMARY KEY CHECK(seq > 0),
            event_id TEXT NOT NULL UNIQUE,
            attempted_at_ms INTEGER NOT NULL,
            step_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            entry_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mtm_checkpoint (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            replay_config_json TEXT NOT NULL,
            event_count INTEGER NOT NULL,
            state_json TEXT NOT NULL,
            state_sha256 TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS no_step_update
          BEFORE UPDATE ON mtm_steps
          BEGIN SELECT RAISE(ABORT, 'immutable_mtm_history'); END;
        CREATE TRIGGER IF NOT EXISTS no_step_delete
          BEFORE DELETE ON mtm_steps
          BEGIN SELECT RAISE(ABORT, 'immutable_mtm_history'); END;
    """)


def _load_verified(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Recompute from event history; never blindly trust the saved balance."""
    steps: list[dict[str, Any]] = []
    prev = GENESIS
    for seq, event_id, attempted, raw, link, digest in conn.execute(
        "SELECT seq,event_id,attempted_at_ms,step_json,previous_hash,entry_hash "
        "FROM mtm_steps ORDER BY seq",
    ):
        if seq != len(steps) + 1 or link != prev or _step_hash(seq, link, raw) != digest:
            raise ValueError("broken_mtm_event_chain")
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_STEP_JSON_BYTES:
            raise ValueError("invalid_mtm_step_size")
        try:
            step = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_mtm_step_json") from exc
        if not isinstance(step, dict) or _canonical(step) != raw:
            raise ValueError("noncanonical_mtm_step")
        entry = step.get("event")
        if not isinstance(entry, dict) or entry.get("id") != event_id or entry.get("attempted_at_ms") != attempted:
            raise ValueError("tampered_mtm_step_identity")
        steps.append(step)
        prev = digest
    if len(steps) > MAX_STORED_STEPS:
        raise ValueError("mtm_history_capacity_exceeded")
    _prevalidate(steps)

    saved = conn.execute(
        "SELECT replay_config_json,event_count,state_json,state_sha256 "
        "FROM mtm_checkpoint WHERE singleton=1",
    ).fetchone()
    if saved is None:
        if steps:
            raise ValueError("missing_mtm_checkpoint")
        return steps, {"initial_cash_usd": "1000.00"}, replay_marked_guarded([])
    config_raw, stored_count, state_raw, state_hash = saved
    try:
        config = json.loads(config_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_mtm_configuration") from exc
    if not isinstance(config, dict) or set(config) != {"initial_cash_usd"} or _canonical(config) != config_raw:
        raise ValueError("unexpected_mtm_configuration")
    new_ledgers(config["initial_cash_usd"])  # validate initial balance
    if stored_count != len(steps):
        raise ValueError("mtm_checkpoint_event_count_mismatch")
    expected = replay_marked_guarded(steps, initial_cash_usd=config["initial_cash_usd"])
    if (not isinstance(state_raw, str)
            or _digest(state_raw) != state_hash
            or _canonical(expected) != state_raw):
        raise ValueError("mtm_checkpoint_integrity_mismatch")
    return steps, config, expected


def verify_and_recover(database: Path) -> dict[str, Any]:
    """Read and fully verify a local persisted paper replay (no live positions)."""
    if not database.is_file():
        raise ValueError("offline_checkpoint_not_found")
    with sqlite3.connect(database, timeout=10) as conn:
        _init(conn)
        steps, config, report = _load_verified(conn)
        return {
            "status": "verified_offline_recovery",
            "events_restored": len(steps),
            "replay_report": report,
            "initial_cash_usd": config["initial_cash_usd"],
            "recovery_used_market_network": False,
            "live_trading_enabled": False,
            "checkpoint_provenance_authenticated": False,
        }


def append_and_checkpoint(
    database: Path, new_steps: list[dict[str, Any]], *,
    initial_cash_usd: str = "1000.00",
) -> dict[str, Any]:
    """Atomic step append + risk state checkpoint, safe against partial commits."""
    if not isinstance(new_steps, list) or not (1 <= len(new_steps) <= MAX_APPEND_BATCH):
        raise ValueError("invalid_mtm_append_batch")
    new_ledgers(initial_cash_usd)
    _prevalidate(new_steps)
    serialized = [_canonical(step) for step in new_steps]
    if any(len(raw.encode("utf-8")) > MAX_STEP_JSON_BYTES for raw in serialized):
        raise ValueError("mtm_step_too_large")
    with sqlite3.connect(database, timeout=10, isolation_level=None) as conn:
        _init(conn)
        conn.execute("BEGIN IMMEDIATE")
        try:
            current, config, _ = _load_verified(conn)
            current_count = len(current)
            if current_count and config["initial_cash_usd"] != initial_cash_usd:
                raise ValueError("changed_initial_cash_not_permitted")
            if conn.execute("SELECT 1 FROM mtm_checkpoint WHERE singleton=1").fetchone():
                if config["initial_cash_usd"] != initial_cash_usd:
                    raise ValueError("changed_initial_cash_not_permitted")
            previous_hash = GENESIS
            if current_count:
                previous_hash = conn.execute(
                    "SELECT entry_hash FROM mtm_steps ORDER BY seq DESC LIMIT 1",
                ).fetchone()[0]
            ids = {step["event"]["id"]: _canonical(step) for step in current}
            last_time = current[-1]["event"]["attempted_at_ms"] if current else 0
            inserted = 0
            for step, raw in zip(new_steps, serialized):
                event = step["event"]
                identifier = event["id"]
                prior = ids.get(identifier)
                if prior is not None:
                    if prior != raw:
                        raise ValueError("conflicting_mtm_event_id")
                    continue  # strict idempotent retry
                if event["attempted_at_ms"] < last_time:
                    raise ValueError("nonchronological_mtm_append")
                if current_count + inserted >= MAX_STORED_STEPS:
                    raise ValueError("mtm_history_capacity_reached")
                seq = current_count + inserted + 1
                digest = _step_hash(seq, previous_hash, raw)
                conn.execute(
                    "INSERT INTO mtm_steps(seq,event_id,attempted_at_ms,"
                    "step_json,previous_hash,entry_hash) VALUES(?,?,?,?,?,?)",
                    (seq, identifier, event["attempted_at_ms"], raw, previous_hash, digest),
                )
                ids[identifier] = raw
                last_time = event["attempted_at_ms"]
                previous_hash = digest
                current.append(step)
                inserted += 1
            report = replay_marked_guarded(current, initial_cash_usd=initial_cash_usd)
            state = _canonical(report)
            config_json = _canonical({"initial_cash_usd": initial_cash_usd})
            conn.execute(
                "INSERT INTO mtm_checkpoint("
                "singleton,replay_config_json,event_count,state_json,state_sha256)"
                "VALUES(1,?,?,?,?) ON CONFLICT(singleton) DO UPDATE SET "
                "replay_config_json=excluded.replay_config_json, "
                "event_count=excluded.event_count, state_json=excluded.state_json, "
                "state_sha256=excluded.state_sha256",
                (config_json, len(current), state, _digest(state)),
            )
            # Same transaction: commit only after full replay recovers exactly.
            _, _, verified = _load_verified(conn)
            if verified != report:
                raise RuntimeError("unrepeatable_mtm_recovery")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    return {
        "status": "offline_checkpoint_committed",
        "events_restored": len(current),
        "events_inserted": inserted,
        "identical_retries_skipped": len(new_steps) - inserted,
        "replay_report": report,
        "recovery_used_market_network": False,
        "live_trading_enabled": False,
        "checkpoint_provenance_authenticated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="OFFLINE MTM paper replay and SQLite checkpoint.")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--initial-cash", default="1000.00")
    args = parser.parse_args()
    if args.verify_only:
        if args.input is not None:
            parser.error("--verify-only cannot import steps")
        report = verify_and_recover(args.database)
    else:
        if args.input is None or not args.input.is_file():
            parser.error("--input must reference a local JSON file")
        if args.input.resolve() == args.database.resolve():
            parser.error("input and database cannot be the same file")
        if args.input.stat().st_size > 4_000_000:
            parser.error("input too large")
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or set(payload) != {"steps"}:
            parser.error("input must be an object with only a steps array")
        report = append_and_checkpoint(
            args.database, payload["steps"], initial_cash_usd=args.initial_cash,
        )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
