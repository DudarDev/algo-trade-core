import pytest
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from src.analytics.metrics import calculate_metrics, get_trades_df

def test_empty_df():
    result = calculate_metrics(pd.DataFrame())
    assert result['total_trades'] == 0
    assert result['win_rate'] == 0.0
    assert result['profit_factor'] == 0.0
    assert result['total_pnl'] == 0.0

def test_no_sell_trades():
    df = pd.DataFrame([
        {'side': 'BUY', 'pnl': 0.0, 'timestamp': datetime.now(timezone.utc)},
        {'side': 'BUY', 'pnl': 0.0, 'timestamp': datetime.now(timezone.utc)},
    ])
    result = calculate_metrics(df)
    assert result['total_trades'] == 0
    assert result['win_rate'] == 0.0
    assert result['profit_factor'] == 0.0

def test_with_trades():
    df = pd.DataFrame([
        {'side': 'SELL', 'pnl': 5.0},
        {'side': 'SELL', 'pnl': -2.0},
        {'side': 'SELL', 'pnl': 3.0},
        {'side': 'BUY', 'pnl': 0.0},
    ])
    result = calculate_metrics(df, initial_balance=100.0)
    assert result['total_trades'] == 3
    assert result['win_rate'] == 66.67
    assert result['profit_factor'] == 4.0
    assert result['total_pnl'] == 6.0
    assert result['avg_win'] == 4.0
    assert result['avg_loss'] == -2.0
    assert result['balance'] == 106.0

def test_all_wins():
    df = pd.DataFrame([
        {'side': 'SELL', 'pnl': 10.0},
        {'side': 'SELL', 'pnl': 20.0},
    ])
    result = calculate_metrics(df, initial_balance=1000.0)
    assert result['total_trades'] == 2
    assert result['win_rate'] == 100.0
    assert result['profit_factor'] == 30.0
    assert result['total_pnl'] == 30.0
    assert result['avg_loss'] == 0.0
    assert result['max_drawdown'] == 0.0

def test_all_losses():
    df = pd.DataFrame([
        {'side': 'SELL', 'pnl': -20.0},
        {'side': 'SELL', 'pnl': -30.0},
    ])
    result = calculate_metrics(df, initial_balance=1000.0)
    assert result['total_trades'] == 2
    assert result['win_rate'] == 0.0
    assert result['profit_factor'] == 0.0
    assert result['total_pnl'] == -50.0
    assert result['balance'] == 950.0
    assert result['max_drawdown'] > 0.0

def test_get_trades_df_mock():
    mock_session = MagicMock()
    mock_trade = MagicMock()
    mock_trade.timestamp = datetime.now(timezone.utc)
    mock_trade.symbol = "BTC/USDT"
    mock_trade.side = "SELL"
    mock_trade.price = 50000.0
    mock_trade.amount = 0.01
    mock_trade.cost = 500.0
    mock_trade.pnl = 15.0

    mock_session.query.return_value.filter.return_value.all.return_value = [mock_trade]

    with patch('src.analytics.metrics.SessionLocal', return_value=mock_session):
        df = get_trades_df(days_back=7)
        assert not df.empty
        assert len(df) == 1
        assert df.iloc[0]['symbol'] == "BTC/USDT"
        assert df.iloc[0]['pnl'] == 15.0
