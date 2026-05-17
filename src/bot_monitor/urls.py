from django.urls import path
from . import views

urlpatterns = [
    # Ваш основний дашборд
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # API для JS
    path('api/status/', views.api_bot_status, name='api_bot_status'),
    path('api/control', views.api_bot_control, name='api_bot_control'), # У JS ви викликали /api/control (без слеша в кінці)
]