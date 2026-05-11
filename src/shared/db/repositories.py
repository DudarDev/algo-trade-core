from sqlalchemy.orm import Session
from src.shared.db.models import Trade, Wallet, ActivePosition

class TradingRepository:
    def __init__(self, session: Session):
        self.session = session

    def load_balance(self, initial_balance: float = 1000.0) -> float:
        wallet = self.session.query(Wallet).first()
        if wallet is None:
            wallet = Wallet(usdt_balance=initial_balance)
            self.session.add(wallet)
            self.session.commit()
        return wallet.usdt_balance

    def save_position(self, symbol, position):
        existing = self.session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()
        if existing:
            existing.amount = position.amount
            existing.entry_price = position.entry_price
            existing.highest_price = position.highest_price
            existing.cost = position.cost
            existing.opened_at = position.opened_at
        else:
            self.session.add(position)
        self.session.commit()

    def get_position(self, symbol):
        return self.session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()

    def get_all_positions(self):
        return self.session.query(ActivePosition).all()

    def delete_position(self, symbol):
        position = self.get_position(symbol)
        if position:
            self.session.delete(position)
            self.session.commit()

    def update_position_high(self, symbol, highest_price):
        position = self.get_position(symbol)
        if position:
            position.highest_price = highest_price
            self.session.commit()

    def record_trade(self, trade):
        self.session.add(trade)
        self.session.commit()
