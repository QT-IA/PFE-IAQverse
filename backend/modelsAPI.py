"""
Modeles Pydantic pour l'API FastAPI
"""

from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Any, List, Optional
import math


class IAQData(BaseModel):
    """Modele de donnees IAQ."""
    timestamp: Optional[datetime] = None
    co2: Optional[float] = None
    pm25: Optional[float] = None
    tvoc: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    enseigne: Optional[str] = "Maison"
    salle: Optional[str] = "Chambre"
    capteur_id: Optional[str] = "Chambre1"

    @field_validator("*", mode="before")
    def empty_to_none(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        try:
            if isinstance(v, float) and math.isnan(v):
                return None
        except Exception:
            pass
        return v

    @field_validator("timestamp", mode="before")
    def ensure_timestamp(cls, v: Any) -> datetime:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return datetime.utcnow()
        return v


class PreventiveAction(BaseModel):
    """Modele pour les actions preventives."""
    timestamp: str
    enseigne: str
    salle: str
    capteur_id: Optional[str] = None
    actions: List[dict]
    prediction_details: Optional[dict] = None


class ActionExecution(BaseModel):
    """Modele pour l'execution d'action."""
    action_type: str
    module_type: str
    enseigne: str
    salle: str
    reason: Optional[dict] = None
    priority: str = "medium"
    parameters: Optional[dict] = None
