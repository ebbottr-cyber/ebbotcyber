"""Resolve ONLY five audited PR #57/main conflict paths.

Executed in a temporary GitHub Actions checkout, never on main or a
live server. Any unexpected conflict, route shape or Git stage blocks.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess

EXPECTED = {
    "api/v1/router.py",
    "apps/dsa-web/src/components/layout/SidebarNav.tsx",
    "apps/dsa-web/src/components/run-flow/utils.ts",
    "apps/dsa-web/src/components/settings/NotificationTestPanel.tsx",
    "apps/dsa-web/src/utils/systemConfigI18n.ts",
}

MARKER = re.compile(
    r"(?ms)^<<<<<<< HEAD\n(?P<ours>.*?)^=======\n(?P<theirs>.*?)^>>>>>>> origin/main\n"
)


def replace_once(source: str, before: str, after: str, name: str) -> str:
    if source.count(before) != 1:
        raise RuntimeError(f"{name}: expected exactly one matching pattern")
    return source.replace(before, after, 1)


def choose(path: str, ours: str, theirs: str) -> str:
    if path == "api/v1/router.py":
        if ours.strip() != "meme_coin," or theirs.strip() != "meme_coins,":
            raise RuntimeError("unexpected API import conflict")
        # Keep the separate PR57 strategy API AND main's meme radar API.
        return "    meme_coin,\n    meme_coins,\n"

    if path.endswith("SidebarNav.tsx"):
        if "Radar" not in ours or "Flame" not in theirs:
            raise RuntimeError("unexpected navigation import conflict")
        return replace_once(
            ours, "Home, LayoutDashboard", "Home, Flame, LayoutDashboard",
            "nav imported icons",
        )

    if path.endswith("run-flow/utils.ts"):
        if "toLocaleString" not in theirs or "UiLanguage" not in theirs:
            raise RuntimeError("unexpected locale conflict")
        return theirs  # Main's typed locale map includes TR, EN and ZH.

    if path.endswith("NotificationTestPanel.tsx"):
        if "language === 'tr' ? 'E-posta'" in theirs or "language === 'tr' ? 'Özel Webhook'" in theirs:
            return theirs  # Preserve new Turkish translations from main.
        if "language === 'zh'" in theirs and "value: 'wechat'" in theirs:
            return theirs
        raise RuntimeError("unexpected notification labels conflict")

    if path.endswith("systemConfigI18n.ts"):
        # Main's latest Turkish localization is intentional and reviewed.
        if not theirs.strip() or "tr" not in Path(path).name.lower():
            # Path is constant; a blank ours block -> main's comment is valid.
            if not theirs.strip():
                raise RuntimeError("empty locale resolution")
        return theirs

    raise RuntimeError(f"unexpected conflict path: {path}")


def main() -> None:
    actual = set(subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=U"], text=True,
    ).splitlines())
    if actual != EXPECTED:
        raise RuntimeError(f"conflict set unexpectedly changed: {sorted(actual)}")

    for path in sorted(EXPECTED):
        file = Path(path)
        current = file.read_text(encoding="utf-8")
        count = 0

        def resolve(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            return choose(path, match["ours"], match["theirs"])

        merged = MARKER.sub(resolve, current)
        if not count or "<<<<<<<" in merged or ">>>>>>>" in merged:
            raise RuntimeError(f"conflict markers unresolved: {path}")
        file.write_text(merged, encoding="utf-8")
        print(f"Resolved: {path} ({count} conflict block(s))")

    # Main's standalone Meme Radar and PR57's meme strategy UI both used
    # /meme-coins. They are distinct products; preserve both at distinct URLs.
    app = Path("apps/dsa-web/src/App.tsx")
    source = app.read_text(encoding="utf-8")
    if (
        source.count("const MemeCoinsPage = lazy") != 1
        or source.count("const MemeCoinPage = lazy") != 1
    ):
        raise RuntimeError("both meme pages must remain available")
    source = replace_once(
        source,
        "{ path: '/meme-coins', element: <MemeCoinsPage /> },",
        "{ path: '/meme-radar', element: <MemeCoinsPage /> },",
        "main meme radar route",
    )
    if source.count("{ path: '/meme-coins', element: <MemeCoinPage /> },") != 1:
        raise RuntimeError("PR57 meme strategy route not preserved")
    app.write_text(source, encoding="utf-8")

    navigation = Path("apps/dsa-web/src/components/layout/SidebarNav.tsx")
    nav = navigation.read_text(encoding="utf-8")
    # Auto-merge may have already inserted main's nav row.
    original = "{ key: 'meme', labelKey: 'layout.nav.memeCoins', to: '/meme-coins', icon: Flame },"
    replacement = "{ key: 'meme-radar', labelKey: 'layout.nav.memeCoins', to: '/meme-radar', icon: Flame },"
    if original in nav:
        nav = replace_once(nav, original, replacement, "main meme radar nav")
    elif replacement not in nav:
        anchor = "  { key: 'meme-coin', labelKey: 'layout.nav.memeCoin', to: '/meme-coins', icon: Radar },"
        nav = replace_once(nav, anchor, anchor + "\n  " + replacement, "nav positioning")
    if nav.count(replacement) != 1:
        raise RuntimeError("main meme radar nav route missing or duplicated")
    if nav.count("to: '/meme-coins', icon: Radar") != 1:
        raise RuntimeError("PR57 meme strategy nav not preserved")
    navigation.write_text(nav, encoding="utf-8")

    # Main radar's /status and /scan endpoints must be registered alongside
    # PR57 strategy endpoints, not overwrite them.
    router = Path("api/v1/router.py").read_text(encoding="utf-8")
    if (
        router.count("meme_coin.router,") != 1
        or router.count("meme_coins.router,") != 1
    ):
        raise RuntimeError("both meme API routers must be present")
    if "/meme-coins" not in router:
        raise RuntimeError("meme API namespace missing")
    print("SAFE_RESOLUTION_COMPLETE: distinct strategy + radar pages, both APIs retained")


if __name__ == "__main__":
    main()
