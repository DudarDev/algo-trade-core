from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Trade, Wallet, ActivePosition, BotConfig # Імпортуй моделі
import json

def dashboard_view(request):
    """Головна сторінка з даними з БД."""
    # Отримуємо дані з БД
    wallet = Wallet.objects.first()
    active_trades = ActivePosition.objects.all()
    recent_trades = Trade.objects.order_by('-timestamp')[:10]
    
    # Готуємо контекст (це те, що відобразиться на сторінці)
    context = {
        'balance': wallet.usdt_balance if wallet else 0.0,
        'active_trades': active_trades,
        'trades': recent_trades,
        # Заглушки для графіків (пізніше заповнимо логікою)
        'total_pnl_usd': 0.0,
        'total_pnl_percent': 0.0,
        'total_trades': Trade.objects.count(),
        'profit_factor': 1.0,
        'win_rate': 0,
        'max_drawdown': 0,
        'risk_reward': 0,
        'avg_win': 0,
        'avg_loss': 0,
        'banned_coins': [],
        'banned_count': 0,
        'chart_labels': [],
        'chart_data': [],
        'chart_colors': [],
        'chart_radius': [],
        'pf_color': '#848e9c'
    }
    return render(request, 'bot_monitor/dashboard.html', context)

def api_bot_status(request):
    """API для отримання поточного статусу бота."""
    config = BotConfig.objects.filter(id=1).first()
    status = config.status if config else "stopped"
    return JsonResponse({
        "status": "success",
        "bot_status": status
    })

@csrf_exempt
def api_bot_control(request):
    """API для керування ботом."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            command = data.get('command') # Тут має бути 'start' або 'stop'
            
            config, _ = BotConfig.objects.get_or_create(id=1)
            if command == 'start':
                config.status = 'active'
            elif command == 'stop':
                config.status = 'stopped'
            else:
                return JsonResponse({"status": "error", "message": "Невідома команда"}, status=400)
            
            config.save()
            return JsonResponse({"status": "success", "bot_status": config.status})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    
    return JsonResponse({"status": "error", "message": "Тільки POST запити"}, status=405)