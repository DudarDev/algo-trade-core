import os
import sys
import logging
import pandas as pd
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ai_brain import GlobalTradingAI
from app.strategy import Strategy
from app.exchange_manager import ExchangeManager
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DebugBacktest")

class DebugBacktest:
    def __init__(self):
        load_dotenv()
        self.strategy = Strategy()
        self.ai = GlobalTradingAI()
        self.timeframe = "5m"
        
        try:
            self.mgr = ExchangeManager("binanceus")
            self.exchange = self.mgr.exchange
            logger.info(f"✅ Підключено до біржі. Таймфрейм: {self.timeframe}")
        except Exception as e:
            logger.critical(f"🔥 Помилка: {e}")
            sys.exit(1)

    def run(self):
        logger.info("\n🔬 ЗАПУСК ДІАГНОСТИКИ (Current Market Snapshot)...")
        print("-" * 50)
        
        symbols = ["BTC/USDT", "ETH/USDT"]
        for symbol in symbols:
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=100)
                if not ohlcv: continue
                    
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                _, ai_conf = self.ai.predict(df)
                df_tech = self.strategy.calculate_indicators(df)
                
                result = self.strategy.get_signal(df_tech, ai_confidence=ai_conf, in_position=False)
                signal = result[0] if isinstance(result, tuple) else result
                
                status_icon = "🟢" if signal == "BUY" else "⚪"
                print(f"{status_icon} {symbol:<10} | AI Conf: {ai_conf:.2f} | Signal: {signal}")
                
            except Exception as e:
                logger.error(f"❌ Помилка ({symbol}): {e}")
        
        print("-" * 50)

if __name__ == "__main__":
    debugger = DebugBacktest()
    debugger.run()