import os
import sys
import logging
import asyncio
import pandas as pd
from pathlib import Path

# Підключаємо корінь проєкту
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from src.engine.application.ai_brain import GlobalTradingAI
from src.engine.application.strategy import HybridStrategy
from src.engine.infrastructure.exchange_manager import ExchangeManager
from src.shared.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MarketSnapshot")

class MarketSnapshot:
    """Утиліта для швидкої діагностики поточного стану ринку (Радар)."""
    
    def __init__(self):
        self.strategy = HybridStrategy(settings=settings)
        self.ai = GlobalTradingAI(settings=settings)
        self.timeframe = "5m"
        
        try:
            self.mgr = ExchangeManager(settings=settings, exchange_id="binanceus")
            self.exchange = self.mgr.exchange
            logger.info(f"✅ Успішно підключено до {self.exchange.id}. Таймфрейм: {self.timeframe}")
        except Exception as e:
            logger.critical(f"🔥 Помилка підключення до біржі: {e}")
            sys.exit(1)

    # ⚡ РОБИМО ФУНКЦІЮ АСИНХРОННОЮ
    async def run(self):
        logger.info("\n🔬 ЗАПУСК ДІАГНОСТИКИ (Поточний зріз ринку)...")
        print("-" * 65)
        print(f"{'Статус':<8} | {'Пара':<10} | {'ШІ Впевненість':<15} | {'Сигнал Стратегії'}")
        print("-" * 65)
        
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT"]
        
        for symbol in symbols:
            try:
                # ⚡ ДОДАЄМО AWAIT (чекаємо, поки біржа реально віддасть дані)
                ohlcv = await self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=100)
                
                if not ohlcv:
                    logger.warning(f"⚠️ Немає даних для {symbol}")
                    continue
                    
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                _, ai_conf = self.ai.predict(df)
                signal, meta = self.strategy.get_signal(df, ai_confidence=ai_conf, in_position=False)
                
                status_icon = "🟢 BUY" if signal == "BUY" else ("🔴 SELL" if signal == "SELL" else "⚪ HOLD")
                print(f"{status_icon:<8} | {symbol:<10} | {ai_conf:>14.2f} | {signal}")
                
            except Exception as e:
                logger.error(f"❌ Помилка під час аналізу {symbol}: {e}")
        
        print("-" * 65)
        logger.info("🏁 Сканування завершено.")
        
        # Правильно закриваємо асинхронну сесію з біржею
        if hasattr(self.exchange, 'close'):
            await self.exchange.close()

if __name__ == "__main__":
    scanner = MarketSnapshot()
    # ⚡ ЗАПУСКАЄМО ЧЕРЕЗ ASYNCIO
    asyncio.run(scanner.run())