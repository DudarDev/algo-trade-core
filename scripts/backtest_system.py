import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
import logging

# --- КОНФІГ ДЛЯ ТЕСТУ ---
CONF = {
    'TIMEFRAME': '5m',
    'TP': 0.015,       # Take Profit 1.5%
    'SL': 0.010,       # Stop Loss 1.0%
    'TRAILING': True,
    'TRAIL_START': 0.005,
    'TRAIL_DROP': 0.003
}

def run_backtest(symbol='BTC/USDT', days=7):
    print(f"⏳ Завантажую історію {symbol} за {days} днів...")
    exchange = ccxt.binanceus()
    
    # Качаємо багато даних
    since = exchange.milliseconds() - (days * 24 * 60 * 60 * 1000)
    all_candles = []
    
    while since < exchange.milliseconds():
        candles = exchange.fetch_ohlcv(symbol, timeframe=CONF['TIMEFRAME'], since=since, limit=1000)
        if not candles: break
        all_candles += candles
        since = candles[-1][0] + 1
        
    df = pd.DataFrame(all_candles, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
    df['date'] = pd.to_datetime(df['ts'], unit='ms')
    
    print(f"📊 Дані отримано: {len(df)} свічок. Починаю симуляцію...")
    
    # --- СИМУЛЯЦІЯ ---
    balance = 1000
    position = None # {'entry': 50000, 'high': 50000}
    trades = 0
    wins = 0
    
    # Простий сигнал: RSI < 30 (Купити)
    df['RSI'] = ta.rsi(df['close'], length=14)
    
    for i in range(20, len(df)):
        row = df.iloc[i]
        price = row['close']
        
        # 1. ЛОГІКА КУПІВЛІ
        if position is None:
            if row['RSI'] < 30: # Сигнал на покупку
                position = {'entry': price, 'high': price}
                # print(f"🟢 BUY at {price:.2f} ({row['date']})")
        
        # 2. ЛОГІКА ПРОДАЖУ (Trailing)
        else:
            entry = position['entry']
            # Оновлюємо максимум
            if price > position['high']: position['high'] = price
            
            pnl = (price - entry) / entry
            drawdown = (position['high'] - price) / position['high']
            
            sell = False
            reason = ""
            
            # Stop Loss
            if pnl < -CONF['SL']:
                sell = True
                reason = "SL"
            
            # Trailing Take Profit
            elif CONF['TRAILING'] and pnl > CONF['TRAIL_START']:
                if drawdown > CONF['TRAIL_DROP']:
                    sell = True
                    reason = "Trailing"
            
            if sell:
                profit = balance * pnl
                balance += profit
                trades += 1
                if pnl > 0: wins += 1
                # print(f"🔴 SELL at {price:.2f} | PnL: {pnl*100:.2f}% ({reason}) | Bal: {balance:.2f}")
                position = None

    print("-" * 30)
    print(f"🏁 РЕЗУЛЬТАТ ЗА {days} ДНІВ:")
    print(f"💰 Фінальний баланс: {balance:.2f} USDT")
    print(f"📈 Всього угод: {trades}")
    print(f"🏆 Прибуткових: {wins} (WinRate: {wins/trades*100 if trades > 0 else 0:.1f}%)")
    print("-" * 30)

if __name__ == "__main__":
    run_backtest()