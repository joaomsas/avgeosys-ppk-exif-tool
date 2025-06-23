from __future__ import annotations

from datetime import datetime
from typing import List

import pandas as pd
from alpaca_trade_api.rest import TimeFrame

from .client import AlpacaClient


class MarketDataCollector:
    def __init__(self, client: AlpacaClient, symbol: str = "SPY", timeframe: TimeFrame = TimeFrame.Minute) -> None:
        self.client = client
        self.symbol = symbol
        self.timeframe = timeframe

    def get_recent_data(self, limit: int = 100) -> pd.DataFrame:
        """Fetch recent market data for the configured symbol."""
        bars = self.client.get_bars(self.symbol, self.timeframe, limit=limit)
        bars.index = pd.to_datetime(bars.index)
        return bars
