from src.infrastructure.logger.logger import log

def heartbeat_logger(counter, tick, current_bar_time=None):

    if counter % 100 != 0:
        return

    if current_bar_time:
        log(
            f"[TICK {counter}] Bar: {current_bar_time}, "
            f"Bid: {tick.bid:.5f}, Ask: {tick.ask:.5f}",
            level="INFO",
        )
    else:
        log(
            f"[TICK {counter}] "
            f"Bid: {tick.bid:.5f}, Ask: {tick.ask:.5f}",
            level="INFO",
        )