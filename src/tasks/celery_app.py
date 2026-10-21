"""
Конфігурація Celery для фонових та періодичних задач квант-бота.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Налаштовуємо Django settings, якщо використовується з Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.core_platform.settings")

app = Celery("algo_trade_tasks")

# Читаємо конфігурацію Celery (або використовуємо Redis/RabbitMQ за замовчуванням)
app.conf.broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
app.conf.result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

app.conf.timezone = "UTC"
app.conf.enable_utc = True

# Розклад періодичних задач (Celery Beat)
app.conf.beat_schedule = {
    "weekly-binance-rf-retraining": {
        "task": "src.tasks.retrain_tasks.weekly_retrain_task",
        # Щонеділі о 02:00 UTC (вночі перед відкриттям азійської/європейської сесії)
        "schedule": crontab(hour=2, minute=0, day_of_week="sunday"),
        "options": {"queue": "ml_training"}
    },
}

app.autodiscover_tasks(["src.tasks"])
