import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET

# ... тут ваш існуючий код dashboard_view ...

@login_required
@require_GET
def api_bot_status(request):
    """Ендпоінт для поллінгу статусу (AJAX)"""
    try:
        status = BotControlService.get_current_status()
        return JsonResponse({"status": "success", "bot_status": status})
    except Exception as e:
        logger.error(f"API Status Error: {e}")
        return JsonResponse({"status": "error", "message": "Internal error"}, status=500)

@login_required
@require_POST
def api_bot_control(request):
    """Ендпоінт для кнопок START / STOP (AJAX)"""
    try:
        # Парсимо JSON з тіла запиту (fetch API відправляє саме body)
        data = json.loads(request.body)
        command = data.get('command')
        
        if command not in ['start', 'stop']:
            return JsonResponse({"status": "error", "message": "Invalid command"}, status=400)
            
        new_status = BotControlService.change_status(command)
        return JsonResponse({"status": "success", "bot_status": new_status})
        
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON format"}, status=400)
    except Exception as e:
        logger.error(f"API Control Error: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)