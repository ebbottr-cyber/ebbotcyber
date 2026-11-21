"""Opt-in, read-only RPC health probe for Robinhood Chain.

Uses only fixed official JSON-RPC endpoints, never accepts a caller-supplied
URL or a transaction payload. No private keys, contracts, swaps or orders.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_NETWORKS = {
    "testnet": ("https://rpc.testnet.chain.robinhood.com", 46630),
    "mainnet": ("https://rpc.mainnet.chain.robinhood.com", 4663),
}
_MAX_BYTES = 16384
_CACHE_SECONDS = 60
_LOCK = threading.RLock()
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_HEX = re.compile(r"^0x[0-9a-fA-F]{1,16}$")


def _flag_enabled() -> bool:
    return os.getenv("MEME_COIN_ROBINHOOD_RPC_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _network() -> str:
    network = os.getenv("MEME_COIN_ROBINHOOD_NETWORK", "testnet").strip().lower()
    if network not in _NETWORKS:
        raise ValueError("unsupported_network")
    return network


def _rpc(url: str, method: str) -> int:
    """Only read-only methods allowed; URL is supplied by internal allowlist."""
    if url not in {pair[0] for pair in _NETWORKS.values()}:
        raise ValueError("unapproved_rpc_url")
    if method not in {"eth_chainId", "eth_blockNumber"}:
        raise ValueError("unsupported_method")
    request = Request(
        url,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": []}).encode(),
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "EBBot-Robinhood-ReadOnly/0.1"},
        method="POST",
    )
    with urlopen(request, timeout=7) as response:
        raw = response.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES:
        raise ValueError("rpc_response_too_large")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("jsonrpc") != "2.0" or data.get("id") != 1:
        raise ValueError("invalid_rpc_response")
    value = data.get("result")
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise ValueError("invalid_rpc_result")
    return int(value, 16)


def get_robinhood_rpc_status() -> dict[str, Any]:
    try:
        network = _network()
    except ValueError:
        return {
            "network": "unknown", "chain_id_expected": None, "chain_id_seen": None,
            "block_number": None, "status": "unavailable", "checked_at": None,
            "error": "unsupported_network", "trading_enabled": False,
        }

    url, chain_id = _NETWORKS[network]
    default = {
        "network": network, "chain_id_expected": chain_id,
        "chain_id_seen": None, "block_number": None, "status": "disabled",
        "checked_at": None, "error": None, "trading_enabled": False,
    }
    if not _flag_enabled():
        return default

    with _LOCK:
        prior = _CACHE.get(network)
        if prior and time.monotonic() - prior[0] < _CACHE_SECONDS:
            return dict(prior[1])
        try:
            actual = _rpc(url, "eth_chainId")
            if actual != chain_id:
                result = {
                    **default, "status": "mismatch", "chain_id_seen": actual,
                    "error": "chain_id_mismatch",
                }
            else:
                block = _rpc(url, "eth_blockNumber")
                result = {
                    **default, "status": "ok", "chain_id_seen": actual,
                    "block_number": block,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
        except (HTTPError, URLError, OSError, TimeoutError, ValueError, TypeError) as exc:
            logger.warning("Robinhood RPC probe failed: %s", type(exc).__name__)
            result = {**default, "status": "unavailable", "error": "rpc_unavailable"}
        _CACHE[network] = (time.monotonic(), result)
        return dict(result)
