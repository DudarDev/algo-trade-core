"""Run analytics and print recommended parameter changes."""
import sys
sys.path.insert(0, '.')

from src.analytics.metrics import get_trades_df, calculate_metrics
from src.analytics.optimizer import optimize_parameters
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("📊 Collecting 30-day trade metrics...")
    df = get_trades_df(days_back=30)
    metrics = calculate_metrics(df)
    logger.info(f"Metrics: {metrics}")

    logger.info("🔍 Searching for optimal parameters...")
    suggestions = optimize_parameters()
    if suggestions:
        logger.info(f"Suggestions: {suggestions}")
    else:
        logger.info("No new suggestions.")
