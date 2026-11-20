#!/usr/bin/env python3
"""Inspect EBBot's desktop source and Windows build without running installers.

Never starts Electron, backend, scheduler, market scans, paper/live orders, or
network connections. A valid build is NOT permission to distribute it.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ("ZhuLinsen", "daily_stock_analysis")
OWN_REPO = ("ebbottr-cyber", "ebbotcyber")


def _check(checks: list[dict], name: str, okay: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(okay), "detail": detail})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha512_base64(path: Path) -> str:
    """Return the base64 SHA-512 used in electron-builder's latest.yml."""
    digest = hashlib.sha512()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return base64.b64encode(digest.digest()).decode("ascii")


def verify_latest_yml(text: str, installer: Path, filename: str, version: str) -> tuple[bool, str]:
    """Check one local NSIS asset, never follow the manifest's URL or execute any file.

    This is a narrow, fail-closed check of electron-builder's *Windows NSIS*
    latest.yml layout. It is not a substitute for authenticating an update
    signature or signing the installer.
    """
    if not installer.is_file():
        return False, "NSIS executable missing; cannot verify manifest hash"
    try:
        # Reject ambiguous/duplicate URL, version, path, digest and file entries.
        def values(pattern: str) -> list[str]:
            return [match.strip().strip("\'\"") for match in re.findall(pattern, text)]

        versions = values(r"(?m)^version:[ \t]*([^\r\n]+)$")
        paths = values(r"(?m)^path:[ \t]*([^\r\n]+)$")
        urls = values(r"(?m)^[ \t]*-[ \t]*url:[ \t]*([^\r\n]+)$")
        hashes = values(r"(?m)^[ \t]*sha512:[ \t]*([^\r\n]+)$")
        file_sizes = values(r"(?m)^[ \t]+size:[ \t]*([^\r\n]+)$")
        files_headers = re.findall(r"(?m)^files:[ \t]*$", text)
        if (len(files_headers) != 1 or len(versions) != 1 or len(paths) != 1 or
                len(urls) != 1 or len(hashes) != 2 or len(file_sizes) > 1):
            return False, "Ambiguous or missing NSIS latest.yml keys"
        if versions[0] != version or paths[0] != filename or urls[0] != filename:
            return False, "Version, installer path or asset URL mismatches EBBot NSIS"
        # Filename equality also rejects traversal, absolute URLs and external hosts.
        calculated = _sha512_base64(installer)
        if any(value != calculated for value in hashes):
            return False, "NSIS installer SHA-512 does not match update metadata"
        if file_sizes and (not file_sizes[0].isdigit() or
                           int(file_sizes[0]) != installer.stat().st_size):
            return False, "NSIS installer size does not match update metadata"
    except (OSError, ValueError):
        return False, "Cannot verify latest.yml or NSIS installer"
    return True, "Single EBBot NSIS asset, version, SHA-512 and size verified offline"


def source_audit(root: Path) -> dict:
    desktop = root / "apps/dsa-desktop"
    manifest = desktop / "package.json"
    main = desktop / "main.js"
    checks: list[dict] = []
    blockers: list[str] = []
    if not manifest.is_file() or not main.is_file():
        _check(checks, "desktop_source_present", False, "Electron package.json/main.js missing")
        return {"checks": checks, "release_blockers": ["Desktop source missing"], "version": ""}
    package = json.loads(manifest.read_text(encoding="utf-8"))
    js = main.read_text(encoding="utf-8")
    version = str(package.get("version", ""))
    _check(checks, "semantic_version", bool(re.fullmatch(r"\d+\.\d+\.\d+(?:-[\w.-]+)?", version)),
           "Desktop version must be semantic")
    build = package.get("build", {})
    _check(checks, "nsis_target", build.get("win", {}).get("target") == "nsis",
           "Windows installer must use the defined NSIS target")
    files = build.get("files", [])
    _check(checks, "electron_bridge", "main.js" in files and "preload.js" in files,
           "Electron main and preload must both be packaged")
    resources = build.get("extraResources", [])
    has_backend = any(x.get("from") == "../../dist/backend/stock_analysis" and
                      x.get("to") == "backend/stock_analysis"
                      for x in resources if isinstance(x, dict))
    _check(checks, "real_backend_resource", has_backend,
           "Actual PyInstaller backend must be bundled; placeholder is forbidden")
    _check(checks, "no_release_workflow", not (root / ".github/workflows/desktop-release.yml").exists(),
           "Tag-triggered desktop-release workflow must remain disabled")
    loading = desktop / "renderer/loading.html"
    _check(checks, "ebbot_loading_window",
           loading.is_file() and "<title>EBBot</title>" in loading.read_text(encoding="utf-8")
           and "<h1 class=\"title\">EBBot</h1>" in loading.read_text(encoding="utf-8")
           and "Daily Stock Analysis" not in loading.read_text(encoding="utf-8"),
           "Packaged loading window must show only the EBBot product name")
    _check(checks, "ebbot_product_identity",
           build.get("productName") == "EBBot" and build.get("appId") == "com.ebbot.desktop"
           and package.get("name") == "ebbot-desktop",
           "Desktop identity and product name must belong to EBBot")
    _check(checks, "ebbot_installer_name",
           build.get("win", {}).get("artifactName") == "EBBot-windows-installer-v${version}.${ext}",
           "Installer artifact must be EBBot-branded")
    _check(checks, "updater_runtime_disabled",
           "const DESKTOP_UPDATES_ENABLED = false;" in js
           and js.count("if (!DESKTOP_UPDATES_ENABLED) {") >= 2,
           "Unapproved desktop update checks and installations must remain disabled")
    _check(checks, "ebbot_update_references",
           all(f"const GITHUB_{name} = '{value}';" in js
               for name, value in zip(("OWNER", "REPO"), OWN_REPO)),
           "Runtime update repository must be EBBot-owned")
    _check(checks, "no_upstream_runtime_refs",
           not any(value in js or value in manifest.read_text(encoding="utf-8")
                   for value in UPSTREAM),
           "Packaged Electron files must not reference the original GitHub repository")
    pub = build.get("win", {}).get("publish", [])
    _check(checks, "ebbot_publish_target",
           pub == [{"provider": "github", "owner": OWN_REPO[0], "repo": OWN_REPO[1]}],
           "Electron publish must target EBBot only")
    if any(isinstance(x, dict) and
           (x.get("owner"), x.get("repo")) == UPSTREAM for x in pub):
        blockers.append("Electron win.publish targets the original upstream GitHub repository")
    if all(re.search(rf"const GITHUB_{name} = ['\"]{re.escape(value)}['\"];", js)
           for name, value in zip(("OWNER", "REPO"), UPSTREAM)):
        blockers.append("main.js update checks target the original upstream GitHub repository")
    if build.get("appId") == "com.daily-stock-analysis.desktop" or build.get("productName") == "Daily Stock Analysis":
        blockers.append("Desktop app identity/productName are still upstream-branded, not EBBot")
    blockers.append("No verified code-signing identity and Windows SmartScreen reputation")
    blockers.append("Real user-device install/update/uninstall and data preservation not tested")
    return {"version": version, "checks": checks, "release_blockers": blockers}


def package_audit(root: Path, dist: Path, version: str) -> dict:
    checks: list[dict] = []
    hashes: dict[str, str] = {}
    expected = f"EBBot-windows-installer-v{version}.exe"
    installer = dist / expected
    blockmap = dist / (expected + ".blockmap")
    latest = dist / "latest.yml"
    unpacked = dist / "win-unpacked"
    for name, path in (("nsis_installer", installer), ("nsis_blockmap", blockmap),
                       ("latest_yml", latest), ("electron_unpacked", unpacked)):
        _check(checks, name, path.is_file() if name != "electron_unpacked" else path.is_dir(),
               "Present" if path.exists() else "Missing " + path.name)
    if latest.is_file():
        valid, detail = verify_latest_yml(
            latest.read_text(encoding="utf-8"), installer, expected, version
        )
        _check(checks, "updater_metadata", valid, detail)
    else:
        _check(checks, "updater_metadata", False, "Missing latest.yml")
    resources = unpacked / "resources"
    _check(checks, "electron_asar", (resources / "app.asar").is_file(),
           "Electron ASAR must be present in unpacked build")
    _check(checks, "safe_sample_env", (resources / ".env.example").is_file(),
           "Shipped configuration must be a sample, not a real .env")
    _check(checks, "no_user_env", not (resources / ".env").exists(),
           "Private .env must not be bundled next to Electron resources")
    backend = resources / "backend" / "stock_analysis"
    _check(checks, "real_backend_exe", (backend / "stock_analysis.exe").is_file(),
           "Packaged PyInstaller stock_analysis.exe is required")
    static = any((backend / folder / "static" / "index.html").is_file()
                 for folder in ("_internal", ""))
    _check(checks, "packaged_react", static,
           "Packaged backend must contain built React static/index.html")
    for path in (installer, blockmap, latest):
        if path.is_file():
            hashes[path.name] = _sha256(path)
    return {"checks": checks, "sha256": hashes,
            "package_validation": "PASSED" if all(x["passed"] for x in checks) else "FAILED"}


def audit(root: Path, dist: Path | None = None) -> dict:
    source = source_audit(root)
    result = {"scope": "source_and_local_build_only", "release_status": "BLOCKED",
              "source": source, "package": None, "enables_trading": False,
              "publishes_release": False, "starts_electron": False}
    if dist is not None:
        result["package"] = package_audit(root, dist, source["version"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dist", type=Path)
    parser.add_argument("--strict-package", action="store_true")
    parser.add_argument("--strict-source", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit(args.root, args.dist)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json
          else f"Desktop packaging: {result['package']['package_validation'] if result['package'] else 'NOT_BUILT'}; "
               f"release status: BLOCKED ({len(result['source']['release_blockers'])} review blockers)")
    if args.strict_source and not all(c["passed"] for c in result["source"]["checks"]):
        return 1
    if args.strict_package and (not result["package"] or
                                result["package"]["package_validation"] != "PASSED"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
