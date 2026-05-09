from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Integer
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
    
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )