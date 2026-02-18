import os
import sys
import pandas as pd
import pandas_ta as ta
import logging

# Гарантуємо, що Python бачить корінь проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import Config
from app.ai_brain import TradingAI
from app.exchange_manager import ExchangeManager

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Backtest")

class Backtester:
    def __init__(self):
        # 🔥 ФІКС ХАРДКОДУ: Використовуємо ExchangeManager для обходу блокування
        try:
            self.mgr = ExchangeManager("binanceus")
            self.exchange = self.mgr.exchange
        except Exception as e:
            logger.critical(f"🔥 Помилка підключення до біржі: {e}")
            sys.exit(1)
            
        self.ai = TradingAI()
        self.symbols = Config.SYMBOLS
        self.timeframe = Config.TIMEFRAME
        
        # Завантажуємо параметри з Config
        self.sl_multiplier = Config.STOP_LOSS_ATR_MULT
        self.tp_multiplier = Config.TAKE_PROFIT_ATR_MULT
        self.risk_per_trade = Config.USDT_PER_TRADE
        self.initial_balance = 1000.0

    def run(self, days=7):
        # Розрахунок ліміту свічок
        limit = int(days * 24 * (60 / 5))
        
        print(f"\n📊 ЗАПУСК БЕКТЕСТУ (Останні {days} днів)...")
        print(f"⚙️  Конфіг: SL={self.sl_multiplier}xATR | TP={self.tp_multiplier}xATR | Threshold={Config.AI_CONFIDENCE_THRESHOLD}")
        print(f"🎯 Фільтри: ADX > 0.20 | RVOL > 1.0 (Sniper Mode)")
        print("-" * 65)
        print(f"{'PAIR':<10} | {'TRADES':<6} | {'WIN RATE':<9} | {'PnL (USDT)':<10} | {'FINAL BAL':<10}")
        print("-" * 65)

        total_pnl = 0
        
        for symbol in self.symbols:
            try:
                # 1. Завантаження історичних даних
                ohlcv = self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                
                # 2. Підготовка AI-фіч (тут розраховується RVOL та ADX)
                processed_df = self.ai.prepare_features(df)
                if processed_df.empty: continue

                # Перестраховка: якщо ATR не порахувався в ai_brain, рахуємо тут
                if 'ATR' not in processed_df.columns:
                    processed_df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
                
                balance = self.initial_balance
                trades_count = 0
                wins = 0
                
                # 3. Основний цикл симуляції
                # Пропускаємо перші 200 свічок для коректності індикаторів
                for i in range(200, len(processed_df) - 1):
                    row = processed_df.iloc[i]
                    
                    # 🔥 SNIPER FILTER:
                    if row['ADX'] < 0.20 or row['RVOL'] < 1.0: 
                        continue 

                    # Якщо фільтри пройдені, запитуємо AI
                    slice_df = df.iloc[:i+1]
                    signal, conf = self.ai.predict(slice_df, symbol)

                    if signal == "BUY":
                        entry_price = row['close']
                        atr = row['ATR']
                        
                        # Розрахунок рівнів
                        sl_price = entry_price - (atr * self.sl_multiplier)
                        tp_price = entry_price + (atr * self.tp_multiplier)
                        
                        outcome = "HOLD"
                        
                        # Перевірка майбутнього (Look-forward loop)
                        for j in range(i + 1, min(i + 60, len(processed_df))):
                            future_candle = processed_df.iloc[j]
                            
                            if future_candle['low'] <= sl_price:
                                outcome = "LOSS"
                                break
                            elif future_candle['high'] >= tp_price:
                                outcome = "WIN"
                                break
                        
                        if outcome != "HOLD":
                            trades_count += 1
                            if outcome == "WIN":
                                wins += 1
                                pnl = (self.risk_per_trade / entry_price) * (tp_price - entry_price)
                                balance += pnl
                            else:
                                pnl = (self.risk_per_trade / entry_price) * (entry_price - sl_price)
                                balance -= abs(pnl)

                # Статистика по парі
                win_rate = (wins / trades_count * 100) if trades_count > 0 else 0
                net_pnl = balance - self.initial_balance
                pnl_str = f"{net_pnl:>10.2f}"
                
                print(f"{symbol:<10} | {trades_count:<6} | {win_rate:>7.1f}% | {pnl_str} | {balance:>10.2f}")
                total_pnl += net_pnl

            except Exception as e:
                print(f"❌ Error testing {symbol}: {e}")

        print("-" * 65)
        print(f"💰 ЗАГАЛЬНИЙ PnL: {total_pnl:.2f} USDT")

if __name__ == "__main__":
    tester = Backtester()
    tester.run()