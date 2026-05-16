import logging
from ninja import Router
from .schemas import ControlSchema, StatusResponseSchema
from .services import BotControlService

logger = logging.getLogger(__name__)
router = Router(tags=["Bot Monitor Management"])

@router.post("/control", response={200: StatusResponseSchema, 500: dict})
def control_bot(request, data: ControlSchema):
    """
    POST ендпоінт для асинхронного перемикання стану торгового бота.
    """
    try:
        new_status = BotControlService.change_status(data.command)
        return 200, {
            "status": "success",
            "bot_status": new_status,
            "message": f"Bot transition to '{new_status}' executed successfully."
        }
    except Exception as e:
        logger.error(f"Control API endpoint failure: {str(e)}")
        return 500, {"status": "error", "message": "Internal Server Error occurred during state update."}

@router.get("/status", response={200: StatusResponseSchema, 500: dict})
def get_bot_status(request):
    """
    GET ендпоінт для отримання поточного статусу (поллінг з фронтенду).
    """
    try:
        current_status = BotControlService.get_current_status()
        return 200, {
            "status": "success",
            "bot_status": current_status
        }
    except Exception as e:
        logger.error(f"Status API endpoint failure: {str(e)}")
        return 500, {"status": "error", "message": "Internal Server Error updating monitor layout."}