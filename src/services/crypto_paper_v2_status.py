"""Inspect Trading Office Paper V2 capabilities without granting execution.

The upstream capabilities response is a SELF-REPORTED claim and is never
proof of authenticated HTTP enforcement, atomicity or production readiness.
This EBBot API is GET-only and can never submit a paper or live order.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from src.services.crypto_office_bridge import _connection_settings

MAX_RESPONSE_BYTES = 32_768
CAPABILITY_PATH = "/api/v1/paper/v2/capabilities"


class PaperV2StatusUnavailable(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def verify_capabilities(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise PaperV2StatusUnavailable("invalid_v2_capability")
    if (raw.get("mode") != "paper_only" or
            raw.get("source") != "Trading Office" or
            raw.get("protocol") != "paper_v2_atomic_sqlite" or
            raw.get("legacy_paper_writes_enabled") is not False or
            raw.get("real_exchange_orders") is not False or
            raw.get("risk_check_location") != "same_sqlite_transaction" or
            raw.get("requires_admin_auth") is not True or
            type(raw.get("paper_execution_permitted")) is not bool):
        raise PaperV2StatusUnavailable("unsafe_v2_capability")

    # A source flag is NOT an execution permission. No EBBot write route
    # exists, regardless of the source's reported local opt-in state.
    source_flag = raw["paper_execution_permitted"]
    return {
        "mode": "paper_only",
        "source": "Trading Office",
        "protocol": "paper_v2_atomic_sqlite",
        "source_state": "SOURCE_FLAG_ON_UNVERIFIED" if source_flag else "SOURCE_INSTALLED_DISABLED",
        "source_flag_claimed_enabled": source_flag,
        "source_claims_legacy_writes_disabled": True,
        "source_claims_atomic_risk_gate": True,
        "readiness_verified": False,
        "ebbot_paper_writes_enabled": False,
        "paper_execution_permitted": False,
        "real_exchange_orders": False,
        "execution": "disabled",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "note": "Kaynak beyanı tek başına işlem yetkisi veya uçtan uca güvenlik kanıtı değildir.",
    }


async def read_v2_status() -> dict:
    try:
        base, key = _connection_settings()
    except Exception as exc:
        raise PaperV2StatusUnavailable("paper_service_not_configured") from exc
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(9.0, connect=3.0),
            trust_env=False, follow_redirects=False,
        ) as client:
            async with client.stream(
                "GET",
                base + CAPABILITY_PATH,
                headers={"X-API-Key": key, "Accept": "application/json"},
            ) as response:
                if response.status_code == 404:
                    raise PaperV2StatusUnavailable("paper_v2_not_installed")
                if response.status_code != 200:
                    raise PaperV2StatusUnavailable("paper_v2_unavailable")
                if "application/json" not in response.headers.get("content-type", "").lower():
                    raise PaperV2StatusUnavailable("invalid_v2_capability")
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) > MAX_RESPONSE_BYTES:
                        raise PaperV2StatusUnavailable("oversized_v2_capability")
                try:
                    decoded = json.loads(payload)
                except (TypeError, ValueError) as exc:
                    raise PaperV2StatusUnavailable("invalid_v2_capability") from exc
                return verify_capabilities(decoded)
    except PaperV2StatusUnavailable:
        raise
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise PaperV2StatusUnavailable("paper_v2_unavailable") from exc
