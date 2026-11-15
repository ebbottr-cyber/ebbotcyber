# -*- coding: utf-8 -*-
"""Strict, dependency-free Yahoo symbols for the Turkish BIST market.

This module validates input syntax only: a valid .IS equity symbol does
not prove current BIST100 membership or quote availability. Market data
routing is intentionally a separate integration step.
"""

from __future__ import annotations

import re

BIST100_INDEX_SYMBOL = "XU100.IS"
_BIST_EQUITY_SYMBOL = re.compile(r"[A-Z]{4,6}\.IS", re.ASCII)


def normalize_bist_equity_symbol(value: str | None) -> str | None:
    """Canonicalize explicit `TICKER.IS` equities without dropping the suffix.

    The suffix is required: bare symbols might collide with US equities.
    Index-like `XU100.IS` is not an equity symbol.
    """
    if not isinstance(value, str):
        return None
    code = value.strip().upper()
    return code if _BIST_EQUITY_SYMBOL.fullmatch(code) else None


def is_bist_equity_symbol(value: str | None) -> bool:
    return normalize_bist_equity_symbol(value) is not None


def normalize_bist100_index_symbol(value: str | None) -> str | None:
    """Recognize the BIST100 benchmark, never a constituent."""
    if not isinstance(value, str):
        return None
    return (
        BIST100_INDEX_SYMBOL
        if value.strip().upper() == BIST100_INDEX_SYMBOL
        else None
    )
