# -*- coding: utf-8 -*-
"""Explicit operator-only BIST100 saved report publisher.

The default is read/validate/preview. Publishing requires an operator-supplied
SHA-256 and --publish and an absolute BIST100_TECHNICAL_REPORT_PATH. The CLI
never touches SQLite, the internet, a model, broker or market-data provider.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from src.services.bist100_technical_report_reader import (
    TechnicalReportInvalid,
    _MAX_BYTES,
    validate_technical_report,
)

_SHA256 = re.compile(r"[a-fA-F0-9]{64}\Z")


class ReportPublicationError(ValueError):
    """Report cannot be safely validated or published."""


def prepare_saved_report(
    source: str | Path,
    *,
    publish: bool = False,
    expected_sha256: str | None = None,
    replace_existing: bool = False,
) -> dict:
    """Validate a dated report and optionally atomically publish to approved path.

    Validation checks report counters, all 2026-Q4 constituents, technical
    indicators, rank ordering, MA5 flags and the official XIST session.
    SHA-256 proves byte equality to the operator-approved source; it is NOT an
    independent authenticity signature for the original market data.
    """
    path = Path(source)
    try:
        if path.is_symlink() or not path.is_file():
            raise ReportPublicationError("Source must be an existing regular file, not a symlink")
        size = path.stat().st_size
        if size < 1 or size > _MAX_BYTES:
            raise ReportPublicationError("Report must be a nonempty JSON file at most 2 MB")
        with path.open("rb") as handle:
            raw = handle.read(_MAX_BYTES + 1)
        if not raw or len(raw) > _MAX_BYTES:
            raise ReportPublicationError("Report is empty or oversized")
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReportPublicationError("Report cannot be read as UTF-8 JSON") from exc

    try:
        validated = validate_technical_report(payload)
    except TechnicalReportInvalid as exc:
        raise ReportPublicationError("Report failed BIST100 historical technical validation") from exc

    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None:
        if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
            raise ReportPublicationError("Expected SHA-256 must contain exactly 64 hex characters")
        if not hmac.compare_digest(digest, expected_sha256.lower()):
            raise ReportPublicationError("Report SHA-256 does not match operator-approved fingerprint")

    result = {
        "mode": "validated_preview",
        "sha256": digest,
        "as_of": validated["as_of"],
        "last_completed_session": validated["last_completed_session"],
        "checked": validated["checked"],
        "analyzed": validated["analyzed"],
        "remaining": validated["remaining"],
        "watchlist_eligible": validated["watchlist_eligible"],
    }
    if not publish:
        return result

    if expected_sha256 is None:
        raise ReportPublicationError("Publishing requires an explicit expected SHA-256 fingerprint")
    # Only the backend operator's configured report path may be published.
    # A Python caller cannot override this with another target file.
    configured = os.getenv("BIST100_TECHNICAL_REPORT_PATH", "").strip()
    if not configured:
        raise ReportPublicationError("BIST100_TECHNICAL_REPORT_PATH is not configured")
    target = Path(configured)
    if not target.is_absolute() or not target.name.endswith(".json"):
        raise ReportPublicationError("Approved destination must be an absolute .json path")
    parent = target.parent
    if any(part.is_symlink() for part in (parent, *parent.parents)) or not parent.is_dir():
        raise ReportPublicationError(
            "Destination parent and its ancestors must exist without symlinks"
        )
    if target.is_symlink():
        raise ReportPublicationError("Refusing to replace a symlink destination")
    if target.exists():
        if not target.is_file():
            raise ReportPublicationError("Existing destination is not a regular file")
        if not replace_existing:
            raise ReportPublicationError("Destination already exists: explicit --replace-existing required")
    # A source path equal to the target is not a useful publication operation.
    if path.resolve() == target.resolve():
        raise ReportPublicationError("Source and destination paths must differ")

    staged: Path | None = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=parent)
        staged = Path(name)
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Do not use os.replace for first publication: that would overwrite a
        # report created between the earlier existence check and this step.
        # An exclusive hard link to a fully synced same-directory temp file is
        # atomic and fails if ANY destination entry appeared in the meantime.
        if replace_existing:
            os.replace(staged, target)
        else:
            try:
                os.link(staged, target)
            except FileExistsError as exc:
                raise ReportPublicationError(
                    "Destination appeared during publication: refusing to overwrite"
                ) from exc
            staged.unlink()
        staged = None
    except OSError as exc:
        raise ReportPublicationError("Failed to atomically publish approved BIST100 report") from exc
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
    result["mode"] = "published"
    # Intentionally exclude physical server filesystem path from output/logs.
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Operator-controlled local saved BIST100 technical JSON publication (preview by default)"
    )
    parser.add_argument("--source", required=True, type=Path, help="Previously generated technical JSON")
    parser.add_argument("--expected-sha256", help="Operator-verified SHA-256; mandatory for --publish")
    parser.add_argument("--publish", action="store_true", help="Opt in to writing the configured server file")
    parser.add_argument("--replace-existing", action="store_true", help="Allow replacing an existing approved report")
    args = parser.parse_args()
    if args.replace_existing and not args.publish:
        parser.error("--replace-existing requires --publish")
    try:
        result = prepare_saved_report(
            args.source,
            publish=args.publish,
            expected_sha256=args.expected_sha256,
            replace_existing=args.replace_existing,
        )
    except ReportPublicationError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
