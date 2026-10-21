import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.engine.application.paper_trader import PaperTrader
from src.engine.domain.models import TradeSide, Position
from src.engine.application.adaptive_risk_controller import AdaptiveRiskController

class MockRepository:
    def __init__(self):
        self.balance = 1000.0
        self.positions = []
        self.saved_positions = []
        self.logged_trades = []
        self.updated_highs = []
        self.deleted_positions = []

    def load_balance(self, initial: float) -> float: 
        return self.balance

    def get_all_positions(self) -> list: 
        return self.positions

    def get_closed_trades(self, limit=None) -> list:
        return self.logged_trades

    def save_position(self, **kwargs) -> None: 
        self.saved_positions.append(kwargs)

    def save_balance(self, balance: float) -> None: 
        self.balance = balance

    def update_position_high(self, symbol: str, high: float) -> None: 
        self.updated_highs.append((symbol, high))

    def delete_position(self, symbol: str) -> None: 
        self.deleted_positions.append(symbol)

    def log_trade(self, **kwargs) -> None: 
        self.logged_trades.append(kwargs)

class MockNotifier:
    async def send_message(self, msg: str) -> None: 
        pass

@pytest.fixture
def settings():
    class MockSettings:
        INITIAL_BALANCE = 1000.0
        risk_per_trade_pct = 0.02
        max_open_positions = 2
        exchange_fee_pct = 0.001
        ENABLE_TELEGRAM = False
        DEFAULT_SL_PCT = 0.02
        DEFAULT_TP_PCT = 0.05
        TRAILING_STOP_ACTIVATION_PCT = 0.03
        TRAILING_OFFSET_PCT = 0.01
        TRADE_TIMEOUT_SECONDS = 3600
        TRAILING_STOP_TRIGGER_PCT = 0.03
        TRAILING_STOP_CALLBACK_PCT = 0.01
        BREAK_EVEN_TRIGGER_PCT = 0.02
    return MockSettings()

@pytest.fixture
def repo():
    return MockRepository()

@pytest.fixture
def paper_trader(settings, repo):
    notifier = MockNotifier()
    return PaperTrader(settings, repo, notifier)

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
    await paper_trader.open_position("BTC/USDT", TradeSide.BUY, 50000.0, 40000.0, 60000.0)
    
    assert "BTC/USDT" in paper_trader.positions
    pos = paper_trader.positions["BTC/USDT"]
    
    assert pos.amount_usdt == 100.0
    assert pos.amount_coins == 0.002
    assert round(paper_trader.balance, 2) == 899.9

@pytest.mark.asyncio
async def test_open_position_with_features_snapshot(paper_trader, repo):
    """Тест 3: Перевірка збереження повного зрізу фіч та режиму (Feature Store)"""
    await paper_trader.initialize()
    snapshot = {"RSI": 0.45, "ADX": 0.28, "EMA_DIST_50": 0.012}
    
    await paper_trader.open_position(
        symbol="ETH/USDT",
        side=TradeSide.BUY,
        price=3000.0,
        sl=2900.0,
        tp=3300.0,
        regime="BULL_MARKET",
        ai_confidence=0.62,
        features_snapshot=snapshot
    )
    
    assert "ETH/USDT" in paper_trader.positions
    pos = paper_trader.positions["ETH/USDT"]
    assert pos.regime == "BULL_MARKET"
    assert pos.ai_confidence == 0.62
    assert pos.features_snapshot == snapshot

    assert len(repo.saved_positions) == 1
    saved = repo.saved_positions[0]
    assert saved["regime"] == "BULL_MARKET"
    assert saved["ai_confidence"] == 0.62
    assert "RSI" in saved["features_json"]

@pytest.mark.asyncio
async def test_prevent_insufficient_funds(paper_trader):
    """Тест 4: Захист від від'ємного балансу (Hard limit 10 USDT)"""
    await paper_trader.initialize()
    paper_trader.balance = 8.0
    
    await paper_trader.open_position("ETH/USDT", TradeSide.BUY, 3000.0, 2900.0, 3100.0)
    assert "ETH/USDT" not in paper_trader.positions
    assert paper_trader.balance == 8.0

@pytest.mark.asyncio
async def test_max_open_positions_limit(paper_trader):
    """Тест 5: Перевірка ліміту одночасних угод"""
    await paper_trader.initialize()
    
    await paper_trader.open_position("BTC/USDT", TradeSide.BUY, 50000.0, 40000.0, 60000.0)
    await paper_trader.open_position("ETH/USDT", TradeSide.BUY, 3000.0, 2500.0, 4000.0)
    assert len(paper_trader.positions) == 2
    
    await paper_trader.open_position("SOL/USDT", TradeSide.BUY, 150.0, 140.0, 180.0)
    assert "SOL/USDT" not in paper_trader.positions
    assert len(paper_trader.positions) == 2

@pytest.mark.asyncio
async def test_close_position_take_profit_and_journaling(paper_trader, repo):
    """Тест 6: Закриття позиції по TP, розрахунок чистого PnL, маркування target_label=1"""
    await paper_trader.initialize()
    feat_snap = {"ADX": 0.32, "RSI": 0.58}

    await paper_trader.open_position(
        symbol="BTC/USDT",
        side=TradeSide.BUY,
        price=50000.0,
        sl=45000.0,
        tp=55000.0,
        regime="BULL_MARKET",
        ai_confidence=0.65,
        features_snapshot=feat_snap
    )
    
    balance_before_exit = paper_trader.balance

    # Оновлюємо ціну вище Take Profit ($56,000 > $55,000)
    await paper_trader.update_position("BTC/USDT", 56000.0)

    # Позиція закрита
    assert "BTC/USDT" not in paper_trader.positions
    assert "BTC/USDT" in repo.deleted_positions
    assert len(repo.logged_trades) == 1

    logged = repo.logged_trades[0]
    assert logged["symbol"] == "BTC/USDT"
    assert logged["side"] == "SELL"
    assert logged["target_label"] == 1  # Win!
    assert logged["pnl"] > 0
    assert logged["regime"] == "BULL_MARKET"
    assert logged["ai_confidence"] == 0.65
    assert "ADX" in logged["features_json"]

@pytest.mark.asyncio
async def test_close_position_stop_loss_and_journaling(paper_trader, repo):
    """Тест 7: Закриття по Stop Loss, маркування target_label=0 (збиток)"""
    await paper_trader.initialize()
    
    await paper_trader.open_position(
        symbol="SOL/USDT",
        side=TradeSide.BUY,
        price=100.0,
        sl=90.0,
        tp=130.0,
        regime="CHOPPY_FLAT",
        ai_confidence=0.35,
        features_snapshot={"ADX": 0.20}
    )

    # Ціна падає нижче SL ($88.0 < $90.0)
    await paper_trader.update_position("SOL/USDT", 88.0)

    assert "SOL/USDT" not in paper_trader.positions
    assert len(repo.logged_trades) == 1
    logged = repo.logged_trades[0]
    assert logged["target_label"] == 0  # Loss
    assert logged["pnl"] < 0
    assert logged["regime"] == "CHOPPY_FLAT"

@pytest.mark.asyncio
async def test_adaptive_risk_controller_integration(settings, repo):
    """Тест 8: Перевірка взаємодії PaperTrader з AdaptiveRiskController"""
    risk_controller = AdaptiveRiskController(
        base_confidence=0.55,
        base_min_adx=25.0,
        base_risk_pct=0.02
    )
    trader = PaperTrader(settings, repo, MockNotifier(), risk_controller=risk_controller)
    await trader.initialize()

    # Відкриваємо та закриваємо зі збитком
    await trader.open_position("BTC/USDT", TradeSide.BUY, 50000.0, 48000.0, 60000.0)
    await trader.update_position("BTC/USDT", 47000.0)  # Trigger SL

    # Контролер зафіксував збиток і підвищив вимоги
    assert risk_controller.consecutive_losses == 1
    assert risk_controller.get_effective_confidence_threshold() > 0.55
    assert risk_controller.get_effective_min_adx() > 25.0
