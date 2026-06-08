from django.urls import path
from . import views
from . import api  # Підключаємо твій файл api.py (я бачу його на скріншоті у вкладках)

urlpatterns = [
    # Ваш основний дашборд
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # API для JS (назви шляхів мають ТОЧНО збігатися з тим, що просить JS)
    path('api/bot_status/', views.api_bot_status, name='api_bot_status'), 
    path('api/control/', views.api_bot_control, name='api_bot_control'),
    
    # Нові ендпоінти для статистики та історії
    path('api/stats/', api.get_stats, name='api_stats'), 
    path('api/recent_trades/', api.get_recent_trades, name='api_recent_trades'),
]