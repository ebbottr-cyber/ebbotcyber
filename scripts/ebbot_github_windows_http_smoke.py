#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launch the actual EBBot FastAPI server on an ephemeral GitHub Windows runner.

* Only GET health, index and one built JS/CSS asset on 127.0.0.1.
* --lifespan off intentionally suppresses production startup tasks, schedulers,
  stock-index refreshes, cache warmup and possible background network work.
* Isolated missing ENV_FILE and unopened DATABASE_PATH, never user credentials.
* This is an HTTP/server integration check, not a real Electron package test.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib import error, parse, request

from ebbot_windows_portfolio_preflight import (
    check_frontend_bundle,
    check_sources,
    local_get,
    probe_local,
    summary,
)

ROOT = Path(__file__).resolve().parent.parent
LOCAL_PORT = 8007
ORIGIN = f"http://127.0.0.1:{LOCAL_PORT}"
ASSET_REF = re.compile(r"""(?:src|href)=["'](/assets/[^"']+)["']""")


def _asset_check(origin: str) -> bool:
    try:
        status, content_type, body = local_get(origin, "/")
        if status != 200 or "html" not in content_type.lower():
            return False
        refs = ASSET_REF.findall(body.decode("utf-8", errors="replace"))
        if not refs:
            return False
        path = refs[0]
        # Only a Vite asset in the checked out, freshly built bundle.
        if not re.fullmatch(r"/assets/[A-Za-z0-9_.-]+", path):
            return False
        # Vite bundles can exceed the 64 KiB cap of JSON health responses.
        # Read only the first 512 bytes, never fetch an entire JS bundle.
        from ebbot_windows_portfolio_preflight import _RejectRedirect
        opener = request.build_opener(request.ProxyHandler({}), _RejectRedirect())
        with opener.open(
            request.Request(origin + path, method="GET"), timeout=4,
        ) as response:
            media_type = response.headers.get("Content-Type", "")
            if response.status != 200 or not response.read(512):
                return False
            if path.endswith(".js") and "javascript" not in media_type.lower():
                return False
            if path.endswith(".css") and "css" not in media_type.lower():
                return False
        return True
    except (OSError, ValueError, error.URLError):
        return False


def main() -> int:
    checks = check_sources(ROOT) + check_frontend_bundle(ROOT)
    if summary(checks) != "PASSED_READ_ONLY":
        print("BLOCKED: Windows source or built Vite asset checks failed.", flush=True)
        return 2

    with tempfile.TemporaryDirectory(prefix="ebbot-ci-http-smoke-") as temp:
        temp_dir = Path(temp)
        missing_env = temp_dir / "missing.env"
        unopened_db = temp_dir / "never-opened.db"
        env = dict(os.environ)
        env.update({
            "ENV_FILE": str(missing_env),
            "DATABASE_PATH": str(unopened_db),
            "ADMIN_AUTH_ENABLED": "false",
            "GUARD_ENABLED": "false",
            "CORS_ALLOW_ALL": "false",
            "RUNTIME_SCHEDULER_SUPPRESS_START": "true",
            "RUNTIME_SCHEDULER_FORCE_ENABLED": "false",
            "RUNTIME_SCHEDULER_RUN_IMMEDIATELY": "false",
            "PYTHONIOENCODING": "utf-8",
        })
        command = [
            sys.executable, "-m", "uvicorn", "api.app:app",
            "--host", "127.0.0.1", "--port", str(LOCAL_PORT),
            "--lifespan", "off", "--no-access-log",
        ]
        logpath = temp_dir / "backend.log"
        with logpath.open("w", encoding="utf-8") as logfile:
            process = subprocess.Popen(
                command, cwd=ROOT, env=env, stdout=logfile,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            )
            try:
                deadline = time.monotonic() + 100
                healthy = False
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        break
                    try:
                        status, ct, raw = local_get(ORIGIN, "/api/health")
                        if status == 200 and "json" in ct.lower():
                            obj = json.loads(raw)
                            if isinstance(obj, dict) and obj.get("status") == "ok":
                                healthy = True
                                break
                    except (OSError, ValueError, error.URLError):
                        pass
                    time.sleep(2)

                if not healthy:
                    print(
                        f"BLOCKED: real FastAPI process not healthy "
                        f"(exit={process.poll()}, within 100s).", flush=True,
                    )
                    return 2

                checks += probe_local(ORIGIN, check_display_fx=False)
                asset_ok = _asset_check(ORIGIN)
                clean = summary(checks) == "PASSED_READ_ONLY" and asset_ok
                report = {
                    "kind": "github_windows_http_integration",
                    "result": "PASSED_READ_ONLY" if clean else "BLOCKED",
                    "backend": next(c.status for c in checks if c.name == "backend_health"),
                    "frontend": next(c.status for c in checks if c.name == "frontend_http"),
                    "served_vite_asset": bool(asset_ok),
                    "scheduler_started": False,
                    "real_or_paper_orders": False,
                    "secrets_loaded": False,
                    "fx_provider_called": False,
                    "desktop_electron_installer_tested": False,
                    "checks": [{"name": c.name, "status": c.status} for c in checks],
                }
                print(json.dumps(report, ensure_ascii=True, sort_keys=True), flush=True)
                return 0 if clean else 2
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)

        # A startup import may create transient files, but no user data exists
        # on this ephemeral runner. Never persist the temporary DB/log artifacts.


if __name__ == "__main__":
    raise SystemExit(main())
