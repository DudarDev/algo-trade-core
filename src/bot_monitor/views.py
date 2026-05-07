from django.shortcuts import render
import logging
from .services import MetricsCalculatorService

logger = logging.getLogger(__name__)

def dashboard(request):
    """
    Чистий View: Викликає Сервіс для обчислення метрик і віддає їх у шаблон.
    """
    try:
        service = MetricsCalculatorService()
        context = service.get_dashboard_data()
        
        return render(request, 'bot_monitor/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Помилка завантаження дашборду: {e}")
        # Запасний контекст у разі критичної помилки
        return render(request, 'bot_monitor/dashboard.html', {'balance': 0.0})