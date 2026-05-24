import math
from collections import deque
from typing import Tuple

from src.indicators.base import Indicator

class IncrementalVolatility(Indicator):
    
    def __init__(self, bb_period: int, bb_dev: float, atr_period: int):
        self.bb_period  = bb_period
        self.bb_dev     = bb_dev
        self.atr_period = atr_period
        
        # Rolling windows
        self.closes     = deque(maxlen=bb_period)
        self.tr_values  = deque(maxlen=atr_period)

        # Cached results
        self._bb_upper:     float | None = None
        self._bb_lower:     float | None = None
        self._bb_middle:    float | None = None
        self._atr:          float = 0.0

        # Previous values for signal generation
        self._prev_bb_upper:    float | None = None
        self._prev_bb_lower:    float | None = None
        self._prev_bb_middle:   float | None = None
        
        
    def update(
        self,
        close: float,
        high: float,
        low: float,
        prev_close: float
    ) -> None:

        # ===== BOLLINGER UPDATE =====
        self.closes.append(close)

        # ===== TRUE RANGE UPDATE =====
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )

        self.tr_values.append(tr)
        
        # ===== RECALCULATE =====
        self._recalculate()
    
    def _recalculate(self) -> None:
        """Recalculate BB and ATR without running sums (prevents drift)."""

        # ---- SHIFT CURRENT → PREVIOUS ----
        self._prev_bb_upper     = self._bb_upper
        self._prev_bb_lower     = self._bb_lower
        self._prev_bb_middle    = self._bb_middle

        # ---- Bollinger Bands (CURRENT) ----
        n = len(self.closes)
        if n < self.bb_period:
            self._bb_upper  = None
            self._bb_lower  = None
            self._bb_middle = None
        else:
            total       = sum(self.closes)
            total_sq    = sum(x * x for x in self.closes)
            mean        = total / n
            variance    = max((total_sq / n) - (mean * mean), 0.0)
            std         = math.sqrt(variance)

            self._bb_middle = mean
            self._bb_upper  = mean + self.bb_dev * std
            self._bb_lower  = mean - self.bb_dev * std

        # ---- ATR ----
        m = len(self.tr_values)
        self._atr = sum(self.tr_values) / m if m > 0 else 0.0
    
     # ===== GETTERS =====
    
    def get_bollinger_bands(self) -> Tuple[float | None, float | None, float | None]:
        return self._bb_upper, self._bb_lower, self._bb_middle

    def get_previous_bollinger_bands(self) -> Tuple[float | None, float | None, float | None]:
        return self._prev_bb_upper, self._prev_bb_lower, self._prev_bb_middle

    def get_atr(self) -> float:
        return self._atr

    def get_bandwidth(self) -> float:
        if (
            self._bb_middle is None
            or self._bb_upper is None
            or self._bb_lower is None
            or self._bb_middle == 0
        ):
            return 0.0
        return (self._bb_upper - self._bb_lower) / self._bb_middle

    def is_ready(self) -> bool:
        return len(self.closes) >= self.bb_period and len(self.tr_values) > 0

class BandwidthMACalculator(Indicator):
    def __init__(self, bw_ma_period: int = 150):
        self.bw_ma_period   = bw_ma_period
        self.values         = deque(maxlen=bw_ma_period)

    def update(self, value: float) -> None:
        self.values.append(value)

    def get_bandwidth_ma(self) -> float:
        if len(self.values) == 0:
            return 0.0
        return sum(self.values) / len(self.values)

    def is_ready(self) -> bool:
        return len(self.values) >= self.bw_ma_period