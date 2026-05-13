"""MT5 Position queries - handles position and deal lookups."""
import MetaTrader5 as mt5
from datetime import datetime, timezone

from src.core.enums import Direction
from src.core.types import Position
from src.infrastructure.logger.logger import log


class PositionRepository:
    """Queries and retrieves position/deal information."""

    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    def get_positions(self, symbol: str):
        """Fetch all open positions for a symbol."""
        if not self.connection_manager.ensure_connected():
            raise ConnectionError("Not connected to MT5")

        raw_position = mt5.position_get(symbol=symbol)
        direction = (
            Direction.LONG
            if raw_position.type == mt5.POSITION_TYPE_BUY
            else Direction.SHORT
        )
        
        return Position(
            ticket      =raw_position.ticket,
            time        =datetime.fromtimestamp(raw_position.time, tz=timezone.utc),
            symbol      =raw_position.symbol,
            direction   =direction,
            volume      =raw_position.volumn,
            sl          =raw_position.sl,
            tp          =raw_position.tp,
            open_price  =raw_position.price_open,
        )

    def history_deals_get(self, ticket):
        """Fetch deal history for a position ticket."""
        if not self.connection_manager.ensure_connected():
            raise ConnectionError("Not connected to MT5")
        
        return mt5.history_deals_get(ticket=ticket)
