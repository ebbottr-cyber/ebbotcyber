#!/usr/bin/env python3
"""Read-only, fail-closed audit of EBBot's NSIS *source* upgrade contract.

This script does not invoke NSIS/electron-builder, start EBBot, modify a user
profile, inspect installed software or authorize a release. A PASS means only
that the pinned source safety invariants are present, not that an installer was
tested on a user's Windows machine.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

INSTALLER = Path("apps/dsa-desktop/installer.nsh")
PACKAGE = Path("apps/dsa-desktop/package.json")
MAIN = Path("apps/dsa-desktop/main.js")
WORKFLOW = Path(".github/workflows/ebbot-electron-windows-offline-package.yml")


def _contains_line(source: str, line: str) -> bool:
    return line in (part.strip() for part in source.splitlines())


def audit(installer: str, package: dict, main: str, workflow: str) -> dict:
    checks: dict[str, bool] = {}
    checks["per_user_install_only"] = (
        re.search(r"(?m)^!macro customInstallMode\s*$\n\s*;", installer) is not None
        and _contains_line(installer, "StrCpy $isForceCurrentInstall 1")
        and installer.count("!macro customInstallMode") == 1
    )
    checks["explicit_safe_install_directory"] = all(
        token in installer for token in (
            "!macro customHeader", "Function .onVerifyInstDir",
            "$PROGRAMFILES", "$PROGRAMFILES64", "$PROGRAMFILES32",
            "$WINDIR", "_dsa_reject:", "Abort",
        )
    )
    # A failed old-uninstaller process must never be treated as success.
    checks["old_uninstaller_nonzero_fails_closed"] = (
        re.search(
            r"\$\{if\}\s+\$R0 == 0\s+Return\s+\$\{endif\}",
            installer,
        ) is not None
        and "DsaQuotedUninstallFailed_${SUFFIX}:" in installer
        and _contains_line(installer, "SetErrorLevel 2")
        and _contains_line(installer, "Quit")
        and "IfErrors DsaQuotedUninstallFailed_${SUFFIX} DsaQuotedUninstallResult_${SUFFIX}" in installer
        and "!insertmacro _dsaRetryQuotedOldUninstall SHELL_CONTEXT Shell" in installer
        and "!insertmacro _dsaRetryQuotedOldUninstall HKEY_CURRENT_USER CurrentUser" in installer
    )
    retry_commands = re.findall(r"(?m)^\s*ExecWait\s+(.+)$", installer)
    checks["quoted_retry_preserves_app_data"] = (
        len(retry_commands) == 2
        and all(
            "/S /KEEP_APP_DATA $R9" in command
            and '"_?=$R8"' in command
            and command.endswith("' $R0")
            for command in retry_commands
        )
        and '"$R5"' in retry_commands[0]
        and '"$R7"' in retry_commands[1]
        and "!insertmacro GetInQuotes $R7 \"$R6\"" in installer
        and '"${INSTALL_REGISTRY_KEY}" InstallLocation' in installer
    )
    # This is an audit of the custom include, NOT electron-builder's own NSIS
    # implementation. Reject new deletion commands in this include.
    checks["no_custom_data_deletion_commands"] = not re.search(
        r"(?mi)^\s*(?:RMDir|Delete|DeleteRegKey|DeleteRegValue|ExecShell)\b",
        installer,
    )
    build = package.get("build", {}) if isinstance(package, dict) else {}
    nsis = build.get("nsis", {}) if isinstance(build, dict) else {}
    win = build.get("win", {}) if isinstance(build, dict) else {}
    target = win.get("target") if isinstance(win, dict) else None
    checks["package_per_user_nsis_constraints"] = (
        build.get("appId") == "com.ebbot.desktop"
        and build.get("productName") == "EBBot"
        and target == "nsis"
        and nsis.get("oneClick") is False
        and nsis.get("allowElevation") is False
        and nsis.get("allowToChangeInstallationDirectory") is True
        and nsis.get("include") == "installer.nsh"
    )
    checks["desktop_auto_update_hard_disabled"] = (
        _contains_line(main, "const DESKTOP_UPDATES_ENABLED = false;")
        and "if (!DESKTOP_UPDATES_ENABLED)" in main
    )
    checks["ci_package_never_published"] = (
        "npx --no-install electron-builder --win nsis --publish never" in workflow
        and "permissions:\n  contents: read" in workflow
        and "Release remains explicitly blocked" in workflow
        and "release_status -ne \"BLOCKED\"" in workflow
        and "Upload audit JSON ONLY" in workflow
        and "never upload installer" in workflow
    )
    checks["installer_and_user_runtime_not_executed_in_ci"] = (
        # CI may launch an isolated, frozen backend and a restricted Electron
        # smoke, but never install NSIS or invoke the regular update path.
        "NO publish or installer execution" in workflow
        and "--publish never" in workflow
        and "DESKTOP_UPDATES_ENABLED = false" in main
    )
    failed = sorted(key for key, value in checks.items() if not value)
    return {
        "schema_version": 1,
        "status": "PASSED_SOURCE_ONLY" if not failed else "REVIEW_REQUIRED",
        "release_status": "BLOCKED",
        "installer_executed": False,
        "upgrade_performed": False,
        "user_files_accessed": False,
        "automatic_updates_enabled": False,
        "ready_to_publish": False,
        "checks": checks,
        "failed_checks": failed,
    }


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        result = audit(
            (root / INSTALLER).read_text(encoding="utf-8"),
            json.loads((root / PACKAGE).read_text(encoding="utf-8")),
            (root / MAIN).read_text(encoding="utf-8"),
            (root / WORKFLOW).read_text(encoding="utf-8"),
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"NSIS source audit failed closed: {type(exc).__name__}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("EBBot NSIS contract: " + result["status"]
              + "; release=BLOCKED; failed=" + ",".join(result["failed_checks"]))
    return 0 if result["status"] == "PASSED_SOURCE_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
