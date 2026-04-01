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
logger = logging.getLogger("DebugBacktest")

class DebugBacktest:
    def __init__(self):
        load_dotenv()
        self.strategy = Strategy()
        self.ai = TradingAI()
        self.timeframe = Config.TIMEFRAME
        
        try:
            self.mgr = ExchangeManager("binanceus")
            self.exchange = self.mgr.exchange
            logger.info(f"✅ Підключено до біржі. Таймфрейм: {self.timeframe}")
            logger.info(f"⚙️ Config: Threshold={Config.AI_CONFIDENCE_THRESHOLD}, SL={Config.STOP_LOSS_ATR_MULT} ATR, TP={Config.TAKE_PROFIT_ATR_MULT} ATR")
        except Exception as e:
            logger.critical(f"🔥 Помилка підключення до біржі: {e}")
            sys.exit(1)

    def run(self):
        logger.info("\n🔬 ЗАПУСК ДІАГНОСТИКИ (Current Market Snapshot)...")
        print("-" * 70)
        
        for symbol in Config.SYMBOLS:
            try:
                # Беремо останні 500 свічок (таймфрейм з конфігу, зараз це 5m)
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
                
                status_icon = "🟢" if signal == "BUY" else "⚪"
                print(f"{status_icon} {symbol:<10} | AI Conf: {ai_conf:.2f} | RSI: {meta.get('rsi', 0):>4.1f} | ADX: {meta.get('adx', 0):>4.1f} | Trend: {meta.get('trend', 'N/A'):<4}")
                
                if signal == "BUY":
                    print(f"    🎯 РІШЕННЯ: СИГНАЛ НА ПОКУПКУ! Причина: {meta.get('reason')}")
                elif ai_conf >= Config.AI_CONFIDENCE_THRESHOLD:
                    print(f"    ⚠️ AI впевнений ({ai_conf:.2f}), але технічні фільтри не пройдені (RSI або ADX або Trend).")
                
            except Exception as e:
                logger.error(f"❌ Помилка під час аналізу {symbol}: {e}")
        
        print("-" * 70)

if __name__ == "__main__":
    debugger = DebugBacktest()
    debugger.run()