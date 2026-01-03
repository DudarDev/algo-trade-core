#!/bin/bash
echo "🚀 Починаємо повне оновлення системи (Django + Bot)..."

# --- ЕТАП 1: Оновлення файлів Django ---
echo "📝 Оновлюємо налаштування веб-сайту..."

# Settings
cat <<PY > web_panel/settings.py
from pathlib import Path
import os
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-update-me'
DEBUG = True
ALLOWED_HOSTS = ['*']
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bot_monitor',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'web_panel.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
WSGI_APPLICATION = 'web_panel.wsgi.application'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'bot_data' / 'bot_data.db',
    }
}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
PY

# Models
cat <<PY > bot_monitor/models.py
from django.db import models

class Trade(models.Model):
    id = models.AutoField(primary_key=True)
    symbol = models.CharField(max_length=20)
    side = models.CharField(max_length=10)
    price = models.FloatField()
    amount = models.FloatField()
    cost = models.FloatField()
    pnl = models.FloatField(default=0.0)
    timestamp = models.DateTimeField() 

    class Meta:
        managed = False
        db_table = 'trades'
        ordering = ['-timestamp']
        verbose_name = 'Торгова Операція'
        verbose_name_plural = 'Історія Угод'

    def __str__(self):
        return f"{self.timestamp} - {self.side} {self.symbol}"

class Wallet(models.Model):
    id = models.AutoField(primary_key=True)
    usdt_balance = models.FloatField()

    class Meta:
        managed = False
        db_table = 'wallet'
        verbose_name = 'Баланс Гаманця'
        verbose_name_plural = 'Баланс'

    def __str__(self):
        return f"Баланс: {self.usdt_balance} USDT"
PY

# Admin
cat <<PY > bot_monitor/admin.py
from django.contrib import admin
from .models import Trade, Wallet
from django.utils.html import format_html

@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'symbol', 'colored_side', 'price', 'amount', 'colored_pnl')
    list_filter = ('symbol', 'side')
    search_fields = ('symbol',)
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

    def colored_side(self, obj):
        color = 'blue' if obj.side == 'BUY' else 'orange'
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.side)
    colored_side.short_description = 'Тип'

    def colored_pnl(self, obj):
        if obj.side == 'BUY': return "-"
        color = 'green' if obj.pnl > 0 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{:.2f}%</span>', color, obj.pnl)
    colored_pnl.short_description = 'PnL (%)'

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('usdt_balance', 'status_display')
    def status_display(self, obj): return "Active"
    status_display.short_description = 'Статус'
    def has_add_permission(self, request): return False
PY

# --- ЕТАП 2: Синхронізація Бази Даних ---
echo "📥 Скачуємо базу даних з сервера (для відображення на сайті)..."
mkdir -p bot_data
# Пробуємо скачати базу (може запитати пароль/підтвердження)
gcloud compute scp --zone us-central1-a yaroslavupwork97@paper-trading-bot:~/bot_data/bot_data.db ./bot_data/bot_data.db --quiet || echo "⚠️ Не вдалося скачати базу. Перевірте, чи запущений сервер."

# --- ЕТАП 3: Налаштування Django ---
echo "⚙️ Налаштовуємо Django..."
pip install django > /dev/null
python3 manage.py migrate

# Створюємо суперюзера автоматично (якщо немає)
echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')" | python3 manage.py shell
echo "✅ Адмін створений: логін 'admin', пароль 'adminpass'"

# --- ЕТАП 4: Збірка Бота ---
echo "🏗️ Збираємо нову версію бота..."
gcloud config set project algo-trade-480920
gcloud builds submit --tag us-central1-docker.pkg.dev/algo-trade-480920/bot-repo/ai-scalper:v1 .

echo "🎉 ОНОВЛЕННЯ ЗАВЕРШЕНО!"
echo "---------------------------------------------------"
echo "👉 Щоб запустити САЙТ, введи: python3 manage.py runserver 0.0.0.0:8080"
echo "👉 Щоб оновити БОТА на сервері, зайди в SSH і виконай 'docker pull...'"
echo "---------------------------------------------------"
