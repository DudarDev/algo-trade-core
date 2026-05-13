"""Перенавчає ML-модель на основі нових даних."""
import os
import sys
import logging
from pathlib import Path
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV

# Додаємо шлях до src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.engine.application.ai_brain import GlobalTradingAI
from src.shared.config import Settings

logger = logging.getLogger(__name__)

def retrain_model(data_dir: str = None) -> bool:
    """Перенавчає модель на основі даних з data_storage/history."""
    if data_dir is None:
        data_dir = BASE_DIR / "data_storage" / "history"
    else:
        data_dir = Path(data_dir)
    
    model_path = BASE_DIR / "data_storage" / "models" / "global_rf_v4.pkl"
    
    try:
        settings = Settings()
        ai = GlobalTradingAI(settings=settings)
        
        # Завантажуємо всі CSV файли
        import glob
        files = glob.glob(str(data_dir / "*.csv"))
        if not files:
            logger.error("Немає файлів для навчання")
            return False
        
        # Створюємо датасет
        all_data = []
        for file in files:
            df = pd.read_csv(file)
            df_features = ai.prepare_features(df)
            if not df_features.empty:
                # Створюємо мітки (спрощена логіка - можна використати create_labels з train_global_model)
                df_features['Target'] = ((df_features['close'].shift(-3) - df_features['close']) / df_features['close'] > 0.002).astype(int)
                df_features = df_features.dropna(subset=['Target'])
                if not df_features.empty:
                    all_data.append(df_features)
        
        if not all_data:
            logger.error("Не вдалося створити датасет")
            return False
        
        combined = pd.concat(all_data, ignore_index=True)
        logger.info(f"Датасет: {len(combined)} рядків")
        
        # Навчаємо нову модель
        X = combined[ai.feature_cols]
        y = combined['Target']
        
        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            class_weight='balanced_subsample',
            n_jobs=-1,
            random_state=42
        )
        
        calibrated = CalibratedClassifierCV(estimator=rf, method='sigmoid', cv=5)
        calibrated.fit(X, y)
        
        # Зберігаємо
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(calibrated, model_path)
        logger.info(f"Модель збережено: {model_path}")
        return True
        
    except Exception as e:
        logger.error(f"Помилка перенавчання: {e}")
        return False
