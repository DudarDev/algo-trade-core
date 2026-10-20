"""Перенавчає ML-модель на основі нових даних."""
import os
import sys
import glob
import logging
from pathlib import Path
import pandas as pd

# Додаємо шлях до src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.infrastructure.ai.predictor import GlobalTradingAI
from src.infrastructure.ai.train_pipeline import AITrainingPipeline
from src.shared.config import settings

logger = logging.getLogger(__name__)

def retrain_model(data_dir: str = None) -> bool:
    """Перенавчає модель на основі даних з data_storage/history з Triple-Barrier розміткою."""
    if data_dir is None:
        data_dir = BASE_DIR / "data_storage" / "history"
    else:
        data_dir = Path(data_dir)
    
    model_path = BASE_DIR / "data_storage" / "models" / "global_rf_v4.pkl"
    
    try:
        pipeline = AITrainingPipeline(model_save_path=str(model_path))
        ai = GlobalTradingAI(settings=settings)
        
        files = glob.glob(str(data_dir / "*.csv"))
        if not files:
            logger.error("Немає файлів для навчання")
            return False
        
        all_data = []
        for file in files:
            try:
                df = pd.read_csv(file)
                df_features = ai.prepare_features(df)
                if not df_features.empty:
                    df_labeled = pipeline.create_labels(df_features)
                    if not df_labeled.empty:
                        all_data.append(df_labeled)
            except Exception as e:
                logger.warning(f"Пропуск {file}: {e}")
        
        if not all_data:
            logger.error("Не вдалося створити датасет")
            return False
        
        combined = pd.concat(all_data, ignore_index=True)
        pipeline.train_model(combined)
        return True
        
    except Exception as e:
        logger.error(f"Помилка перенавчання: {e}", exc_info=True)
        return False
