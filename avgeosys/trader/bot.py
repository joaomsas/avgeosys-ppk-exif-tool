from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from alpaca_trade_api.rest import TimeFrame, REST

from .client import AlpacaClient
from .data import MarketDataCollector
from .strategy import MovingAverageCrossoverStrategy
from .risk import RiskManager, RiskParameters


logger = logging.getLogger(__name__)


class TradingBot:
    def __init__(self, client: AlpacaClient, capital: float = 10000.0) -> None:
        self.client = client
        self.data_collector = MarketDataCollector(client)
        self.strategy = MovingAverageCrossoverStrategy()
        self.risk = RiskManager(RiskParameters())
        self.capital = capital
        self.position = 0

    def run_cycle(self) -> Optional[dict]:
        if not self.risk.can_trade(self.capital):
            logger.info("Trading halted due to risk limits")
            return None

        data = self.data_collector.get_recent_data(limit=50)
        signal = self.strategy.generate_signals(data).iloc[-1]
        if signal == 1 and self.position <= 0:
            order = self._buy()
            return order
        elif signal == -1 and self.position >= 0:
            order = self._sell()
            return order
        return None

    def _buy(self) -> dict:
        qty = 1  # simplificado
        order = self.client.submit_order(symbol="SPY", qty=qty, side="buy", type="market", time_in_force="day")
        self.position += qty
        return order

    def _sell(self) -> dict:
        qty = 1
        order = self.client.submit_order(symbol="SPY", qty=qty, side="sell", type="market", time_in_force="day")
        self.position -= qty
        return order
