# src/domain/models.py
import time
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class Position(BaseModel):
    symbol: str
    side: TradeSide
    entry_price: float = Field(..., gt=0)
    amount_usdt: float = Field(..., gt=0)
    amount_coins: float = Field(..., gt=0)
    sl: float = Field(..., gt=0)
    tp: float = Field(..., gt=0)
    entry_time: float = Field(default_factory=time.time)
    highest_price: float = Field(default=0.0)

    model_config = ConfigDict(strict=True, validate_assignment=True)

class ArbitrageOpportunity(BaseModel):
    symbol: str
    buy_exchange: str
    buy_price: float = Field(..., gt=0)
    sell_exchange: str
    sell_price: float = Field(..., gt=0)
    gross_spread_pct: float
    net_spread_pct: float
    timestamp: float = Field(default_factory=time.time)

    model_config = ConfigDict(strict=True)