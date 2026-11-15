# -*- coding: utf-8 -*-
"""P0 SQLite migration safety integrated with BIST100 historical screening.

All files are created under pytest tmp_path. The user's configured database,
network, paid models and execution gateways are never used.
"""
from datetime import date

import pandas as pd
from sqlalchemy import inspect

from src.config import Config
from src.storage import DatabaseManager, StockDaily
from src.services.bist100_screener import ReadOnlyStockDaily, screen_bist100_from_db
from src.stock_analyzer import StockTrendAnalyzer


def test_pr2_database_reinitialization_preserves_bist_history_and_ranking(tmp_path):
    db_path = tmp_path / "seven-market-compatibility.sqlite"
    url = f"sqlite:///{db_path}"
    sessions = pd.bdate_range(end="2026-11-13", periods=80)
    prices = pd.DataFrame({
        "date": [session.date() for session in sessions],
        "open": [100.0 + i * 0.25 for i in range(80)],
        "high": [103.0 + i * 0.25 for i in range(80)],
        "low": [98.0 + i * 0.25 for i in range(80)],
        "close": [101.0 + i * 0.25 for i in range(80)],
        "volume": [2000.0 + i * 15 for i in range(80)],
    })

    Config.reset_instance()
    DatabaseManager.reset_instance()
    try:
        manager = DatabaseManager(db_url=url)
        assert hasattr(manager, "_ensure_intelligence_items_secondary_indexes")
        assert manager.save_daily_data(
            prices, "THYAO.IS", "Yahoo Finance", canonical_id="THYAO.IS"
        ) == 80
        stored = manager.get_data_range("THYAO.IS", date(2026, 1, 1), date(2026, 11, 13))
        assert len(stored) == 80
        assert all(row.canonical_id == "THYAO.IS" for row in stored)
        assert all(row.data_source == "Yahoo Finance" for row in stored)

        # A P0 safe-repair startup must never rewrite, duplicate or drop
        # existing historical prices while repairing unrelated indexes.
        before = [(row.id, row.code, row.date, row.close) for row in stored]
        DatabaseManager.reset_instance()
        after_manager = DatabaseManager(db_url=url)
        after = [
            (row.id, row.code, row.date, row.close)
            for row in after_manager.get_data_range(
                "THYAO.IS", date(2026, 1, 1), date(2026, 11, 13)
            )
        ]
        assert before == after
        indexes = {idx["name"] for idx in inspect(after_manager._engine).get_indexes("intelligence_items")}
        assert {"ix_intel_item_scope_time", "ix_intel_item_fetch_time"}.issubset(indexes)

        with ReadOnlyStockDaily(db_path) as reader:
            raw = reader.get_data_range(
                "THYAO.IS", date(2026, 1, 1), date(2026, 11, 13)
            )
        assert len(raw) == 80
        assert raw[-1]["date"] == "2026-11-13"

        ranking = screen_bist100_from_db(
            as_of=date(2026, 11, 15),
            symbols=("THYAO.IS",),
            db_path=db_path,
            last_session=date(2026, 11, 13),
            analyze=StockTrendAnalyzer().analyze,
        )
        assert ranking["checked"] == ranking["analyzed"] == 1
        assert ranking["status_counts"] == {"analyzed": 1}
        assert ranking["ranking"][0]["symbol"] == "THYAO.IS"
        assert 0 <= ranking["ranking"][0]["score"] <= 100
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
