# -*- coding: utf-8 -*-
"""Optional read-only live provider probe, not a risk or trading-data feed.

Run on a networked machine with yfinance installed:
    python scripts/probe_portfolio_try_fx_live.py

Exit code 0 means all configured currencies have independently validated
intraday cross quotes. 1 means missing/stale/skewed quote evidence, including
during market closures; this does NOT signal an internal test failure.
"""
from __future__ import annotations

import sys
from src.services.portfolio_display_fx import CROSS_CURRENCIES, get_try_display_rates


def main() -> int:
    data = get_try_display_rates()
    print("Kaynak:", data["source"])
    print("Kur kontrolleri: azami yas 30 dk, USD karsilastirma farki 15 dk")
    statuses = data["pair_status"]
    valid = True
    for currency in ("USD", *CROSS_CURRENCIES):
        key = currency.lower()
        status = statuses.get(key, "unavailable")
        try_value = data.get("usd_try" if currency == "USD" else f"{key}_try")
        as_of = data["pair_as_of"].get(key, "—")
        print(f"{currency}/TRY: durum={status}; kur={try_value if try_value is not None else '—'}; zaman={as_of}")
        if status != "current" or try_value is None or not as_of or as_of == "—":
            valid = False
    print("Sonuc:", "GUNCEL" if valid else "DOGRULANAMADI — eski/eksik kurla degerleme yapmayin")
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
