"""src/engine/components/warmup.py"""
from src.domain.market_data import History
from src.infrastructure.logger.logger import log
 
 
def warmup_strategy(strategy, history: History) -> None:

    closes      = history.close
    highs       = history.high
    lows        = history.low
    opens       = history.open
    time_unix   = history.time_unix
    tick_volume = history.tick_volume
 
    log(f"Warming up strategy with {len(closes)} bars...", level="INFO")
 
    for i in range(1, len(closes)):
        sub_history = History(
            symbol      = history.symbol,
            timeframe   = history.timeframe,
            close       = closes[: i + 1],
            high        = highs[: i + 1],
            low         = lows[: i + 1],
            open        = opens[: i + 1],
            time_unix   = time_unix[: i + 1],
            tick_volume = tick_volume[: i + 1],
        )
        if hasattr(strategy, "update_indicators"):
            strategy.update_indicators(sub_history)
 
    if time_unix:
        strategy._current_bar_time = time_unix[-1]
 
    log("Strategy warmup complete.", level="INFO")