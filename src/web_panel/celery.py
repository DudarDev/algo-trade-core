import os
import logging
from celery import Celery

logger = logging.getLogger(__name__)

# Встановлюємо налаштування Django за замовчуванням
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_panel.settings')

app = Celery('algo_trade_celery')

# Завантажуємо налаштування з Django settings з префіксом CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматичне виявлення задач у зареєстрованих додатках та src/engine/application/tasks.py
app.autodiscover_tasks(['engine.application', 'bot_monitor', 'src.engine.application'])

# Розклад періодичних фонових завдань (Celery Beat)
app.conf.beat_schedule = {
    'scheduled-news-radar-refresh': {
        'task': 'engine.application.tasks.task_refresh_news_feed',
        'schedule': 300.0,  # кожні 5 хвилин
    },
    'scheduled-macro-sentiment-sync': {
        'task': 'engine.application.tasks.task_sync_market_sentiment',
        'schedule': 900.0,  # кожні 15 хвилин
    },
    'scheduled-nightly-feedback-retrain': {
        'task': 'engine.application.tasks.task_feedback_loop_retrain',
        'schedule': 86400.0,  # кожні 24 години
    },
}

@app.task(bind=True)
def debug_task(self):
    logger.info(f"Celery Debug Request: {self.request!r}")
    return {"status": "ok", "task_id": self.request.id}
