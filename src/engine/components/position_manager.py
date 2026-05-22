'''src/engine/components/position_manager.py'''
import ast
from datetime import datetime

from src.domain.enums import Direction
from src.domain.market_data import TickData
from src.domain.trading import Position
from src.infrastructure.logger.logger import log
from src.infrastructure.logger.data_logger import DataLogger


class PositionManager:
    def __init__(self, bridge, datalogger: DataLogger | None = None):

        self.bridge = bridge
        self.datalogger = datalogger or DataLogger()

        self._position_metadata: dict[int, dict] = {}

    # ------------------------------------------------------------------
    # Position Queries
    # ------------------------------------------------------------------

    def get_strategy_positions(self, symbol: str, strategy_id: str) -> list[Position]:

        positions = self.bridge.get_positions(symbol)

        if not positions:
            return []
        
        result = []

        for pos in positions:
            if pos.comment != str(strategy_id):
                continue
            result.append(pos)
        log(f"[POSITION] {len(result)} position(s) matched strategy_id='{strategy_id}'", level="DEBUG")

        return result
    

    def export_metadata(self):
        return dict(self._position_metadata)
    

    def load_metadata(self, metadata: dict) -> None:

        if not metadata:
            self._position_metadata = {}
            return
            
        restored = {}

        for k, v in metadata.items():
            try:
                restored[int(k)] = v
            except (ValueError, TypeError) as e:
                log(f"[RECOVERY] Bad metadata key '{k}': {e}", level="ERROR")
        self._position_metadata = restored
        log(f"[RECOVERY] Restored metadata for {len(restored)} positions", level="INFO")


    def remove_metadata(self, ticket: int):
        key = int(ticket)
        if key in self._position_metadata:
            del self._position_metadata[key]
            log(f"[META] Removed metadata for ticket={ticket}", level="DEBUG")


    def ensure_metadata(self, pos) -> None:
        key = int(pos.ticket)
        if key not in self._position_metadata:
            log(f"[META] Creating placeholder for ticket={pos.ticket}", level="WARNING")
            self._position_metadata[key] = {
                'setup_id':   None,
                'entry_price': pos.open_price,
                'mae':        0.0,
                'mfe':        0.0,
                'recovered':  True,
            }

    def reconcile(self, mt5_positions, checkpoint_data, position_storage):
        if not checkpoint_data:
            return

        result = position_storage.check_positions(mt5_positions, checkpoint_data)

        for ticket in result["closed"]:
            self.remove_metadata(ticket)

        mt5_map = {int(p.ticket): p for p in mt5_positions}
        for ticket in result["new"]:
            pos = mt5_map.get(ticket)
            if pos:
                self.ensure_metadata(pos)

    def has_open_position(self, symbol: str, strategy_id: str) -> bool:
        """Check if strategy has any open positions."""
        return len(self.get_strategy_positions(symbol, strategy_id)) > 0

    # ------------------------------------------------------------------
    # Position Lifecycle Tracking
    # ------------------------------------------------------------------

    def track_entry_position(
        self,
        position_ticket: int,
        setup_id: str,
        entry_slippage: float = 0.0,
        entry_latency_ms: float = 0.0,
    ) -> None:
        """Register position metadata when order fills."""
        metadata_key = self._build_position_key(position_ticket)

        self._position_metadata[metadata_key] = {
            'setup_id':         setup_id,
            'entry_slippage':   entry_slippage,
            'entry_latency_ms': entry_latency_ms,
            'entry_price':      None,
            'mae':              0.0,
            'mfe':              0.0,
        }

        log(f"[TRACKED] Position ticket={position_ticket} setup={setup_id}", level="DEBUG")

    # ------------------------------------------------------------------
    # MAE/MFE Tracking
    # ------------------------------------------------------------------

    def _update_mae_mfe(self, tick: TickData, pos: Position) -> None:

        key = int(pos.ticket)
        if key not in self._position_metadata:
            return
        
        meta        = self._position_metadata[key]
        entry_price = pos.open_price or meta.get('entry_fill_price')

        if entry_price is None:
            return
        
        mid_price = (tick.bid + tick.ask) / 2

        if pos.direction == Direction.LONG:
            adverse   = entry_price - mid_price
            favorable = mid_price   - entry_price
        else:
            adverse   = mid_price   - entry_price
            favorable = entry_price - mid_price

        meta['mae'] = max(meta.get('mae', 0.0), adverse)
        meta['mfe'] = max(meta.get('mfe', 0.0), favorable)

    # ── Private helpers ────────────────────────────────────────────────

    def _get_position_key(self, pos) -> int:
        return int(pos.ticket)

    def _build_position_key(self, ticket: int) -> int:
        return int(ticket)