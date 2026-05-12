"""Suggest optimal strategy parameters based on recent trading history."""
import logging
from src.analytics.metrics import get_trades_df, calculate_metrics
from src.shared.config import Settings

logger = logging.getLogger(__name__)

def suggest_parameters() -> dict:
    """Return a dictionary of recommended environment variables to change."""
    settings = Settings()
    cur_conf = getattr(settings, 'CONFIDENCE_THRESHOLD', 0.6)
    cur_rsi = getattr(settings, 'RSI_BUY_LIMIT', 70)

    df = get_trades_df(days_back=7)
    m = calculate_metrics(df)

    suggestions = {}
    if m['total_trades'] > 0:
        if m['win_rate'] < 40:
            suggestions['CONFIDENCE_THRESHOLD'] = min(0.9, cur_conf + 0.1)
        elif m['win_rate'] > 60:
            suggestions['CONFIDENCE_THRESHOLD'] = max(0.3, cur_conf - 0.1)

        if m['profit_factor'] < 1.1:
            suggestions['RSI_BUY_LIMIT'] = min(80, cur_rsi + 5)
        elif m['profit_factor'] > 1.5:
            suggestions['RSI_BUY_LIMIT'] = max(50, cur_rsi - 5)

    return suggestions

def optimize_parameters() -> dict:
    """Entry point – currently uses heuristic rules. Can be extended with grid search."""
    return suggest_parameters()
