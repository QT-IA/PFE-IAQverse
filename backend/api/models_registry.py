"""
API endpoints pour la gestion du registre des modèles ML
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from ..core import get_sqlite_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["ml_registry"])


class ModelRegistration(BaseModel):
    """Modèle pour l'enregistrement d'un nouveau modèle ML"""
    model_name: str
    model_version: str
    model_type: str
    model_path: str
    metrics: Optional[Dict[str, Any]] = None
    training_date: Optional[str] = None
    set_active: bool = True


@router.post("/register")
def register_model(model_data: ModelRegistration):
    """
    Enregistre un nouveau modèle ML dans le registry.
    """
    try:
        registry = get_sqlite_registry()
        
        success = registry.register_model(
            model_name=model_data.model_name,
            model_version=model_data.model_version,
            model_type=model_data.model_type,
            model_path=model_data.model_path,
            metrics=model_data.metrics,
            training_date=model_data.training_date,
            set_active=model_data.set_active
        )
        
        if success:
            return {
                "status": "success",
                "message": f"Modèle {model_data.model_name} v{model_data.model_version} enregistré",
                "model_name": model_data.model_name,
                "model_version": model_data.model_version
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Échec de l'enregistrement du modèle"
            )
        
    except Exception as e:
        logger.error(f"Erreur enregistrement modèle: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active/{model_name}")
def get_active_model(model_name: str):
    """
    Retourne le modèle actif pour un nom donné.
    """
    try:
        registry = get_sqlite_registry()
        model = registry.get_active_model(model_name)
        
        if not model:
            raise HTTPException(
                status_code=404,
                detail=f"Aucun modèle actif trouvé pour '{model_name}'"
            )
        
        return model
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération modèle actif: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
def list_models(model_name: Optional[str] = None):
    """
    Liste tous les modèles ou ceux d'un nom spécifique.
    """
    try:
        registry = get_sqlite_registry()
        models = registry.list_models(model_name=model_name)
        
        return {
            "total": len(models),
            "models": models
        }
        
    except Exception as e:
        logger.error(f"Erreur liste modèles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/activate/{model_name}/{model_version}")
def activate_model(model_name: str, model_version: str):
    """
    Active un modèle spécifique.
    """
    try:
        registry = get_sqlite_registry()
        
        success = registry.set_active_model(
            model_name=model_name,
            model_version=model_version
        )
        
        if success:
            return {
                "status": "success",
                "message": f"Modèle {model_name} v{model_version} activé",
                "model_name": model_name,
                "model_version": model_version
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Échec de l'activation du modèle"
            )
        
    except Exception as e:
        logger.error(f"Erreur activation modèle: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training-history")
def get_training_history(
    model_name: Optional[str] = None,
    limit: int = 100
):
    """
    Retourne l'historique des entraînements.
    """
    try:
        registry = get_sqlite_registry()
        history = registry.get_training_history(
            model_name=model_name,
            limit=limit
        )
        
        return {
            "total": len(history),
            "history": history
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération historique: {e}")
        raise HTTPException(status_code=500, detail=str(e))
