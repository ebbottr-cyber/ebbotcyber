"""Opt-in daily wrapper for the existing V9 prospective paper CLI.

This file DOES NOT install a schedule or enable paper tracking by itself.
The operator must invoke it (e.g. with cron) and explicitly choose --commit
on a persistent PC/VPS. Always writes a small local status JSON file and
can optionally send a *failure-only* alert through existing notification
channels. Never sends a trade, makes a portfolio decision, or backfills.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from scripts.observe_etf_paper_v9 import parser as paper_parser, run as run_paper


def parser() -> argparse.ArgumentParser:
    ap = paper_parser()
    ap.description = "Opt-in manual/scheduled paper close checker with local health status"
    ap.add_argument("--status-file", type=Path, required=True,
                    help="Persistent local JSON status file; parent directory must exist")
    ap.add_argument("--notify-on-error", action="store_true",
                    help="Opt in to a generic failure alert through configured NotificationService")
    return ap


def _write_status(path: Path, payload: dict) -> None:
    if path.is_symlink() or not path.parent.is_dir():
        raise ValueError("health status file must have an existing local parent and not be a symlink")
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True).encode("utf-8")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".paper-health-", dir=path.parent, delete=False) as file:
            tmp = Path(file.name)
            os.chmod(tmp, 0o600)
            file.write(raw + b"\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def _send_failure_alert(kind: str) -> bool:
    """Generic alert with no ETF orders, journal content, credentials or file path."""
    from src.notification import NotificationService

    notifier = NotificationService()
    if not notifier.is_available():
        return False
    return bool(notifier.send(
        f"EBBot V10 prospective paper observation BLOCKED ({kind}). "
        "Review the local operator status JSON; no trades were executed.",
        route_type="report",
    ))


def execute(args: argparse.Namespace) -> int:
    if args.status or args.commit and args.status_file == args.journal:
        raise ValueError("cannot replace journal with status JSON")
    if args.status_file.resolve(strict=False) == args.journal.resolve(strict=False):
        raise ValueError("status and journal paths must be different")
    now = datetime.now(timezone.utc)
    # By default a run is only a read-only PREVIEW. This is deliberate:
    # a person must opt in to --commit when configuring their cron/systemd task.
    try:
        code = run_paper(args)
        if code != 0:
            raise RuntimeError("paper CLI returned a nonzero status")
    except Exception as exc:
        kind = type(exc).__name__
        result = {
            "status": "BLOCKED",
            "at_utc": now.isoformat(),
            "error_type": kind,
            "record_mode": bool(args.commit),
            "trading_enabled": False,
        }
        _write_status(args.status_file, result)
        if args.notify_on_error:
            try:
                delivered = _send_failure_alert(kind)
                result["notification_delivered"] = delivered
                _write_status(args.status_file, result)
            except Exception:
                # The original paper failure is never masked by notifier errors.
                result["notification_delivered"] = False
                _write_status(args.status_file, result)
        print(json.dumps(result, ensure_ascii=False), file=__import__("sys").stderr)
        return 1

    result = {
        "status": "RECORDED" if args.commit else "PREVIEW_ONLY",
        "at_utc": now.isoformat(),
        "record_mode": bool(args.commit),
        "trading_enabled": False,
    }
    _write_status(args.status_file, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main() -> int:
    args = parser().parse_args()
    try:
        return execute(args)
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED", "error_type": type(exc).__name__,
                          "trading_enabled": False}), file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
