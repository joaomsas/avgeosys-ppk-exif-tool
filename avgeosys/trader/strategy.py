from __future__ import annotations

import pandas as pd



class MovingAverageCrossoverStrategy:
    """Simple moving average crossover."""

    def __init__(self, fast: int = 10, slow: int = 30) -> None:
        self.fast = fast
        self.slow = slow

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        df = df.copy()
        df["fast_ma"] = df["close"].rolling(window=self.fast).mean()
        df["slow_ma"] = df["close"].rolling(window=self.slow).mean()
        df["signal"] = 0
        df.loc[df["fast_ma"] > df["slow_ma"], "signal"] = 1
        df.loc[df["fast_ma"] < df["slow_ma"], "signal"] = -1
        return df["signal"]
