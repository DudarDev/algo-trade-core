from ninja import NinjaAPI
from bot_monitor.api import router as monitor_router

api = NinjaAPI(title="AlgoTrade API")
# Підключаємо без префікса, щоб шляхи були рівно /api/stats
api.add_router("", monitor_router)