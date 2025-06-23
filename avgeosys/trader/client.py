from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

from alpaca_trade_api.rest import REST, TimeFrame


@dataclass
class AlpacaClient:
    api_key: str
    api_secret: str
    base_url: str = "https://paper-api.alpaca.markets"

    def __post_init__(self) -> None:
        self._rest = REST(self.api_key, self.api_secret, self.base_url)

    @classmethod
    def from_env(cls) -> "AlpacaClient":
        return cls(
            api_key=os.environ.get("ALPACA_API_KEY", ""),
            api_secret=os.environ.get("ALPACA_API_SECRET", ""),
            base_url=os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
        )

    def get_bars(self, symbol: str, timeframe: TimeFrame, limit: int = 100):
        return self._rest.get_bars(symbol, timeframe, limit=limit).df

    def submit_order(self, **order: Any) -> Dict[str, Any]:
        return self._rest.submit_order(**order)
