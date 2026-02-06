import pandas as pd
import logging
import time
from app.ai_brain import TradingAI
from app.config import Config
from app.strategy import Strategy
from app.exchange_manager import ExchangeManager # <--- FIX: Використовуємо менеджер

# Налаштування логів
logging.basicConfig(level=logging.INFO, format='%(asctime)s - TRAINER - %(message)s')
logger = logging.getLogger("Trainer")

class ModelTrainer:
    def __init__(self):
        self.ai = TradingAI()
        self.strategy = Strategy()
        
        # 👇 FIX: Підключаємося через менеджер до Binance.US
        try:
            self.mgr = ExchangeManager("binanceus")
            self.exchange = self.mgr.exchange
        except Exception as e:
            logger.critical(f"🔥 Не вдалося підключитися до біржі: {e}")
            raise e

    def fetch_training_data(self, symbol: str) -> pd.DataFrame:
        """Завантажує максимально доступну історію."""
        logger.info(f"📥 Завантаження даних для {symbol}...")
        try:
            # Binance US ліміт - 1000 свічок.
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=Config.TIMEFRAME, limit=1000)
            if not ohlcv:
                return pd.DataFrame()
            
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            return df
        except Exception as e:
            logger.error(f"❌ API Error {symbol}: {e}")
            return pd.DataFrame()

    def run(self):
        """Запускає цикл тренування для всіх пар."""
        logger.info(f"💪 Початок тренування AI моделей (Timeframe: {Config.TIMEFRAME})...")
        
        symbols = Config.SYMBOLS 
        success_count = 0
        
        for symbol in symbols:
            # 1. Завантаження сирих даних
            df = self.fetch_training_data(symbol)
            
            if len(df) < 500:
                logger.warning(f"⚠️ {symbol}: Пропущено (мало даних: {len(df)})")
                continue
            
            # 2. 🔥 ДОДАВАННЯ ФІЧ (Feature Engineering)
            # Використовуємо ту саму логіку, що і в реальному боті
            df = self.strategy.calculate_indicators(df)
            
            # 3. Очистка від NaN (через EMA200 перші 200 рядків будуть пусті)
            df.dropna(inplace=True)
            
            if df.empty:
                logger.warning(f"⚠️ {symbol}: Дані пусті після розрахунку індикаторів.")
                continue

            logger.info(f"🧠 Навчання {symbol} на {len(df)} свічках...")
            
            # 4. Тренування і збереження
            self.ai.train_model(df, symbol)
            success_count += 1
            
            # Пауза, щоб не злити API ліміти
            time.sleep(1)
            
        logger.info(f"🎉 Тренування завершено! Успішно оновлено: {success_count}/{len(symbols)} моделей.")

if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.run()