"""Аналізує ефективність торгівлі по кожній парі."""
import pandas as pd
from datetime import datetime, timedelta
from src.shared.db.session import SessionLocal
from src.shared.db.models import Trade

def analyze_pairs(days_back: int = 30) -> pd.DataFrame:
    """Повертає DataFrame з метриками по кожній парі."""
    session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        trades = session.query(Trade).filter(Trade.timestamp >= cutoff, Trade.side == 'SELL').all()
        if not trades:
            return pd.DataFrame()
        
        data = []
        for t in trades:
            data.append({
                'symbol': t.symbol,
                'pnl': t.pnl,
                'is_win': t.pnl > 0,
                'timestamp': t.timestamp
            })
        df = pd.DataFrame(data)
        if df.empty:
            return df
        
        # Групуємо по парах
        grouped = df.groupby('symbol').agg(
            total_trades=('symbol', 'count'),
            win_rate=('is_win', 'mean'),
            total_pnl=('pnl', 'sum'),
            avg_pnl=('pnl', 'mean'),
            max_loss=('pnl', 'min'),
            max_profit=('pnl', 'max')
        ).reset_index()
        
        # Обчислюємо win_rate у відсотках
        grouped['win_rate'] = grouped['win_rate'] * 100
        
        # Сортуємо за загальним PnL
        grouped = grouped.sort_values('total_pnl', ascending=False)
        return grouped
    finally:
        session.close()

def get_best_pairs(min_trades: int = 5, min_win_rate: float = 40.0) -> list:
    """Повертає список найкращих пар."""
    df = analyze_pairs()
    if df.empty:
        return []
    
    best = df[(df['total_trades'] >= min_trades) & (df['win_rate'] >= min_win_rate)]
    return best['symbol'].tolist()

def get_worst_pairs(min_trades: int = 5, max_win_rate: float = 20.0) -> list:
    """Повертає список найгірших пар (для бана)."""
    df = analyze_pairs()
    if df.empty:
        return []
    
    worst = df[(df['total_trades'] >= min_trades) & (df['win_rate'] <= max_win_rate)]
    return worst['symbol'].tolist()
