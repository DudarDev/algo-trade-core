from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Підключаємо урли твого додатку bot_monitor
    path('bot_monitor/', include('bot_monitor.urls')),
    # Якщо користувач заходить просто на IP-адресу, кидаємо його в адмінку або на дашборд
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
]
