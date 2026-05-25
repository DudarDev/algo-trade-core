import os
import sys
import logging
import asyncio
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from src.infrastructure.ai.predictor import GlobalTradingAI   # ← правильний шлях
from src.engine.application.strategy import HybridStrategy
from src.engine.infrastructure.exchange_manager import ExchangeManager
from src.shared.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MarketSnapshot")

class MarketSnapshot:
    def __init__(self):
        self.strategy = HybridStrategy(settings=settings)
        self.ai = GlobalTradingAI(settings=settings)
        self.timeframe = "5m"
        try:
            self.mgr = ExchangeManager(settings=settings)
            self.exchange = self.mgr.exchange
            logger.info(f"✅ Підключено до {self.exchange.id}")
        except Exception as e:
            logger.critical(f"🔥 Помилка підключення: {e}")
            sys.exit(1)

    async def run(self):
        logger.info("\n🔬 Діагностика ринку...")
        print("-" * 65)
        print(f"{'Статус':<8} | {'Пара':<10} | {'ШІ Впевненість':<15} | {'Сигнал'}")
        print("-" * 65)

        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT"]
        for symbol in symbols:
            try:
                ohlcv = await self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=100)
                if not ohlcv:
                    print(f"❌ Немає даних для {symbol}")
                    continue
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                _, ai_conf = self.ai.predict(df)
                signal, meta = self.strategy.get_signal(df, ai_confidence=ai_conf, in_position=False)
                icon = "🟢 BUY" if signal == "BUY" else ("🔴 SELL" if signal == "SELL" else "⚪ HOLD")
                print(f"{icon:<8} | {symbol:<10} | {ai_conf:>14.2f} | {signal}")
            except Exception as e:
                logger.error(f"Помилка аналізу {symbol}: {e}")
        print("-" * 65)
        logger.info("🏁 Сканування завершено.")
        if hasattr(self.exchange, 'close'):
            await self.exchange.close()

if __name__ == "__main__":
    asyncio.run(MarketSnapshot().run())