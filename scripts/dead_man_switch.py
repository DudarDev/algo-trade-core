#!/usr/bin/env python3
"""
Dead Man's Switch (Watchdog Supervisor) for AlgoTrade PRO.
Monitors the Redis heartbeat of 'algo-bot'.
If no heartbeat is detected for > 180 seconds, sends an emergency SOS alert
to Telegram and triggers an automated service restart.
"""
import sys
import os
import time
import logging
import subprocess

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.config import settings
from src.engine.infrastructure.cache_manager import cache_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] Watchdog: %(message)s'
)
logger = logging.getLogger("DeadMansSwitch")

STALL_THRESHOLD_SECONDS = 180  # 3 minutes

def send_emergency_alert(msg: str):
    try:
        from src.engine.infrastructure.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        import asyncio
        asyncio.run(notifier.send_message(msg))
    except Exception as e:
        logger.error(f"Failed to send emergency telegram message: {e}")

def main():
    logger.info("🛡️ [Dead Man's Switch] Watchdog Supervisor запущено. Інтервал перевірки: 30с.")
    consecutive_missing = 0

    while True:
        try:
            hb = cache_manager.get("system:heartbeat")
            now = time.time()
            if not hb:
                consecutive_missing += 1
                logger.warning(f"⚠️ Heartbeat відсутній у Redis (спроба #{consecutive_missing}).")
                if consecutive_missing >= 6:  # 6 * 30s = 3 minutes
                    alert = "🚨 <b>[DEAD MAN'S SWITCH]</b> УВАГА! Торговий бот algo-bot не надсилає серцебиття понад 3 хвилини! Ініціюю аварійний автоперезапуск..."
                    logger.critical(alert)
                    send_emergency_alert(alert)
                    subprocess.run(["sudo", "systemctl", "restart", "algo-bot"], check=False)
                    consecutive_missing = 0
                    time.sleep(60)
            else:
                consecutive_missing = 0
                hb_ts = float(hb.get("timestamp", now))
                age = now - hb_ts
                if age > STALL_THRESHOLD_SECONDS:
                    alert = f"🚨 <b>[DEAD MAN'S SWITCH]</b> Зависання! Останній heartbeat був {age:.0f}с тому (> {STALL_THRESHOLD_SECONDS}с). Перезапускаю algo-bot..."
                    logger.critical(alert)
                    send_emergency_alert(alert)
                    subprocess.run(["sudo", "systemctl", "restart", "algo-bot"], check=False)
                    time.sleep(60)
                else:
                    logger.debug(f"Heartbeat OK (age: {age:.1f}s, balance: {hb.get('balance')} USDT, status: {hb.get('status')})")

        except Exception as e:
            logger.error(f"Помилка циклу наглядача: {e}")

        time.sleep(30)

if __name__ == "__main__":
    main()
