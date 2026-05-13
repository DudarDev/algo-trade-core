"""Автоматичне покращення AI та стратегії."""
import sys
import logging
sys.path.insert(0, '.')

from src.ai_optimizer.pair_analyzer import analyze_pairs, get_best_pairs, get_worst_pairs
from src.ai_optimizer.model_retrainer import retrain_model
from src.analytics.optimizer import optimize_parameters
from src.analytics.metrics import get_trades_df, calculate_metrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОПТИМІЗАЦІЇ AI ТА СТРАТЕГІЇ")
    logger.info("=" * 60)
    
    # 1. Аналіз пар
    logger.info("📊 Аналіз ефективності пар...")
    pairs_df = analyze_pairs(days_back=30)
    if not pairs_df.empty:
        logger.info(f"Топ-5 найкращих пар:")
        for _, row in pairs_df.head(5).iterrows():
            logger.info(f"  {row['symbol']}: Win Rate {row['win_rate']:.1f}%, PnL {row['total_pnl']:.2f}, Trades {row['total_trades']}")
        
        logger.info(f"Топ-5 найгірших пар:")
        for _, row in pairs_df.tail(5).iterrows():
            logger.info(f"  {row['symbol']}: Win Rate {row['win_rate']:.1f}%, PnL {row['total_pnl']:.2f}, Trades {row['total_trades']}")
    
    # 2. Перенавчання моделі
    logger.info("🧠 Перенавчання ML-моделі...")
    if retrain_model():
        logger.info("✅ Модель успішно перенавчена")
    else:
        logger.warning("⚠️ Не вдалося перенавчити модель")
    
    # 3. Аналіз загальних метрик
    logger.info("📈 Загальні метрики:")
    df = get_trades_df(days_back=30)
    metrics = calculate_metrics(df)
    logger.info(f"  Total Trades: {metrics['total_trades']}")
    logger.info(f"  Win Rate: {metrics['win_rate']:.1f}%")
    logger.info(f"  Profit Factor: {metrics['profit_factor']:.2f}")
    logger.info(f"  Total PnL: ${metrics['total_pnl']:.2f}")
    logger.info(f"  Max Drawdown: {metrics['max_drawdown']:.2f}%")
    
    # 4. Рекомендації щодо параметрів
    logger.info("💡 Рекомендації щодо параметрів:")
    suggestions = optimize_parameters()
    if suggestions:
        for key, value in suggestions.items():
            logger.info(f"  {key} = {value}")
    else:
        logger.info("  Немає нових рекомендацій")
    
    logger.info("=" * 60)
    logger.info("✅ ОПТИМІЗАЦІЯ ЗАВЕРШЕНА")
    logger.info("=" * 60)
