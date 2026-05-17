from typing import Protocol, List
from datetime import datetime

class DbPositionProtocol(Protocol):
    """Сувора абстракція для об'єктів позиції, що повертаються з бази даних."""
    symbol: str
    entry_price: float
    cost: float
    amount: float
    highest_price: float
    opened_at: datetime


class NotifierProtocol(Protocol):
    """Абстракція сервісу сповіщень."""
    async def send_message(self, text: str) -> None:
        ...


class TradingRepositoryProtocol(Protocol):
    """Абстракція доступу до даних."""
    def load_balance(self, default_balance: float) -> float: ...
    def save_balance(self, balance: float) -> None: ...
    
    # Використовуємо наш новий суворий протокол замість плейсхолдера
    def get_all_positions(self) -> List[DbPositionProtocol]: ...
    
    def save_position(self, symbol: str, amount: float, entry_price: float, highest_price: float, cost: float) -> None: ...
    def update_position_high(self, symbol: str, highest_price: float) -> None: ...
    def delete_position(self, symbol: str) -> None: ...
    def log_trade(self, symbol: str, side: str, price: float, amount: float, cost: float, pnl: float) -> None: ...