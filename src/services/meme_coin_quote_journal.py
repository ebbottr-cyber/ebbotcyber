"""Local, transactional, tamper-EVIDENT Jupiter quote archive (OFFLINE CLI).

Only manually exported, walletless V9 quote snapshots can be stored. No web
endpoint, scheduler, market fetch, transaction handling or trading integration.
Hashes defend against accidental editing, NOT malicious admin/SQLite tampering.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from src.services.meme_coin_jupiter_quotes import USDC_MINT, normalize_quote

GENESIS = "0" * 64
STRATEGIES = ("new_launch", "momentum")
MAX_CAPTURE_BYTES = 8192
MAX_ENTRIES_PER_STRATEGY = 10000


def _canonical_capture(raw: Any) -> tuple[str, str, str]:
    if not isinstance(raw, dict):
        raise ValueError("invalid_capture")
    required = {
        "capture_id", "source", "strategy", "mint", "side",
        "input_mint", "output_mint", "amount_in_raw", "amount_out_raw",
        "fee_bps", "router", "captured_at_ms", "captured_at",
        "transaction_returned", "execution_is_real", "token_safety_verified",
        "estimated_network_fee_available", "tradable",
    }
    if set(raw) != required:
        raise ValueError("unsupported_capture_fields")
    strategy = raw["strategy"]
    side = raw["side"]
    if strategy not in STRATEGIES or side not in ("buy", "sell"):
        raise ValueError("invalid_strategy_or_side")
    if any(raw[key] is not False for key in (
        "transaction_returned", "execution_is_real",
        "token_safety_verified", "estimated_network_fee_available", "tradable",
    )):
        raise ValueError("unsafe_capture")
    mint = raw["mint"]
    request = {
        "source": "jupiter_swap_v2_order_quote_only", "strategy": strategy,
        "mint": mint, "side": side,
        "input_mint": USDC_MINT if side == "buy" else mint,
        "output_mint": mint if side == "buy" else USDC_MINT,
        "amount_in_raw": raw["amount_in_raw"],
    }
    quote = {
        "inAmount": raw["amount_in_raw"], "outAmount": raw["amount_out_raw"],
        "feeBps": raw["fee_bps"], "router": raw["router"],
        "transaction": None,
    }
    normalized = normalize_quote(request, quote, observed_at_ms=raw["captured_at_ms"])
    if normalized != raw:
        raise ValueError("quote_integrity_mismatch")
    serialized = json.dumps(raw, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > MAX_CAPTURE_BYTES:
        raise ValueError("capture_too_large")
    return strategy, raw["capture_id"], serialized


def _entry_hash(strategy: str, seq: int, prior: str, data: str) -> str:
    return hashlib.sha256(
        (strategy + "|" + str(seq) + "|" + prior + "|" + data).encode("utf-8")
    ).hexdigest()


def _init(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS quote_journal(
            strategy TEXT NOT NULL CHECK(strategy IN ('new_launch','momentum')),
            seq INTEGER NOT NULL CHECK(seq > 0),
            capture_id TEXT NOT NULL,
            captured_at_ms INTEGER NOT NULL CHECK(captured_at_ms > 0),
            capture_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            entry_hash TEXT NOT NULL,
            PRIMARY KEY(strategy, seq),
            UNIQUE(strategy, capture_id)
        );
        CREATE TRIGGER IF NOT EXISTS no_quote_update
          BEFORE UPDATE ON quote_journal
          BEGIN SELECT RAISE(ABORT, 'immutable_quote_journal'); END;
        CREATE TRIGGER IF NOT EXISTS no_quote_delete
          BEFORE DELETE ON quote_journal
          BEGIN SELECT RAISE(ABORT, 'immutable_quote_journal'); END;
    """)


def _verify(conn: sqlite3.Connection) -> dict[str, Any]:
    counts: dict[str, int] = {}
    tips: dict[str, str] = {}
    for strategy in STRATEGIES:
        prev = GENESIS
        number = 0
        last_observed = 0
        rows = conn.execute(
            "SELECT seq,capture_id,captured_at_ms,capture_json,previous_hash,entry_hash "
            "FROM quote_journal WHERE strategy=? ORDER BY seq", (strategy,),
        )
        for seq, capture_id, captured, raw_json, previous, digest in rows:
            number += 1
            if seq != number or previous != prev:
                raise ValueError("broken_journal_sequence_or_link")
            try:
                quote = json.loads(raw_json)
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid_journal_json") from exc
            parsed_strategy, parsed_id, serialized = _canonical_capture(quote)
            if (parsed_strategy != strategy or parsed_id != capture_id
                    or quote["captured_at_ms"] != captured
                    or captured < last_observed or serialized != raw_json):
                raise ValueError("modified_or_unsorted_capture")
            expected = _entry_hash(strategy, seq, previous, raw_json)
            if digest != expected:
                raise ValueError("journal_hash_mismatch")
            prev = digest
            last_observed = captured
        counts[strategy] = number
        tips[strategy] = prev
    return {
        "status": "local_integrity_verified",
        "strategy_counts": counts,
        "chain_tips": tips,
        "provenance_authenticated": False,
        "append_only_against_privileged_attackers": False,
        "live_trading_enabled": False,
    }


def verify_journal(database: Path) -> dict[str, Any]:
    """Verify a local archive; does not establish that quotes came from Jupiter."""
    with sqlite3.connect(database, timeout=10) as conn:
        _init(conn)
        return _verify(conn)


def append_captures(database: Path, captures: list[dict[str, Any]]) -> dict[str, Any]:
    """Atomic batch and conflict-safe idempotency; fail before partial writes."""
    if not isinstance(captures, list) or not 1 <= len(captures) <= 500:
        raise ValueError("invalid_capture_batch")
    canonical = [_canonical_capture(item) for item in captures]
    with sqlite3.connect(database, timeout=10, isolation_level=None) as conn:
        _init(conn)
        conn.execute("BEGIN IMMEDIATE")
        try:
            before = _verify(conn)
            sequence = dict(before["strategy_counts"])
            tips = dict(before["chain_tips"])
            last_times: dict[str, int] = {}
            for strategy in STRATEGIES:
                row = conn.execute(
                    "SELECT captured_at_ms FROM quote_journal WHERE strategy=? ORDER BY seq DESC LIMIT 1",
                    (strategy,),
                ).fetchone()
                last_times[strategy] = row[0] if row else 0
            inserted = 0
            for raw, (strategy, capture_id, serialized) in zip(captures, canonical):
                prior = conn.execute(
                    "SELECT capture_json FROM quote_journal WHERE strategy=? AND capture_id=?",
                    (strategy, capture_id),
                ).fetchone()
                if prior is not None:
                    if prior[0] != serialized:
                        raise ValueError("duplicate_capture_conflict")
                    continue  # idempotent retry
                timestamp = raw["captured_at_ms"]
                if timestamp < last_times[strategy]:
                    raise ValueError("nonchronological_capture")
                if sequence[strategy] >= MAX_ENTRIES_PER_STRATEGY:
                    raise ValueError("archive_capacity_reached")
                seq = sequence[strategy] + 1
                prev = tips[strategy]
                digest = _entry_hash(strategy, seq, prev, serialized)
                conn.execute(
                    "INSERT INTO quote_journal(strategy,seq,capture_id,captured_at_ms,"
                    "capture_json,previous_hash,entry_hash) VALUES (?,?,?,?,?,?,?)",
                    (strategy, seq, capture_id, timestamp, serialized, prev, digest),
                )
                sequence[strategy] = seq
                tips[strategy] = digest
                last_times[strategy] = timestamp
                inserted += 1
            after = _verify(conn)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    return {
        **after, "inserted": inserted,
        "duplicate_identical_skipped": len(captures) - inserted,
        "storage_scope": "local_offline_sqlite_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="OFFLINE walletless quote archive (no trades).")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        if args.input:
            parser.error("verification cannot import data")
        if not args.database.is_file():
            parser.error("cannot verify a missing archive")
        result = verify_journal(args.database)
    else:
        if args.input is None or not args.input.is_file():
            parser.error("an input JSON file is required")
        if args.input.stat().st_size > 3_000_000:
            parser.error("capture import file exceeds 3 MB")
        if args.input.resolve() == args.database.resolve():
            parser.error("database and capture file must differ")
        document = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or set(document) != {"captures"}:
            parser.error("input must be a {captures: [...]} JSON object")
        result = append_captures(args.database, document["captures"])
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
