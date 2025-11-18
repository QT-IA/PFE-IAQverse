"""
API endpoints pour la gestion des actions préventives et leur exécution
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from datetime import datetime
import logging

from ..modelsAPI import PreventiveAction, ActionExecution
from ..core import get_influx_client, get_websocket_manager, get_sqlite_registry, settings
from ..utils import load_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["actions"])

# Historique en mémoire (fallback)
preventive_actions_log = []
actions_execution_log = []


@router.post("/preventive-actions")
async def post_preventive_actions(action_data: PreventiveAction):
    """
    Endpoint pour recevoir et logger les actions préventives recommandées par le système ML.
    """
    try:
        action_dict = action_data.dict()
        preventive_actions_log.append(action_dict)
        
        capteur_info = f"/{action_dict.get('capteur_id', 'N/A')}" if action_dict.get('capteur_id') else ""
        logger.info(f"Actions préventives reçues pour {action_dict['enseigne']}/{action_dict['salle']}{capteur_info}")
        logger.info(f"Nombre d'actions: {len(action_dict['actions'])}")
        
        for action in action_dict['actions']:
            logger.info(f"- [{action.get('priority', 'N/A')}] {action.get('metric', 'N/A')}: {action.get('action', 'N/A')}")
        
        # Limiter la taille du log
        if len(preventive_actions_log) > 1000:
            preventive_actions_log[:] = preventive_actions_log[-1000:]
        
        # Diffusion WebSocket
        if settings.WEBSOCKET_ENABLED:
            ws_manager = get_websocket_manager()
            await ws_manager.broadcast_alert({
                "enseigne": action_dict['enseigne'],
                "salle": action_dict['salle'],
                "actions": action_dict['actions'],
                "timestamp": action_dict['timestamp']
            })
        
        return {
            "status": "success",
            "message": f"Actions préventives enregistrées: {len(action_dict['actions'])} actions",
            "timestamp": action_dict['timestamp']
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement des actions préventives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preventive-actions")
def get_preventive_actions(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None,
    capteur_id: Optional[str] = None,
    limit: int = 50
):
    """Récupère l'historique des actions préventives"""
    filtered = preventive_actions_log
    
    if enseigne:
        e = enseigne.strip().lower()
        filtered = [a for a in filtered if str(a.get("enseigne", "")).strip().lower() == e]
    
    if salle:
        s = salle.strip().lower()
        filtered = [a for a in filtered if str(a.get("salle", "")).strip().lower() == s]
    
    if capteur_id:
        c = capteur_id.strip().lower()
        filtered = [a for a in filtered if str(a.get("capteur_id", "")).strip().lower() == c]
    
    try:
        filtered = sorted(filtered, key=lambda x: x.get("timestamp", ""), reverse=True)
    except Exception:
        pass
    
    return filtered[:limit]


@router.get("/preventive-actions/stats")
def get_preventive_actions_stats():
    """Retourne des statistiques sur les actions préventives"""
    if not preventive_actions_log:
        return {
            "total_actions": 0,
            "by_room": {},
            "by_sensor": {},
            "by_metric": {},
            "by_priority": {}
        }
    
    stats = {
        "total_entries": len(preventive_actions_log),
        "total_actions": sum(len(entry.get("actions", [])) for entry in preventive_actions_log),
        "by_room": {},
        "by_sensor": {},
        "by_metric": {},
        "by_priority": {},
        "most_recent": preventive_actions_log[-1].get("timestamp") if preventive_actions_log else None
    }
    
    for entry in preventive_actions_log:
        salle = entry.get("salle", "Unknown")
        stats["by_room"][salle] = stats["by_room"].get(salle, 0) + 1
        
        capteur = entry.get("capteur_id", "Unknown")
        stats["by_sensor"][capteur] = stats["by_sensor"].get(capteur, 0) + 1
    
    for entry in preventive_actions_log:
        for action in entry.get("actions", []):
            metric = action.get("metric", "Unknown")
            priority = action.get("priority", "Unknown")
            
            stats["by_metric"][metric] = stats["by_metric"].get(metric, 0) + 1
            stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
    
    return stats


@router.post("/execute-action")
async def execute_action(action: ActionExecution):
    """
    Endpoint pour exécuter une action sur un module.
    Cette version simule l'exécution (logs uniquement).
    TODO: Intégrer MQTT pour contrôle réel des modules.
    """
    try:
        timestamp = datetime.now().isoformat()
        
        # Vérifier que le module existe et est contrôlable
        config = load_config()
        if not config:
            raise HTTPException(status_code=500, detail="Configuration non disponible")
        
        enseignes = config.get("lieux", {}).get("enseignes", [])
        module_config = None
        
        for ens in enseignes:
            if ens.get("nom", "").strip().lower() == action.enseigne.strip().lower():
                pieces = ens.get("pieces", [])
                for piece in pieces:
                    if piece.get("nom", "").strip().lower() == action.salle.strip().lower():
                        modules = piece.get("modules", {})
                        module_config = modules.get(action.module_type)
                        break
        
        if not module_config:
            raise HTTPException(
                status_code=404,
                detail=f"Module '{action.module_type}' non trouvé dans la salle '{action.salle}'"
            )
        
        if not module_config.get("controllable", False):
            raise HTTPException(
                status_code=400,
                detail=f"Module '{action.module_type}' n'est pas contrôlable"
            )
        
        # Logger l'action
        action_log = {
            "timestamp": timestamp,
            "action_type": action.action_type,
            "module_type": action.module_type,
            "enseigne": action.enseigne,
            "salle": action.salle,
            "reason": action.reason,
            "priority": action.priority,
            "parameters": action.parameters,
            "status": "simulated",
            "message": "Action simulée avec succès (pas de module physique connecté)"
        }
        
        actions_execution_log.append(action_log)
        
        # Écrire dans InfluxDB si disponible
        influx = get_influx_client(
            url=settings.INFLUXDB_URL,
            token=settings.INFLUXDB_TOKEN,
            org=settings.INFLUXDB_ORG,
            bucket=settings.INFLUXDB_BUCKET
        )
        
        if influx and influx.available:
            influx.write_action(action_log)
        
        # Mettre à jour le registry SQLite
        registry = get_sqlite_registry()
        registry.update_module_state(
            enseigne=action.enseigne,
            salle=action.salle,
            module_type=action.module_type,
            current_state=action.action_type,
            last_action=action.action_type,
            metadata=action.parameters
        )
        
        # Diffusion WebSocket
        if settings.WEBSOCKET_ENABLED:
            ws_manager = get_websocket_manager()
            await ws_manager.broadcast_action(action_log)
        
        logger.info("="*60)
        logger.info(f"EXECUTION D'ACTION: {action.action_type.upper()}")
        logger.info(f"Enseigne: {action.enseigne}")
        logger.info(f"Salle: {action.salle}")
        logger.info(f"Module: {action.module_type}")
        logger.info(f"Priorité: {action.priority}")
        
        if action.reason:
            logger.info(f"Raison: {action.reason.get('pollutant')} = {action.reason.get('value')} ({action.reason.get('level')})")
        
        if action.parameters:
            logger.info(f"Paramètres: {action.parameters}")
        
        logger.info("Status: SIMULÉ (TODO: intégrer MQTT)")
        logger.info("="*60)
        
        return {
            "success": True,
            "timestamp": timestamp,
            "action": action_log,
            "message": "Action exécutée avec succès (mode simulation)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de l'action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions-log")
def get_actions_log(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None,
    limit: int = 50
):
    """Retourne l'historique des actions exécutées"""
    if not actions_execution_log:
        return []
    
    filtered = actions_execution_log
    
    if enseigne:
        e = enseigne.strip().lower()
        filtered = [a for a in filtered if str(a.get("enseigne", "")).strip().lower() == e]
    
    if salle:
        s = salle.strip().lower()
        filtered = [a for a in filtered if str(a.get("salle", "")).strip().lower() == s]
    
    try:
        filtered = sorted(filtered, key=lambda x: x.get("timestamp", ""), reverse=True)
    except Exception:
        pass
    
    return filtered[:limit]


@router.get("/actions-stats")
def get_actions_stats():
    """Retourne des statistiques sur les actions exécutées"""
    if not actions_execution_log:
        return {
            "total_actions": 0,
            "by_room": {},
            "by_module": {},
            "by_action_type": {},
            "by_priority": {}
        }
    
    stats = {
        "total_actions": len(actions_execution_log),
        "by_room": {},
        "by_module": {},
        "by_action_type": {},
        "by_priority": {},
        "most_recent": actions_execution_log[-1].get("timestamp") if actions_execution_log else None
    }
    
    for action in actions_execution_log:
        salle = action.get("salle", "Unknown")
        stats["by_room"][salle] = stats["by_room"].get(salle, 0) + 1
        
        module = action.get("module_type", "Unknown")
        stats["by_module"][module] = stats["by_module"].get(module, 0) + 1
        
        action_type = action.get("action_type", "Unknown")
        stats["by_action_type"][action_type] = stats["by_action_type"].get(action_type, 0) + 1
        
        priority = action.get("priority", "Unknown")
        stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
    
    return stats
