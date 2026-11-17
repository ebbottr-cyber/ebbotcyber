"""Durable, crypto-only audit trail of hypothetical risk reviews.

Never grants a transferable approval; cannot be used to bypass a later
paper-order transaction's independent risk checks.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from src.services import crypto_research_audit as research_audit


class RiskAuditError(RuntimeError):
    pass


def record_risk_review(proposal: dict, review: dict) -> int:
    if (not isinstance(proposal, dict) or not isinstance(review, dict)
            or review.get("status") not in ("REVIEW_ONLY", "BLOCKED")
            or review.get("paper_execution_permitted") is not False
            or review.get("risk_approved") is not False
            or review.get("real_exchange_orders") is not False
            or review.get("execution") != "disabled"):
        raise RiskAuditError("unsafe_review")
    try:
        request_json = json.dumps(proposal, allow_nan=False, sort_keys=True)
        result_json = json.dumps(review, allow_nan=False, sort_keys=True, ensure_ascii=False)
        if len(request_json) + len(result_json) > 30_000:
            raise RiskAuditError("oversized_review")
        sha = hashlib.sha256((request_json + "|" + result_json).encode("utf-8")).hexdigest()
        with research_audit._LOCK, closing(research_audit._connect()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS crypto_risk_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                market TEXT NOT NULL CHECK(market IN ('spot','futures')),
                symbol TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('REVIEW_ONLY','BLOCKED')),
                proposal_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                integrity_sha256 TEXT NOT NULL,
                paper_execution_permitted INTEGER NOT NULL DEFAULT 0
                    CHECK(paper_execution_permitted=0),
                real_exchange_orders INTEGER NOT NULL DEFAULT 0
                    CHECK(real_exchange_orders=0)
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_crypto_risk_recent ON crypto_risk_reviews(id DESC)")
            cursor = db.execute(
                """INSERT INTO crypto_risk_reviews
                (created_at, market, symbol, status, proposal_json, result_json, integrity_sha256)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (datetime.now(timezone.utc).isoformat(), proposal["market"],
                 proposal["symbol"], review["status"], request_json, result_json, sha),
            )
            db.commit()
            return int(cursor.lastrowid)
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError) as exc:
        raise RiskAuditError("risk_audit_unavailable") from exc


def recent_risk_reviews(limit: int = 30) -> dict:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise RiskAuditError("invalid_parameters")
    try:
        with research_audit._LOCK, closing(research_audit._connect()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS crypto_risk_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                market TEXT NOT NULL CHECK(market IN ('spot','futures')),
                symbol TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('REVIEW_ONLY','BLOCKED')),
                proposal_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                integrity_sha256 TEXT NOT NULL,
                paper_execution_permitted INTEGER NOT NULL DEFAULT 0
                    CHECK(paper_execution_permitted=0),
                real_exchange_orders INTEGER NOT NULL DEFAULT 0
                    CHECK(real_exchange_orders=0)
            )""")
            rows = db.execute(
                """SELECT id, created_at, market, symbol, status, result_json
                FROM crypto_risk_reviews ORDER BY id DESC LIMIT ?""", (limit,),
            ).fetchall()
        results = []
        for row in rows:
            result = json.loads(row["result_json"])
            results.append({
                "id": row["id"], "created_at": row["created_at"],
                "market": row["market"], "symbol": row["symbol"], "status": row["status"],
                "reasons": result.get("reasons", []),
                "risk_review_passed": result.get("risk_review_passed", False),
                "paper_execution_permitted": False, "real_exchange_orders": False,
            })
        return {"reviews": results, "count": len(results), "paper_execution_permitted": False}
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError) as exc:
        raise RiskAuditError("risk_audit_unavailable") from exc
