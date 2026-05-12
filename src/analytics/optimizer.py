"""Пропонує оптимальні параметри стратегії на основі історичних даних."""
import logging
from itertools import product
from src.analytics.metrics import get_trades_df, calculate_metrics
from src.shared.config import Settings

logger = logging.getLogger(__name__)

def suggest_parameters() -> dict:
    """Повертає рекомендовані параметри для .env."""
    # Отримуємо поточні параметри
    settings = Settings()
    current_conf = getattr(settings, 'CONFIDENCE_THRESHOLD', 0.6)
    current_rsi = getattr(settings, 'RSI_BUY_LIMIT', 70)
    
    # Пропонуємо невеликі зміни на основі простого аналізу
    df = get_trades_df(days_back=7)
    metrics = calculate_metrics(df)
    
    suggestions = {}
    
    if metrics['total_trades'] > 0:
        # Якщо Win Rate низький, підвищити поріг впевненості
        if metrics['win_rate'] < 40:
            suggestions['CONFIDENCE_THRESHOLD'] = min(0.9, current_conf + 0.1)
        elif metrics['win_rate'] > 60:
            suggestions['CONFIDENCE_THRESHOLD'] = max(0.3, current_conf - 0.1)
        
        # Якщо прибутковість низька, зменшити ліміт RSI
        if metrics['profit_factor'] < 1.1:
            suggestions['RSI_BUY_LIMIT'] = min(80, current_rsi + 5)
        elif metrics['profit_factor'] > 1.5:
            suggestions['RSI_BUY_LIMIT'] = max(50, current_rsi - 5)
    
    return suggestions

def optimize_parameters() -> dict:
    """Перебирає комбінації параметрів та повертає найкращі (заглушка)."""
    # Тут можна реалізувати grid search на історичних даних,
    # але поки що повертаємо евристичні рекомендації
    return suggest_parameters()
