from django.shortcuts import render
from .models import Trade, Wallet
import json

def dashboard(request):
    # 1. Отримуємо баланс
    try:
        wallet = Wallet.objects.first()
        balance = wallet.usdt_balance if wallet else 1000.0
    except: balance = 1000.0

    # 2. Отримуємо угоди (OPTIMIZATION: беремо тільки останні 1000 для графіку, щоб не вбити RAM)
    # Якщо угод менше 1000, він візьме всі. Це врятує твій e2-micro в майбутньому.
    all_trades_qs = Trade.objects.all().order_by('-timestamp')
    trades = list(all_trades_qs[:1000]) 
    
    # 3. Базова статистика
    total_trades = all_trades_qs.count() # Count у SQL дешевий
    # Для Win Rate беремо статистику по завантажених угодах (або можна окремим SQL запитом)
    wins = sum(1 for t in trades if t.pnl > 0)
    local_count = len(trades)
    win_rate = (wins / local_count * 100) if local_count > 0 else 0
    
    # 4. Підготовка даних (Equity Curve + Profit Factor)
    chart_labels = []
    chart_data = []
    
    current_equity = 1000.0 # Стартовий депозит симуляції
    
    # Змінні для Profit Factor
    gross_profit = 0.0
    gross_loss = 0.0

    # Йдемо від найстаріших до нових (reversed працює, бо ми зробили list[:1000])
    for t in reversed(trades):
        # Рахуємо PnL тільки для закритих угод (SELL), як у твоїй логіці
        if t.side == 'SELL':
            # Абсолютний профіт у $ (формула: об'єм * ціна * %/100)
            profit_usd = t.amount * t.price * (t.pnl / 100)
            
            # Накопичуємо дані для Profit Factor
            if profit_usd > 0:
                gross_profit += profit_usd
            else:
                gross_loss += abs(profit_usd) # беремо модуль від мінуса

            # Оновлюємо графік
            current_equity += profit_usd
            chart_labels.append(t.timestamp.strftime("%d-%m %H:%M"))
            chart_data.append(round(current_equity, 2))

    # 5. Фінальний розрахунок Profit Factor
    if gross_loss == 0:
        profit_factor = 10.0 if gross_profit > 0 else 0.0 # Штучне обмеження
    else:
        profit_factor = round(gross_profit / gross_loss, 2)

    # Визначаємо колір для UI
    if profit_factor >= 1.5:
        pf_color = '#00C853' # Яскраво-зелений (Super)
    elif profit_factor >= 1.1:
        pf_color = '#FFD600' # Жовтий (OK)
    else:
        pf_color = '#FF3D00' # Червоний (Warning)

    context = {
        'balance': round(balance, 2),
        'total_trades': total_trades,
        'win_rate': round(win_rate, 1),
        'profit_factor': profit_factor,   # <--- НОВА ЗМІННА
        'pf_color': pf_color,             # <--- КОЛІР ДЛЯ ШАБЛОНУ
        'trades': trades[:10],            # Останні 10 для таблиці (зріз списку, не QuerySet)
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'dashboard.html', context)