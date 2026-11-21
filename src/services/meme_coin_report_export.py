"""Opt-in local-only export of verified SYNTHETIC research snapshots.

This is an untrusted-viewer interchange format, not an authenticated
performance record. No API, scheduler, real data, wallet or trade execution.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.services.meme_coin_persistent_journal import read_synthetic_scenarios

FORMAT = "ebbot-synthetic-report-v1"


def export_synthetic_report(
    *, database_path: Any, starting_equity_usd: Any,
    output_path: Any, enabled: bool = False,
) -> dict[str, Any]:
    """Export a verified offline SQLite snapshot without overwriting files."""
    if enabled is not True:
        return {"status": "blocked", "reason": "offline_export_disabled"}
    snapshot = read_synthetic_scenarios(
        database_path=database_path, starting_equity_usd=starting_equity_usd,
        enabled=True,
    )
    if snapshot.get("status") != "synthetic_storage_snapshot":
        return {"status": "blocked", "reason": snapshot.get("reason", "read_failed")}
    if not isinstance(output_path, (Path, str)) or not str(output_path):
        return {"status": "blocked", "reason": "invalid_output_path"}
    path = Path(output_path).absolute()
    if path.suffix != ".json" or not path.parent.is_dir() or path.is_symlink():
        return {"status": "blocked", "reason": "invalid_output_path"}
    payload = json.dumps(
        {"format": FORMAT, "snapshot": snapshot},
        sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2,
    ) + "\n"
    if len(payload.encode("utf-8")) > 262144:
        return {"status": "blocked", "reason": "report_too_large"}
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        return {"status": "blocked", "reason": "output_already_exists"}
    except OSError:
        return {"status": "blocked", "reason": "output_unavailable"}
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
    except OSError:
        try:
            path.unlink()
        except OSError:
            pass
        return {"status": "blocked", "reason": "output_unavailable"}
    return {
        "status": "exported",
        "format": FORMAT,
        "event_count": snapshot["event_count"],
        "output_path": str(path),
        "trade_executed": False,
        "live_trading_enabled": False,
    }
