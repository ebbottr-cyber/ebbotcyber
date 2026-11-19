"""Germany/Xetra reference inventory and explicitly requested quote metadata.

No background polling, orders, execution, chart backfill or AI analysis.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from contextlib import contextmanager
import os
import threading
import time
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
MAX_SOURCE_AGE_DAYS = 7
MANUAL_QUOTE_COOLDOWN_SECONDS = 30


class _ManualQuoteGate:
    """Best-effort single-process quote concurrency/cooldown guard.

    This is deliberately *not* claimed to be a distributed rate limiter.
    A reverse proxy must enforce global per-admin limits in production.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._busy = False
        self._last_started = float("-inf")

    @contextmanager
    def request_slot(self):
        with self._lock:
            elapsed = time.monotonic() - self._last_started
            if self._busy or elapsed < MANUAL_QUOTE_COOLDOWN_SECONDS:
                raise HTTPException(
                    status_code=429,
                    detail="xetra_manual_quote_cooldown",
                    headers={"Retry-After": str(MANUAL_QUOTE_COOLDOWN_SECONDS)},
                )
            self._busy = True
            self._last_started = time.monotonic()
        try:
            yield
        finally:
            with self._lock:
                self._busy = False


_quote_gate = _ManualQuoteGate()


def _source_date(rows: dict[str, dict[str, str]]) -> tuple[str, int]:
    """Require one source date; mixed/stale manifests fail closed for quotes."""
    source_dates = {item["source_as_of_date"] for item in rows.values()}
    if len(source_dates) != 1:
        raise HTTPException(status_code=503, detail="xetra_mixed_source_dates")
    source = source_dates.pop()
    age = (date.today() - date.fromisoformat(source)).days
    return source, age



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
    selected = [code for code in sorted(rows) if term in code or term in rows[code]["isin"]][:limit]
    latest, age = _source_date(rows)
    return {
        "status": "CANDIDATE_INVENTORY_ONLY",
        "market": "XETR",
        "currency_expected": "EUR",
        "candidate_count": len(rows),
        "source_as_of_date": latest,
        "snapshot_age_days": age,
        "source_stale": age > MAX_SOURCE_AGE_DAYS,
        "items": [
            {"symbol": code, "isin": rows[code]["isin"], "price_symbol_verified": False}
            for code in selected
        ],
        "manual_quote_check_enabled": _ui_quotes_enabled() and age <= MAX_SOURCE_AGE_DAYS,
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
    _, age = _source_date(rows)
    if age > MAX_SOURCE_AGE_DAYS or age < 0:
        raise HTTPException(status_code=409, detail="xetra_snapshot_stale")
    codes = body.symbols
    if len(set(codes)) != len(codes) or any(code not in rows for code in codes):
        raise HTTPException(status_code=422, detail="invalid_or_off_manifest_xetra_symbol")
    try:
        with _quote_gate.request_slot():
            return check_symbols(rows, codes, fetch_yahoo_chart, now=datetime.now(timezone.utc))
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_xetra_quote_request") from None
