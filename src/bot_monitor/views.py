import json
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Avg, Count

from .models import Trade, Wallet, ActivePosition, BotConfig
from .services import BotControlService

logger = logging.getLogger(__name__)

def dashboard_view(request):
    """Головна сторінка з даними з БД (Без SQLite!)."""
    wallet = Wallet.objects.first()
    active_trades = ActivePosition.objects.all()
    
    # Витягуємо всі угоди для аналітики
    all_trades = Trade.objects.all().order_by('timestamp')
    recent_trades = Trade.objects.order_by('-timestamp')[:10]
    
    # --- МАТЕМАТИКА МЕТРИК ---
    total_trades = all_trades.count()
    winning_trades = all_trades.filter(pnl__gt=0).count()
    losing_trades = all_trades.filter(pnl__lt=0).count()
    
    total_pnl_usd = all_trades.aggregate(total=Sum('pnl'))['total'] or 0.0
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    avg_win = all_trades.filter(pnl__gt=0).aggregate(avg=Avg('pnl'))['avg'] or 0.0
    avg_loss = all_trades.filter(pnl__lt=0).aggregate(avg=Avg('pnl'))['avg'] or 0.0
    
    risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0
    
    # --- ДАНІ ДЛЯ ГРАФІКА (Cumulative PNL) ---
    chart_labels = []
    chart_data = []
    cumulative_pnl = 0.0
    
    # Беремо 30 останніх угод для графіка (у хронологічному порядку)
    recent_trades_chart = all_trades.order_by('-timestamp')[:30]
    for t in reversed(recent_trades_chart): 
        chart_labels.append(t.timestamp.strftime('%d %b %H:%M'))
        cumulative_pnl += t.pnl
        chart_data.append(round(cumulative_pnl, 2))

    # Розрахунок Max Drawdown на основі кривої капіталу
    from src.shared.config import settings
    from datetime import datetime
    initial_balance = getattr(settings, 'INITIAL_BALANCE', 1000.0)
    current_equity = initial_balance
    peak_equity = initial_balance
    max_drawdown_pct = 0.0

    for t in all_trades:
        current_equity += float(t.pnl or 0.0)
        if current_equity > peak_equity:
            peak_equity = current_equity
        dd = ((peak_equity - current_equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0
        if dd > max_drawdown_pct:
            max_drawdown_pct = dd

    total_pnl_percent = round((total_pnl_usd / initial_balance) * 100.0, 2) if initial_balance > 0 else 0.0

    # Витягуємо монети на 48h динамічному кулдауні
    banned_coins = []
    try:
        from src.engine.infrastructure.cache_manager import cache_manager
        scanned_symbols = ['NEAR/USDT', 'AVAX/USDT', 'DOGE/USDT', 'UNI/USDT', 'APT/USDT', 'LINK/USDT', 'SOL/USDT', 'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'SUI/USDT', 'DOT/USDT', 'ARB/USDT', 'OP/USDT', 'TIA/USDT', 'INJ/USDT', 'BCH/USDT', 'LTC/USDT']
        for s in scanned_symbols:
            cd = cache_manager.get(f"cooldown:{s}")
            if cd:
                banned_coins.append(s)
    except Exception:
        pass

    context = {
        'balance': wallet.usdt_balance if wallet else 0.0,
        'active_trades': active_trades,
        'trades': recent_trades,
        
        # Реальні метрики
        'total_pnl_usd': round(total_pnl_usd, 2),
        'total_trades': total_trades,
        'profit_factor': round(risk_reward, 2),
        'win_rate': round(win_rate, 1),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        
        # Графіки
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'chart_colors': ['#0ecb81' if pnl >= 0 else '#f6465d' for pnl in chart_data],
        'chart_radius': [3] * len(chart_data),
        
        'total_pnl_percent': total_pnl_percent, 
        'max_drawdown': round(max_drawdown_pct, 1),
        'banned_coins': banned_coins,
        'banned_count': len(banned_coins),
    }
    return render(request, 'bot_monitor/dashboard.html', context)


def export_report_view(request):
    """Генерація інвесторського PDF/HTML аудиту для клієнтів або портфоліо."""
    from src.shared.config import settings
    from datetime import datetime
    wallet = Wallet.objects.first()
    all_trades = Trade.objects.all().order_by('timestamp')
    total_trades = all_trades.count()
    winning = all_trades.filter(pnl__gt=0).count()
    losing = all_trades.filter(pnl__lt=0).count()
    gross_profits = all_trades.filter(pnl__gt=0).aggregate(total=Sum('pnl'))['total'] or 0.0
    gross_losses = abs(all_trades.filter(pnl__lt=0).aggregate(total=Sum('pnl'))['total'] or 0.0)
    net_pnl = gross_profits - gross_losses
    profit_factor = round(gross_profits / gross_losses, 2) if gross_losses > 0 else (99.0 if gross_profits > 0 else 0.0)
    win_rate = round((winning / total_trades * 100.0), 1) if total_trades > 0 else 0.0

    initial_balance = getattr(settings, 'INITIAL_BALANCE', 1000.0)
    current_equity = initial_balance
    peak_equity = initial_balance
    max_dd = 0.0
    for t in all_trades:
        current_equity += float(t.pnl or 0.0)
        if current_equity > peak_equity:
            peak_equity = current_equity
        dd = ((peak_equity - current_equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    context = {
        'initial_balance': initial_balance,
        'current_balance': round(wallet.usdt_balance if wallet else initial_balance, 2),
        'total_trades': total_trades,
        'winning_trades': winning,
        'losing_trades': losing,
        'win_rate': win_rate,
        'gross_profits': round(gross_profits, 2),
        'gross_losses': round(gross_losses, 2),
        'net_pnl': round(net_pnl, 2),
        'profit_factor': profit_factor,
        'max_drawdown': round(max_dd, 2),
        'risk_reward_target': getattr(settings, 'RISK_REWARD_RATIO', 2.0),
        'execution_mode': getattr(settings, 'TRADING_MODE', 'PAPER'),
        'trades': list(all_trades.order_by('-timestamp')[:50]),
        'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    }
    return render(request, 'bot_monitor/investor_report.html', context)

def api_bot_status(request):
    try:
        status = BotControlService.get_current_status()
        return JsonResponse({"status": "success", "bot_status": status})
    except Exception as e:
        return JsonResponse({"status": "error", "message": "Internal error"}, status=500)

@csrf_exempt
def api_bot_control(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            command = data.get('command')
            if command not in ['start', 'stop']:
                return JsonResponse({"status": "error", "message": "Invalid command"}, status=400)

            new_status = BotControlService.change_status(command)
            return JsonResponse({"status": "success", "bot_status": new_status})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    return JsonResponse({"status": "error", "message": "Only POST"}, status=405)