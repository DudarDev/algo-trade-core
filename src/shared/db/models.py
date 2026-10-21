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
    
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )