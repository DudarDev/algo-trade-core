import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from .models import Trade, Wallet, ActivePosition

logger = logging.getLogger(__name__)

class TradingRepository:
    def __init__(self, session: Session):
        self.session = session

    # ---------- Wallet ----------
    def get_wallet(self) -> Optional[Wallet]:
        try:
            return self.session.query(Wallet).first()
        except Exception as e:
            logger.error(f"Помилка отримання гаманця: {e}")
            return None

    def save_wallet(self, balance: float) -> Wallet:
        wallet = self.get_wallet()
        if wallet:
            wallet.usdt_balance = balance
        else:
            wallet = Wallet(usdt_balance=balance)
            self.session.add(wallet)
        self.session.commit()
        return wallet

    # ---------- Trade ----------
    def save_trade(self, trade_data: dict) -> Trade:
        trade = Trade(**trade_data)
        self.session.add(trade)
        self.session.commit()
        return trade

    def get_trades(self, limit: int = 100) -> List[Trade]:
        try:
            return self.session.query(Trade).order_by(Trade.timestamp.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Помилка отримання угод: {e}")
            return []

    # ---------- ActivePosition ----------
    def get_position(self, symbol: str) -> Optional[ActivePosition]:
        """Безпечне отримання позиції. У разі помилки повертає None."""
        try:
            return self.session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()
        except Exception as e:
            logger.error(f"Помилка отримання позиції {symbol}: {e}")
            # Не робимо rollback глобально, щоб не зламати активну транзакцію
            return None

    def save_position(self, symbol: str, amount: float, entry_price: float,
                      highest_price: float, cost: float) -> ActivePosition:
        position = self.get_position(symbol)
        if position:
            position.amount = amount
            position.entry_price = entry_price
            position.highest_price = highest_price
            position.cost = cost
        else:
            position = ActivePosition(
                symbol=symbol,
                amount=amount,
                entry_price=entry_price,
                highest_price=highest_price,
                cost=cost
            )
            self.session.add(position)
        self.session.commit()
        return position

    def update_position_high(self, symbol: str, highest_price: float):
        position = self.get_position(symbol)
        if position:
            position.highest_price = highest_price
            self.session.commit()

    def delete_position(self, symbol: str):
        position = self.get_position(symbol)
        if position:
            self.session.delete(position)
            self.session.commit()

    def get_all_positions(self) -> List[ActivePosition]:
        try:
            return self.session.query(ActivePosition).all()
        except Exception as e:
            logger.error(f"Помилка отримання позицій: {e}")
            return []
