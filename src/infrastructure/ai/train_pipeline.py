import os
import glob
import pandas as pd
import numpy as np
import joblib
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from src.shared.config import settings
# Синхронізація з ботом!
from src.infrastructure.ai.feature_engineer import calculate_features, get_feature_columns

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("AIPipeline")

class AITrainingPipeline:
    def __init__(self, model_save_path: str = "data_storage/models/global_rf_v4.pkl"):
        self.model_save_path = model_save_path
        
        # ВИКОРИСТОВУЄМО ТІ САМІ ФІЧІ, ЩО І ПРЕДИКТОР
        self.features = get_feature_columns()
        
        os.makedirs(os.path.dirname(self.model_save_path), exist_ok=True)
        
        self.model = RandomForestClassifier(
            n_estimators=300, # Більше фіч -> більше дерев
            max_depth=12,
            min_samples_split=10,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )

    def create_labels(self, df: pd.DataFrame, lookahead: int = 4, target_profit_pct: float = 0.005) -> pd.DataFrame:
        df = df.copy()
        df['Future_High'] = df['high'].shift(-lookahead).rolling(window=lookahead, min_periods=1).max()
        df['Target'] = ((df['Future_High'] - df['close']) / df['close']) >= target_profit_pct
        df['Target'] = df['Target'].astype(int)
        return df.dropna()

    def train_model(self, df: pd.DataFrame):
        logger.info("Підготовка датасету...")
        for col in self.features:
            if col not in df.columns:
                raise ValueError(f"Відсутня фіча: {col}")

        X = df[self.features]
        y = df['Target']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        
        logger.info(f"Тренування на {len(X_train)} зразках. Розподіл класів:\n{y_train.value_counts()}")
        self.model.fit(X_train, y_train)

        predictions = self.model.predict(X_test)
        logger.info("\n" + classification_report(y_test, predictions))
        
        importance = pd.DataFrame({
            'Feature': self.features,
            'Importance': self.model.feature_importances_
        }).sort_values(by='Importance', ascending=False)
        logger.info(f"Важливість параметрів (Топ-15):\n{importance.head(15)}")

        joblib.dump(self.model, self.model_save_path)
        logger.info(f"✅ Модель успішно збережена у {self.model_save_path}")

if __name__ == "__main__":
    pipeline = AITrainingPipeline()
    history_files = glob.glob("data_storage/history/*.csv")
    
    if not history_files:
        logger.error("❌ Не знайдено жодного CSV файлу в data_storage/history/")
        exit(1)
        
    logger.info(f"Знайдено {len(history_files)} файлів для навчання.")
    
    all_data = []
    for file in history_files:
        try:
            df = pd.read_csv(file)
            if len(df) < 100:
                continue
                
            # ВИКОРИСТОВУЄМО ТУ САМУ ФУНКЦІЮ!
            df_features = calculate_features(df)
            
            if df_features.empty:
                continue
                
            df_labeled = pipeline.create_labels(df_features)
            all_data.append(df_labeled)
            
        except Exception as e:
            logger.warning(f"Помилка обробки {file}: {e}")
            
    if not all_data:
        logger.error("❌ Після розрахунку фіч не залишилося валідних даних!")
        exit(1)
        
    master_df = pd.concat(all_data, ignore_index=True)
    logger.info(f"✅ Фінальний датасет зібрано: {len(master_df)} рядків.")
    pipeline.train_model(master_df)