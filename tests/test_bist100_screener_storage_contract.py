# -*- coding: utf-8 -*-
"""SQLite storage contract: read-only screener consumes the actual StockDaily ORM schema.

Tests use an isolated temporary database, not the user's configured database,
and never initialize DatabaseManager or run its schema migrations.
"""
from datetime import date

import pandas as pd
import sqlite3
from sqlalchemy import create_engine

from src.storage import StockDaily
from src.services.bist100_screener import ReadOnlyStockDaily, screen_bist100_from_db
from src.stock_analyzer import StockTrendAnalyzer


def test_read_only_screener_handles_real_stockdaily_orm_schema(tmp_path):
    location = tmp_path / "isolated-stockdaily.db"
    engine = create_engine(f"sqlite:///{location}")
    try:
        # The existing canonical SQLAlchemy StockDaily model defines the table,
        # not an ad hoc duplicate schema. No global DB service is instantiated.
        StockDaily.__table__.create(engine)
        sessions = pd.bdate_range(end="2026-11-13", periods=80)
        with engine.begin() as connection:
            connection.execute(
                StockDaily.__table__.insert(),
                [
                    {
                        "code": "THYAO.IS",
                        "canonical_id": "THYAO.IS",
                        "data_source": "Yahoo Finance",
                        "date": day.date(),
                        "open": 100.0 + i * 0.1,
                        "high": 103.0 + i * 0.1,
                        "low": 98.0 + i * 0.1,
                        "close": 101.0 + i * 0.1,
                        "volume": 1500.0 + i * 10.0,
                    }
                    for i, day in enumerate(sessions)
                ],
            )
    finally:
        engine.dispose()

    with ReadOnlyStockDaily(location) as read_only:
        rows = read_only.get_data_range(
            "THYAO.IS", date(2026, 1, 1), date(2026, 11, 13)
        )
        assert len(rows) == 80
        assert rows[-1]["date"] == "2026-11-13"
        assert rows[-1]["data_source"] == "Yahoo Finance"
        assert rows[-1]["canonical_id"] == "THYAO.IS"
        try:
            read_only.connection.execute("DELETE FROM stock_daily")
        except sqlite3.OperationalError:
            pass
        else:
            raise AssertionError("Read-only StockDaily handle unexpectedly allowed DELETE")

    report = screen_bist100_from_db(
        as_of=date(2026, 11, 15),
        symbols=("THYAO.IS",),
        db_path=location,
        last_session=date(2026, 11, 13),
        analyze=StockTrendAnalyzer().analyze,
    )
    assert report["checked"] == 1
    assert report["analyzed"] == 1
    assert report["status_counts"] == {"analyzed": 1}
    assert report["ranking"][0]["symbol"] == "THYAO.IS"
    assert report["ranking"][0]["bars"] == 80
    assert report["ranking"][0]["rank"] == 1
    assert 0 <= report["ranking"][0]["score"] <= 100

    with sqlite3.connect(location) as connection:
        assert connection.execute("SELECT COUNT(*) FROM stock_daily").fetchone()[0] == 80
