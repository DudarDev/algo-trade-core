import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from src.shared.db.models import Trade, Wallet, ActivePosition

logger = logging.getLogger(__name__)

class TradingRepository:
    """Репозиторій для роботи з торговими даними. 
    Ізолює базу даних від бізнес-логіки бота."""
    
    def __init__(self, session: Session):
        self.session = session

    # --- WALLET ---
    def load_balance(self, default: float = 1000.0) -> float:
        wallet = self.session.query(Wallet).filter(Wallet.id == 1).first()
        return wallet.usdt_balance if wallet else default

    def save_balance(self, balance: float) -> Wallet:
        wallet = self.session.query(Wallet).filter(Wallet.id == 1).first()
        if not wallet:
            wallet = Wallet(id=1, usdt_balance=balance)
            self.session.add(wallet)
        else:
            wallet.usdt_balance = balance
        
        self.session.commit()
        return wallet

    # --- TRADES ---
    def log_trade(self, symbol: str, side: str, price: float, amount: float, cost: float, pnl: float = 0.0) -> Trade:
        trade = Trade(
            symbol=symbol, side=side, price=price, 
            amount=amount, cost=cost, pnl=pnl
        )
        self.session.add(trade)
        self.session.commit()
        return trade

    # --- ACTIVE POSITIONS ---
    def get_all_positions(self) -> List[ActivePosition]:
        return self.session.query(ActivePosition).all()

    def get_position(self, symbol: str) -> Optional[ActivePosition]:
        return self.session.query(ActivePosition).filter(ActivePosition.symbol == symbol).first()

    def save_position(self, symbol: str, amount: float, entry_price: float, highest_price: float, cost: float) -> ActivePosition:
        position = self.get_position(symbol)
        
        if not position:
            position = ActivePosition(symbol=symbol)
            self.session.add(position)
            
        position.amount = amount
        position.entry_price = entry_price
        position.highest_price = highest_price
        position.cost = cost
        
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