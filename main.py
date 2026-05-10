import time
import logging
import asyncio
import json
from pathlib import Path
from typing import List

# ==========================================
# 1. ІМПОРТИ НОВОЇ АРХІТЕКТУРИ
# ==========================================
from src.shared.config import settings
from src.shared.db.session import SessionLocal
from src.shared.db.repositories import TradingRepository

from src.engine.infrastructure.telegram_notifier import TelegramNotifier
from src.engine.infrastructure.exchange_manager import ExchangeManager
from src.engine.infrastructure.market_scanner import MarketScanner

from src.engine.application.ai_brain import GlobalTradingAI
from src.engine.application.strategy import HybridStrategy
from src.engine.application.risk_management import RiskManager, RiskConfig
from src.engine.application.paper_trader import PaperTrader

# Налаштування логування
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("Main")

# ⚙️ Спільний файл для керування станом (зупинка/запуск з веб-панелі)
STATUS_FILE = Path("/app/data_storage/bot_status.json")

def is_bot_active() -> bool:
    """Перевіряє, чи дозволено боту торгувати. За замовчуванням – так."""
    if not STATUS_FILE.exists():
        return True
    try:
        with open(STATUS_FILE, "r") as f:
            data = json.load(f)
            return data.get("status") != "stopped"
    except Exception:
        return True  # при помилці читання продовжуємо роботу

class CryptoBot:
    """Головний Оркестратор Бота (Trading Loop)"""
    
    def __init__(
        self,
        exchange: ExchangeManager,
        scanner: MarketScanner,
        ai: GlobalTradingAI,
        strategy: HybridStrategy,
        risk_manager: RiskManager,
        trader: PaperTrader
    ):
        logger.info("🚀 Ініціалізація Quantum Scalper Core (Senior Async Edition)...")
        
        # 💉 Dependency Injection
        self.exchange = exchange 
        self.scanner = scanner  
        self.ai = ai
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.trader = trader
        
        # 🛡️ Семафор для захисту CPU від перенавантаження Pandas/Sklearn
        self.concurrency_limit = asyncio.Semaphore(5)

    async def setup(self):
        """Асинхронна підготовка (відновлення стану з БД)."""
        await self.trader.initialize()

    async def cleanup(self):
        """Коректне закриття з'єднань при зупинці бота."""
        logger.info("🧹 Очищення ресурсів...")
        await self.exchange.close()

    async def process_pair(self, symbol: str):
        """Асинхронний конвеєр обробки однієї торгової пари під захистом семафора."""
        async with self.concurrency_limit:
            try:
                # 1. Отримуємо сирі дані з біржі
                df = await self.exchange.fetch_data(symbol, timeframe=settings.TIMEFRAME, limit=100)
                if df is None or df.empty:
                    return

                # 2. Перевіряємо відкриті позиції (Трейлінг стоп)
                if symbol in self.trader.positions:
                    await self.trader.update_position(symbol, df.iloc[-1]['close'])
                    return 
                
                # 3. Генерація фіч (в окремому потоці, щоб не блокувати Event Loop)
                df_features = await asyncio.to_thread(self.ai.prepare_features, df)
                if df_features.empty:
                    return
                    
                # 4. Прогноз ШІ
                ai_signal, confidence = await asyncio.to_thread(self.ai.predict, df)
                
                # 5. Валідація класичним Технічним Аналізом (Гібридна Стратегія)
                final_signal, meta = self.strategy.get_signal(
                    df=df_features, 
                    ai_confidence=confidence, 
                    in_position=(symbol in self.trader.positions)
                )
                
                # 6. Управління ризиками та відкриття ордера
                if final_signal == "BUY":
                    current_price = float(df_features.iloc[-1]['close'])
                    current_atr = float(df_features.iloc[-1]['ATR'])
                    current_balance = self.trader.balance 
                    
                    trade_params = self.risk_manager.evaluate_trade(
                        entry_price=current_price, 
                        atr=current_atr,
                        capital=current_balance,
                        trade_type='BUY'
                    )
                    
                    if trade_params:
                        reason = meta.get('reason', 'AI_Signal')
                        logger.info(f"🔥 ВХІД: {symbol} | Conf: {confidence:.2f} | R:R: {trade_params.risk_reward_ratio:.2f} | Причина: {reason}")
                        
                        await self.trader.open_position(
                            symbol=symbol,
                            side="BUY",
                            price=trade_params.entry_price,
                            sl=trade_params.stop_loss,
                            tp=trade_params.take_profit
                        )

            except Exception as e:
                logger.error(f"❌ Помилка обробки {symbol}: {e}", exc_info=True)

    async def run_cycle(self):
        """Один повний цикл опитування ринку."""
        logger.info("📡 Пошук волатильних пар...")
        active_pairs = await self.scanner.get_top_volatile_pairs(min_volume=500_000)
        
        if not active_pairs:
            logger.warning("⚠️ Ринок неліквідний. Чекаю...")
            return

        logger.info(f"📊 Обчислення {len(active_pairs)} пар (Max 5 паралельно)...")
        tasks = [self.process_pair(symbol) for symbol in active_pairs]
        await asyncio.gather(*tasks)
        
        logger.info("✅ Цикл завершено.")

    async def start(self):
        """Головний нескінченний цикл із перевіркою статусу."""
        logger.info("🟢 Бот успішно стартував і готовий до роботи!")
        while True:
            # 🔒 Перевірка: чи не зупинили бота через веб-панель
            if not is_bot_active():
                logger.info("⏸️ Бот зупинений через Веб-панель. Очікування команди START...")
                await asyncio.sleep(10)
                continue

            try:
                start_time = time.time()
                await self.run_cycle()
                
                elapsed = time.time() - start_time
                sleep_time = max(0, 300 - elapsed) # 5 хвилин між циклами
                
                logger.info(f"💤 Очікування наступного циклу ({sleep_time:.1f}с)...")
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                logger.info("🛑 Отримано сигнал зупинки бота...")
                break
            except Exception as e:
                logger.error(f"❌ Критична помилка у головному циклі: {e}", exc_info=True)
                await asyncio.sleep(60)

# ==========================================
# 🏗️ COMPOSITION ROOT (Місце зборки бота)
# ==========================================
async def main():
    # 1. Ініціалізуємо БД
    db_session = SessionLocal()
    repo = TradingRepository(session=db_session)
    
    # 2. Інфраструктура
    notifier = TelegramNotifier() if settings.ENABLE_TELEGRAM else None
    exchange = ExchangeManager(settings=settings)
    scanner = MarketScanner(exchange_manager=exchange)
    
    # 3. Бізнес-логіка (AI, Стратегія, Ризики)
    ai = GlobalTradingAI(settings=settings)
    strategy = HybridStrategy(settings=settings)
    
    risk_config = RiskConfig(
        max_risk_pct=2.0, 
        min_risk_reward=settings.RISK_REWARD_RATIO
    )
    risk_manager = RiskManager(config=risk_config)
    
    # 4. Трейдер
    trader = PaperTrader(
        settings=settings,
        repo=repo,
        notifier=notifier
    )
    
    # 5. Ін'єкція залежностей в Оркестратор
    bot = CryptoBot(
        exchange=exchange,
        scanner=scanner,
        ai=ai,
        strategy=strategy,
        risk_manager=risk_manager,
        trader=trader
    )
    
    try:
        await bot.setup() 
        await bot.start() 
    finally:
        await bot.cleanup()
        db_session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот вимкнений користувачем (KeyboardInterrupt).")
