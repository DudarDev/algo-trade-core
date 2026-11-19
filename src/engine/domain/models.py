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
    
    # Feature Store & Journaling (Етап 1)
    regime: str = Field(default="CHOPPY_FLAT")
    ai_confidence: float = Field(default=0.0)
    features_snapshot: dict[str, float] = Field(default_factory=dict)
    
    # Scale-Out Engine (Partial Take Profit)
    partial_tp_hit: bool = Field(default=False)
    order_type: str = Field(default="MAKER")

    model_config = ConfigDict(strict=False, validate_assignment=True)

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


class DeltaNeutralMode(str, Enum):
    SPOT_PERP = "SPOT_PERP"
    SYNTHETIC_PERP_PERP = "SYNTHETIC_PERP_PERP"


class DeltaNeutralStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ROLLBACK = "ROLLBACK"


class DeltaNeutralPosition(BaseModel):
    position_id: str
    symbol: str
    mode: DeltaNeutralMode = DeltaNeutralMode.SPOT_PERP
    
    # Нога 1 (Spot Long або Bybit Perp Long)
    leg1_exchange: str
    leg1_symbol: str
    leg1_side: TradeSide = TradeSide.BUY
    leg1_entry_price: float = Field(..., gt=0)
    leg1_amount: float = Field(..., gt=0)
    
    # Нога 2 (Binance Perp Short)
    leg2_exchange: str
    leg2_symbol: str
    leg2_side: TradeSide = TradeSide.SELL
    leg2_entry_price: float = Field(..., gt=0)
    leg2_amount: float = Field(..., gt=0)
    
    notional_usdt: float = Field(..., gt=0)
    entry_basis_pct: float = Field(default=0.0)
    accrued_funding_usdt: float = Field(default=0.0)
    funding_cycles_collected: int = Field(default=0)
    entry_fees_usdt: float = Field(default=0.0)
    
    current_8h_rate: float = Field(default=0.0)
    projected_apy: float = Field(default=0.0)
    
    opened_at: float = Field(default_factory=time.time)
    last_funding_time: float = Field(default_factory=time.time)
    status: DeltaNeutralStatus = DeltaNeutralStatus.OPEN
    close_reason: str = Field(default="")

    @property
    def group_id(self) -> str:
        return self.position_id

    model_config = ConfigDict(strict=False, validate_assignment=True)
