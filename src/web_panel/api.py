from ninja import NinjaAPI
from bot_monitor.api import router as monitor_router

api = NinjaAPI(title="AlgoTrade API")
# Підключаємо без префікса (/api/stats, /api/bot_control) та з префіксом /monitor (/api/monitor/...)
api.add_router("", monitor_router)
api.add_router("monitor", monitor_router, url_name_prefix="monitor")