"""
Celery таски для перенавчання моделі ШІ.
"""

import logging
from src.tasks.celery_app import app
from src.ai_optimizer.weekly_retrain_service import WeeklyRetrainService

logger = logging.getLogger("CeleryRetrainTask")

@app.task(bind=True, max_retries=3, default_retry_delay=300)
def weekly_retrain_task(self):
    """
    Періодична задача Celery Beat:
    Виконується щонеділі о 02:00 UTC.
    """
    logger.info("🚀 [Celery] Початок виконання задачі weekly_retrain_task...")
    try:
        service = WeeklyRetrainService(history_days=45, min_auc_threshold=0.60)
        success = service.execute_full_cycle()
        if not success:
            logger.warning("⚠️ [Celery] Задача завершилася без оновлення ваг (відхилено Quality Gate).")
            return {"status": "REJECTED_QUALITY_GATE"}
        
        logger.info("✅ [Celery] Задача успішно виконана, модель оновлено.")
        return {"status": "SUCCESS", "deployed": True}
        
    except Exception as exc:
        logger.error(f"❌ [Celery] Критична помилка у weekly_retrain_task: {exc}")
        raise self.retry(exc=exc)
