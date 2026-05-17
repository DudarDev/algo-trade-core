import os
import django
import asyncio
import logging

# Ініціалізація Django (щоб бот міг писати в базу)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.web_panel.settings')
django.setup()

# Тепер імпортуємо рушій
from src.shared.config import settings
from src.engine.application.paper_trader import PaperTrader
from src.engine.application.strategy import HybridStrategy
from src.infrastructure.ai.predictor import GlobalTradingAI
from src.shared.db.repositories import TradingRepository

logger = logging.getLogger(__name__)

async def main():
    logger.info("🚀 Запуск торгового рушія...")
    
    # Ініціалізація залежностей
    repo = TradingRepository()
    ai_predictor = GlobalTradingAI(settings)
    strategy = HybridStrategy(settings)
    
    paper_trader = PaperTrader(settings=settings, repo=repo, notifier=None)
    await paper_trader.initialize()
    
    # Основний цикл бота
    while True:
        # Тут ваша логіка сканування ринку та отримання сигналів
        logger.info("📡 Сканування ринку...")
        await asyncio.sleep(60) # Пауза 60 секунд

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бота зупинено.")