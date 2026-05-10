from ninja import NinjaAPI
from bot_monitor.api import router as monitor_router

api = NinjaAPI(title="AlgoTrade API")
api.add_router("/monitor", monitor_router)
