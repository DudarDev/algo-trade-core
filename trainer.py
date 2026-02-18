import os
import sys
import time
import logging
import pandas as pd
from dotenv import load_dotenv

# Гарантуємо, що Python бачить корінь проекту (щоб імпорти app. працювали)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ai_brain import TradingAI
from app.config import Config
from app.strategy import Strategy
from app.exchange_manager import ExchangeManager

# Налаштування логів
logging.basicConfig(level=logging.INFO, format='%(asctime)s - TRAINER - %(message)s')
logger = logging.getLogger("Trainer")

class ModelTrainer:
    def __init__(self):
        load_dotenv() # Обов'язково вантажимо .env для ключів біржі
        self.ai = TradingAI()
        self.strategy = Strategy()
        
        # Підключаємося через менеджер до Binance.US
        try:
            self.mgr = ExchangeManager("binanceus")
            self.exchange = self.mgr.exchange
            logger.info("✅ Успішно підключено до біржі для завантаження даних.")
        except Exception as e:
            logger.critical(f"🔥 Не вдалося підключитися до біржі: {e}")
            sys.exit(1)

    def fetch_training_data(self, symbol: str) -> pd.DataFrame:
        """Завантажує максимально доступну історію свічок."""
        logger.info(f"📥 Завантаження даних для {symbol}...")
        try:
            # Беремо ліміт з конфігу (замість хардкоду 1000)
            limit = getattr(Config, 'TRAINING_LOOKBACK', 1000)
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=Config.TIMEFRAME, limit=limit)
            
            if not ohlcv:
                return pd.DataFrame()
            
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            return df
        except Exception as e:
            logger.error(f"❌ API Error {symbol}: {e}")
            return pd.DataFrame()

    def run(self):
        """Запускає цикл тренування для всіх активних пар."""
        logger.info(f"💪 Початок тренування AI моделей (Timeframe: {Config.TIMEFRAME})...")
        
        symbols = Config.SYMBOLS 
        success_count = 0
        
        for symbol in symbols:
            # 1. Завантаження сирих даних
            df = self.fetch_training_data(symbol)
            
            if df.empty or len(df) < 250:
                logger.warning(f"⚠️ {symbol}: Пропущено (замало сирих даних: {len(df)})")
                continue
            
            # 2. 🔥 ДОДАВАННЯ ФІЧ (Feature Engineering)
            df = self.strategy.calculate_indicators(df)
            
            # 3. Очистка від NaN (EMA200 з'їдає перші 200 рядків)
            df.dropna(inplace=True)
            
            if df.empty or len(df) < 50:
                logger.warning(f"⚠️ {symbol}: Пропущено (замало чистих даних після індикаторів).")
                continue

            logger.info(f"🧠 Навчання {symbol} на {len(df)} чистих свічках...")
            
            # 4. Тренування і збереження
            try:
                self.ai.train_model(df, symbol)
                success_count += 1
                logger.info(f"✅ Модель для {symbol} успішно оновлено!")
            except Exception as e:
                logger.error(f"❌ Помилка під час тренування {symbol}: {e}")
            
            # Пауза, щоб не злити ліміти (Rate Limit) біржі
            time.sleep(1.5)
            
        logger.info(f"🎉 Тренування завершено! Успішно оновлено: {success_count}/{len(symbols)} моделей.")

if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.run()