"""Prospective, close-only, single-ETF/cash paper observation.

Only historical bars available **through the observed close** may be supplied.
First observation starts in cash at equity 1.0; it never backfills or replays
profitable older trades. A signal recorded at today's close may only fill at
the NEXT session close. No broker, portfolio or trading API is imported.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, time, timezone
from hashlib import sha256
import json
import math
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import pandas as pd

from src.core.etf_rotation import (
    CASH, RotationParams, is_rebalance_day, momentum_scores, select_holdings,
)

SCHEMA_VERSION = 1
MAX_PRIOR_CLOSE_REVISION_BPS = 1.0  # fail closed instead of silently rebasing P&L


def _canonical(data: Mapping[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def fingerprint(record_without_hash: Mapping[str, Any]) -> str:
    return sha256(_canonical(record_without_hash)).hexdigest()


def check_hash(record: Mapping[str, Any]) -> bool:
    if not isinstance(record, dict) or not isinstance(record.get("hash"), str):
        return False
    payload = {key: val for key, val in record.items() if key != "hash"}
    return fingerprint(payload) == record["hash"]


def _frozen_rules(asset_code: str, params: RotationParams,
                  slippage_bps: float) -> dict[str, Any]:
    if not isinstance(asset_code, str) or not asset_code.isdigit() or len(asset_code) != 6:
        raise ValueError("requires a six-digit ETF code")
    if not isinstance(params, RotationParams) or params.top_n != 1:
        raise ValueError("single-asset RotationParams(top_n=1) required")
    if isinstance(slippage_bps, bool) or not isinstance(slippage_bps, (int, float)) \
            or not math.isfinite(slippage_bps) or slippage_bps < 0 \
            or slippage_bps + params.cost_bps >= 10000:
        raise ValueError("invalid per-side fee/slippage")
    return {"asset_code": asset_code, "lookback_days": params.lookback_days,
            "rebalance": params.rebalance, "top_n": 1,
            "switch_buffer_pct": params.switch_buffer_pct,
            "fee_bps": params.cost_bps, "slippage_bps": float(slippage_bps)}


def _check_history(history: pd.DataFrame, asset_code: str, day: date,
                   lookback: int) -> pd.Series:
    if not isinstance(history, pd.DataFrame) or history.columns.has_duplicates \
            or list(history.columns) != [asset_code]:
        raise ValueError("requires one-column adjusted ETF history")
    if not isinstance(history.index, pd.DatetimeIndex) or history.index.tz is not None \
            or history.index.hasnans or not history.index.is_unique \
            or not history.index.is_monotonic_increasing \
            or any(history.index != history.index.normalize()):
        raise ValueError("daily index must be unique, sorted and timezone naive")
    if len(history) < lookback + 1 or history.index[-1].date() != day:
        raise ValueError("history must end at observed session and include momentum warmup")
    if not pd.api.types.is_numeric_dtype(history[asset_code]):
        raise ValueError("close prices must be numeric")
    prices = history[asset_code].astype(float)
    if not all(math.isfinite(p) and p > 0 for p in prices):
        raise ValueError("all historical closes must be finite and positive")
    return prices


def observe_completed_close(
    history: pd.DataFrame,
    *,
    asset_code: str,
    params: RotationParams,
    source: str,
    as_of: date,
    next_session: date,
    observed_at_utc: datetime,
    previous: Mapping[str, Any] | None,
    slippage_bps: float = 0.0,
) -> dict[str, Any]:
    """Compute the NEXT immutable journal record, without storing it.

    Caller must confirm calendar sessions, latest completed market close, and
    forward-adjusted provider history independently (see opt-in CLI).
    prev_hash is only a tamper-evident checksum, not a digital signature.
    """
    rules = _frozen_rules(asset_code, params, slippage_bps)
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source name required")
    if not isinstance(as_of, date) or isinstance(as_of, datetime) \
            or not isinstance(next_session, date) or isinstance(next_session, datetime) \
            or next_session <= as_of:
        raise ValueError("valid ordered exchange sessions required")
    if not isinstance(observed_at_utc, datetime) or observed_at_utc.tzinfo is None:
        raise ValueError("observation must have a timezone-aware timestamp")
    at = observed_at_utc.astimezone(timezone.utc)
    shanghai_close = datetime.combine(as_of, time(15, 0), tzinfo=ZoneInfo("Asia/Shanghai"))
    if at < shanghai_close.astimezone(timezone.utc):
        raise ValueError("cannot record an ETF close before Shanghai market close")
    prices = _check_history(history, asset_code, as_of, params.lookback_days)
    close = float(prices.iloc[-1])
    equity, peak, drawdown = 1.0, 1.0, 0.0
    position = False
    fill = None
    seq = 0
    prev_hash = None
    if previous is not None:
        if not check_hash(previous):
            raise ValueError("previous event hash mismatch")
        if previous.get("schema_version") != SCHEMA_VERSION or previous.get("rules") != rules \
                or previous.get("source") != source:
            raise ValueError("frozen paper rules or data source changed; start a NEW journal")
        if previous.get("next_session") != as_of.isoformat():
            raise ValueError("missing, duplicate or out-of-order close; no historical backfill")
        prior_at = datetime.fromisoformat(previous["observed_at_utc"])
        if prior_at.tzinfo is None or at <= prior_at.astimezone(timezone.utc):
            raise ValueError("observation time must increase")
        prior_day = pd.Timestamp(previous["session"])
        if prior_day not in prices.index:
            raise ValueError("previous close is missing from the refreshed provider history")
        prior_close = float(previous["close"])
        revised = float(prices.loc[prior_day])
        drift = abs(revised / prior_close - 1.0) * 10000.0
        if drift > MAX_PRIOR_CLOSE_REVISION_BPS:
            raise ValueError("adjusted historical prior close was revised; do not silently rebase paper returns")
        if not isinstance(previous.get("seq"), int) or isinstance(previous["seq"], bool):
            raise ValueError("previous journal sequence invalid")
        seq = previous["seq"] + 1
        prev_hash = previous["hash"]
        position = previous["invested"]
        equity = float(previous["equity"])
        peak = float(previous["peak_equity"])
        drawdown = float(previous["max_drawdown_pct"])
        if position:
            equity *= close / prior_close
        pending = previous["pending_target"]
        if pending is not None and pending != position:
            equity *= 1.0 - (params.cost_bps + slippage_bps) / 10000.0
            position = pending
            fill = "BUY" if position else "SELL"
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak * 100.0)
    signal = False
    pending_target = None
    if is_rebalance_day(pd.Timestamp(as_of), pd.Timestamp(next_session), params.rebalance):
        # Signal only uses date <= as_of, and fills at the *next* close.
        scores = momentum_scores(prices.to_frame(asset_code), params.lookback_days).iloc[-1]
        selected = select_holdings(scores, [asset_code] if position else [], params)
        pending_target = asset_code in selected
        signal = True
    record = {
        "schema_version": SCHEMA_VERSION,
        "seq": seq,
        "observed_at_utc": at.isoformat(),
        "session": as_of.isoformat(),
        "next_session": next_session.isoformat(),
        "source": source,
        "rules": rules,
        "close": close,
        "signal": signal,
        "pending_target": pending_target,
        "fill": fill,
        "invested": bool(position),
        "equity": equity,
        "peak_equity": peak,
        "max_drawdown_pct": drawdown,
        "return_pct": (equity - 1.0) * 100.0,
        "prev_hash": prev_hash,
        "research_only": True,
    }
    record["hash"] = fingerprint(record)
    return record
