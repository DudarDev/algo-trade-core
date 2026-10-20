from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from .api import api  # Імпортуємо NinjaAPI

urlpatterns = [
    path('admin/', admin.site.urls),
    path('bot_monitor/', include('bot_monitor.urls')),
    path('api/', api.urls),  # <--- ОСЬ ТУТ МАГІЯ NINJA!
    path('', RedirectView.as_view(url='/bot_monitor/dashboard/', permanent=False)),
]