from src.domain.market_data import History
from src.infrastructure.logger.logger import log


def warmup_strategy(strategy, history: History) -> None:

    closes      = history.close
    highs       = history.high
    lows        = history.low
    opens       = history.open
    time_unix   = history.time_unix
    tick_volume = history.tick_volume
    n           = len(closes)

    log(f"[WARMUP] Warming up strategy with {n} bars...", level="INFO")

    # ── Prefer incremental path (O(n) total) ──────────────────────────
    if hasattr(strategy, "update_indicators_incremental"):
        for i in range(1, n):
            strategy.update_indicators_incremental(
                close      = closes[i],
                high       = highs[i],
                low        = lows[i],
                open_      = opens[i],
                prev_close = closes[i - 1],
                time_unix  = time_unix[i],
                tick_volume= tick_volume[i],
            )

    # ── Fallback: original O(n²) slice path ───────────────────────────
    # Kept for strategies that haven't implemented update_indicators_incremental. Will produce a deprecation warning in logs.
    else:
        log(
            f"[WARMUP] Strategy '{strategy.__class__.__name__}' does not implement "
            f"update_indicators_incremental() — falling back to O(n²) slice warmup. "
            f"Implement update_indicators_incremental() to fix startup performance.",
            level="WARNING",
        )
        for i in range(1, n):
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

    # ── Set bar time so live loop doesn't double-update on first tick ──
    if time_unix:
        strategy._current_bar_time = time_unix[-1]

    log(f"[WARMUP] Strategy warmup complete ({n} bars processed)", level="INFO")