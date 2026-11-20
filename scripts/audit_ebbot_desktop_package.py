#!/usr/bin/env python3
"""Inspect EBBot's desktop source and Windows build without running installers.

Never starts Electron, backend, scheduler, market scans, paper/live orders, or
network connections. A valid build is NOT permission to distribute it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ("ZhuLinsen", "daily_stock_analysis")


def _check(checks: list[dict], name: str, okay: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(okay), "detail": detail})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    pub = build.get("win", {}).get("publish", [])
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
    expected = f"daily-stock-analysis-windows-installer-v{version}.exe"
    installer = dist / expected
    blockmap = dist / (expected + ".blockmap")
    latest = dist / "latest.yml"
    unpacked = dist / "win-unpacked"
    for name, path in (("nsis_installer", installer), ("nsis_blockmap", blockmap),
                       ("latest_yml", latest), ("electron_unpacked", unpacked)):
        _check(checks, name, path.is_file() if name != "electron_unpacked" else path.is_dir(),
               "Present" if path.exists() else "Missing " + path.name)
    if latest.is_file():
        text = latest.read_text(encoding="utf-8")
        vm = re.search(r"(?m)^version:\s*['\"]?([^'\"\r\n\s]+)", text)
        pm = re.search(r"(?m)^path:\s*['\"]?([^'\"\r\n]+)", text)
        um = re.search(r"(?m)^\s*-\s*url:\s*['\"]?([^'\"\r\n]+)", text)
        valid = (bool(vm) and vm.group(1).strip() == version and
                 bool(pm) and pm.group(1).strip() == expected and
                 (um is None or um.group(1).strip() == expected) and
                 bool(re.search(r"(?m)^sha512:\s*\S+", text)))
        _check(checks, "updater_metadata", valid,
               "NSIS metadata version, file URL, path and sha512 must agree with package")
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
