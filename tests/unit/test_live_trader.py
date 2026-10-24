import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import ccxt

from src.shared.config import Settings
from src.engine.domain.models import TradeSide
from src.engine.application.live_trader import LiveBinanceTrader


class MockTradingRepository:
    def __init__(self):
        self.saved_balance = 1000.0
        self.saved_positions = {}
        self.deleted_positions = []
        self.logged_trades = []

    def load_balance(self, default_balance: float) -> float:
        return self.saved_balance

    def save_balance(self, balance: float) -> None:
        self.saved_balance = balance

    def get_all_positions(self):
        return []

    def save_position(self, symbol, amount, entry_price, highest_price, cost, regime="CHOPPY_FLAT", ai_confidence=0.0, features_json="{}", partial_tp_hit=0):
        self.saved_positions[symbol] = {
            "amount": amount,
            "entry_price": entry_price,
            "cost": cost,
            "partial_tp_hit": partial_tp_hit
        }

    def update_position_high(self, symbol, highest_price):
        pass

    def delete_position(self, symbol):
        if symbol in self.saved_positions:
            del self.saved_positions[symbol]
        self.deleted_positions.append(symbol)

    def log_trade(self, symbol, side, price, amount, cost, pnl, exit_reason="UNKNOWN", regime="CHOPPY_FLAT", ai_confidence=0.0, target_label=0, features_json="{}"):
        self.logged_trades.append({
            "symbol": symbol,
            "side": side,
            "price": price,
            "amount": amount,
            "pnl": pnl,
            "exit_reason": exit_reason
        })


@pytest.fixture
def mock_exchange_manager():
    mgr = MagicMock()
    mgr.public_exchange = MagicMock()
    mgr.private_exchange = MagicMock()
    mgr.fetch_current_price = AsyncMock(return_value=100.0)
    return mgr


@pytest.mark.asyncio
async def test_live_trader_safe_fallback_without_keys():
    """Тест безпечного режиму: якщо TRADING_MODE='PAPER', реальні ордери не відправляються."""
    settings = Settings(TRADING_MODE="PAPER")
    repo = MockTradingRepository()
    mock_mgr = MagicMock()
    mock_mgr.private_exchange = None  # Ключі відсутні
    mock_mgr.fetch_current_price = AsyncMock(return_value=100.0)

    trader = LiveBinanceTrader(
        settings=settings,
        repo=repo,
        exchange_manager=mock_mgr
    )
    await trader.initialize()

    assert trader.is_live is False
    assert trader.execution_mode == "PAPER"
    assert trader.balance == 1000.0

    # Відкриття позиції має працювати в емуляторі
    await trader.open_position(
        symbol="BTC/USDT",
        side=TradeSide.BUY,
        price=100.0,
        sl=98.0,
        tp=103.0,
        regime="BULL_TREND",
        ai_confidence=0.75
    )

    assert "BTC/USDT" in trader.positions
    assert trader.positions["BTC/USDT"].amount_coins > 0


@pytest.mark.asyncio
async def test_live_trader_slippage_guard_rejection(mock_exchange_manager):
    """Тест Slippage Guard: відхилення ордера при стрибку ціни > 0.5%."""
    settings = Settings(TRADING_MODE="LIVE", MAX_SLIPPAGE_PCT=0.005)
    repo = MockTradingRepository()
    
    # Симулюємо стрибок ринкової ціни до 102.0 (прослизання 2% відносно сигналу 100.0)
    mock_exchange_manager.fetch_current_price = AsyncMock(return_value=102.0)

    trader = LiveBinanceTrader(
        settings=settings,
        repo=repo,
        exchange_manager=mock_exchange_manager
    )
    await trader.initialize()

    # Спроба входу по 100.0
    await trader.open_position(
        symbol="ETH/USDT",
        side=TradeSide.BUY,
        price=100.0,
        sl=98.0,
        tp=103.0
    )

    # Ордер мав бути відхилений Slippage Guard
    assert "ETH/USDT" not in trader.positions
    assert mock_exchange_manager.private_exchange.create_order.called is False


@pytest.mark.asyncio
async def test_live_trader_live_execution_buy_order(mock_exchange_manager):
    """Тест виконання реального ордера купівлі на Binance при валідних ключах."""
    settings = Settings(TRADING_MODE="LIVE", MAX_SLIPPAGE_PCT=0.01)
    repo = MockTradingRepository()

    # Симулюємо відповідь біржі на баланс та ордер
    mock_exchange_manager.private_exchange.fetch_balance = AsyncMock(return_value={
        'free': {'USDT': 1500.0},
        'total': {'USDT': 1500.0}
    })
    mock_exchange_manager.fetch_current_price = AsyncMock(return_value=100.0)
    mock_exchange_manager.private_exchange.create_order = AsyncMock(return_value={
        'id': 'binance_order_123',
        'average': 100.05,
        'filled': 0.4,
        'cost': 40.02,
        'fee': {'cost': 0.04, 'currency': 'USDT'}
    })

    trader = LiveBinanceTrader(
        settings=settings,
        repo=repo,
        exchange_manager=mock_exchange_manager
    )
    await trader.initialize()

    assert trader.is_live is True
    assert trader.balance == 1500.0

    await trader.open_position(
        symbol="SOL/USDT",
        side=TradeSide.BUY,
        price=100.0,
        sl=98.0,
        tp=103.0,
        ai_confidence=0.80
    )

    assert "SOL/USDT" in trader.positions
    assert mock_exchange_manager.private_exchange.create_order.called is True
    order_call_args = mock_exchange_manager.private_exchange.create_order.call_args[1]
    assert order_call_args['symbol'] == "SOL/USDT"
    assert order_call_args['side'] == 'buy'


@pytest.mark.asyncio
async def test_live_trader_scale_out_execution(mock_exchange_manager):
    """Тест реального Scale-Out 50% TP1 на біржі."""
    settings = Settings(TRADING_MODE="LIVE")
    repo = MockTradingRepository()

    mock_exchange_manager.private_exchange.fetch_balance = AsyncMock(return_value={
        'free': {'USDT': 1000.0},
        'total': {'USDT': 1000.0}
    })
    mock_exchange_manager.fetch_current_price = AsyncMock(return_value=100.0)
    mock_exchange_manager.private_exchange.create_order = AsyncMock(return_value={
        'id': 'scale_out_order_456',
        'average': 101.5,
        'filled': 0.2,
        'cost': 20.3
    })

    trader = LiveBinanceTrader(
        settings=settings,
        repo=repo,
        exchange_manager=mock_exchange_manager
    )
    await trader.initialize()

    # Відкриваємо позицію
    await trader.open_position("AVAX/USDT", TradeSide.BUY, price=100.0, sl=98.0, tp=103.0)
    initial_coins = trader.positions["AVAX/USDT"].amount_coins

    # Викликаємо частковий тейк на 101.5 (+1.5%)
    await trader._partial_close_position("AVAX/USDT", 101.5, "Take Profit 1 (+1.5% Scale-out 50%)")

    # Перевіряємо, що було відправлено ордер на біржу на половину монет
    pos_after = trader.positions["AVAX/USDT"]
    assert pos_after.partial_tp_hit is True
    assert pos_after.amount_coins == pytest.approx(initial_coins * 0.50, rel=1e-3)
    assert pos_after.sl >= pos_after.entry_price # Стоп переведено в безубиток


@pytest.mark.asyncio
async def test_live_trader_insufficient_funds_handling(mock_exchange_manager):
    """Тест безпечної обробки відмови біржі через брак коштів (ccxt.InsufficientFunds)."""
    settings = Settings(TRADING_MODE="LIVE")
    repo = MockTradingRepository()

    mock_exchange_manager.private_exchange.fetch_balance = AsyncMock(return_value={
        'free': {'USDT': 1000.0},
        'total': {'USDT': 1000.0}
    })
    mock_exchange_manager.fetch_current_price = AsyncMock(return_value=100.0)
    mock_exchange_manager.private_exchange.create_order = AsyncMock(
        side_effect=ccxt.InsufficientFunds("Account has insufficient balance")
    )

    trader = LiveBinanceTrader(
        settings=settings,
        repo=repo,
        exchange_manager=mock_exchange_manager
    )
    await trader.initialize()

    # Спроба входу не повинна викидати необроблений exception або створювати фантомну позицію
    await trader.open_position("DOT/USDT", TradeSide.BUY, price=100.0, sl=98.0, tp=103.0)

    assert "DOT/USDT" not in trader.positions
    assert trader.balance == 1000.0  # Баланс не списано


@pytest.mark.asyncio
async def test_live_trader_auth_error_fallback(mock_exchange_manager):
    """Тест автоматичного перемикання в Paper режим при помилці аутентифікації ключів."""
    settings = Settings(TRADING_MODE="LIVE")
    repo = MockTradingRepository()

    mock_exchange_manager.private_exchange.fetch_balance = AsyncMock(
        side_effect=ccxt.AuthenticationError("Invalid API-key, IP, or permissions for action.")
    )

    trader = LiveBinanceTrader(
        settings=settings,
        repo=repo,
        exchange_manager=mock_exchange_manager
    )
    await trader.initialize()

    # Повинен деградувати до PAPER режиму
    assert trader.is_live is False
    assert trader.execution_mode == "PAPER"

