"""Germany/Xetra reference inventory and explicitly requested quote metadata.

No background polling, orders, execution, chart backfill or AI analysis.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from src.auth import is_auth_enabled
from src.services.xetra_quote_guard import (
    check_symbols, fetch_yahoo_chart, read_xetra_manifest,
)

router = APIRouter()
_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = _ROOT / "data/market_snapshots/de/xetra-candidates.csv"
MAX_QUOTES_PER_REQUEST = 5


def _ui_quotes_enabled() -> bool:
    # An authenticated admin session is enforced by existing API middleware
    # when ADMIN_AUTH_ENABLED is configured. Never expose a public proxy.
    return (
        is_auth_enabled()
        and os.getenv("EBBOT_XETRA_QUOTES_UI_ENABLED", "").strip().lower() == "true"
    )


def _manifest():
    try:
        return read_xetra_manifest(MANIFEST)
    except (OSError, ValueError, UnicodeError):
        raise HTTPException(status_code=503, detail="xetra_inventory_unavailable") from None


@router.get("/inventory", summary="Read-only Xetra common-stock reference inventory")
def get_inventory(
    response: Response,
    query: str = Query("", max_length=30),
    limit: int = Query(30, ge=1, le=50),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    rows = _manifest()
    term = query.strip().upper()
    # Only search official source codes, not arbitrary market identifiers.
    selected = [code for code in sorted(rows) if term in code][:limit]
    sources = sorted(set(value["source_as_of_date"] for value in rows.values()))
    today = date.today()
    latest = max(sources)
    age = (today - date.fromisoformat(latest)).days
    return {
        "status": "CANDIDATE_INVENTORY_ONLY",
        "market": "XETR",
        "currency_expected": "EUR",
        "candidate_count": len(rows),
        "source_as_of_date": latest,
        "snapshot_age_days": age,
        "source_stale": age > 7,
        "items": [
            {"symbol": code, "isin": rows[code]["isin"], "price_symbol_verified": False}
            for code in selected
        ],
        "manual_quote_check_enabled": _ui_quotes_enabled(),
        "quotes_auto_loaded": False,
        "broker_access_verified": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "orders": 0,
    }


class XetraQuoteCheckRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=MAX_QUOTES_PER_REQUEST)


@router.post("/quote-check", summary="Manual read-only Xetra quote metadata sample")
def check_xetra_quotes(body: XetraQuoteCheckRequest, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    if not _ui_quotes_enabled():
        raise HTTPException(status_code=403, detail="xetra_manual_quote_check_disabled")
    rows = _manifest()
    codes = body.symbols
    if len(set(codes)) != len(codes) or any(code not in rows for code in codes):
        raise HTTPException(status_code=422, detail="invalid_or_off_manifest_xetra_symbol")
    try:
        return check_symbols(rows, codes, fetch_yahoo_chart, now=datetime.now(timezone.utc))
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_xetra_quote_request") from None
