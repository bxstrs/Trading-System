"""MT5 Order execution - handles sending and closing trades."""
import time
import MetaTrader5 as mt5
import uuid

from typing import Optional
from src.core.enums import Direction, ExecutionStatus
from src.core.types import TradeExecution
from src.infrastructure.logger.logger import log


class OrderExecutor:
    """Executes trades with retry logic and error handling."""

    def __init__(self, data_fetcher):
        self.data_fetcher = data_fetcher

    def send_order(self, symbol: str, direction: Direction, volume: float,
                   magic: int, comment: str = "forward_test",
                   max_retries: int = 3):
        
        tick = self.data_fetcher.get_tick(symbol)

        if direction == Direction.LONG:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        elif direction == Direction.SHORT:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            raise ValueError(f"Unsupported direction: {direction}")

        request = self._build_order_request(
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            price=price,
            magic=magic,
            comment=comment
        )

        # Retry logic with exponential backoff
        for attempt in range(1, max_retries + 1):
            try:
                result = mt5.order_send(request)

                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    log(f"Order success (attempt {attempt}): {result}", level="INFO")
                    return TradeExecution(
                            execution_id        = str(uuid.uuid4()),
                            setup_id            = None,
                            order               = result.order,
                            filled_entry_price  = result.price,
                            filled_volume       = result.volume,
                            filled_time         = None,
                            slippage            = None,
                            latency_ms          = None,
                            status              = ExecutionStatus.DONE,
                    )
                else:
                    error_msg = f"Order failed with retcode {result.retcode}: {getattr(result, 'comment', 'N/A')}"
                    log(error_msg, level="WARNING")

                    if attempt < max_retries:
                        # Exponential backoff: [0.5, 1.0, 2.0] seconds
                        backoff = 0.5 * (2 ** (attempt - 1))
                        log(f"Retrying order in {backoff}s (attempt {attempt}/{max_retries})...", level="INFO")
                        time.sleep(backoff)
                    else:
                        log(f"Order failed after {max_retries} attempts", level="ERROR")
                        return result

            except Exception as e:
                log(f"Order send exception (attempt {attempt}): {e}", level="ERROR")
                if attempt < max_retries:
                    backoff = 0.5 * (2 ** (attempt - 1))
                    log(f"Retrying order in {backoff}s (attempt {attempt}/{max_retries})...", level="INFO")
                    time.sleep(backoff)
                else:
                    return None

        return None

    def close_position(self, position):

        """Close an open position."""
        tick = self.data_fetcher.get_tick(position.symbol)

        if position.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid

        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask

        request = self._build_order_request(
            symbol=position.symbol,
            order_type=order_type,
            volume=position.volume,
            price=price,
            magic=position.magic,
            comment="close",
            position_ticket=position.ticket
        )

        return mt5.order_send(request)
    
    # ── Private helpers ───────────────────────────────────────────────────────────

    def _build_order_request(self, symbol: str, order_type: int, volume: float,
                            price: float, magic: int, comment: str,
                            position_ticket: Optional[int] = None) -> dict:
        """
        Build MT5 order request dict.
        Args:
            position_ticket: If closing a position, provide ticket number
        Returns:
            Order request dict ready for mt5.order_send()
        """
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 10,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if position_ticket is not None:
            request["position"] = position_ticket

        return request
