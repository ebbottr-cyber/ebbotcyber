"""Local append-only paper journal with fail-closed chain validation.

The SHA-256 hash chain detects accidental mutation/corruption, not an attacker
who can rewrite the file and all hashes. Files must be backed up independently.
No cloud, database, GitHub repo or broker writes occur.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

from src.core.prospective_paper import SCHEMA_VERSION, check_hash, _canonical


def _checked_records(contents: bytes) -> list[dict[str, Any]]:
    if not contents:
        raise ValueError("empty journal is invalid")
    if not contents.endswith(b"\n"):
        raise ValueError("incomplete journal write; manual recovery required")
    records: list[dict[str, Any]] = []
    base_rules: Any = None
    source: str | None = None
    previous = None
    for line in contents.splitlines():
        if not line:
            raise ValueError("blank journal entry")
        try:
            data = json.loads(line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("invalid journal JSON entry") from exc
        if not isinstance(data, dict) or not check_hash(data):
            raise ValueError("paper journal hash mismatch")
        if data.get("schema_version") != SCHEMA_VERSION or data.get("research_only") is not True:
            raise ValueError("unsupported journal version or purpose")
        if type(data.get("seq")) is not int or data["seq"] != len(records):
            raise ValueError("missing or out-of-order paper record")
        if type(data.get("invested")) is not bool or data.get("pending_target") not in (None, True, False) \
                or data.get("fill") not in (None, "BUY", "SELL"):
            raise ValueError("invalid journal paper state")
        try:
            session = datetime.fromisoformat(data["session"]).date()
            next_session = datetime.fromisoformat(data["next_session"]).date()
            observed = datetime.fromisoformat(data["observed_at_utc"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError("journal has invalid date/time") from exc
        if next_session <= session or observed.tzinfo is None:
            raise ValueError("invalid or timezone-naive journal session")
        if not data.get("source") or not isinstance(data.get("rules"), dict):
            raise ValueError("journal source/rules missing")
        if not all(type(data.get(k)) in (int, float) and math.isfinite(float(data[k])) and float(data[k]) > 0
                   for k in ("close", "equity", "peak_equity")):
            raise ValueError("non-positive or invalid journal equity/price")
        if previous is None:
            if data.get("prev_hash") is not None or data["equity"] != 1.0 \
                    or data["invested"] is not False or data["fill"] is not None:
                raise ValueError("journal first record must start from cash")
            base_rules, source = data["rules"], data["source"]
        else:
            if data.get("prev_hash") != previous["hash"] or data["session"] != previous["next_session"]:
                raise ValueError("journal chain contains a skipped or modified session")
            if data["rules"] != base_rules or data["source"] != source:
                raise ValueError("paper rules or provider changed inside journal")
            if observed.astimezone(timezone.utc) <= datetime.fromisoformat(
                    previous["observed_at_utc"]).astimezone(timezone.utc):
                raise ValueError("paper observation timestamps not increasing")
        records.append(data)
        previous = data
    return records


def read_journal(path: str | Path) -> list[dict[str, Any]]:
    dest = Path(path)
    if dest.is_symlink():
        raise ValueError("journal symlinks are not allowed")
    if not dest.exists():
        return []
    if not dest.is_file():
        raise ValueError("journal must be a regular file")
    return _checked_records(dest.read_bytes())


def append_paper_record(path: str | Path, record: Mapping[str, Any]) -> None:
    """Append one already-calculated close under a cross-platform exclusive lock.

    Creates a sibling .lock file with O_EXCL; never auto-breaks a stale lock.
    A concurrent writer must retry after the other has exited.
    """
    dest = Path(path)
    if not dest.parent.is_dir() or dest.is_symlink():
        raise ValueError("journal parent must exist and journal cannot be a symlink")
    lock = Path(str(dest) + ".lock")
    lock_fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        current = read_journal(dest)
        payload = dict(record)
        if not check_hash(payload):
            raise ValueError("new paper entry hash invalid")
        if type(payload.get("seq")) is not int or payload["seq"] != len(current):
            raise ValueError("stale or duplicate journal record")
        if current and payload.get("prev_hash") != current[-1]["hash"]:
            raise ValueError("journal was advanced by another writer")
        if not current and payload.get("prev_hash") is not None:
            raise ValueError("first paper event must have no predecessor")
        # Verify the whole next chain before performing a write.
        data = _canonical(payload) + b"\n"
        _checked_records(b"".join(_canonical(x) + b"\n" for x in current) + data)
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(dest), flags, 0o600)
        try:
            with os.fdopen(fd, "ab", buffering=0) as file:
                written = file.write(data)
                if written != len(data):
                    raise OSError("partial paper journal write")
                os.fsync(file.fileno())
        except BaseException:
            # Corruption is deliberate fail-closed, never silently repaired.
            raise
    finally:
        os.close(lock_fd)
        os.unlink(lock)
