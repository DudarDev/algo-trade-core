"""
Планувальник щотижневого запуску перенавчання моделі Random Forest.
Працює щонеділі о 02:00 UTC через APScheduler (з резервним механізмом на schedule).
"""

import sys
import time
import signal
import logging
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_optimizer.weekly_retrain_service import WeeklyRetrainService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AIRetrainScheduler")

def job_weekly_retrain():
    """Задача, яка викликається щонеділі вночі."""
    logger.info("⏰ Тригер планувальника спрацював: запуск щотижневого циклу перенавчання...")
    try:
        service = WeeklyRetrainService(history_days=45, min_auc_threshold=0.60)
        success = service.execute_full_cycle()
        logger.info(f"🏁 Щотижневий цикл завершено зі статусом: {success}")
    except Exception as e:
        logger.error(f"❌ Помилка виконання планової задачі: {e}", exc_info=True)

def run_apscheduler():
    """Запуск через професійний APScheduler."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("⚠️ APScheduler не встановлено, переходжу на бібліотеку schedule...")
        return run_fallback_schedule()

    scheduler = BlockingScheduler()
    
    # Щонеділі о 02:00 UTC
    trigger = CronTrigger(day_of_week="sun", hour=2, minute=0, timezone="UTC")
    scheduler.add_job(
        job_weekly_retrain,
        trigger=trigger,
        id="weekly_rf_retrain",
        name="Weekly Binance 5m Random Forest Retraining",
        replace_existing=True
    )

    logger.info("==================================================================")
    logger.info("📅 ПЛАНУВАЛЬНИК ШІ УСПІШНО ЗАПУЩЕНО (APScheduler)")
    logger.info("🕒 Розклад: Щонеділі о 02:00 UTC")
    logger.info("🎯 Дія: Свіжі свічки Binance 5m -> Triple-Barrier -> Calibrated RF")
    logger.info("==================================================================")

    def shutdown(signum, frame):
        logger.info("🛑 Отримано сигнал зупинки планувальника...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Планувальник зупинено користувачем.")

def run_fallback_schedule():
    """Резервний варіант через бібліотеку schedule."""
    import schedule

    # Щонеділі о 02:00
    schedule.every().sunday.at("02:00").do(job_weekly_retrain)

    logger.info("📅 Планувальник запущено через модуль schedule (Щонеділі о 02:00).")
    while True:
        schedule.run_pending()
        time.sleep(30)

def main():
    parser = argparse.ArgumentParser(description="Планувальник щотижневого перенавчання ШІ")
    parser.add_argument("--now", action="store_true", help="Виконати перенавчання негайно (для тестування)")
    parser.add_argument("--days", type=int, default=45, help="Кількість днів історії для навчання")
    args = parser.parse_args()

    if args.now:
        logger.info("⚡ Запуск негайного позачергового перенавчання моделі (--now)...")
        service = WeeklyRetrainService(history_days=args.days)
        service.execute_full_cycle()
        return

    run_apscheduler()

if __name__ == "__main__":
    main()
