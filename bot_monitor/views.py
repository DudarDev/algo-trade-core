from django.shortcuts import render
from .models import Trade, Wallet
import pandas as pd
import json
import logging

logger = logging.getLogger(__name__)

def calculate_risk_metrics(trades_df, equity_curve):
    """
    Допоміжна функція: Розрахунок Max Drawdown, Risk/Reward та середніх значень.
    """
    # --- 1. Max Drawdown (MDD) - Максимальна просадка ---
    max_drawdown = 0.0
    if equity_curve:
        # Перетворюємо список на pandas Series для швидкості
        equity_series = pd.Series(equity_curve)
        # Знаходимо поточний пік (cummax)
        running_max = equity_series.cummax()
        # Рахуємо відсоток падіння від піку
        drawdown = (equity_series - running_max) / running_max
        # Найменше значення (найглибша яма) * 100
        max_drawdown = drawdown.min() * 100 

    # --- 2. Avg Win / Avg Loss (Risk/Reward) ---
    if not trades_df.empty:
        # Аналізуємо тільки закриті угоди (SELL)
        closed = trades_df[trades_df['side'] == 'SELL']
        
        # Середній % виграшу
        avg_win = closed[closed['pnl'] > 0]['pnl'].mean()
        # Середній % програшу
        avg_loss = closed[closed['pnl'] <= 0]['pnl'].mean()
        
        # Заміна NaN на 0, якщо угод мало
        avg_win = 0 if pd.isna(avg_win) else avg_win
        avg_loss = 0 if pd.isna(avg_loss) else avg_loss
    else:
        avg_win, avg_loss = 0, 0

    # Risk / Reward Ratio (Співвідношення Ризик/Прибуток)
    if abs(avg_loss) > 0:
        rr_ratio = round(avg_win / abs(avg_loss), 2)
    else:
        rr_ratio = round(avg_win, 2) if avg_win > 0 else 0

    return round(abs(max_drawdown), 2), rr_ratio, round(avg_win, 2), round(avg_loss, 2)

def dashboard(request):
    # 1. Отримуємо поточний баланс гаманця
    try:
        wallet = Wallet.objects.first()
        balance = wallet.usdt_balance if wallet else 1000.0
    except: 
        balance = 1000.0

    # 2. Завантажуємо угоди з бази даних
    trades_qs = Trade.objects.all().order_by('-timestamp')
    # Перетворюємо в список словників для створення DataFrame
    trades_data = list(trades_qs.values('timestamp', 'symbol', 'side', 'price', 'amount', 'pnl'))
    
    # Якщо угод немає, показуємо пустий дашборд
    if not trades_data:
        return render(request, 'bot_monitor/dashboard.html', {'balance': balance})

    df = pd.DataFrame(trades_data)
    
    # 3. Базова статистика
    total_trades = len(df)
    
    # Win Rate (Рахуємо тільки для закритих угод SELL)
    closed_trades = df[df['side'] == 'SELL']
    total_closed = len(closed_trades)
    wins_count = len(closed_trades[closed_trades['pnl'] > 0])
    
    win_rate = (wins_count / total_closed * 100) if total_closed > 0 else 0
    
    # 4. Побудова графіку Equity Curve (Крива капіталу)
    chart_labels = []
    chart_data = []
    chart_colors = []
    chart_radius = []
    
    # Початковий депозит для симуляції графіку
    simulated_equity = 1000.0 
    
    gross_profit = 0.0
    gross_loss = 0.0

    # Сортуємо від старого до нового для правильної побудови лінії
    df_sorted = df.sort_values('timestamp')

    for index, t in df_sorted.iterrows():
        # Змінюємо баланс тільки при продажу (SELL)
        if t['side'] == 'SELL' and t['pnl'] is not None:
            # Приблизний PnL в доларах = (Об'єм угоди) * (PnL% / 100)
            trade_val = float(t['amount']) * float(t['price'])
            profit_usd = trade_val * (float(t['pnl']) / 100.0)
            
            # Накопичуємо суми для Profit Factor
            if profit_usd > 0:
                gross_profit += profit_usd
                point_color = '#00C853' # Зелений колір точки
            else:
                gross_loss += abs(profit_usd)
                point_color = '#FF3D00' # Червоний колір точки

            simulated_equity += profit_usd
            
            # Додаємо точку на графік
            chart_labels.append(t['timestamp'].strftime("%d %b %H:%M"))
            chart_data.append(round(simulated_equity, 2))
            chart_colors.append(point_color)
            chart_radius.append(2) 

    # --- Total PnL (Чистий результат) ---
    total_pnl_usd = round(gross_profit - gross_loss, 2)
    total_pnl_percent = round((total_pnl_usd / 1000.0) * 100, 2)

    # 5. Розрахунок складних метрик (MDD, Sharpe і т.д.)
    mdd, rr_ratio, avg_win, avg_loss = calculate_risk_metrics(df, chart_data)

    # 6. Profit Factor (Головний показник для інвесторів)
    if gross_loss == 0:
        profit_factor = round(gross_profit, 2) if gross_profit > 0 else 0.0
    else:
        profit_factor = round(gross_profit / gross_loss, 2)

    # Колір для Profit Factor
    if profit_factor >= 1.5: pf_color = '#00C853' # Відмінно
    elif profit_factor >= 1.1: pf_color = '#FFD600' # Нормально
    else: pf_color = '#FF3D00' # Погано

    # Беремо останні 20 угод для таблиці
    recent_trades = trades_qs[:20]

    context = {
        'balance': round(balance, 2),
        'total_trades': total_trades,
        'win_rate': round(win_rate, 1),
        'profit_factor': profit_factor,
        'pf_color': pf_color,
        'trades': recent_trades,
        
        # PnL Metrics
        'total_pnl_usd': total_pnl_usd,
        'total_pnl_percent': total_pnl_percent,

        # Risk Metrics
        'max_drawdown': mdd,
        'risk_reward': rr_ratio,
        'avg_win': avg_win,
        'avg_loss': avg_loss,

        # Chart Data (JSON)
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'chart_colors': json.dumps(chart_colors),
        'chart_radius': json.dumps(chart_radius), 
    }
    
    return render(request, 'bot_monitor/dashboard.html', context)