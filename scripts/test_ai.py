#!/usr/bin/env python3
import asyncio
import logging
import sys
from pathlib import Path

# Додаємо корінь проєкту в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.engine.infrastructure.exchange_manager import ExchangeManager
from src.engine.application.ai_brain import GlobalTradingAI
from src.shared.config import Settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

async def main():
    # Ініціалізуємо біржу
    exchange = ExchangeManager()
    await exchange.initialize()
    
    # Отримуємо налаштування (з .env або стандартні)
    settings = Settings()
    
    # Ініціалізуємо AI
    ai = GlobalTradingAI(settings)
    
    # Перевіряємо пари з твого списку волатильних
    test_symbols = ['SAGA/USDT', 'A2Z/USDT', 'DEGO/USDT', 'BTC/USDT']
    
    for symbol in test_symbols:
        logger.info(f"\n--- Отримую дані для {symbol} ---")
        try:
            # Отримуємо 100 свічок (5-хвилинок) для аналізу
            klines = await exchange.get_klines(symbol, interval='5m', limit=100)
            if klines is None or len(klines) < 60:
                logger.warning(f"Недостатньо даних для {symbol}")
                continue
            
            # Перетворюємо в DataFrame
            df = exchange.klines_to_dataframe(klines)
            df['symbol'] = symbol  # додаємо символ для логування
            
            # Отримуємо сигнал
            signal, proba = ai.predict(df)
            logger.info(f"Результат для {symbol}: сигнал={signal}, впевненість={proba:.4f}")
            
        except Exception as e:
            logger.error(f"Помилка при обробці {symbol}: {e}", exc_info=True)
    
    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())