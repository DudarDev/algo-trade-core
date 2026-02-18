from django.shortcuts import render
from .models import Trade, Wallet
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def calculate_risk_metrics(trades_df, equity_curve):
    """
    Допоміжна функція: Розрахунок Max Drawdown, Risk/Reward та середніх значень.
    """
    max_drawdown = 0.0
    if equity_curve:
        equity_series = pd.Series(equity_curve)
        running_max = equity_series.cummax()
        drawdown = (equity_series - running_max) / running_max
        max_drawdown = drawdown.min() * 100 

    if not trades_df.empty:
        closed = trades_df[trades_df['side'] == 'SELL']
        avg_win = closed[closed['pnl'] > 0]['pnl'].mean()
        avg_loss = closed[closed['pnl'] <= 0]['pnl'].mean()
        
        avg_win = 0 if pd.isna(avg_win) else avg_win
        avg_loss = 0 if pd.isna(avg_loss) else avg_loss
    else:
        avg_win, avg_loss = 0, 0

    if abs(avg_loss) > 0:
        rr_ratio = round(avg_win / abs(avg_loss), 2)
    else:
        rr_ratio = round(avg_win, 2) if avg_win > 0 else 0

    return round(abs(max_drawdown), 2), rr_ratio, round(avg_win, 2), round(avg_loss, 2)

def dashboard(request):
    try:
        wallet = Wallet.objects.first()
        balance = wallet.usdt_balance if wallet else 1000.0
    except: 
        balance = 1000.0

    trades_qs = Trade.objects.all().order_by('-timestamp')
    trades_data = list(trades_qs.values('timestamp', 'symbol', 'side', 'price', 'amount', 'pnl'))
    
    if not trades_data:
        return render(request, 'bot_monitor/dashboard.html', {'balance': balance})

    df = pd.DataFrame(trades_data)
    
    total_trades = len(df)
    
    closed_trades = df[df['side'] == 'SELL']
    total_closed = len(closed_trades)
    wins_count = len(closed_trades[closed_trades['pnl'] > 0])
    
    win_rate = (wins_count / total_closed * 100) if total_closed > 0 else 0
    
    chart_labels = []
    chart_data = []
    chart_colors = []
    chart_radius = []
    
    simulated_equity = 1000.0 
    
    gross_profit = 0.0
    gross_loss = 0.0

    df_sorted = df.sort_values('timestamp')

    for index, t in df_sorted.iterrows():
        if t['side'] == 'SELL' and t['pnl'] is not None:
            trade_val = float(t['amount']) * float(t['price'])
            profit_usd = trade_val * (float(t['pnl']) / 100.0)
            
            if profit_usd > 0:
                gross_profit += profit_usd
                point_color = '#00C853' 
            else:
                gross_loss += abs(profit_usd)
                point_color = '#FF3D00' 

            simulated_equity += profit_usd
            
            chart_labels.append(t['timestamp'].strftime("%d %b %H:%M"))
            chart_data.append(round(simulated_equity, 2))
            chart_colors.append(point_color)
            chart_radius.append(2) 

    total_pnl_usd = round(gross_profit - gross_loss, 2)
    total_pnl_percent = round((total_pnl_usd / 1000.0) * 100, 2)

    mdd, rr_ratio, avg_win, avg_loss = calculate_risk_metrics(df, chart_data)

    if gross_loss == 0:
        profit_factor = round(gross_profit, 2) if gross_profit > 0 else 0.0
    else:
        profit_factor = round(gross_profit / gross_loss, 2)

    if profit_factor >= 1.5: pf_color = '#00C853' 
    elif profit_factor >= 1.1: pf_color = '#FFD600' 
    else: pf_color = '#FF3D00' 

    recent_trades = trades_qs[:20]

    context = {
        'balance': round(balance, 2),
        'total_trades': total_trades,
        'win_rate': round(win_rate, 1),
        'profit_factor': profit_factor,
        'pf_color': pf_color,
        'trades': recent_trades,
        'total_pnl_usd': total_pnl_usd,
        'total_pnl_percent': total_pnl_percent,
        'max_drawdown': mdd,
        'risk_reward': rr_ratio,
        'avg_win': avg_win,
        'avg_loss': avg_loss,

        # 🔥 ВИПРАВЛЕНО: Жодного json.dumps! Передаємо чисті списки
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'chart_colors': chart_colors,
        'chart_radius': chart_radius, 
    }
    
    return render(request, 'bot_monitor/dashboard.html', context)