import os
import sys
import time
import logging
import asyncio
import django
from sqlalchemy import text

# 1. ФІКС ШЛЯХІВ ТА ІНІЦІАЛІЗАЦІЯ DJANGO
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_panel.settings')
django.setup()

# 2. ФІКС ЛОГУВАННЯ (Після django.setup!)
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    force=True # Примусово перезаписуємо налаштування Django
)
logger = logging.getLogger("Main")

from src.shared.config import settings
from src.shared.db.session import SessionLocal
from src.shared.db.repositories import TradingRepository
from src.engine.domain.models import TradeSide
from src.engine.infrastructure.telegram_notifier import TelegramNotifier
from src.engine.infrastructure.exchange_manager import ExchangeManager
from src.engine.infrastructure.market_scanner import MarketScanner
from src.infrastructure.ai.predictor import GlobalTradingAI
from src.engine.application.strategy import HybridStrategy
from src.engine.application.risk_management import RiskManager, RiskConfig
from src.engine.application.paper_trader import PaperTrader

class CryptoBot:
    def __init__(self, db_session, exchange, scanner, ai, strategy, risk_manager, trader):
        logger.info("🚀 Ініціалізація Quantum Scalper Core (Senior Edition)...")
        self.db_session = db_session
        self.exchange = exchange
        self.scanner = scanner
        self.ai = ai
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.trader = trader
        self.concurrency_limit = asyncio.Semaphore(5)

    def is_bot_active(self) -> bool:
        """ ФІКС: Обов'язковий rollback при помилці БД """
        try:
            # Використовуємо окрему транзакцію для перевірки, щоб не ламати основну
            with self.db_session.begin_nested():
                query = text("SELECT status FROM bot_config WHERE id=1")
                result = self.db_session.execute(query).scalar()
            
            if result is None:
                # Якщо таблиця порожня, пробуємо ініціалізувати
                try:
                    self.db_session.execute(text("INSERT INTO bot_config (id, status) VALUES (1, 'stopped')"))
                    self.db_session.commit()
                    return False
                except Exception:
                    self.db_session.rollback()
                    return False
                
            return result == "active"
        except Exception as e:
            # ЯКЩО БУДЬ-ЯКА ПОМИЛКА — РОБИМО ROLLBACK
            self.db_session.rollback() 
            logger.error(f"❌ DB Error checking status: {e}")
            return False
            
    async def setup(self):
        await self.trader.initialize()

    async def cleanup(self):
        logger.info("🧹 Очищення ресурсів...")
        await self.exchange.close()

    async def process_pair(self, symbol: str):
        async with self.concurrency_limit:
            try:
                df = await self.exchange.fetch_data(symbol, timeframe=settings.TIMEFRAME, limit=100)
                if df is None or df.empty: return

                if len(df) < 60:
                    return

                if symbol in self.trader.positions:
                    await self.trader.update_position(symbol, float(df.iloc[-1]['close']))
                    return

                df_features = await asyncio.to_thread(self.ai.prepare_features, df)
                if df_features.empty: return

                final_signal, proba = self.ai.predict(df_features)
                signal_action, meta = self.strategy.get_signal(
                    df=df_features,
                    ai_confidence=proba,
                    in_position=(symbol in self.trader.positions)
                )

                if signal_action == "BUY":
                    current_price = float(df_features.iloc[-1]['close'])
                    current_atr = float(df_features.iloc[-1]['ATR_PCT']) * current_price
                    trade_params = self.risk_manager.evaluate_trade(
                        entry_price=current_price, atr=current_atr,
                        capital=self.trader.balance, trade_type='BUY'
                    )
                    if trade_params:
                        reason = meta.reason if hasattr(meta, 'reason') else meta.get('reason', 'AI_Signal')
                        logger.info(f"🔥 ВХІД: {symbol} | Conf: {proba:.2f} | R:R: {trade_params.risk_reward_ratio:.2f} | Причина: {reason}")
                        await self.trader.open_position(
                            symbol=symbol, side=TradeSide.BUY, price=trade_params.entry_price,
                            sl=trade_params.stop_loss, tp=trade_params.take_profit
                        )
            except Exception as e:
                logger.error(f"❌ Помилка обробки {symbol}: {e}") # Прибрав exc_info=True щоб не спамити Traceback-ами

    async def run_cycle(self):
        logger.info("📡 Пошук волатильних пар...")
        active_pairs = await self.scanner.get_top_volatile_pairs(min_volume=500_000)
        if not active_pairs: return
        tasks = [self.process_pair(symbol) for symbol in active_pairs]
        await asyncio.gather(*tasks)
        logger.info("✅ Цикл завершено.")

    async def start(self):
        logger.info("🟢 Бот запущено! Очікування команди з дашборду...")
        while True:
            if not self.is_bot_active():
                logger.info("⏸️ Бот зупинений. Очікування команди START...")
                await asyncio.sleep(10)
                continue
            try:
                start_time = time.time()
                await self.run_cycle()
                elapsed = time.time() - start_time
                sleep_time = max(0, 300 - elapsed)
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Помилка циклу: {e}")
                await asyncio.sleep(60)

async def main():
    db_session = SessionLocal()
    bot = CryptoBot(
        db_session=db_session,
        exchange=ExchangeManager(settings=settings),
        scanner=MarketScanner(exchange_manager=ExchangeManager(settings=settings)),
        ai=GlobalTradingAI(settings=settings),
        strategy=HybridStrategy(settings=settings),
        risk_manager=RiskManager(config=RiskConfig(max_risk_pct=2.0, min_risk_reward=settings.RISK_REWARD_RATIO)),
        trader=PaperTrader(settings=settings, repo=TradingRepository(session=db_session), notifier=TelegramNotifier() if settings.ENABLE_TELEGRAM else None)
    )
    try:
        await bot.setup()
        await bot.start()
    finally:
        await bot.cleanup()
        db_session.close()

if __name__ == "__main__":
    # Щоб не було помилок unclosed session при зупинці
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинено вручну.")