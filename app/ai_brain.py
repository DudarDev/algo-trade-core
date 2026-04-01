import pandas as pd
import numpy as np
import pandas_ta as ta
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
import joblib
import os
import logging
from typing import Tuple, Optional, List
from app.config import settings

logger = logging.getLogger(__name__)

class GlobalTradingAI:
    def __init__(self, model_path: str = 'app/data/models/global_rf_v4.pkl'):
        self.model_path = model_path
        self.confidence_threshold = settings.CONFIDENCE_THRESHOLD 
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.model: Optional[CalibratedClassifierCV] = self._load_model()
        
        # Розширений список ознак
        self.base_features: List[str] = [
            'RSI', 'MACD_HIST', 'BB_WIDTH', 'BB_POS', 'ATR_PCT', 
            'ADX', 'STOCH_K', 'STOCH_D', 'OBV_SLOPE', 'EMA_DIST_20', 
            'EMA_DIST_50', 'LOG_RET', 'VOL_SPIKE', 'BUY_PRESSURE'
        ]
        self.lag_features: List[str] = ['RSI', 'LOG_RET', 'MACD_HIST']
        self.lags: List[int] = [1, 2, 3]
        self.feature_cols: List[str] = self._get_feature_names()

    def _load_model(self) -> Optional[CalibratedClassifierCV]:
        if os.path.exists(self.model_path):
            try:
                return joblib.load(self.model_path)
            except Exception as e:
                logger.error(f"Помилка завантаження моделі: {e}")
        return None

    def _get_feature_names(self) -> List[str]:
        cols = self.base_features.copy()
        for feature in self.lag_features:
            for lag in self.lags:
                cols.append(f"{feature}_lag_{lag}")
        return cols

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or len(df) < 60:
            return pd.DataFrame()
        
        data = df.copy().sort_values('timestamp')

        # Momentum
        data['RSI'] = ta.rsi(data['close'], length=14) / 100.0
        
        macd = ta.macd(data['close'])
        if macd is not None and not macd.empty:
            data['MACD_HIST'] = macd.iloc[:, 1] # Histogram
        else:
            data['MACD_HIST'] = 0.0

        stoch = ta.stoch(data['high'], data['low'], data['close'])
        if stoch is not None and not stoch.empty:
            data['STOCH_K'] = stoch.iloc[:, 0] / 100.0
            data['STOCH_D'] = stoch.iloc[:, 1] / 100.0
        else:
            data['STOCH_K'], data['STOCH_D'] = 0.5, 0.5

        # Volatility
        bb = ta.bbands(data['close'], length=20, std=2.0)
        if bb is not None and not bb.empty:
            data['BB_WIDTH'] = (bb.iloc[:, 0] - bb.iloc[:, 2]) / bb.iloc[:, 1]
            data['BB_POS'] = (data['close'] - bb.iloc[:, 2]) / (bb.iloc[:, 0] - bb.iloc[:, 2])
        else:
            data['BB_WIDTH'], data['BB_POS'] = 0.0, 0.5

        data['ATR'] = ta.atr(data['high'], data['low'], data['close'], length=14)
        data['ATR_PCT'] = data['ATR'] / data['close']

        # Trend
        adx_df = ta.adx(data['high'], data['low'], data['close'], length=14)
        data['ADX'] = adx_df.iloc[:, 0] / 100.0 if adx_df is not None and not adx_df.empty else 0.0

        ema20 = ta.ema(data['close'], length=20)
        ema50 = ta.ema(data['close'], length=50)
        data['EMA_DIST_20'] = (data['close'] - ema20) / (ema20 + 1e-9)
        data['EMA_DIST_50'] = (data['close'] - ema50) / (ema50 + 1e-9)

        # Volume & Price Action
        data['OBV'] = ta.obv(data['close'], data['volume'])
        data['OBV_SLOPE'] = data['OBV'].diff(3) / (data['OBV'].abs() + 1e-9)
        
        vol_sma = data['volume'].rolling(window=20).mean()
        vol_std = data['volume'].rolling(window=20).std()
        data['VOL_SPIKE'] = (data['volume'] > (vol_sma + 2 * vol_std)).astype(int)
        
        data['BUY_PRESSURE'] = (data['close'] - data['low']) / (data['high'] - data['low'] + 1e-9)
        data['LOG_RET'] = np.log(data['close'] / data['close'].shift(1))

        # Lags
        for feature in self.lag_features:
            for lag in self.lags:
                data[f"{feature}_lag_{lag}"] = data[feature].shift(lag)

        return data.replace([np.inf, -np.inf], np.nan).dropna()

    def create_labels(self, data: pd.DataFrame, horizon: int = 12) -> pd.DataFrame:
        rr_ratio = settings.RISK_REWARD_RATIO
        data = data.copy()
        
        # Симуляція шляху ціни (Path Dependency)
        data['Target'] = np.nan
        
        for i in range(len(data) - horizon):
            entry_price = data['close'].iloc[i]
            atr = data['ATR'].iloc[i]
            
            stop_loss = entry_price - (atr * 1.5)
            take_profit = entry_price + (atr * 1.5 * rr_ratio)
            
            future_window = data.iloc[i+1 : i+1+horizon]
            
            hit_tp = False
            hit_sl = False
            
            for _, row in future_window.iterrows():
                if row['low'] <= stop_loss:
                    hit_sl = True
                    break
                if row['high'] >= take_profit:
                    hit_tp = True
                    break
            
            if hit_tp and not hit_sl:
                data.loc[data.index[i], 'Target'] = 1
            elif hit_sl:
                data.loc[data.index[i], 'Target'] = 0
            else:
                data.loc[data.index[i], 'Target'] = 0 # Якщо нічого не торкнулося, вважаємо неуспіхом

        return data.dropna(subset=['Target'])

    def predict(self, df: pd.DataFrame) -> Tuple[str, float]:
        if self.model is None:
            return "HOLD", 0.0
        processed_df = self.prepare_features(df)
        if processed_df.empty: 
            return "HOLD", 0.0
        try:
            last_row = processed_df[self.feature_cols].iloc[[-1]]
            proba = float(self.model.predict_proba(last_row)[0][1])
            signal = "BUY" if proba >= self.confidence_threshold else "HOLD"
            return signal, proba
        except Exception as e:
            logger.error(f"Помилка передбачення: {e}", exc_info=True)
            return "HOLD", 0.0
