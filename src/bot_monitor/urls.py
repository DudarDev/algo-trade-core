from django.urls import path
from . import views

urlpatterns = [
    # Залишаємо ТІЛЬКИ HTML-шаблон дашборду.
    # Всі API-запити тепер оброблятиме Django Ninja через головний urls.py!
    path('dashboard/', views.dashboard_view, name='dashboard'),
]