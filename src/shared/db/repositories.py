import logging
from sqlalchemy.orm import Session, exc
from .models import Trade, Wallet, ActivePosition

logger = logging.getLogger(__name__)

class TradingRepository:
    def __init__(self, session: Session):
        self.session = session

    # ---------- Wallet ----------
    def load_balance(self, initial_balance: float = 1000.0) -> float:
        try:
            wallet = self.session.query(Wallet).first()
            if wallet is None:
                wallet = Wallet(usdt_balance=initial_balance)
                self.session.add(wallet)
                self.session.commit()
            return wallet.usdt_balance
        except Exception as e:
            self.session.rollback()
            logger.error(f"Помилка load_balance: {e}")
            return initial_balance

    def save_balance(self, balance: float):
        """Оновлює баланс гаманця."""
        try:
            wallet = self.session.query(Wallet).first()
            if wallet:
                wallet.usdt_balance = balance
            else:
                wallet = Wallet(usdt_balance=balance)
                self.session.add(wallet)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Помилка save_balance: {e}")

    # ---------- Positions (потокобезпечні) ----------
    def save_position(self, symbol, **kwargs):
        """Вставляє або оновлює активну позицію (merge – безпечно при конкурентному доступі)."""
        try:
            # Створюємо тимчасовий об'єкт із переданих полів
            pos = ActivePosition()
            pos.symbol = symbol
            for k, v in kwargs.items():
                if hasattr(pos, k):
                    setattr(pos, k, v)
            # merge шукає існуючий запис за primary key (symbol) і оновлює його,
            # або створює новий, якщо не знайдено
            self.session.merge(pos)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Помилка save_position({symbol}): {e}")

    def get_position(self, symbol):
        return self.session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()

    def get_all_positions(self):
        return self.session.query(ActivePosition).all()

    def delete_position(self, symbol):
        try:
            position = self.get_position(symbol)
            if position:
                self.session.delete(position)
                self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Помилка delete_position({symbol}): {e}")

    def update_position_high(self, symbol, highest_price):
        try:
            position = self.get_position(symbol)
            if position:
                position.highest_price = highest_price
                self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Помилка update_position_high({symbol}): {e}")

    # ---------- Trades ----------
    def record_trade(self, **kwargs):
        """Зберігає угоду (запис у таблицю trades)."""
        try:
            trade = Trade(**kwargs)
            self.session.add(trade)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Помилка record_trade: {e}")

    def log_trade(self, **kwargs):
        """Псевдонім для record_trade, який очікує PaperTrader."""
        self.record_trade(**kwargs)
