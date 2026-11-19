from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Float, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from src.shared.db.session import Base

class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(10))  # "BUY" або "SELL"
    price: Mapped[float] = mapped_column(Float)
    amount: Mapped[float] = mapped_column(Float)
    cost: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    
    # --- Feature Store & Trade Journaling (Етап 1) ---
    exit_reason: Mapped[str] = mapped_column(String(50), default="UNKNOWN")
    regime: Mapped[str] = mapped_column(String(30), default="CHOPPY_FLAT")
    ai_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    target_label: Mapped[int] = mapped_column(Integer, default=0)  # 1 = Win/TP, 0 = Loss/SL
    features_json: Mapped[str] = mapped_column(Text, default="{}")  # Повний зріз квант-індикаторів на момент входу

    # Використовуємо UTC timezone-aware datetime
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

class Wallet(Base):
    __tablename__ = "wallet"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    usdt_balance: Mapped[float] = mapped_column(Float)

class ActivePosition(Base):
    __tablename__ = "active_positions"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    amount: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    highest_price: Mapped[float] = mapped_column(Float)
    cost: Mapped[float] = mapped_column(Float)
    
    # --- Feature Store: Зріз ринку при вході в активну позицію ---
    regime: Mapped[str] = mapped_column(String(30), default="CHOPPY_FLAT")
    ai_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    features_json: Mapped[str] = mapped_column(Text, default="{}")
    partial_tp_hit: Mapped[int] = mapped_column(Integer, default=0)
    
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

class BotConfig(Base):
    __tablename__ = "bot_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

class DeltaNeutralPositionModel(Base):
    __tablename__ = "delta_neutral_positions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    mode: Mapped[str] = mapped_column(String(30), default="SPOT_PERP")
    
    # Нога 1
    leg1_exchange: Mapped[str] = mapped_column(String(20))
    leg1_symbol: Mapped[str] = mapped_column(String(30))
    leg1_side: Mapped[str] = mapped_column(String(10), default="BUY")
    leg1_entry_price: Mapped[float] = mapped_column(Float)
    leg1_amount: Mapped[float] = mapped_column(Float)
    
    # Нога 2
    leg2_exchange: Mapped[str] = mapped_column(String(20))
    leg2_symbol: Mapped[str] = mapped_column(String(30))
    leg2_side: Mapped[str] = mapped_column(String(10), default="SELL")
    leg2_entry_price: Mapped[float] = mapped_column(Float)
    leg2_amount: Mapped[float] = mapped_column(Float)
    
    notional_usdt: Mapped[float] = mapped_column(Float)
    entry_basis_pct: Mapped[float] = mapped_column(Float, default=0.0)
    accrued_funding_usdt: Mapped[float] = mapped_column(Float, default=0.0)
    funding_cycles_collected: Mapped[int] = mapped_column(Integer, default=0)
    entry_fees_usdt: Mapped[float] = mapped_column(Float, default=0.0)
    
    current_8h_rate: Mapped[float] = mapped_column(Float, default=0.0)
    projected_apy: Mapped[float] = mapped_column(Float, default=0.0)
    
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    close_reason: Mapped[str] = mapped_column(String(100), default="")
    
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_funding_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    @property
    def group_id(self) -> str:
        return self.id

    @property
    def futures_entry_price(self) -> float:
        return self.leg2_entry_price

    @property
    def notional_value_usdt(self) -> float:
        return self.notional_usdt

    @property
    def quantity(self) -> float:
        return self.leg2_amount

