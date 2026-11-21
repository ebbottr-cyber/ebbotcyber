"""Conservative, source-labelled Turkish market summary response."""
from typing import Literal

from pydantic import BaseModel, Field


class TurkishMarketItem(BaseModel):
    key: Literal["bist100", "bist30", "usdtry", "eurtry", "gramgold"]
    label: str
    symbol: str | None = None
    currency: str
    price: float | None = Field(default=None, gt=0)
    change_pct: float | None = None
    as_of: str | None = None
    status: Literal["ready", "stale", "unavailable"]
    source: str | None = None
    note: str


class TurkishMarketOverviewResponse(BaseModel):
    as_of: str
    cadence: Literal["delayed_daily"]
    items: list[TurkishMarketItem]
