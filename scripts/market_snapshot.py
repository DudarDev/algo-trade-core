import os
import sys
import logging
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
    """Утиліта для швидкої діагностики поточного стану ринку."""
    def __init__(self):
        self.strategy = HybridStrategy(settings=settings)
        self.ai = GlobalTradingAI(settings=settings)
        self.timeframe = "5m"
        
        try:
            # Зміни 'binanceus' на свою біржу, якщо потрібно
            self.mgr = ExchangeManager("binanceus")
            self.exchange = self.mgr.exchange
            logger.info(f"✅ Підключено до {self.exchange.id}. Таймфрейм: {self.timeframe}")
        except Exception as e:
            logger.critical(f"🔥 Помилка підключення: {e}")
            sys.exit(1)

    def run(self):
        logger.info("\n🔬 ЗАПУСК ДІАГНОСТИКИ (Поточний зріз ринку)...")
        print("-" * 55)
        
        # Можеш додати сюди більше пар
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        
        for symbol in symbols:
            try:
                # Тягнемо свіжі свічки
                ohlcv = self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=100)
                if not ohlcv: continue
                    
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Запитуємо ШІ та Стратегію
                _, ai_conf = self.ai.predict(df)
                signal, meta = self.strategy.get_signal(df, ai_confidence=ai_conf, in_position=False)
                
                # Візуалізація
                status_icon = "🟢" if signal == "BUY" else ("🔴" if signal == "SELL" else "⚪")
                print(f"{status_icon} {symbol:<10} | ШІ Впевненість: {ai_conf:.2f} | Сигнал: {signal}")
                
            except Exception as e:
                logger.error(f"❌ Помилка ({symbol}): {e}")
        
        print("-" * 55)

if __name__ == "__main__":
    scanner = MarketSnapshot()
    scanner.run()