from django.shortcuts import render
from .models import Trade, Wallet
import json

def calculate_risk_metrics(trades, equity_curve):
    """
    Допоміжна функція для розрахунку Max Drawdown та середніх показників.
    equity_curve - це список значень балансу з графіка.
    """
    # --- 1. Max Drawdown (MDD) ---
    max_drawdown = 0.0
    peak = -999999.0
    
    if equity_curve:
        for value in equity_curve:
            if value > peak:
                peak = value
            if peak > 0:
                drawdown = (peak - value) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
    
    mdd_percent = round(max_drawdown * 100, 2)

    # --- 2. Avg Win / Avg Loss ---
    closed_trades = [t for t in trades if t.pnl is not None]
    
    winning_trades = [t.pnl for t in closed_trades if t.pnl > 0]
    losing_trades = [t.pnl for t in closed_trades if t.pnl < 0]

    avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0
    
    if abs(avg_loss) > 0:
        rr_ratio = round(avg_win / abs(avg_loss), 2)
    else:
        rr_ratio = round(avg_win, 2) if avg_win > 0 else 0

    return mdd_percent, rr_ratio, round(avg_win, 2), round(avg_loss, 2)


def dashboard(request):
    # 1. Отримуємо баланс
    try:
        wallet = Wallet.objects.first()
        balance = wallet.usdt_balance if wallet else 1000.0
    except: balance = 1000.0

    # 2. Отримуємо угоди
    all_trades_qs = Trade.objects.all().order_by('-timestamp')
    trades = list(all_trades_qs[:1000]) 
    
    # 3. Базова статистика
    total_trades = all_trades_qs.count()
    
    # Win Rate
    wins = sum(1 for t in trades if t.pnl is not None and t.pnl > 0)
    local_count = len(trades)
    win_rate = (wins / local_count * 100) if local_count > 0 else 0
    
    # 4. Підготовка даних (Equity Curve + Profit Factor + PnL)
    chart_labels = []
    chart_data = []
    chart_colors = []
    chart_radius = []
    
    current_equity = 1000.0 # Стартовий депозит
    
    gross_profit = 0.0
    gross_loss = 0.0

    # Йдемо від старого до нового
    for t in reversed(trades):
        if t.side == 'SELL' and t.pnl is not None:
            profit_usd = t.amount * t.price * (t.pnl / 100)
            
            if profit_usd > 0:
                gross_profit += profit_usd
                point_color = '#00C853'
            else:
                gross_loss += abs(profit_usd)
                point_color = '#FF3D00'

            current_equity += profit_usd
            
            chart_labels.append(t.timestamp.strftime("%d-%m %H:%M"))
            chart_data.append(round(current_equity, 2))
            chart_colors.append(point_color)
            chart_radius.append(4) 

    # --- НОВЕ: Розрахунок Total PnL ---
    total_pnl_usd = round(gross_profit - gross_loss, 2)
    # Відсоток від стартового депозиту (1000$)
    total_pnl_percent = round((total_pnl_usd / 1000.0) * 100, 2)

    # 5. Розрахунок метрик ризику
    mdd, rr_ratio, avg_win, avg_loss = calculate_risk_metrics(trades, chart_data)

    # 6. Profit Factor
    if gross_loss == 0:
        profit_factor = 10.0 if gross_profit > 0 else 0.0
    else:
        profit_factor = round(gross_profit / gross_loss, 2)

    if profit_factor >= 1.5: pf_color = '#00C853'
    elif profit_factor >= 1.1: pf_color = '#FFD600'
    else: pf_color = '#FF3D00'

    context = {
        'balance': round(balance, 2),
        'total_trades': total_trades,
        'win_rate': round(win_rate, 1),
        'profit_factor': profit_factor,
        'pf_color': pf_color,
        'trades': trades[:10],
        
        # --- Нові змінні PnL ---
        'total_pnl_usd': total_pnl_usd,
        'total_pnl_percent': total_pnl_percent,

        # --- Метрики ризику ---
        'max_drawdown': mdd,
        'risk_reward': rr_ratio,
        'avg_win': avg_win,
        'avg_loss': avg_loss,

        # --- Графік ---
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'chart_colors': json.dumps(chart_colors),
        'chart_radius': json.dumps(chart_radius), 
    }
    return render(request, 'dashboard.html', context)