from django.urls import path
from .api import get_bot_status

app_name = 'bot_monitor'

urlpatterns = [
    path('api/v1/status/', get_bot_status, name='api_bot_status'),
]