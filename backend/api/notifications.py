from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# Simple in-memory storage for the demo
class Notification(BaseModel):
    title: str
    message: str
    type: str # 'success', 'warning', 'error', 'info', 'syndic'
    timestamp: Optional[str] = None

# Global variable to store the last notification
_last_notification = None

@router.post("/")
async def create_notification(notif: Notification):
    global _last_notification
    # Add server timestamp
    notif.timestamp = datetime.now().isoformat()
    _last_notification = notif
    return {"status": "ok", "data": notif}

@router.get("/latest")
async def get_latest_notification():
    return _last_notification if _last_notification else {}
