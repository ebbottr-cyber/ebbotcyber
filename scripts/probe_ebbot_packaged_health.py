#!/usr/bin/env python3
"""Windows CI-only frozen backend loopback smoke probe; no installer or trading."""
from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def _packaged_executable(path: Path) -> Path:
    exe = path.resolve(strict=True)
    if not exe.is_file() or exe.name.lower() != "stock_analysis.exe":
        raise ValueError("Expected a real packaged stock_analysis.exe")
    parents = [part.name.lower() for part in exe.parents[:4]]
    if parents != ["stock_analysis", "backend", "resources", "win-unpacked"]:
        raise ValueError("Probe only accepts the unpacked Electron backend")
    return exe


def _sanitized_environment() -> dict[str, str]:
    # Deliberately do not inherit API credentials, GitHub tokens, proxies,
    # portfolio settings or trading/scheduler settings from the CI runner.
    allowed = {
        "SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC",
        "PROGRAMDATA", "APPDATA", "LOCALAPPDATA", "USERPROFILE",
        "HOMEDRIVE", "HOMEPATH", "TEMP", "TMP", "OS",
        "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS",
    }
    env = {key: val for key, val in os.environ.items() if key.upper() in allowed}
    env.update({
        "GITHUB_ACTIONS": "true",
        "EBBOT_PACKAGED_HEALTH_PROBE": "1",
        "SCHEDULE_ENABLED": "false",
        "RUNTIME_SCHEDULER_SUPPRESS_START": "true",
        "RUNTIME_SCHEDULER_FORCE_ENABLED": "false",
        "RUNTIME_SCHEDULER_RUN_IMMEDIATELY": "false",
        "MEME_COIN_DISCOVERY_ENABLED": "false",
        "MEME_RADAR_LIVE_ENABLED": "false",
        "USE_PROXY": "false",
        "CORS_ALLOW_ALL": "false",
        "WEBUI_ENABLED": "false",
        "NO_PROXY": "*",
    })
    return env


def _get(port: int, path: str) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        conn.request("GET", path, headers={"Host": "127.0.0.1"})
        res = conn.getresponse()
        return res.status, res.read(4096)
    finally:
        conn.close()


def run(exe: Path, timeout_seconds: int) -> None:
    if sys.platform != "win32" or os.getenv("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Only the isolated Windows GitHub Actions runner may execute this probe")
    exe = _packaged_executable(exe)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind(("127.0.0.1", 0))
        port = int(candidate.getsockname()[1])

    child = subprocess.Popen(
        [str(exe), "--serve-only", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(exe.parent),
        env=_sanitized_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    try:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            code = child.poll()
            if code is not None:
                raise RuntimeError(f"Frozen backend exited before health response: code={code}")
            try:
                status, body = _get(port, "/api/health")
                if status != 200:
                    raise RuntimeError(f"Health status must be HTTP 200, received {status}")
                payload = json.loads(body)
                if payload != {"status": "ok", "probe": "offline-packaged"}:
                    raise RuntimeError("Unexpected health response; offline route isolation not verified")
                blocked_status, _ = _get(port, "/api/v1/analysis/analyze")
                if blocked_status != 404:
                    raise RuntimeError(f"Analysis endpoint unexpectedly exposed: HTTP {blocked_status}")
                print("PASS: frozen Windows backend served loopback health only; analysis unavailable.")
                return
            except (ConnectionRefusedError, ConnectionResetError, TimeoutError, OSError):
                time.sleep(1)
        raise TimeoutError(f"Frozen backend did not serve loopback health within {timeout_seconds}s")
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--timeout-seconds", default=180, type=int)
    args = parser.parse_args()
    if not 10 <= args.timeout_seconds <= 240:
        parser.error("Timeout must be between 10 and 240 seconds")
    try:
        run(args.exe, args.timeout_seconds)
    except Exception as exc:
        print(f"FAIL: isolated packaged health check: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
