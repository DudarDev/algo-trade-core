import os
import glob
import pandas as pd
import numpy as np
import pandas_ta as ta
import joblib
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("AIPipeline")

class AITrainingPipeline:
    def __init__(self, model_save_path: str = "data_storage/models/global_rf_v4.pkl"):
        self.model_save_path = model_save_path
        self.features = ['RSI', 'EMA_DIST_50', 'MACD_HIST', 'ATR_PCT', 'ADX', 'VOL_CHANGE']
        
        # Переконуємось, що папка для моделі існує
        os.makedirs(os.path.dirname(self.model_save_path), exist_ok=True)
        
        # Ініціалізуємо ліс зі збалансованими вагами, щоб він не ігнорував рідкісні, але прибуткові сетапи
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=10,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Розрахунок технічних індикаторів для машинного навчання"""
        df = df.copy()
        
        # Базові індикатори
        df['RSI'] = ta.rsi(df['close'], length=14)
        
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None:
            df['MACD_HIST'] = macd['MACDh_12_26_9']
        else:
            df['MACD_HIST'] = 0.0

        # Трендові індикатори
        df['EMA_50'] = ta.ema(df['close'], length=50)
        # Додаємо захист від ділення на нуль
        df['EMA_DIST_50'] = np.where(
            df['EMA_50'] == 0, 
            0, 
            (df['close'] - df['EMA_50']) / df['EMA_50']
        )
        
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx is not None:
            df['ADX'] = adx['ADX_14']
        else:
            df['ADX'] = 0.0

        # Волатильність та об'єм
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        # Додаємо захист від ділення на нуль
        df['ATR_PCT'] = np.where(
            df['close'] == 0, 
            0, 
            df['ATR'] / df['close']
        )
        df['VOL_CHANGE'] = df['volume'].pct_change()

        # === КРИТИЧНЕ ОЧИЩЕННЯ ДАНИХ ===
        # Замінюємо нескінченності (inf) на NaN, а потім видаляємо всі NaN
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        return df.dropna()

    def create_labels(self, df: pd.DataFrame, lookahead: int = 4, target_profit_pct: float = 0.005) -> pd.DataFrame:
        """
        Створюємо Label (Таргет). 
        1 - якщо ціна виросла на target_profit_pct (напр. 0.5%) протягом наступних 4 свічок.
        0 - якщо ні.
        """
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
                raise ValueError(f"Відсутня фіча: {col}")

        X = df[self.features]
        y = df['Target']

        # Розділяємо дані (80% тренування, 20% тест), не перемішуючи час (shuffle=False)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        
        logger.info(f"Тренування на {len(X_train)} зразках. Розподіл класів:\n{y_train.value_counts()}")
        self.model.fit(X_train, y_train)

        # Оцінка
        predictions = self.model.predict(X_test)
        logger.info("\n" + classification_report(y_test, predictions))
        
        # Важливість фіч
        importance = pd.DataFrame({
            'Feature': self.features,
            'Importance': self.model.feature_importances_
        }).sort_values(by='Importance', ascending=False)
        logger.info(f"Важливість параметрів:\n{importance}")

        # Збереження
        joblib.dump(self.model, self.model_save_path)
        logger.info(f"✅ Модель успішно збережена у {self.model_save_path}")

# === ЗАПУСК НАВЧАННЯ ===
if __name__ == "__main__":
    pipeline = AITrainingPipeline()
    
    # Шукаємо всі CSV файли з історією в папці
    history_files = glob.glob("data_storage/history/*.csv")
    
    if not history_files:
        logger.error("❌ Не знайдено жодного CSV файлу в data_storage/history/")
        exit(1)
        
    logger.info(f"Знайдено {len(history_files)} файлів для навчання.")
    
    # Збираємо всі дані в один великий DataFrame
    all_data = []
    for file in history_files:
        try:
            df = pd.read_csv(file)
            
            # Якщо датасет занадто малий для розрахунку індикаторів
            if len(df) < 100:
                continue
                
            # Розрахунок фіч (RSI, ADX, MACD тощо)
            df_features = pipeline.engineer_features(df)
            
            # Розмітка (де був профіт > 0.5%)
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