import logging
from sqlalchemy.orm import Session
from .models import Trade, Wallet, ActivePosition
from .session import SessionLocal   # фабрика сесій, вже налаштована

logger = logging.getLogger(__name__)

class TradingRepository:
    def __init__(self, session: Session = None):
        # session ігнорується, кожен метод створює власну сесію
        pass

    def _get_session(self):
        return SessionLocal()

    # ---------- Wallet ----------
    def load_balance(self, initial_balance: float = 1000.0) -> float:
        session = self._get_session()
        try:
            wallet = session.query(Wallet).first()
            if wallet is None:
                wallet = Wallet(usdt_balance=initial_balance)
                session.add(wallet)
                session.commit()
            return wallet.usdt_balance
        finally:
            session.close()

    def save_balance(self, balance: float):
        session = self._get_session()
        try:
            wallet = session.query(Wallet).first()
            if wallet:
                wallet.usdt_balance = balance
            else:
                wallet = Wallet(usdt_balance=balance)
                session.add(wallet)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"save_balance: {e}")
        finally:
            session.close()

    # ---------- Positions ----------
    def save_position(self, symbol, **kwargs):
        session = self._get_session()
        try:
            pos = ActivePosition()
            pos.symbol = symbol
            for k, v in kwargs.items():
                if hasattr(pos, k):
                    setattr(pos, k, v)
            session.merge(pos)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"save_position({symbol}): {e}")
        finally:
            session.close()

    def get_position(self, symbol):
        session = self._get_session()
        try:
            return session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()
        finally:
            session.close()

    def get_all_positions(self):
        session = self._get_session()
        try:
            return session.query(ActivePosition).all()
        finally:
            session.close()

    def delete_position(self, symbol):
        session = self._get_session()
        try:
            position = session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()
            if position:
                session.delete(position)
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"delete_position({symbol}): {e}")
        finally:
            session.close()

    def update_position_high(self, symbol, highest_price):
        session = self._get_session()
        try:
            position = session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()
            if position:
                position.highest_price = highest_price
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"update_position_high({symbol}): {e}")
        finally:
            session.close()

    # ---------- Trades ----------
    def record_trade(self, **kwargs):
        session = self._get_session()
        try:
            trade = Trade(**kwargs)
            session.add(trade)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"record_trade: {e}")
        finally:
            session.close()

    def log_trade(self, **kwargs):
        self.record_trade(**kwargs)
