"""Collects and calculates key strategy metrics from the database."""
import pandas as pd
from datetime import datetime, timedelta, timezone
from src.shared.db.session import SessionLocal
from src.shared.db.models import Trade

def get_trades_df(days_back: int = 30) -> pd.DataFrame:
    """Return DataFrame of trades for the last N days."""
    session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        trades = session.query(Trade).filter(Trade.timestamp >= cutoff).all()
        if not trades:
            return pd.DataFrame()
        data = [{
            'timestamp': t.timestamp,
            'symbol': t.symbol,
            'side': t.side,
            'price': t.price,
            'amount': t.amount,
            'cost': t.cost,
            'pnl': t.pnl,
        } for t in trades]
        return pd.DataFrame(data)
    finally:
        session.close()

def calculate_metrics(df: pd.DataFrame, initial_balance: float = 1000.0) -> dict:
    """Compute core performance metrics from a DataFrame of trades."""
    if df.empty:
        return {'total_trades': 0, 'win_rate': 0.0, 'profit_factor': 0.0, 'total_pnl': 0.0}

    closed = df[df['side'] == 'SELL']
    total_trades = len(closed)
    if total_trades == 0:
        return {'total_trades': 0, 'win_rate': 0.0, 'profit_factor': 0.0, 'total_pnl': 0.0}

    wins = closed[closed['pnl'] > 0]
    losses = closed[closed['pnl'] <= 0]
    win_rate = (len(wins) / total_trades) * 100

    gross_profit = wins['pnl'].sum() if not wins.empty else 0.0
    gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else (gross_profit if gross_profit > 0 else 0.0)

    total_pnl = closed['pnl'].sum()
    avg_win = wins['pnl'].mean() if not wins.empty else 0.0
    avg_loss = losses['pnl'].mean() if not losses.empty else 0.0

    balance = initial_balance
    peak = balance
    max_dd = 0.0
    for _, r in df.iterrows():
        if r['side'] == 'SELL':
            balance += r['pnl']
            if balance > peak:
                peak = balance
            elif peak > 0:
                cur_dd = ((peak - balance) / peak) * 100.0
                if cur_dd > max_dd:
                    max_dd = cur_dd

    return {
        'total_trades': total_trades,
        'win_rate': round(win_rate, 2),
        'profit_factor': round(profit_factor, 2),
        'total_pnl': round(total_pnl, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'max_drawdown': round(max_dd, 2),
        'balance': round(balance, 2),
    }
