#!/usr/bin/env python3
"""Fail-closed Windows Authenticode policy review for an OFFLINE EBBot package.

The inputs are only local JSON collected from Windows Get-AuthenticodeSignature.
This script never executes installers, downloads files, signs code, enables updates,
or makes release/trading decisions. It must never authorize a public release.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("nsis_installer", "electron_app", "python_backend")
THUMBPRINT = re.compile(r"^[0-9A-F]{40}$")


def _utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Missing certificate validity date")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Expected timezone-aware certificate validity date")
    return parsed.astimezone(timezone.utc)


def audit(policy: dict, observation: dict, *, at: datetime | None = None) -> dict:
    now = at or datetime.now(timezone.utc)
    errors: list[str] = []
    checks: list[dict] = []
    if not isinstance(policy, dict) or not isinstance(observation, dict):
        raise ValueError("Policy and observation must both be JSON objects")
    if policy.get("schema_version") != 1 or policy.get("product") != "EBBot":
        errors.append("Unknown signing policy format or product")
    if policy.get("release_enabled") is not False:
        errors.append("Release must remain explicitly disabled in signing policy")
    if policy.get("required_targets") != list(TARGETS):
        errors.append("All three Windows executables must be required")
    if (observation.get("schema_version") != 1 or
            observation.get("product") != "EBBot" or
            observation.get("platform") != "windows"):
        errors.append("Invalid Windows signature observation")
    if not isinstance(observation.get("version"), str) or not re.fullmatch(
            r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", observation["version"]):
        errors.append("Invalid or missing desktop version")

    pinned = policy.get("approved_signer_thumbprints")
    if not isinstance(pinned, list) or any(
            not isinstance(item, str) or THUMBPRINT.fullmatch(item.upper()) is None
            for item in pinned):
        errors.append("Approved signer thumbprints must be 40-digit SHA-1 certificate fingerprints")
        pinned = []
    allowed = {item.upper() for item in pinned}

    signatures = observation.get("signatures")
    if not isinstance(signatures, dict) or set(signatures) != set(TARGETS):
        errors.append("Signature observation must contain exactly the three known executables")
        signatures = signatures if isinstance(signatures, dict) else {}

    for name in TARGETS:
        value = signatures.get(name)
        reasons: list[str] = []
        if not isinstance(value, dict):
            reasons.append("Missing signature observation")
        else:
            if value.get("present") is not True:
                reasons.append("Executable was not found on Windows runner")
            if value.get("status") != "Valid":
                reasons.append("Windows Authenticode did not return Valid")
            signer = value.get("thumbprint")
            if not isinstance(signer, str) or signer.upper() not in allowed:
                reasons.append("Certificate thumbprint is not on the approved signer allowlist")
            if not isinstance(signer, str) or THUMBPRINT.fullmatch(signer.upper()) is None:
                reasons.append("No valid certificate thumbprint")
            try:
                not_before = _utc(value.get("valid_from", ""))
                not_after = _utc(value.get("valid_until", ""))
                if not not_before <= now <= not_after:
                    reasons.append("Certificate is outside its validity interval")
            except (TypeError, ValueError):
                reasons.append("Missing or invalid certificate validity interval")
        checks.append({"target": name, "passed": not reasons, "reasons": reasons})

    valid = not errors and all(item["passed"] for item in checks)
    blockers = errors + [
        f"{check['target']}: {reason}"
        for check in checks for reason in check["reasons"]
    ]
    blockers.extend([
        "No verified Windows SmartScreen reputation or production rollout",
        "No verified Windows user installation, update, uninstall or data migration",
        "Public releases and desktop updates remain disabled",
    ])
    return {
        "scope": "local_windows_authenticode_metadata_only",
        "signing_validation": "PASSED" if valid else "BLOCKED",
        "release_status": "BLOCKED",
        "signature_checks": checks,
        "release_blockers": blockers,
        "executes_binary": False,
        "enables_updates": False,
        "publishes_release": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", required=True, type=Path)
    parser.add_argument("--policy", type=Path, default=ROOT / ".github/ebbot-desktop-signing-policy.json")
    parser.add_argument("--strict-signature", action="store_true",
                        help="Non-zero unless all local executables have trusted pinned signatures")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        observation = json.loads(args.observation.read_text(encoding="utf-8"))
        result = audit(policy, observation)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"release_status": "BLOCKED", "signing_validation": "BLOCKED",
                          "inspection_error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else
          f"Signature verification: {result['signing_validation']}; release: BLOCKED")
    return int(bool(args.strict_signature and result["signing_validation"] != "PASSED"))


if __name__ == "__main__":
    raise SystemExit(main())
