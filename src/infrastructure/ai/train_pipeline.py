import os
import glob
import logging
from pathlib import Path
from typing import List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, roc_auc_score

from src.shared.config import settings
from src.infrastructure.ai.feature_engineer import calculate_features, get_feature_columns

logger = logging.getLogger("AIPipeline")

def create_triple_barrier_labels(
    df: pd.DataFrame, 
    tp_mult: float = 1.8, 
    sl_mult: float = 1.2, 
    horizon: int = 12, 
    min_fee_buffer: float = 0.0025
) -> pd.DataFrame:
    """
    Професійна потрійна бар'єрна розмітка (Triple-Barrier Method):
    - Верхній бар'єр (Take Profit): ціна зростає на tp_mult * ATR
    - Нижній бар'єр (Stop Loss): ціна падає на sl_mult * ATR
    - Горизонт: horizon свічок (наприклад, 1 година = 12 свічок по 5м)
    - Враховується обов'язкове покриття біржових комісій (min_fee_buffer)
    """
    if df is None or len(df) < horizon + 10:
        return pd.DataFrame()

    data = df.copy().reset_index(drop=True)
    n = len(data)
    targets = np.zeros(n, dtype=int)
    valid_mask = np.zeros(n, dtype=bool)

    closes = data['close'].values
    highs = data['high'].values
    lows = data['low'].values
    atr_pcts = data['ATR_PCT'].values if 'ATR_PCT' in data.columns else np.full(n, 0.015)

    for i in range(n - horizon):
        entry = closes[i]
        if entry <= 0:
            continue

        atr_val = atr_pcts[i] * entry
        atr_val = max(atr_val, entry * 0.004)

        tp = entry + (atr_val * tp_mult)
        sl = entry - (atr_val * sl_mult)

        hit_tp = False
        hit_sl = False

        for k in range(i + 1, i + horizon + 1):
            if lows[k] <= sl:
                hit_sl = True
                break
            if highs[k] >= tp:
                hit_tp = True
                break

        if hit_tp and not hit_sl:
            gross_return = (tp - entry) / entry
            if gross_return > min_fee_buffer:
                targets[i] = 1
        else:
            targets[i] = 0

        valid_mask[i] = True

    data['Target'] = targets
    return data[valid_mask].copy()


class AITrainingPipeline:
    def __init__(self, model_save_path: Optional[str] = None):
        if model_save_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            model_save_path = str(project_root / settings.MODEL_PATH)
        
        self.model_save_path = Path(model_save_path)
        self.features = get_feature_columns()
        self.model_save_path.parent.mkdir(parents=True, exist_ok=True)

    def create_labels(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        return create_triple_barrier_labels(df, **kwargs)

    def train_model(self, df: pd.DataFrame):
        logger.info(f"🧠 Підготовка датасету з {len(df)} рядків та {len(self.features)} фіч...")
        
        missing_cols = [c for c in self.features if c not in df.columns]
        if missing_cols:
            raise ValueError(f"Відсутні фічі у датасеті: {missing_cols}")

        X = df[self.features].copy()
        y = df['Target'].copy()

        # Заміна можливих NaN або inf
        X.replace([np.inf, -np.inf], np.nan, inplace=True)
        X.fillna(0.0, inplace=True)

        # Time-Series Split (без перемішування, щоб уникнути витоку даних з майбутнього)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        class_counts = y_train.value_counts().to_dict()
        logger.info(f"📊 Тренувальна вибірка: {len(X_train)} свічок (Розподіл класів: {class_counts})")

        # 1. Базовий Random Forest із захистом від перенавчання
        base_rf = RandomForestClassifier(
            n_estimators=150,
            max_depth=10,
            min_samples_split=30,
            min_samples_leaf=15,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )

        # 2. Калібратор ймовірностей з часовою валідацією
        tscv = TimeSeriesSplit(n_splits=3)
        calibrated_model = CalibratedClassifierCV(
            estimator=base_rf,
            method='sigmoid',
            cv=tscv
        )

        logger.info("⚙️ Навчання та калібрування моделі через TimeSeriesSplit...")
        calibrated_model.fit(X_train, y_train)

        # 3. Валідація на відкладеній вибірці (Out-of-Sample)
        y_pred = calibrated_model.predict(X_test)
        y_proba = calibrated_model.predict_proba(X_test)[:, 1]

        logger.info("\n" + "="*50)
        logger.info("🎯 ОЦІНКА ТОЧНОСТІ МОДЕЛІ (Out-of-Sample Test)")
        logger.info("="*50)
        logger.info("\n" + classification_report(y_test, y_pred, zero_division=0))

        try:
            auc = roc_auc_score(y_test, y_proba)
            logger.info(f"⭐ ROC-AUC Score: {auc:.4f}")
        except Exception:
            pass

        # 4. Збереження навченої моделі
        joblib.dump(calibrated_model, self.model_save_path)
        logger.info(f"✅ Високоточна калібрована модель збережена: {self.model_save_path}")
        return calibrated_model
