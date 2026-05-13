from enum import Enum

class Direction(str, Enum):
    """Trade direction enumeration."""
    LONG = "LONG"
    SHORT = "SHORT"


class OrderType(str, Enum):
    """Order type enumeration."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
# Haven't been used yet -> multistrat maybe

class TradeStatus(str, Enum):
    """Trade status enumeration."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    FAILED = "FAILED"
    PENDING = "PENDING"


class ExecutionStatus(str, Enum):
    DONE = "DONE"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    REQUOTE = "REQUOTE"


class PredictionDecision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    
