#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EBBot Windows source/desktop preflight, deliberately read-only.

No database, .env, secrets, orders, scheduler, installations or file writes.
Network is disabled by default. With --origin, ONLY local HTTP GET requests
are permitted. A passing result is NOT permission to trade or deploy.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_SOURCE_FILES = (
    "apps/dsa-web/index.html",
    "apps/dsa-web/package.json",
    "apps/dsa-web/src/pages/PortfolioPage.tsx",
    "apps/dsa-desktop/main.js",
    "apps/dsa-desktop/package.json",
    "api/app.py",
    "api/v1/endpoints/portfolio.py",
    "src/services/portfolio_historical_fx.py",
    "src/services/portfolio_display_fx.py",
)
ASSET_PATTERN = re.compile(r"""(?:src|href)=["'](/assets/[^"']+)["']""")
MAX_RESPONSE_BYTES = 65_536


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # "ok", "warning", "blocked"
    detail: str


def safe_origin(raw: str) -> str:
    """Only a local, origin-only, unauthenticated HTTP URL is permitted."""
    parsed = parse.urlsplit(raw)
    if parsed.scheme != "http" or parsed.username or parsed.password:
        raise ValueError("Yalnızca şifresiz yerel http:// adresi kabul edilir.")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Adreste yol, sorgu veya # parçası bulunmamalı.")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Yerel sunucu adı eksik.")
    if hostname.lower() != "localhost":
        try:
            if not ipaddress.ip_address(hostname).is_loopback:
                raise ValueError("Uzak veya yerel ağ sunucularına erişim yasak.")
        except ValueError as exc:
            raise ValueError("Yalnızca localhost veya 127.0.0.1 kullanılabilir.") from exc
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Geçersiz port.") from exc
    if port is None or not 1 <= port <= 65535:
        raise ValueError("Seçili masaüstü portunu açıkça girin (8000-8100).")
    if not 8000 <= port <= 8100:
        raise ValueError("Masaüstü portu yalnızca 8000-8100 aralığında olabilir.")
    return f"http://{parsed.netloc}"


def _node_version() -> tuple[int, int, int] | None:
    if shutil.which("node") is None:
        return None
    try:
        result = subprocess.run(
            ["node", "--version"], check=False, text=True,
            capture_output=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", result.stdout.strip())
        return tuple(map(int, match.groups())) if match else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def check_sources(root: Path = ROOT) -> list[Check]:
    """Never load user configuration or the portfolio database."""
    missing = [path for path in REQUIRED_SOURCE_FILES if not (root / path).is_file()]
    checks = [
        Check(
            "source_files", "blocked" if missing else "ok",
            "Eksik kaynak dosyası: " + ", ".join(missing) if missing else
            "Portföy, Electron ve FX kaynak girişleri mevcut.",
        ),
        Check(
            "python", "ok" if sys.version_info >= (3, 10) else "blocked",
            "Python 3.10+ gerekli." if sys.version_info < (3, 10) else
            "Python sürümü uygun.",
        ),
    ]
    node = _node_version()
    checks.append(Check(
        "node", "ok" if node is not None and node >= (20, 19, 0) else "blocked",
        "Node.js >=20.19.0 hazır." if node is not None and node >= (20, 19, 0)
        else "Node.js >=20.19.0 gerekli; node --version ile kontrol edin.",
    ))
    return checks


def check_frontend_bundle(root: Path = ROOT) -> list[Check]:
    """Verify index/assets consistency without building or touching files."""
    static = root / "static"
    index = static / "index.html"
    if not index.is_file():
        return [Check(
            "built_frontend", "blocked",
            "static/index.html yok. Önce apps/dsa-web altında npm ci ve npm run build çalıştırın.",
        )]
    try:
        html = index.read_text(encoding="utf-8", errors="replace")
        refs = ASSET_PATTERN.findall(html)
    except OSError:
        return [Check("built_frontend", "blocked", "Derlenmiş arayüz okunamadı.")]
    if not refs:
        return [Check("built_frontend", "blocked", "HTML içinde Vite /assets referansı bulunamadı.")]
    if any(
        ".." in Path(ref).parts or not (static / ref.lstrip("/")).is_file()
        for ref in refs
    ):
        return [Check("built_frontend", "blocked", "index.html dosyasında bulunamayan veya güvensiz /assets referansı var.")]
    return [Check("built_frontend", "ok", f"Derlenmiş arayüzün {len(refs)} JS/CSS referansı doğrulandı.")]


class _RejectRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise error.HTTPError(req.full_url, code, "redirect forbidden", headers, fp)


def local_get(origin: str, path: str) -> tuple[int, str, bytes]:
    """Make a bounded GET with proxies, redirects, credentials and POST disabled."""
    if not path.startswith("/") or "//" in path:
        raise ValueError("Invalid endpoint path")
    opener = request.build_opener(request.ProxyHandler({}), _RejectRedirect())
    req = request.Request(
        origin + path,
        method="GET",
        headers={"Accept": "application/json, text/html"},
    )
    with opener.open(req, timeout=4) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("Yanıt boyutu beklenen sınırı aştı.")
        return response.status, response.headers.get("Content-Type", ""), raw


Fetch = Callable[[str, str], tuple[int, str, bytes]]


def probe_local(
    origin: str,
    *,
    check_display_fx: bool = False,
    fetch: Fetch = local_get,
    now: datetime | None = None,
) -> list[Check]:
    """Check local backend and UI; optional FX display is observational only."""
    checks: list[Check] = []
    try:
        status, content_type, data = fetch(origin, "/api/health")
        payload = json.loads(data) if status == 200 and "json" in content_type.lower() else None
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            raise ValueError("Beklenen sağlık durumu alınamadı.")
        checks.append(Check("backend_health", "ok", "Yerel EBBot /api/health doğrulandı."))
    except (OSError, ValueError, error.URLError, json.JSONDecodeError, TimeoutError):
        checks.append(Check("backend_health", "blocked", "Yerel backend yanıt vermiyor veya sağlık biçimi geçersiz."))

    try:
        status, content_type, data = fetch(origin, "/")
        html = data.decode("utf-8", errors="replace") if status == 200 and "html" in content_type.lower() else ""
        if not re.search(r"""id\s*=\s*["']root["']""", html):
            raise ValueError("Derlenmiş React kökü yok.")
        if "/assets/" not in html:
            raise ValueError("Derlenmiş JS/CSS referansları yok.")
        checks.append(Check("frontend_http", "ok", "Yerel React arayüzü ve derlenmiş varlık referansları mevcut."))
    except (OSError, ValueError, error.URLError, TimeoutError):
        checks.append(Check("frontend_http", "blocked", "Yerel arayüz yok veya 'Frontend Not Built' sayfası dönüyor."))

    if check_display_fx:
        try:
            status, ctype, body = fetch(origin, "/api/v1/portfolio/fx/display-rates")
            payload = json.loads(body) if status == 200 and "json" in ctype.lower() else None
            if not isinstance(payload, dict) or not isinstance(payload.get("pair_status"), dict):
                raise ValueError("Kur çiftlerinin durumu doğrulanamadı.")
            instant = now or datetime.now(timezone.utc)
            usable = 0
            for code in ("usd", "cny", "hkd", "jpy", "krw", "twd"):
                state = payload["pair_status"].get(code)
                if state not in ("current", "stale", "unavailable"):
                    raise ValueError("Geçersiz kur durum etiketi.")
                if state != "current":
                    continue
                timestamp = payload.get("pair_as_of", {}).get(code)
                if not isinstance(timestamp, str):
                    raise ValueError("Güncel etiketli kurun kaynak zamanı yok.")
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError("Kur kaynak zamanında saat dilimi yok.")
                age_seconds = (instant - parsed.astimezone(timezone.utc)).total_seconds()
                field = "usd_try" if code == "usd" else f"{code}_try"
                value = payload.get(field)
                if not (isinstance(value, (int, float)) and not isinstance(value, bool)
                        and 0 < value < float("inf") and 0 <= age_seconds <= 1800):
                    raise ValueError("Güncel etiketli kur eski, gelecekte veya geçersiz.")
                usable += 1
            checks.append(Check(
                "display_fx", "ok" if usable == 6 else "warning",
                f"{usable}/6 gösterim kuru doğrulandı. Eksik/eski kurlar risk işlemi için uygun değildir.",
            ))
        except (OSError, ValueError, TypeError, error.URLError, json.JSONDecodeError, TimeoutError):
            checks.append(Check(
                "display_fx", "warning",
                "Gösterim kur servisi doğrulanamadı; TL gösterimi ve finansal veri lisansı ayrıca incelenmeli.",
            ))
    return checks


def summary(checks: list[Check]) -> str:
    if any(check.status == "blocked" for check in checks):
        return "BLOCKED"
    if any(check.status == "warning" for check in checks):
        return "NOT_VERIFIED"
    return "PASSED_READ_ONLY"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="EBBot salt-okunur Windows portföy hazırlık kontrolü. İşlem veya kurulum yapmaz.",
    )
    parser.add_argument("--mode", choices=("source", "desktop"), default="source")
    parser.add_argument("--origin", help="Açıkça seçilmiş yerel adres, örn. http://127.0.0.1:8000")
    parser.add_argument("--check-display-fx", action="store_true",
                        help="Yerel FX ekran GET uç noktasını da gözlemle; Yahoo ağına çıkabilir.")
    parser.add_argument("--json", action="store_true", help="Sır içermeyen denetim özeti")
    args = parser.parse_args(argv)
    if args.check_display_fx and not args.origin:
        parser.error("--check-display-fx için --origin gerekli.")
    if args.mode == "desktop" and not args.origin:
        parser.error("Masaüstü doğrulaması için seçili port ile --origin gerekli.")
    try:
        origin = safe_origin(args.origin) if args.origin else None
    except ValueError as exc:
        parser.error(str(exc))

    checks = check_sources()
    if args.mode == "desktop":
        checks += check_frontend_bundle()
    if origin:
        checks += probe_local(origin, check_display_fx=args.check_display_fx)
    result = summary(checks)
    output = {
        "mode": args.mode,
        "result": result,
        "can_trade": False,
        "can_deploy": False,
        "checks": [asdict(check) for check in checks],
    }
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"EBBot Windows ön kontrol: {result}")
        for check in checks:
            print(f"[{check.status.upper()}] {check.name}: {check.detail}")
        print("Bu denetim emir, veritabanı, kur kaydı veya dağıtım yapmaz.")
    return 2 if result == "BLOCKED" else 1 if result == "NOT_VERIFIED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
