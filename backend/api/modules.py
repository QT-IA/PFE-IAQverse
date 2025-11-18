"""
API endpoints pour la gestion des modules IoT
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

from ..core import get_sqlite_registry
from ..utils import load_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["modules"])


@router.get("/room-modules")
def get_room_modules(enseigne: str, salle: str):
    """
    Retourne la configuration des modules disponibles pour une salle.
    """
    try:
        config = load_config()
        if not config:
            raise HTTPException(status_code=500, detail="Configuration non disponible")
        
        enseignes = config.get("lieux", {}).get("enseignes", [])
        
        for ens in enseignes:
            if ens.get("nom", "").strip().lower() == enseigne.strip().lower():
                pieces = ens.get("pieces", [])
                
                for piece in pieces:
                    if piece.get("nom", "").strip().lower() == salle.strip().lower():
                        modules = piece.get("modules", {})
                        
                        # Enrichir avec l'état actuel depuis le registry
                        registry = get_sqlite_registry()
                        for module_type, module_config in modules.items():
                            state = registry.get_module_state(
                                enseigne=enseigne,
                                salle=salle,
                                module_type=module_type
                            )
                            if state:
                                module_config["current_state"] = state.get("current_state")
                                module_config["last_action"] = state.get("last_action")
                                module_config["last_action_timestamp"] = state.get("last_action_timestamp")
                        
                        return {
                            "enseigne": enseigne,
                            "salle": salle,
                            "piece_id": piece.get("id"),
                            "modules": modules
                        }
        
        raise HTTPException(
            status_code=404,
            detail=f"Salle '{salle}' non trouvée dans l'enseigne '{enseigne}'"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des modules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules/states")
def get_all_module_states(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None
):
    """
    Retourne l'état de tous les modules (depuis le registry SQLite).
    """
    try:
        registry = get_sqlite_registry()
        states = registry.list_module_states(enseigne=enseigne, salle=salle)
        return {"states": states}
        
    except Exception as e:
        logger.error(f"Erreur récupération états modules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules/{module_type}/state")
def get_module_state(
    enseigne: str,
    salle: str,
    module_type: str
):
    """
    Retourne l'état d'un module spécifique.
    """
    try:
        registry = get_sqlite_registry()
        state = registry.get_module_state(
            enseigne=enseigne,
            salle=salle,
            module_type=module_type
        )
        
        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"État du module '{module_type}' non trouvé"
            )
        
        return state
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération état module: {e}")
        raise HTTPException(status_code=500, detail=str(e))
