#!/usr/bin/env python3
"""
CLI-інтерфейс для щотижневого завантаження даних та перенавчання моделі ШІ.
Використання:
    python scripts/run_weekly_retrain.py --now          # Запустити негайно (для тесту або позачергового оновлення)
    python scripts/run_weekly_retrain.py --schedule     # Запустити планувальник (щонеділі о 02:00 UTC)
    python scripts/run_weekly_retrain.py --days 60      # Вказати глибину свічок у днях
"""

import sys
import argparse
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_optimizer.weekly_retrain_service import WeeklyRetrainService
from src.ai_optimizer.scheduler import run_apscheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("RunWeeklyRetrain")

def main():
    parser = argparse.ArgumentParser(description="Автоматичний конвеєр перенавчання моделі Random Forest")
    parser.add_argument("--now", action="store_true", help="Виконати завантаження та перенавчання негайно")
    parser.add_argument("--schedule", action="store_true", help="Запустити у режимі фонового демона-планувальника")
    parser.add_argument("--days", type=int, default=45, help="Глибина історії в днях (за замовчуванням 45)")
    parser.add_argument("--min-auc", type=float, default=0.60, help="Мінімальний поріг ROC-AUC для деплою")
    args = parser.parse_args()

    if args.schedule:
        logger.info("🕒 Запуск планувальника щонедільного перенавчання...")
        run_apscheduler()
    else:
        logger.info(f"🚀 Запуск разового конвеєра перенавчання (глибина: {args.days} днів, поріг ROC-AUC: {args.min_auc})...")
        service = WeeklyRetrainService(history_days=args.days, min_auc_threshold=args.min_auc)
        success = service.execute_full_cycle()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
