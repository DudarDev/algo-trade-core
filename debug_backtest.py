import pandas as pd
import ccxt
import pandas_ta as ta
import logging
import numpy as np
from app.ai_brain import TradingAI
from app.config import Config

logging.basicConfig(level=logging.INFO, format='%(message)s')

class DebugBacktester:
    def __init__(self):
        self.exchange = ccxt.binance()
        self.ai = TradingAI()
        self.symbols = ['BTC/USDT', 'SOL/USDT'] # Тестуємо тільки 2 пари для швидкості
        self.timeframe = Config.TIMEFRAME

    def run(self):
        print(f"\n🔬 ЗАПУСК ДІАГНОСТИКИ...")
        
        for symbol in self.symbols:
            print(f"\n🔍 Аналіз {symbol}...")
            # Беремо 500 свічок
            ohlcv = self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=500)
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            
            processed_df = self.ai.prepare_features(df)
            processed_df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            
            # Збираємо статистику передбачень
            probs = []
            signals = 0
            
            print(f"   Датасет: {len(processed_df)} точок. Скануємо...")

            for i in range(50, len(processed_df)):
                # Емуляція реального часу
                slice_df = df.iloc[:i+1]
                
                # Предикт
                _, proba = self.ai.predict(slice_df, symbol)
                probs.append(proba)
                
                # Логуємо тільки високі ймовірності, щоб не спамити
                if proba > 0.55:
                    current_adx = processed_df.iloc[i]['ADX']
                    print(f"   [{i}] Conf: {proba:.2f} | ADX: {current_adx:.1f} | Price: {slice_df.iloc[-1]['close']}")
                    
                    if proba >= 0.70:
                        signals += 1

            # Статистика по парі
            avg_conf = np.mean(probs) if probs else 0
            max_conf = np.max(probs) if probs else 0
            print(f"   📊 Статистика {symbol}:")
            print(f"      Середня впевненість: {avg_conf:.4f}")
            print(f"      Максимальна впевненість: {max_conf:.4f}")
            print(f"      Кількість сигналів (>0.70): {signals}")

if __name__ == "__main__":
    debugger = DebugBacktester()
    debugger.run()