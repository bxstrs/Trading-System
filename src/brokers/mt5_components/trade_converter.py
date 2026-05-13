'''src/domain/trade_converter.py'''
import MetaTrader5 as mt5

from src.core.enums import  Direction, TradeStatus
from src.core.types import TradeResult
from datetime import datetime, timezone



def mt5_position_to_trade_result(
    pos,
    setup_id: str | None,
    execution_id: str | None,
    entry_slippage: float = 0.0,
    entry_latency_ms: float = 0.0
) -> TradeResult:
    required_attrs = ['ticket', 'type', 'symbol', 'price_open', 'volume', 'profit', 'time']

    for attr in required_attrs:
        if not hasattr(pos, attr):
            raise ValueError(f"Position missing required attribute: {attr}")
        
    direction = (
        Direction.LONG
        if pos.type == mt5.POSITION_TYPE_BUY
        else Direction.SHORT
    )

    return TradeResult(
        trade_id            =str(pos.ticket),
        setup_id            =setup_id,
        execution_id        =execution_id,
        symbol              =pos.symbol,
        direction           =direction,
        entry_price         =pos.price_open,
        volume              =pos.volume,
        entry_time          =datetime.fromtimestamp(pos.time, tz=timezone.utc),
        entry_slippage      =entry_slippage,
        entry_latency_ms    =entry_latency_ms,
        exit_price          =None,
        exit_time           =None,
        exit_bid            =None,
        exit_ask            =None,
        net_pnl             =pos.profit,
        status              =TradeStatus.PENDING
    )