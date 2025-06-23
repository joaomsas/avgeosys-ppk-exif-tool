from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskParameters:
    max_daily_loss: float = 100.0
    risk_per_trade: float = 0.01  # fraction of capital


class RiskManager:
    def __init__(self, params: RiskParameters) -> None:
        self.params = params
        self.daily_loss = 0.0

    def can_trade(self, capital: float) -> bool:
        return self.daily_loss < self.params.max_daily_loss and capital > 0

    def update_loss(self, trade_result: float) -> None:
        self.daily_loss += max(-trade_result, 0)
