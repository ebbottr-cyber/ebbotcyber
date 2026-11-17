"""Durable, isolated audit of ALL successful crypto research decisions, including HOLD.

Stores only the validated, non-executable EBBot research response. A failed
audit write is fatal for the requested analysis: never display an unlogged
decision. This file never imports or accesses the stock/portfolio database.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.crypto_office_bridge import SENSITIVE_VALUE

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "cache" / "ebbot_crypto_research_audit.sqlite3"
_LOCK = threading.RLock()


class CryptoAuditError(Exception):
    """Audit persistence must fail closed without leaking raw DB details."""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("""CREATE TABLE IF NOT EXISTS crypto_research_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        decision_kind TEXT NOT NULL CHECK (decision_kind IN ('ensemble','strategy')),
        market TEXT NOT NULL CHECK (market IN ('spot','futures')),
        symbol TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        action TEXT NOT NULL CHECK (action IN ('BUY','SELL','HOLD')),
        confidence REAL NOT NULL,
        candle_timestamp INTEGER NOT NULL,
        payload_sha256 TEXT NOT NULL,
        report_json TEXT NOT NULL,
        risk_approved INTEGER NOT NULL DEFAULT 0 CHECK (risk_approved=0),
        orders_placed INTEGER NOT NULL DEFAULT 0 CHECK (orders_placed=0)
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS ix_crypto_research_audit_recent ON crypto_research_decisions(created_at DESC)")
    return db


def record_decision(kind: str, report: dict[str, Any]) -> int:
    if kind not in {"ensemble", "strategy"} or not isinstance(report, dict):
        raise CryptoAuditError("invalid_decision")
    if (report.get("risk_approved") is not False or report.get("orders_placed") is not False
            or report.get("execution") != "disabled"
            or report.get("action") not in {"BUY", "SELL", "HOLD"}
            or report.get("market") not in {"spot", "futures"}):
        raise CryptoAuditError("unsafe_decision")
    try:
        payload = json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True)
        if len(payload.encode("utf-8")) > 80_000 or SENSITIVE_VALUE.search(payload):
            raise CryptoAuditError("invalid_decision")
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        created = datetime.now(timezone.utc).isoformat()
        with _LOCK, closing(_connect()) as db:
            with db:
                cursor = db.execute(
                    """INSERT INTO crypto_research_decisions
                    (created_at,decision_kind,market,symbol,timeframe,action,confidence,
                     candle_timestamp,payload_sha256,report_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        created, kind, report["market"], report["symbol"],
                        report["timeframe"], report["action"], report["confidence"],
                        report["candle_timestamp"], digest, payload,
                    ),
                )
                return int(cursor.lastrowid)
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError) as exc:
        raise CryptoAuditError("audit_unavailable") from exc


def recent_decisions(limit: int = 30) -> dict[str, Any]:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise CryptoAuditError("invalid_parameters")
    try:
        with _LOCK, closing(_connect()) as db:
            rows = db.execute(
                """SELECT id,created_at,decision_kind,market,symbol,timeframe,
                   action,confidence,candle_timestamp,report_json
                   FROM crypto_research_decisions ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        output = []
        for row in rows:
            # Do not expose full stored rationales in the lightweight history feed.
            payload = json.loads(row["report_json"])
            output.append({
                "id": row["id"], "created_at": row["created_at"],
                "decision_kind": row["decision_kind"], "market": row["market"],
                "symbol": row["symbol"], "timeframe": row["timeframe"],
                "action": row["action"], "confidence": row["confidence"],
                "candle_timestamp": row["candle_timestamp"],
                "risk_approved": False, "orders_placed": False,
                "journal_recorded": payload.get("journal_recorded", 0),
            })
        return {"decisions": output, "count": len(output), "orders_placed": False}
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError) as exc:
        raise CryptoAuditError("audit_unavailable") from exc
