import ccxt
import pandas as pd
import os

def download_candles(symbol='BTC/USDT', timeframe='1h', days=30):
    print(f"📉 Починаю скачування {symbol} за останні {days} днів...")
    
    exchange = ccxt.binance()
    limit = days * 24 
    
    try:
        # Створюємо папку data, якщо її немає
        if not os.path.exists('data'):
            os.makedirs('data')

        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=1000)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        filename = f"data/{symbol.replace('/', '_')}_history.csv"
        df.to_csv(filename, index=False)
        
        print(f"✅ Успішно! Дані збережено у файл: {filename}")
        print(f"📊 Всього рядків: {len(df)}")
        
    except Exception as e:
        print(f"❌ Помилка: {e}")

if __name__ == "__main__":
    download_candles(symbol='BTC/USDT', timeframe='1h', days=30)