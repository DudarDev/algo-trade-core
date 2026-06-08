from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Залишаємо старий шлях, щоб твоє посилання в браузері не зламалося
    path('bot_monitor/', include('bot_monitor.urls')),
    
    # МАГІЯ: Прокидаємо ці ж урли в корінь! Тепер JS знайде /api/stats
    path('', include('bot_monitor.urls')),
]