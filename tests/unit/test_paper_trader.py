import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.engine.application.paper_trader import PaperTrader
from src.engine.domain.models import TradeSide, Position
from src.shared.config import Settings

# --- MOCKS (Підробки для тестів) ---
class MockRepository:
    def load_balance(self, initial): return 1000.0
    def get_all_positions(self): return []
    def save_position(self, **kwargs): pass
    def save_balance(self, balance): pass
    def update_position_high(self, symbol, high): pass
    def delete_position(self, symbol): pass
    def log_trade(self, **kwargs): pass

class MockNotifier:
    async def send_message(self, msg): pass

@pytest.fixture
def settings():
    s = Settings()
    s.INITIAL_BALANCE = 1000.0
    s.TRADE_FRACTION = 0.1  # 10% на угоду
    s.MIN_TRADE_SIZE = 10.0
    s.DEFAULT_SL_PCT = 0.02
    s.DEFAULT_TP_PCT = 0.05
    s.ENABLE_TELEGRAM = False
    return s

@pytest.fixture
def paper_trader(settings):
    repo = MockRepository()
    notifier = MockNotifier()
    return PaperTrader(settings, repo, notifier)

# --- ТЕСТИ ---

@pytest.mark.asyncio
async def test_initialization(paper_trader):
    """Тест 1: Перевірка правильної ініціалізації балансу"""
    await paper_trader.initialize()
    assert paper_trader.balance == 1000.0
    assert len(paper_trader.positions) == 0
    assert paper_trader._is_initialized is True

@pytest.mark.asyncio
async def test_open_position_success(paper_trader, settings):
    """Тест 2: Перевірка відкриття угоди та зняття грошей з балансу"""
    await paper_trader.initialize()
    
    # Відкриваємо угоду на покупку BTC по ціні $50,000
    await paper_trader.open_position("BTC/USDT", TradeSide.BUY, 50000.0, 49000.0, 52000.0)
    
    assert "BTC/USDT" in paper_trader.positions
    pos = paper_trader.positions["BTC/USDT"]
    
    # Мали зайти на 10% від 1000 = 100 доларів
    assert pos.amount_usdt == 100.0
    # Кількість монет має бути 100 / 50000 = 0.002
    assert pos.amount_coins == 100.0 / 50000.0
    # Баланс має зменшитись на 100
    assert paper_trader.balance == 900.0

@pytest.mark.asyncio
async def test_prevent_insufficient_funds(paper_trader, settings):
    """Тест 3: Захист від від'ємного балансу (Edge Case)"""
    await paper_trader.initialize()
    paper_trader.balance = 5.0 # Штучно робимо баланс меншим за MIN_TRADE_SIZE (10.0)
    
    await paper_trader.open_position("ETH/USDT", TradeSide.BUY, 3000.0, 2900.0, 3100.0)
    
    # Угода не мала відкритися
    assert "ETH/USDT" not in paper_trader.positions
    assert paper_trader.balance == 5.0 # Баланс не змінився