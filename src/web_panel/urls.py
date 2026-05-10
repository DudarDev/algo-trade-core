from django.contrib import admin
from django.urls import path
from bot_monitor.views import dashboard
from .api import api

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('admin/', admin.site.urls),
    path('api/', api.urls),
]
