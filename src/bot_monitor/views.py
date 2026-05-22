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
    
    # Беремо останні 30 угод для графіка
    for t in all_trades.order_by('timestamp')[:30]: 
        chart_labels.append(t.timestamp.strftime('%d %b %H:%M'))
        cumulative_pnl += t.pnl
        chart_data.append(round(cumulative_pnl, 2))

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
        
        'total_pnl_percent': 0.0, 
        'max_drawdown': 0,
        'banned_coins': [],
        'banned_count': 0,
    }
    return render(request, 'bot_monitor/dashboard.html', context)

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