from sqlalchemy.orm import Session
from src.shared.db.models import Trade, Wallet, ActivePosition

class TradingRepository:
    def __init__(self, session: Session):
        self.session = session

    # ---------- Wallet ----------
    def load_balance(self, initial_balance: float = 1000.0) -> float:
        wallet = self.session.query(Wallet).first()
        if wallet is None:
            wallet = Wallet(usdt_balance=initial_balance)
            self.session.add(wallet)
            self.session.commit()
        return wallet.usdt_balance

    # ---------- Positions ----------
    def save_position(self, symbol, **kwargs):
        """Зберігає або оновлює активну позицію.
        Очікує аргументи: symbol, amount, entry_price, cost, opened_at (та інші)
        """
        existing = self.session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()
        if existing:
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
        else:
            # Створюємо нову позицію, передаючи тільки відомі поля
            pos_data = {'symbol': symbol}
            pos_data.update(kwargs)
            # Відкидаємо невідомі поля
            valid_fields = {c.name for c in ActivePosition.__table__.columns}
            filtered = {k: v for k, v in pos_data.items() if k in valid_fields}
            new_pos = ActivePosition(**filtered)
            self.session.add(new_pos)
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

    # ---------- Trades ----------
    def record_trade(self, **kwargs):
        trade = Trade(**kwargs)
        self.session.add(trade)
        self.session.commit()
