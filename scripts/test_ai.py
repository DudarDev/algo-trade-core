import asyncio
import logging
import sys
from pathlib import Path

# Додаємо корінь проєкту в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.engine.infrastructure.exchange_manager import ExchangeManager
from src.infrastructure.ai.predictor import GlobalTradingAI
from src.shared.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

async def main():
    # Ініціалізуємо біржу з імпортованими settings
    exchange = ExchangeManager(settings)
    await exchange.initialize()
    
    # Ініціалізуємо AI
    ai = GlobalTradingAI(settings)
    
    # Перевіряємо топові ліквідні пари
    test_symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'DOGE/USDT']
    
    logger.info("="*50)
    logger.info("🧠 ТЕСТУВАННЯ СИРОЇ ВПЕВНЕНОСТІ ШІ")
    logger.info("="*50)

    for symbol in test_symbols:
        try:
            # Отримуємо 100 свічок (5-хвилинок) для аналізу
            klines = await exchange.get_klines(symbol, interval='5m', limit=100)
            if klines is None or len(klines) < 60:
                logger.warning(f"Недостатньо даних для {symbol}")
                continue
            
            # Перетворюємо в DataFrame і готуємо фічі
            df = exchange.klines_to_dataframe(klines)
            df_features = ai.prepare_features(df)
            
            if df_features.empty:
                continue
                
            # Беремо найсвіжішу свічку
            latest_features = df_features[ai.feature_cols].iloc[-1:]
            
            # Отримуємо СИРУ ймовірність (proba) від 0 до 1
            proba = ai.model.predict_proba(latest_features)[0][1]
            
            logger.info(f"📊 {symbol}: Сира впевненість ШІ = {proba:.4f} ({proba*100:.2f}%)")
            
        except Exception as e:
            logger.error(f"Помилка при обробці {symbol}: {e}")
    
    await exchange.close()
    logger.info("="*50)

if __name__ == "__main__":
    asyncio.run(main())