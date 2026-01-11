import sys
import os

# --- МАГІЯ ШЛЯХІВ (Додаємо це, щоб Python бачив папку app) ---
# Це каже скрипту: "Шукай модулі на одну папку вище від цього файлу"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# -------------------------------------------------------------

import pandas as pd
import ccxt
from app.ai_brain import TradingAI
import logging

# Налаштування виводу
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

def run_debug(symbol='SOL/USDT'):
    print(f"\n🧠 === DEBUGGING BRAIN FOR {symbol} === 🧠")
    
    # 1. Ініціалізація
    try:
        brain = TradingAI()
        print("✅ Brain Initialized. Threshold:", brain.CONFIDENCE_THRESHOLD)
    except Exception as e:
        print(f"❌ Failed to initialize Brain: {e}")
        return

    # 2. Отримання даних (Deep History)
    print(f"📥 Downloading deep history for {symbol}...")
    try:
        df = brain.fetch_deep_history(symbol)
    except Exception as e:
        print(f"❌ Error fetching history: {e}")
        return
    
    if df.empty:
        print("❌ FAILED to fetch data. Check internet or exchange connection.")
        return

    print(f"📊 Downloaded {len(df)} candles.")
    last_close = df['close'].iloc[-1]
    print(f"💲 Current Price: {last_close}")

    # 3. Підготовка фіч (як це робить бот всередині)
    print("⚙️ Calculating technical indicators (RSI, BB, RVOL)...")
    df_features = brain.prepare_features(df)
    
    if df_features.empty:
        print("❌ Not enough data to calculate features.")
        return
        
    last_row = df_features.iloc[[-1]]
    print("\n--- LATEST CANDLE FEATURES ---")
    print(last_row[['RSI', 'BB_POS', 'RVOL', 'ATR_PCT']])
    print("-" * 30)

    # 4. Примусове тренування
    print("\n🎓 Forcing Model Retraining...")
    # Емулюємо тренування на завантажених даних
    brain.train_new_model(df, symbol=symbol) 
    
    if not brain.is_trained:
        print("❌ MODEL FAILED TO TRAIN. Possible reasons:")
        print("   1. Market volatility is too low (target 0.4% not reached).")
        print("   2. Not enough positive examples in history.")
        return

    # 5. "Хірургічне втручання" - дістаємо ймовірності вручну
    features_cols = ['RSI', 'BB_POS', 'RVOL', 'ATR_PCT']
    
    try:
        # Прямий доступ до моделі sklearn
        # Перевіряємо, чи є scaler (якщо він використовується в ai_brain)
        if hasattr(brain, 'scaler') and brain.scaler:
             X_input = brain.scaler.transform(last_row[features_cols])
        else:
             X_input = last_row[features_cols]

        raw_proba = brain.model.predict_proba(X_input)[0]
        prob_buy = raw_proba[1] # Ймовірність класу 1 (BUY)
        
        print(f"\n🤖 REAL AI CONFIDENCE: {prob_buy:.4f} ({(prob_buy*100):.2f}%)")
        print(f"🎯 THRESHOLD NEEDED:   {brain.CONFIDENCE_THRESHOLD}")
        
        if prob_buy > brain.CONFIDENCE_THRESHOLD:
            print("✅ SIGNAL: BUY! (Бот мав би купити)")
        elif prob_buy > 0.60:
            print("⚠️ SIGNAL: CLOSE CALL. (Бот думає, але боїться)")
        else:
            print("zzZ SIGNAL: SLEEP. (Ситуація нецікава)")
            
    except Exception as e:
        print(f"❌ Error during manual prediction: {e}")

if __name__ == "__main__":
    # Тестуємо на найбільш волатильній монеті
    run_debug('SOL/USDT')
    # run_debug('DOGE/USDT') # Можна розкоментувати