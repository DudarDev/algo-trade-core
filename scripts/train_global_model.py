import os
import sys
import glob
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
import joblib

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from src.engine.application.ai_brain import GlobalTradingAI
from src.shared.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("GlobalTrainer")

class ModelTrainer:
    def __init__(self):
        self.data_dir = BASE_DIR / "data_storage" / "history"
        self.model_path = BASE_DIR / "data_storage" / "models" / "global_rf_v4.pkl"
        self.ai = GlobalTradingAI(settings=settings)

    def create_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Пом'якшена розмітка: профіт > 0.2% за наступні 3 свічки."""
        data = df.copy()
        future_returns = (data['close'].shift(-3) - data['close']) / data['close']
        data['Target'] = (future_returns > 0.002).astype(int)  # Було 0.005, стало 0.002
        return data.dropna(subset=['Target'])

    def load_and_prepare_data(self) -> pd.DataFrame:
        all_files = glob.glob(str(self.data_dir / "*.csv"))
        if not all_files:
            logger.error(f"❌ Не знайдено CSV файлів у {self.data_dir}")
            return pd.DataFrame()

        dataset_parts: List[pd.DataFrame] = []
        for file in all_files:
            symbol_name = Path(file).stem.split('_')[0]
            logger.info(f"Обробка даних для {symbol_name}...")
            try:
                df = pd.read_csv(file)
                df_features = self.ai.prepare_features(df)
                if df_features.empty: continue
                df_labeled = self.create_labels(df_features)
                if not df_labeled.empty:
                    dataset_parts.append(df_labeled)
            except Exception as e:
                logger.error(f"Помилка обробки файлу {file}: {e}")

        if not dataset_parts:
            return pd.DataFrame()

        full_dataset = pd.concat(dataset_parts, ignore_index=True)
        logger.info(f"✅ Датасет сформовано. Загальна кількість рядків: {len(full_dataset)}")
        class_counts = full_dataset['Target'].value_counts()
        logger.info(f"📊 Розподіл класів: 0={class_counts.get(0,0)}, 1={class_counts.get(1,0)}")
        return full_dataset

    def train(self):
        data = self.load_and_prepare_data()
        if data.empty: return

        feature_cols = self.ai.feature_cols
        X = data[feature_cols]
        y = data['Target']

        logger.info(f"🧠 Навчання RandomForest на {len(X)} рядках...")
        rf_base = RandomForestClassifier(
            n_estimators=200,          # більше дерев
            max_depth=15,              # глибші дерева
            min_samples_split=10,
            min_samples_leaf=5,
            class_weight='balanced_subsample',  # автоматичне зважування
            n_jobs=-1,
            random_state=42
        )

        calibrated_model = CalibratedClassifierCV(estimator=rf_base, method='sigmoid', cv=5)
        calibrated_model.fit(X, y)

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(calibrated_model, self.model_path)
        logger.info(f"🎉 Модель навчена та збережена: {self.model_path}")

if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.train()
