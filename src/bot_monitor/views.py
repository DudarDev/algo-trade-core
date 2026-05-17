# src/bot_monitor/views.py
import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .services import MetricsCalculatorService, BotControlService

logger = logging.getLogger(__name__)

@login_required
def dashboard_view(request):
    try:
        # Отримуємо валідований об'єкт DTO
        metrics_dto = MetricsCalculatorService.get_dashboard_data()
        
        # Конвертуємо Pydantic модель у словник (dict) для Django шаблону
        context = metrics_dto.model_dump()
        
        # Додаємо статус бота (його немає в DTO метрик)
        context['bot_status'] = BotControlService.get_current_status()

        return render(request, 'bot_monitor/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Помилка рендерингу дашборду: {e}", exc_info=True)
        return render(request, 'bot_monitor/error.html', {"error": "Internal Server Error"})