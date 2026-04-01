import os
import glob
import logging
import pandas as pd
from typing import List
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
import joblib

# Імпортуємо наш мозок з основної папки додатку
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.ai_brain import GlobalTradingAI

# Налаштування логера
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("GlobalTrainer")

class ModelTrainer:
    """Модуль для агрегації даних та навчання єдиної глобальної ML-моделі."""
    
    def __init__(self, data_dir: str = 'app/data/history/', model_path: str = 'app/data/models/global_rf_v4.pkl'):
        self.data_dir = data_dir
        self.model_path = model_path
        self.ai = GlobalTradingAI(model_path=self.model_path)
        
    def load_and_prepare_data(self) -> pd.DataFrame:
        """Зчитує всі CSV, генерує фічі та зливає їх в один датасет."""
        all_files = glob.glob(os.path.join(self.data_dir, "*.csv"))
        if not all_files:
            logger.error(f"❌ Не знайдено CSV файлів у {self.data_dir}")
            return pd.DataFrame()

        dataset_parts: List[pd.DataFrame] = []
        
        for file in all_files:
            symbol_name = os.path.basename(file).split('_')[0]
            logger.info(f"Обробка даних для {symbol_name}...")
            
            try:
                df = pd.read_csv(file)
                # 1. Генерація фіч (RSI, MACD, ATR, OBV тощо)
                df_features = self.ai.prepare_features(df)
                
                # 2. Генерація таргетів (Чи буде профіт > 1.5 ATR)
                df_labeled = self.ai.create_labels(df_features)
                
                if not df_labeled.empty:
                    dataset_parts.append(df_labeled)
                    
            except Exception as e:
                logger.error(f"Помилка обробки файлу {file}: {e}")

        # Зливаємо все разом
        full_dataset = pd.concat(dataset_parts, ignore_index=True)
        logger.info(f"✅ Датасет сформовано. Загальна кількість зразків: {len(full_dataset)}")
        return full_dataset

    def train(self):
        """Головний процес тренування."""
        data = self.load_and_prepare_data()
        if data.empty:
            return

        feature_cols = self.ai.feature_cols
        X = data[feature_cols]
        y = data['Target']

        logger.info(f"🧠 Починаю навчання RandomForest на {len(X)} рядках. Це може зайняти час...")
        
        # Базова модель з балансуванням класів (бо прибуткових угод завжди менше)
        rf_base = RandomForestClassifier(
            n_estimators=150, 
            max_depth=10, 
            min_samples_split=20,
            min_samples_leaf=10, 
            class_weight='balanced', 
            n_jobs=-1, 
            random_state=42
        )
        
        # Калібрування ймовірностей для точніших сигналів
        calibrated_model = CalibratedClassifierCV(estimator=rf_base, method='sigmoid', cv=5)
        calibrated_model.fit(X, y)
        
        # Збереження моделі
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(calibrated_model, self.model_path)
        logger.info(f"🎉 Модель успішно навчена та збережена у: {self.model_path}")

if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.train()