import pytest
import pandas as pd
from src.analytics.metrics import calculate_metrics

def test_empty_df():
    result = calculate_metrics(pd.DataFrame())
    assert result['total_trades'] == 0
    assert result['profit_factor'] == 0.0

def test_with_trades():
    df = pd.DataFrame([
        {'side': 'SELL', 'pnl': 5.0},
        {'side': 'SELL', 'pnl': -2.0},
        {'side': 'SELL', 'pnl': 3.0},
        {'side': 'BUY', 'pnl': 0},
    ])
    result = calculate_metrics(df, initial_balance=100.0)
    assert result['total_trades'] == 3
    assert result['win_rate'] == 66.67
    assert result['profit_factor'] == 4.0
    assert result['total_pnl'] == 6.0
