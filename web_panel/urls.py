from django.contrib import admin
from django.urls import path
from bot_monitor import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='home'), # Головна сторінка
]
