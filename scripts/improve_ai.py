"""Автоматичне покращення AI та стратегії."""
import sys
import logging
from pathlib import Path

# Додаємо корінь проєкту в sys.path, якщо скрипт запускається не з кореневої теки
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ai_optimizer.pair_analyzer import analyze_pairs
from src.ai_optimizer.model_retrainer import retrain_model
from src.analytics.optimizer import optimize_parameters
from src.analytics.metrics import get_trades_df, calculate_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

def safe_get_metrics(df):
    """Безпечно отримує метрики, навіть якщо даних немає."""
    if df is None or df.empty:
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0
        }
    try:
        return calculate_metrics(df)
    except Exception as e:
        logger.error(f"Помилка розрахунку метрик: {e}")
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0
        }

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОПТИМІЗАЦІЇ AI ТА СТРАТЕГІЇ")
    logger.info("=" * 60)

    # 1. Аналіз ефективності пар
    logger.info("📊 Аналіз ефективності пар...")
    try:
        pairs_df = analyze_pairs(days_back=30)
        if not pairs_df.empty:
            logger.info("Топ-5 найкращих пар:")
            for _, row in pairs_df.head(5).iterrows():
                logger.info(f"  {row['symbol']}: Win Rate {row['win_rate']:.1f}%, PnL {row['total_pnl']:.2f}, Trades {row['total_trades']}")
            logger.info("Топ-5 найгірших пар:")
            for _, row in pairs_df.tail(5).iterrows():
                logger.info(f"  {row['symbol']}: Win Rate {row['win_rate']:.1f}%, PnL {row['total_pnl']:.2f}, Trades {row['total_trades']}")
        else:
            logger.warning("Немає даних для аналізу пар.")
    except Exception as e:
        logger.error(f"Помилка аналізу пар: {e}")

    # 2. Перенавчання ML-моделі
    logger.info("🧠 Перенавчання ML-моделі...")
    try:
        if retrain_model():
            logger.info("✅ Модель успішно перенавчена")
        else:
            logger.warning("⚠️ Не вдалося перенавчити модель")
    except Exception as e:
        logger.error(f"Помилка перенавчання: {e}")

    # 3. Загальні метрики
    logger.info("📈 Загальні метрики:")
    try:
        df = get_trades_df(days_back=30)
        metrics = safe_get_metrics(df)
        logger.info(f"  Total Trades: {metrics.get('total_trades', 0)}")
        logger.info(f"  Win Rate: {metrics.get('win_rate', 0.0):.1f}%")
        logger.info(f"  Profit Factor: {metrics.get('profit_factor', 0.0):.2f}")
        logger.info(f"  Total PnL: ${metrics.get('total_pnl', 0.0):.2f}")
        # Ось виправлення — безпечне отримання max_drawdown
        max_dd = metrics.get('max_drawdown', 0.0)
        logger.info(f"  Max Drawdown: {max_dd:.2f}%")
    except Exception as e:
        logger.error(f"Помилка отримання метрик: {e}")

    # 4. Рекомендації щодо параметрів
    logger.info("💡 Рекомендації щодо параметрів:")
    try:
        suggestions = optimize_parameters()
        if suggestions:
            for key, value in suggestions.items():
                logger.info(f"  {key} = {value}")
        else:
            logger.info("  Немає нових рекомендацій")
    except Exception as e:
        logger.error(f"Помилка оптимізації параметрів: {e}")

    logger.info("=" * 60)
    logger.info("✅ ОПТИМІЗАЦІЯ ЗАВЕРШЕНА")
    logger.info("=" * 60)

if __name__ == '__main__':
    main()