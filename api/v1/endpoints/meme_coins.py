"""Read-only Solana meme monitoring endpoints; no trade execution."""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from scripts.scan_solana_meme import scan

router = APIRouter()
_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 30
_last_scan_at = 0.0
_last_scan_limit = 0
_last_scan: dict[str, Any] | None = None


class MemeScanRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=8)


def _live_enabled() -> bool:
    return os.environ.get("MEME_RADAR_LIVE_ENABLED", "").strip().lower() in (
        "1", "true", "yes", "on"
    )


@router.get("/status")
def status() -> dict[str, Any]:
    """This endpoint never requests third-party data."""
    return {
        "available": True,
        "live_enabled": _live_enabled(),
        "trading_enabled": False,
        "strategies": ["new_coin_hunter", "momentum_watcher"],
    }


@router.post("/scan")
def manual_scan(request: MemeScanRequest) -> dict[str, Any]:
    """Explicitly requested market-data scan; never place orders."""
    global _last_scan_at, _last_scan_limit, _last_scan
    if not _live_enabled():
        raise HTTPException(status_code=403, detail="Meme Radar live data disabled")
    if not _LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Scan already running")
    try:
        now = time.monotonic()
        if (
            _last_scan is not None
            and request.limit == _last_scan_limit
            and now - _last_scan_at < _CACHE_TTL_SECONDS
        ):
            return {**_last_scan, "cached": True}
        try:
            payload = scan(live=True, limit=request.limit)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Market data scan failed") from exc
        _last_scan = payload
        _last_scan_limit = request.limit
        _last_scan_at = time.monotonic()
        return {**payload, "cached": False}
    finally:
        _LOCK.release()
