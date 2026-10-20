import sys
import glob
import logging
from pathlib import Path
from typing import List
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from src.infrastructure.ai.predictor import GlobalTradingAI
from src.infrastructure.ai.train_pipeline import AITrainingPipeline
from src.shared.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("GlobalTrainer")

class ModelTrainer:
    def __init__(self):
        self.data_dir = BASE_DIR / "data_storage" / "history"
        self.model_path = BASE_DIR / "data_storage" / "models" / "global_rf_v4.pkl"
        self.ai = GlobalTradingAI(settings=settings)
        self.pipeline = AITrainingPipeline(model_save_path=str(self.model_path))

    def load_and_prepare_data(self) -> pd.DataFrame:
        all_files = glob.glob(str(self.data_dir / "*.csv"))
        if not all_files:
            logger.error(f"❌ Не знайдено CSV файлів у {self.data_dir}")
            return pd.DataFrame()

        dataset_parts: List[pd.DataFrame] = []
        for file in all_files:
            symbol_name = Path(file).stem.split('_')[0]
            logger.info(f"Обробка та Triple-Barrier розмітка для {symbol_name}...")
            try:
                df = pd.read_csv(file)
                df_features = self.ai.prepare_features(df)
                if df_features.empty:
                    continue
                df_labeled = self.pipeline.create_labels(df_features)
                if not df_labeled.empty:
                    dataset_parts.append(df_labeled)
            except Exception as e:
                logger.error(f"Помилка обробки файлу {file}: {e}")

        if not dataset_parts:
            return pd.DataFrame()

        full_dataset = pd.concat(dataset_parts, ignore_index=True)
        logger.info(f"✅ Датасет сформовано. Загальна кількість свічок: {len(full_dataset)}")
        class_counts = full_dataset['Target'].value_counts().to_dict()
        logger.info(f"📊 Баланс класів: {class_counts}")
        return full_dataset

    def train(self):
        data = self.load_and_prepare_data()
        if data.empty:
            logger.error("❌ Немає валідних даних для навчання!")
            return
        self.pipeline.train_model(data)

if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.train()
