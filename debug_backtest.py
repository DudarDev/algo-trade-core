import os
import sys
import logging
import pandas as pd
from dotenv import load_dotenv

# Додаємо корінь проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ai_brain import TradingAI
from app.strategy import Strategy
from app.exchange_manager import ExchangeManager
from app.config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Backtest")

class DebugBacktest:
    def __init__(self):
        load_dotenv()
        self.strategy = Strategy()
        self.ai = TradingAI()
        self.timeframe = Config.TIMEFRAME
        
        # 🔥 ФІКС ХАРДКОДУ: Використовуємо наш менеджер замість прямого ccxt.binance()
        try:
            self.mgr = ExchangeManager("binanceus")
            self.exchange = self.mgr.exchange
            logger.info(f"✅ Підключено до біржі (Binance US). Таймфрейм: {self.timeframe}")
        except Exception as e:
            logger.critical(f"🔥 Помилка підключення до біржі: {e}")
            sys.exit(1)

    def run(self):
        logger.info("🔬 ЗАПУСК ДІАГНОСТИКИ (BACKTEST)...")
        for symbol in Config.SYMBOLS:
            logger.info(f"🔍 Аналіз {symbol}...")
            try:
                # Беремо останні 500 свічок
                ohlcv = self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=500)
                if not ohlcv:
                    logger.warning(f"⚠️ Немає даних для {symbol}")
                    continue
                    
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                
                # 1. Запитуємо думку AI
                _, ai_conf = self.ai.predict(df, symbol)
                
                # 2. Рахуємо технічні індикатори
                df_tech = self.strategy.calculate_indicators(df)
                
                # 3. Запитуємо сигнал у Стратегії
                signal, meta = self.strategy.get_signal(df_tech, ai_confidence=ai_conf, in_position=False)
                
                logger.info(f"📊 Результат {symbol}: Сигнал = {signal} | Впевненість AI = {ai_conf:.2f}")
                logger.info(f"   Деталі: {meta}\n")
                
            except Exception as e:
                logger.error(f"❌ Помилка під час аналізу {symbol}: {e}\n")

if __name__ == "__main__":
    debugger = DebugBacktest()
    debugger.run()