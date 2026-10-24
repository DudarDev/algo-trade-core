from typing import Protocol, List, Dict, Any, Optional
from datetime import datetime

class DbPositionProtocol(Protocol):
    """Сувора абстракція для об'єктів позиції, що повертаються з бази даних."""
    symbol: str
    entry_price: float
    cost: float
    amount: float
    highest_price: float
    opened_at: datetime
    regime: str
    ai_confidence: float
    features_json: str


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
    
    def save_position(
        self,
        symbol: str,
        amount: float,
        entry_price: float,
        highest_price: float,
        cost: float,
        regime: str = "CHOPPY_FLAT",
        ai_confidence: float = 0.0,
        features_json: str = "{}"
    ) -> None: ...
    
    def update_position_high(self, symbol: str, highest_price: float) -> None: ...
    def delete_position(self, symbol: str) -> None: ...
    
    def log_trade(
        self,
        symbol: str,
        side: str,
        price: float,
        amount: float,
        cost: float,
        pnl: float,
        exit_reason: str = "UNKNOWN",
        regime: str = "CHOPPY_FLAT",
        ai_confidence: float = 0.0,
        target_label: int = 0,
        features_json: str = "{}"
    ) -> None: ...


class TraderProtocol(Protocol):
    """Уніфікований інтерфейс виконання для Paper та Live торгівлі."""
    positions: Dict[str, Any]
    balance: float
    
    async def initialize(self) -> None: ...
    async def open_position(
        self,
        symbol: str,
        side: Any,
        price: float,
        sl: float,
        tp: float,
        regime: str = "CHOPPY_FLAT",
        ai_confidence: float = 0.0,
        features_snapshot: Optional[Dict[str, float]] = None
    ) -> None: ...
    async def update_position(self, symbol: str, current_price: float) -> None: ...
    async def _close_position(self, symbol: str, close_price: float, reason: str) -> None: ...
    async def _partial_close_position(self, symbol: str, close_price: float, reason: str) -> None: ...
