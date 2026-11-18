"""Bounded, read-only presentation of a user-supplied prospective paper journal.

No server-side journal path, import persistence, market-data download, or
execution capability. The server verifies the full V9 hash chain, then emits
only a small sanitized summary and recent simulated fills to the UI.
"""
from __future__ import annotations

import math

from src.services.prospective_paper_journal import _checked_records

MAX_JOURNAL_BYTES = 524288
MAX_JOURNAL_RECORDS = 5000
DISPLAY_RECENT_EVENTS = 40


def inspect_paper_journal_text(text: str) -> dict:
    if not isinstance(text, str):
        raise ValueError("journal content must be UTF-8 text")
    raw = text.encode("utf-8")
    if len(raw) > MAX_JOURNAL_BYTES:
        raise ValueError("paper journal exceeds 512 KiB limit")
    if not raw:
        raise ValueError("empty journal has no prospective observations")
    entries = _checked_records(raw)
    if len(entries) > MAX_JOURNAL_RECORDS:
        raise ValueError("too many paper journal rows")
    first, last = entries[0], entries[-1]
    rules = first.get("rules", {})
    asset = rules.get("asset_code")
    if not isinstance(asset, str) or len(asset) != 6 or not asset.isdigit():
        raise ValueError("journal is not an eligible single-ETF paper experiment")

    # Use validated equity marks rather than trusting a serialized percentage.
    # The original account starts in cash at equity 1.0.
    peak = 1.0
    worst_dd = 0.0
    for entry in entries:
        val = float(entry["equity"])
        if not math.isfinite(val) or val <= 0:
            raise ValueError("invalid paper equity")
        peak = max(peak, val)
        worst_dd = max(worst_dd, 100.0 * (peak - val) / peak)

    events = [
        {
            "session": x["session"],
            "paper_fill": x["fill"],
            "paper_invested": x["invested"],
            "signal_recorded": x["signal"] is True,
            "equity": float(x["equity"]),
        }
        for x in entries[-DISPLAY_RECENT_EVENTS:]
    ]
    return {
        "status": "PAPER_ONLY",
        "research_only": True,
        "source": first["source"],
        "asset_code": asset,
        "record_count": len(entries),
        "first_session": first["session"],
        "last_session": last["session"],
        "last_observed_at_utc": last["observed_at_utc"],
        "last_equity": float(last["equity"]),
        "observed_return_pct": (float(last["equity"]) - 1.0) * 100.0,
        "observed_max_drawdown_pct": worst_dd,
        "paper_buy_count": sum(x["fill"] == "BUY" for x in entries),
        "paper_sell_count": sum(x["fill"] == "SELL" for x in entries),
        "invested": last["invested"],
        "next_expected_session": last["next_session"],
        "events": events,
        "verified_hash_chain": True,
        "note": "Journal integrity checked; no independent verification of actual forward observation timestamps or price provider.",
    }
