import os
import glob
import pandas as pd
import numpy as np
import joblib
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# Імпортуємо ваш основний конфіг та клас предиктора, щоб логіка фіч була 100% ідентичною!
from src.shared.config import settings
from src.infrastructure.ai.predictor import GlobalTradingAI

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("AIPipeline")

class AITrainingPipeline:
    def __init__(self, model_save_path: str = "data_storage/models/global_rf_v4.pkl"):
        self.model_save_path = model_save_path
        
        # Ініціалізуємо ваш AI клас (він дасть нам метод prepare_features та список feature_cols)
        # Оскільки модель ще може не існувати, ми ігноруємо попередження при ініціалізації
        self.ai_core = GlobalTradingAI(settings=settings)
        
        # Витягуємо ТОЧНО той самий список фіч, який використовуватиме бот у реальному часі!
        self.features = self.ai_core.feature_cols
        
        os.makedirs(os.path.dirname(self.model_save_path), exist_ok=True)
        
        # Збільшимо кількість дерев до 300, оскільки фіч стало набагато більше
        self.model = RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_split=10,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )

    def create_labels(self, df: pd.DataFrame, lookahead: int = 4, target_profit_pct: float = 0.005) -> pd.DataFrame:
        """Створюємо Label (Таргет). 1 - якщо ціна виросла на target_profit_pct протягом наступних lookahead свічок."""
        df = df.copy()
        
        # Шукаємо максимальну ціну в майбутньому вікні
        df['Future_High'] = df['high'].shift(-lookahead).rolling(window=lookahead, min_periods=1).max()
        
        # Визначаємо, чи досягли ми бажаного профіту
        df['Target'] = ((df['Future_High'] - df['close']) / df['close']) >= target_profit_pct
        df['Target'] = df['Target'].astype(int)
        
        return df.dropna()

    def train_model(self, df: pd.DataFrame):
        """Тренування та збереження моделі"""
        logger.info("Підготовка датасету...")
        
        # Перевіряємо наявність потрібних фіч
        for col in self.features:
            if col not in df.columns:
                raise ValueError(f"Відсутня фіча: {col}. Датасет не збігається з логікою GlobalTradingAI!")

        X = df[self.features]
        y = df['Target']

        # Розділяємо дані (80% тренування, 20% тест), не перемішуючи час
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        
        logger.info(f"Тренування на {len(X_train)} зразках. Розподіл класів:\n{y_train.value_counts()}")
        self.model.fit(X_train, y_train)

        # Оцінка
        predictions = self.model.predict(X_test)
        logger.info("\n" + classification_report(y_test, predictions))
        
        # Важливість фіч (виводимо топ-15, бо їх тепер багато)
        importance = pd.DataFrame({
            'Feature': self.features,
            'Importance': self.model.feature_importances_
        }).sort_values(by='Importance', ascending=False)
        logger.info(f"Важливість параметрів (Топ-15):\n{importance.head(15)}")

        # Збереження
        joblib.dump(self.model, self.model_save_path)
        logger.info(f"✅ Модель успішно збережена у {self.model_save_path}")


# === ЗАПУСК НАВЧАННЯ ===
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
                
            # ВИКОРИСТОВУЄМО ТУ САМУ ФУНКЦІЮ, ЩО І В ТОРГІВЛІ!
            df_features = pipeline.ai_core.prepare_features(df)
            
            if df_features.empty:
                continue
                
            # Розмітка
            df_labeled = pipeline.create_labels(df_features)
            all_data.append(df_labeled)
            
        except Exception as e:
            logger.warning(f"Помилка обробки {file}: {e}")
            
    if not all_data:
        logger.error("❌ Після розрахунку фіч не залишилося валідних даних!")
        exit(1)
        
    # Об'єднуємо всі монети в один тренувальний набір
    master_df = pd.concat(all_data, ignore_index=True)
    logger.info(f"✅ Фінальний датасет зібрано: {len(master_df)} рядків.")
    
    # Тренуємо модель
    pipeline.train_model(master_df)