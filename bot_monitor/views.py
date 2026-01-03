from django.shortcuts import render
from .models import Trade, Wallet
import json

def dashboard(request):
    # 1. Отримуємо баланс
    try:
        wallet = Wallet.objects.first()
        balance = wallet.usdt_balance if wallet else 1000.0
    except: balance = 1000.0

    # 2. Отримуємо всі угоди
    trades = Trade.objects.all().order_by('-timestamp')
    
    # 3. Статистика
    total_trades = trades.count()
    wins = trades.filter(pnl__gt=0).count()
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    # 4. Підготовка даних для графіку (Equity Curve)
    # Нам треба список дат і балансу в той момент
    chart_labels = []
    chart_data = []
    
    # Симуляція історії балансу (від 1000 до поточного)
    # У реальності краще записувати історію балансу окремо, 
    # але для демо вирахуємо приблизно
    
    current_equity = 1000.0
    equity_curve = []
    
    # Йдемо від найстаріших до нових
    for t in reversed(trades):
        if t.side == 'SELL':
            # Приблизний профіт у доларах
            profit_usd = t.amount * t.price * (t.pnl / 100)
            current_equity += profit_usd
            
            chart_labels.append(t.timestamp.strftime("%d-%m %H:%M"))
            chart_data.append(round(current_equity, 2))

    context = {
        'balance': round(balance, 2),
        'total_trades': total_trades,
        'win_rate': round(win_rate, 1),
        'trades': trades[:10], # Останні 10 угод для таблиці
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'dashboard.html', context)
