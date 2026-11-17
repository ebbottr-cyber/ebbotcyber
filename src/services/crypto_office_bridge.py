"""Strict, read-only bridge from EBBot to the isolated crypto research service.

No credentials or market order capabilities are exposed to a browser.
The upstream /integration/dashboard schema is versioned at 1.1.
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx

SCHEMA_VERSION = "1.1"
MAX_RESPONSE_BYTES = 2_000_000
SECTIONS = (
    "application", "portfolio", "risk", "performance", "validation",
    "agents", "strategies", "operations", "safety",
)
SENSITIVE_KEY = re.compile(
    r"(?:api.?key|secret|password|passwd|token|authorization|bearer|private.?key)",
    re.IGNORECASE,
)
SENSITIVE_VALUE = re.compile(
    r"(?:sk-(?:live|proj|test)-[A-Za-z0-9_-]{8,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AIza[0-9A-Za-z_-]{20,}|Bearer\s+[A-Za-z0-9._~+/-]{12,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.IGNORECASE,
)


class CryptoOfficeUnavailable(Exception):
    """Safe error code only; no secrets or upstream response bodies."""

    def __init__(self, code: str = "upstream_unavailable"):
        super().__init__(code)
        self.code = code


def _walk(data: Any, depth: int = 0):
    if depth > 25:
        raise CryptoOfficeUnavailable("invalid_dashboard")
    if isinstance(data, dict):
        for key, value in data.items():
            yield str(key), value
            yield from _walk(value, depth + 1)
    elif isinstance(data, list):
        for value in data:
            yield from _walk(value, depth + 1)


def _valid_time(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return False
        age = datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)
        return -timedelta(minutes=5) <= age <= timedelta(hours=24)
    except (ValueError, OverflowError):
        return False


def validate_dashboard(value: Any) -> dict:
    """Reject invalid contracts, unsafe capabilities, stale data, and secret leaks."""
    if not isinstance(value, dict):
        raise CryptoOfficeUnavailable("invalid_dashboard")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise CryptoOfficeUnavailable("unsupported_schema")
    if value.get("mode") != "paper_only":
        raise CryptoOfficeUnavailable("unsafe_mode")
    if not all(isinstance(value.get(key), dict) for key in SECTIONS):
        raise CryptoOfficeUnavailable("invalid_dashboard")
    if not _valid_time(value.get("generated_at")):
        raise CryptoOfficeUnavailable("stale_dashboard")
    flags = value["safety"]
    if flags.get("real_exchange_orders") is not False or flags.get("live_trading_enabled") is not False:
        raise CryptoOfficeUnavailable("unsafe_mode")

    combined = value["portfolio"].get("combined")
    if not isinstance(combined, dict) or not isinstance(combined.get("valuation_complete"), bool):
        raise CryptoOfficeUnavailable("invalid_valuation")
    equity = combined.get("equity")
    if combined["valuation_complete"]:
        if (isinstance(equity, bool) or not isinstance(equity, (int, float))
                or not math.isfinite(equity) or equity < 0):
            raise CryptoOfficeUnavailable("invalid_valuation")
    elif equity is not None:
        # Never turn missing pricing information into an apparent zero balance.
        raise CryptoOfficeUnavailable("invalid_valuation")

    for key, content in _walk(value):
        if SENSITIVE_KEY.search(key):
            raise CryptoOfficeUnavailable("credential_leak")
        if isinstance(content, str) and SENSITIVE_VALUE.search(content):
            raise CryptoOfficeUnavailable("credential_leak")
    return value


def _connection_settings() -> tuple[str, str]:
    if os.getenv("TRADING_ENABLED", "false").lower() not in {"false", "0", "no", ""}:
        raise CryptoOfficeUnavailable("unsafe_mode")
    source = os.getenv("TRADING_OFFICE_URL", "").strip()
    key = os.getenv("TRADING_OFFICE_READ_API_KEY", "").strip()
    if not source or len(key) < 32:
        raise CryptoOfficeUnavailable("not_configured")

    try:
        parsed = urlsplit(source)
        port = parsed.port
    except ValueError as exc:
        raise CryptoOfficeUnavailable("invalid_url") from exc
    # Phase 1 deliberately permits only an isolated local service. Do not
    # allow an admin-supplied URL to turn the proxy into an arbitrary HTTP client.
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment or not port):
        raise CryptoOfficeUnavailable("invalid_url")
    return source.rstrip("/"), key


async def read_crypto_dashboard() -> dict:
    base, key = _connection_settings()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(12.0, connect=3.0),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            async with client.stream(
                "GET",
                base + "/api/v1/integration/dashboard",
                headers={"X-API-Key": key, "Accept": "application/json"},
            ) as response:
                if response.status_code != 200:
                    raise CryptoOfficeUnavailable("upstream_unavailable")
                if "application/json" not in response.headers.get("content-type", "").lower():
                    raise CryptoOfficeUnavailable("invalid_dashboard")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_RESPONSE_BYTES:
                        raise CryptoOfficeUnavailable("oversized_dashboard")
                try:
                    payload = json.loads(data)
                except (TypeError, ValueError) as exc:
                    raise CryptoOfficeUnavailable("invalid_dashboard") from exc
    except CryptoOfficeUnavailable:
        raise
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise CryptoOfficeUnavailable("upstream_unavailable") from exc
    return validate_dashboard(payload)
