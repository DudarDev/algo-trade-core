"""Запускає аналітику та виводить рекомендації."""
import sys
sys.path.insert(0, '.')

from src.analytics.metrics import get_trades_df, calculate_metrics
from src.analytics.optimizer import optimize_parameters
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("📊 Збір метрик за останні 30 днів...")
    df = get_trades_df(days_back=30)
    metrics = calculate_metrics(df)
    logger.info(f"Метрики: {metrics}")
    
    logger.info("🔍 Пошук оптимальних параметрів...")
    suggestions = optimize_parameters()
    if suggestions:
        logger.info(f"Рекомендації: {suggestions}")
    else:
        logger.info("Немає нових рекомендацій")
