from typing import List, Optional
from .session import SessionLocal
from .models import ActivePosition, Wallet, Trade

class TradingRepository:
    def __init__(self, session=None):
        pass # Ми керуємо сесіями через context manager

    def load_balance(self, default_balance: float = 1000.0) -> float:
        with SessionLocal() as session:
            wallet = session.query(Wallet).first()
            if wallet:
                return wallet.usdt_balance
            
            # Якщо гаманця немає - створюємо!
            new_wallet = Wallet(usdt_balance=default_balance)
            session.add(new_wallet)
            session.commit()
            return default_balance

    def save_balance(self, balance: float) -> None:
        with SessionLocal() as session:
            wallet = session.query(Wallet).first()
            if wallet:
                wallet.usdt_balance = balance
            else:
                wallet = Wallet(usdt_balance=balance)
                session.add(wallet)
            session.commit()

    def get_all_positions(self) -> List[ActivePosition]:
        with SessionLocal() as session:
            return session.query(ActivePosition).all()

    def save_position(self, symbol: str, amount: float, entry_price: float, highest_price: float, cost: float) -> None:
        with SessionLocal() as session:
            pos = ActivePosition(
                symbol=symbol,
                amount=amount,
                entry_price=entry_price,
                highest_price=highest_price,
                cost=cost
            )
            session.add(pos)
            session.commit()

    def update_position_high(self, symbol: str, highest_price: float) -> None:
        with SessionLocal() as session:
            pos = session.query(ActivePosition).filter_by(symbol=symbol).first()
            if pos:
                pos.highest_price = highest_price
                session.commit()

    def delete_position(self, symbol: str) -> None:
        with SessionLocal() as session:
            session.query(ActivePosition).filter_by(symbol=symbol).delete()
            session.commit()

    def log_trade(self, symbol: str, side: str, price: float, amount: float, cost: float, pnl: float) -> None:
        with SessionLocal() as session:
            trade = Trade(
                symbol=symbol,
                side=side,
                price=price,
                amount=amount,
                cost=cost,
                pnl=pnl
            )
            session.add(trade)
            session.commit()
