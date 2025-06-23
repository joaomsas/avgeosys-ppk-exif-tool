import pandas as pd
from avgeosys.trader.strategy import MovingAverageCrossoverStrategy


def test_moving_average_crossover():
    data = pd.DataFrame({"close": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
    strat = MovingAverageCrossoverStrategy(fast=3, slow=5)
    signals = strat.generate_signals(data)
    # After enough data points, fast MA should be above slow MA
    assert signals.iloc[-1] == 1
