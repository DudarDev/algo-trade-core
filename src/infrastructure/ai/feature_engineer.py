import pandas as pd
import numpy as np
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)

# Константи для фіч (Єдине джерело істини)
BASE_FEATURES = [
    'RSI', 'MACD_HIST', 'BB_WIDTH', 'BB_POS', 'ATR_PCT',
    'ADX', 'STOCH_K', 'STOCH_D', 'OBV_SLOPE', 'EMA_DIST_20',
    'EMA_DIST_50', 'LOG_RET', 'VOL_SPIKE', 'BUY_PRESSURE'
]
LAG_FEATURES = ['RSI', 'LOG_RET', 'MACD_HIST']
LAGS = [1, 2, 3]

def get_feature_columns() -> list:
    """Генерує фінальний список усіх назв колонок, включаючи лаги."""
    cols = BASE_FEATURES.copy()
    for feature in LAG_FEATURES:
        for lag in LAGS:
            cols.append(f"{feature}_lag_{lag}")
    return cols

def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
    """Універсальна функція генерації фіч (Використовується і для Тренування, і для Торгівлі)"""
    if df is None or df.empty or len(df) < 60:
        return pd.DataFrame()

    data = df.copy().sort_values('timestamp').reset_index(drop=True)
    feature_cols = get_feature_columns()

    try:
        # 1. Базові індикатори
        data['RSI'] = ta.rsi(data['close'], length=14) / 100.0
        
        macd = ta.macd(data['close'])
        data['MACD_HIST'] = macd.iloc[:, 1] if macd is not None else 0.0

        stoch = ta.stoch(data['high'], data['low'], data['close'])
        if stoch is not None:
            data['STOCH_K'] = stoch.iloc[:, 0] / 100.0
            data['STOCH_D'] = stoch.iloc[:, 1] / 100.0
        else:
            data[['STOCH_K', 'STOCH_D']] = 0.5

        bb = ta.bbands(data['close'], length=20, std=2.0)
        if bb is not None:
            data['BB_WIDTH'] = (bb.iloc[:, 0] - bb.iloc[:, 2]) / (bb.iloc[:, 1] + 1e-9)
            bb_range = np.where((bb.iloc[:, 0] - bb.iloc[:, 2]) == 0, 1e-9, (bb.iloc[:, 0] - bb.iloc[:, 2]))
            data['BB_POS'] = (data['close'] - bb.iloc[:, 2]) / bb_range
        else:
            data[['BB_WIDTH', 'BB_POS']] = [0.0, 0.5]

        # 2. Волатильність та тренд
        atr = ta.atr(data['high'], data['low'], data['close'], length=14)
        data['ATR_PCT'] = atr / data['close'] if atr is not None else 0.0

        adx = ta.adx(data['high'], data['low'], data['close'])
        data['ADX'] = adx.iloc[:, 0] / 100.0 if adx is not None else 0.0

        obv = ta.obv(data['close'], data['volume'])
        if obv is not None:
            data['OBV_SLOPE'] = obv.diff(periods=5) / (obv.rolling(window=20).std() + 1e-9)
        else:
            data['OBV_SLOPE'] = 0.0

        # 3. Ковзні середні та дистанції
        ema20 = ta.ema(data['close'], length=20)
        ema50 = ta.ema(data['close'], length=50)
        data['EMA_DIST_20'] = (data['close'] - ema20) / (ema20 + 1e-9) if ema20 is not None else 0.0
        data['EMA_DIST_50'] = (data['close'] - ema50) / (ema50 + 1e-9) if ema50 is not None else 0.0

        # 4. Ринковий тиск та об'ємні фічі
        data['LOG_RET'] = np.log(data['close'] / data['close'].shift(1))
        vol_ma = data['volume'].rolling(window=20).mean()
        data['VOL_SPIKE'] = data['volume'] / (vol_ma + 1e-9)
        
        price_spread = data['high'] - data['low']
        data['BUY_PRESSURE'] = (data['close'] - data['low']) / (price_spread + 1e-9)

        # 5. Генерація лагів (Lag Features)
        for feature in LAG_FEATURES:
            for lag in LAGS:
                data[f"{feature}_lag_{lag}"] = data[feature].shift(lag)

        # Очищення нескінченних значень та перевірка фінального набору колонок
        data.replace([np.inf, -np.inf], np.nan, inplace=True)
        
        missing_cols = [col for col in feature_cols if col not in data.columns]
        if missing_cols:
            logger.error(f"❌ Помилка Data Pipeline: відсутні колонки: {missing_cols}")
            return pd.DataFrame()

        return data.dropna(subset=feature_cols)

    except Exception as e:
        logger.error(f"❌ Критична помилка під час Feature Engineering: {e}", exc_info=True)
        return pd.DataFrame()