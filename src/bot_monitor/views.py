from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def dashboard(request):
    """Головна сторінка веб-панелі."""
    return render(request, 'bot_monitor/dashboard.html')

def api_bot_status(request):
    """API для отримання поточного статусу бота."""
    return JsonResponse({
        "status": "active",
        "message": "Бот працює та сканує ринок"
    })

@csrf_exempt
def api_bot_control(request):
    """API для зупинки/запуску бота з веб-панелі."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'start':
                return JsonResponse({"status": "success", "message": "Бот запущено"})
            elif action == 'stop':
                return JsonResponse({"status": "success", "message": "Бот зупинено"})
            else:
                return JsonResponse({"status": "error", "message": "Невідома команда"}, status=400)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    
    return JsonResponse({"status": "error", "message": "Тільки POST запити"}, status=405)
