import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.engine.application.paper_trader import PaperTrader
from src.engine.domain.models import TradeSide, Position
from src.shared.config import Settings

# --- MOCKS (Підробки для тестів) ---
class MockRepository:
    def load_balance(self, initial: float) -> float: 
        return 1000.0
    def get_all_positions(self) -> list: 
        return []
    def save_position(self, **kwargs) -> None: 
        pass
    def save_balance(self, balance: float) -> None: 
        pass
    def update_position_high(self, symbol: str, high: float) -> None: 
        pass
    def delete_position(self, symbol: str) -> None: 
        pass
    def log_trade(self, **kwargs) -> None: 
        pass

class MockNotifier:
    async def send_message(self, msg: str) -> None: 
        pass

# --- FIXTURES ---
@pytest.fixture
def settings():
    s = Settings()
    s.INITIAL_BALANCE = 1000.0
    
    # Нові конфіги ризик-менеджменту
    s.risk_per_trade_pct = 0.02     # Ризик 2% на угоду
    s.max_open_positions = 2        # Максимум 2 одночасні угоди
    s.exchange_fee_pct = 0.001      # Комісія 0.1%
    s.ENABLE_TELEGRAM = False
    
    # Заглушки для сумісності з іншими модулями
    s.DEFAULT_SL_PCT = 0.02
    s.DEFAULT_TP_PCT = 0.05
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
    """Тест 2: Перевірка динамічного розрахунку об'єму (Position Sizing) та зняття комісії"""
    await paper_trader.initialize()
    
    # Відкриваємо угоду на покупку BTC по $50,000. Стоп-лос на $40,000.
    # Ризик на 1 монету = 50,000 - 40,000 = $10,000.
    # Бюджет ризику = 1000 * 0.02 (2%) = $20.
    # Бот має купити: 20 / 10,000 = 0.002 BTC.
    # Вартість 0.002 BTC = 0.002 * 50,000 = 100 USDT.
    
    await paper_trader.open_position("BTC/USDT", TradeSide.BUY, 50000.0, 40000.0, 60000.0)
    
    assert "BTC/USDT" in paper_trader.positions
    pos = paper_trader.positions["BTC/USDT"]
    
    # Перевіряємо об'єми
    assert pos.amount_usdt == 100.0
    assert pos.amount_coins == 0.002
    
    # Перевіряємо зняття коштів з комісією (0.1% від 100 USDT = 0.1 USDT)
    # 1000.0 - 100.0 (тіло) - 0.1 (комісія) = 899.9
    assert round(paper_trader.balance, 2) == 899.9

@pytest.mark.asyncio
async def test_prevent_insufficient_funds(paper_trader, settings):
    """Тест 3: Захист від від'ємного балансу (Hard limit 10 USDT)"""
    await paper_trader.initialize()
    paper_trader.balance = 8.0  # Штучно робимо баланс меншим за ліміт біржі (10 USDT)
    
    await paper_trader.open_position("ETH/USDT", TradeSide.BUY, 3000.0, 2900.0, 3100.0)
    
    # Угода не мала відкритися через малий баланс
    assert "ETH/USDT" not in paper_trader.positions
    assert paper_trader.balance == 8.0  # Баланс не змінився

@pytest.mark.asyncio
async def test_max_open_positions_limit(paper_trader, settings):
    """Тест 4: Перевірка ліміту одночасних угод (захист від overexposure)"""
    await paper_trader.initialize()
    
    # Відкриваємо 2 дозволені угоди
    await paper_trader.open_position("BTC/USDT", TradeSide.BUY, 50000.0, 40000.0, 60000.0)
    await paper_trader.open_position("ETH/USDT", TradeSide.BUY, 3000.0, 2500.0, 4000.0)
    
    assert len(paper_trader.positions) == 2
    
    # Намагаємося відкрити 3-тю угоду (ліміт max_open_positions = 2)
    await paper_trader.open_position("SOL/USDT", TradeSide.BUY, 150.0, 140.0, 180.0)
    
    # Третя угода має бути заблокована
    assert "SOL/USDT" not in paper_trader.positions
    assert len(paper_trader.positions) == 2