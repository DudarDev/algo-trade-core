import json
from pathlib import Path
from ninja import Router
from django.conf import settings
from .schemas import ControlSchema

router = Router()

STATUS_FILE = settings.PROJECT_ROOT / 'data_storage' / 'bot_status.json'

@router.post("/control")
def control_bot(request, data: ControlSchema):
    new_status = "active" if data.command == "start" else "stopped"
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump({"status": new_status}, f)
    return {"status": "success", "bot_status": new_status}

@router.get("/status")
def get_bot_status(request):
    if not STATUS_FILE.exists():
        return {"bot_status": "active"}
    try:
        with open(STATUS_FILE, "r") as f:
            data = json.load(f)
            return {"bot_status": data.get("status", "active")}
    except Exception:
        return {"bot_status": "active"}
