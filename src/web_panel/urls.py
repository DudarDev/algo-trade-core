from django.contrib import admin
from django.urls import path
from bot_monitor import views
from .api import api  # 👈 Імпортуємо наш API об'єкт

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='home'), # Головна сторінка
    path('api/', api.urls),  # 👈 Всі запити на /api/ підуть у Django Ninja
]
