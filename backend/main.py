"""
API FastAPI pour le systeme IAQ
Point d'entree principal de l'application
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import pandas as pd
import numpy as np
import asyncio
import logging

from .modelsAPI import IAQData, PreventiveAction, ActionExecution
from .utils import (
    sanitize_for_storage,
    load_dataset_df,
    load_config,
    save_config,
    extract_sensors_from_config
)
from .action_selector import IAQScoreCalculator

logger = logging.getLogger("uvicorn.error")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bases de donnees en memoire
iaq_database: List[dict] = []
preventive_actions_log: List[dict] = []
actions_execution_log: List[dict] = []

# Chargement du dataset au demarrage
DATA_DF = load_dataset_df()

# Tache de posting periodique
posting_task: Optional[asyncio.Task] = None
INTERVAL_SECONDS = 3

# Prédicteur ML (initialisé paresseusement)
ml_predictor = None

def get_ml_predictor():
    """Initialise le prédicteur ML une seule fois."""
    global ml_predictor
    if ml_predictor is None:
        try:
            from .ml.ml_predict_generic import RealtimeGenericPredictor
            model_dir = Path(__file__).parent.parent / "assets" / "ml_models"
            ml_predictor = RealtimeGenericPredictor(model_dir=model_dir)
            logger.info("✅ ML Predictor initialized")
        except Exception as e:
            logger.error(f"❌ Failed to load ML predictor: {e}")
            ml_predictor = False  # Marquer comme échoué pour ne pas réessayer
    return ml_predictor if ml_predictor is not False else None


# ============================================================================
# ENDPOINTS IAQ DATA
# ============================================================================

@app.get("/iaq/data")
def get_iaq_data(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None,
    capteur_id: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    hours: Optional[int] = None,
    step: Optional[str] = None,
    raw: bool = False
):
    """
    Endpoint unifie pour recuperer les donnees IAQ avec filtrage et agregation flexibles.
    
    Parametres de filtrage:
    - enseigne: Filtrer par enseigne
    - salle: Filtrer par salle
    - capteur_id: Filtrer par capteur
    
    Parametres temporels:
    - start: Date de debut (ISO format)
    - end: Date de fin (ISO format)
    - hours: Recupere les N dernieres heures (si start/end absents)
    
    Parametres d'agregation:
    - step: Intervalle d'agregation (5min, daily, weekly)
    - raw: Si True, retourne les donnees brutes sans agregation
    """
    if not iaq_database:
        return []
    
    try:
        df = pd.DataFrame(iaq_database)
    except Exception:
        return []
    
    if df.empty or "timestamp" not in df.columns:
        return []
    
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    try:
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        else:
            df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
    except Exception:
        pass
    
    if enseigne:
        e = enseigne.strip().lower()
        if "enseigne" in df.columns:
            df = df[df["enseigne"].astype(str).str.strip().str.lower() == e]
        else:
            return []
    
    if salle:
        s = salle.strip().lower()
        if "salle" in df.columns:
            df = df[df["salle"].astype(str).str.strip().str.lower() == s]
        else:
            return []
    
    if capteur_id:
        c = capteur_id.strip().lower()
        if "capteur_id" in df.columns:
            df = df[df["capteur_id"].astype(str).str.strip().str.lower() == c]
        else:
            return []
    
    if df.empty:
        return []
    
    try:
        start_ts = pd.to_datetime(start, utc=True) if start else None
        end_ts = pd.to_datetime(end, utc=True) if end else None
    except Exception:
        raise HTTPException(status_code=400, detail="Format de date invalide")
    
    if hours is not None and start_ts is None and end_ts is None:
        try:
            end_ts = pd.to_datetime(df["timestamp"].max(), utc=True)
            if pd.isna(end_ts):
                return []
            start_ts = end_ts - pd.Timedelta(hours=hours)
        except Exception:
            return []
    
    if start_ts is not None:
        df = df[df["timestamp"] >= start_ts]
    if end_ts is not None:
        df = df[df["timestamp"] <= end_ts]
    
    if df.empty:
        return []
    
    if raw or step is None:
        df = df.sort_values("timestamp")
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
        out = df.to_dict(orient="records")
        
        # Calculer global_score pour les données brutes aussi
        for record in out:
            try:
                predictions = {
                    "co2": record.get("co2"),
                    "pm25": record.get("pm25"),
                    "tvoc": record.get("tvoc"),
                    "humidity": record.get("humidity")
                }
                # Ne calculer que si on a au moins une valeur
                if any(v is not None for v in predictions.values()):
                    # Remplacer None par 0 pour le calcul (valeurs neutres)
                    clean_predictions = {k: (v if v is not None else 0) for k, v in predictions.items()}
                    score_data = IAQScoreCalculator.calculate_global_score(clean_predictions)
                    record["global_score"] = score_data["global_score"]
                    record["global_level"] = score_data["global_level"]
            except Exception as e:
                logger.warning(f"Erreur calcul score raw: {e}")
                record["global_score"] = None
                record["global_level"] = None
        
        return [sanitize_for_storage(r) for r in out]
    
    step_l = step.lower()
    freq_map = {"5min": "5min", "daily": "D", "weekly": "W"}
    
    if step_l not in freq_map:
        raise HTTPException(
            status_code=400,
            detail=f"Parametre 'step' invalide. Valeurs acceptees: {', '.join(freq_map.keys())}"
        )
    
    df = df.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
    
    freq = freq_map[step_l]
    metrics = ["co2", "pm25", "tvoc", "temperature", "humidity"]
    
    try:
        resampled = df.resample(freq, label="left", closed="left").mean(numeric_only=True)
    except TypeError:
        resampled = df.resample(freq, label="left", closed="left").mean()
    
    resampled = resampled.reindex(columns=[c for c in metrics if c in resampled.columns])
    
    try:
        resampled = resampled.round(2)
    except Exception:
        pass
    
    try:
        cols_to_keep = [c for c in ["enseigne", "salle", "capteur_id"] if c in df.columns]
        if cols_to_keep:
            def choose_val(s):
                m = s.dropna()
                if m.empty:
                    return None
                mode = m.mode()
                return mode.iat[0] if not mode.empty else m.iat[0]
            
            meta = df[cols_to_keep].resample(freq, label="left", closed="left").agg(
                lambda s: choose_val(s)
            )
            resampled = resampled.join(meta)
    except Exception:
        pass
    
    resampled = resampled.dropna(how="all")
    if resampled.empty:
        return []
    
    try:
        resampled.index = resampled.index.tz_convert("UTC")
    except Exception:
        pass
    
    resampled = resampled.reset_index()
    resampled["timestamp"] = resampled["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    
    out = resampled.to_dict(orient="records")
    
    # Calculer global_score pour chaque enregistrement
    for record in out:
        try:
            predictions = {
                "co2": record.get("co2"),
                "pm25": record.get("pm25"),
                "tvoc": record.get("tvoc"),
                "humidity": record.get("humidity")
            }
            # Ne calculer que si on a au moins une valeur
            if any(v is not None for v in predictions.values()):
                # Remplacer None par 0 pour le calcul (valeurs neutres)
                clean_predictions = {k: (v if v is not None else 0) for k, v in predictions.items()}
                score_data = IAQScoreCalculator.calculate_global_score(clean_predictions)
                record["global_score"] = score_data["global_score"]
                record["global_level"] = score_data["global_level"]
        except Exception as e:
            logger.warning(f"Erreur calcul score: {e}")
            record["global_score"] = None
            record["global_level"] = None
    
    return [sanitize_for_storage(r) for r in out]


# ============================================================================
# ENDPOINT ML PREDICTION
# ============================================================================

@app.get("/api/predict/score")
def get_predicted_score(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None,
    capteur_id: Optional[str] = None
):
    """
    Retourne le score IAQ prédit dans 30 minutes par le modèle ML.
    
    Args:
        enseigne: Nom de l'enseigne (défaut: "Maison")
        salle: Nom de la salle (défaut: première salle trouvée)
        capteur_id: ID du capteur (défaut: premier capteur trouvé)
        
    Returns:
        {
            "predicted_score": float (0-100),
            "predicted_level": str,
            "forecast_minutes": int,
            "predictions": {...},
            "error": str (si erreur)
        }
    """
    try:
        predictor = get_ml_predictor()
        if not predictor:
            return {
                "error": "ML model not available",
                "predicted_score": None,
                "predicted_level": None
            }
        
        # Valeurs par défaut
        if not enseigne:
            enseigne = "Maison"
        
        # Faire la prédiction
        prediction_result = predictor.predict(
            enseigne=enseigne,
            salle=salle,
            capteur_id=capteur_id
        )
        
        # Vérifier s'il y a une erreur
        if "error" in prediction_result:
            return {
                "error": prediction_result["error"],
                "predicted_score": None,
                "predicted_level": None
            }
        
        # Calculer le score global à partir des prédictions
        predicted_values = prediction_result.get("predicted_values", {})
        
        if predicted_values:
            # Utiliser le même calculateur de score que pour les données actuelles
            score_data = IAQScoreCalculator.calculate_global_score(predicted_values)
            
            return {
                "predicted_score": score_data["global_score"],
                "predicted_level": score_data["global_level"],
                "forecast_minutes": prediction_result.get("forecast_minutes", 30),
                "predictions": predicted_values,
                "enseigne": prediction_result.get("enseigne"),
                "salle": prediction_result.get("salle"),
                "capteur_id": prediction_result.get("capteur_id"),
                "timestamp": prediction_result.get("timestamp")
            }
        else:
            return {
                "error": "No predictions available",
                "predicted_score": None,
                "predicted_level": None
            }
            
    except Exception as e:
        logger.error(f"Error in predict score endpoint: {e}")
        return {
            "error": str(e),
            "predicted_score": None,
            "predicted_level": None
        }


@app.get("/iaq/debug")
def debug_iaq():
    """Endpoint de debug: affiche iaq_database dans les logs."""
    logger.info(f"iaq_database dump ({len(iaq_database)} items): {iaq_database}")
    return {"count": len(iaq_database), "sample": iaq_database[:20]}


@app.get("/api/iaq-database")
def get_iaq_database_direct(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None,
    capteur_id: Optional[str] = None,
    limit: Optional[int] = None
):
    """
    Acces direct a iaq_database pour le systeme ML.
    Retourne les donnees brutes filtrees.
    """
    if not iaq_database:
        return []
    
    filtered = iaq_database
    
    if enseigne:
        e = enseigne.strip().lower()
        filtered = [d for d in filtered if str(d.get("enseigne", "")).strip().lower() == e]
    
    if salle:
        s = salle.strip().lower()
        filtered = [d for d in filtered if str(d.get("salle", "")).strip().lower() == s]
    
    if capteur_id:
        c = capteur_id.strip().lower()
        filtered = [d for d in filtered if str(d.get("capteur_id", "")).strip().lower() == c]
    
    try:
        filtered = sorted(filtered, key=lambda x: x.get("timestamp", ""), reverse=True)
    except Exception:
        pass
    
    if limit and limit > 0:
        return filtered[:limit]
    
    return filtered


# ============================================================================
# ENDPOINTS CONFIGURATION
# ============================================================================

@app.get("/config")
def get_config():
    """Retourne la configuration complete de l'application."""
    config = load_config()
    if config is None:
        raise HTTPException(status_code=500, detail="Impossible de charger la configuration")
    return config


@app.post("/api/saveConfig")
async def save_config_endpoint(updates: dict):
    """Sauvegarde les modifications de la configuration."""
    logger.info(f"Received config updates: {list(updates.keys())}")
    config = load_config()
    if config is None:
        raise HTTPException(status_code=500, detail="Impossible de charger la configuration")
    
    def update_config(base, updates):
        for key, value in updates.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                update_config(base[key], value)
            else:
                base[key] = value
    
    update_config(config, updates)
    
    if save_config(config):
        return {"message": "Configuration mise a jour", "config": config}
    raise HTTPException(status_code=500, detail="Erreur lors de la sauvegarde")


@app.get("/api/sensors-config")
def get_sensors_config():
    """
    Retourne la liste des capteurs configures.
    Extrait automatiquement depuis config.json.
    """
    try:
        config = load_config()
        if config is None:
            raise HTTPException(status_code=500, detail="Impossible de charger la configuration")
        
        sensors = extract_sensors_from_config(config)
        
        logger.info(f"GET /api/sensors-config: {len(sensors)} capteur(s) configure(s)")
        
        return {"sensors": sensors}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur dans GET /api/sensors-config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINTS FICHIERS GLB
# ============================================================================

@app.post("/api/uploadGlb")
async def upload_glb(file: UploadFile = File(...), filename: str = Form(...)):
    """
    Upload d'un fichier .glb via multipart/form-data.
    Le fichier est enregistre dans assets/rooms/.
    """
    try:
        if not filename.lower().endswith('.glb'):
            raise HTTPException(status_code=400, detail="Le nom de fichier doit se terminer par .glb")

        rooms_dir = Path(__file__).resolve().parent.parent / 'assets' / 'rooms'
        rooms_dir.mkdir(parents=True, exist_ok=True)

        safe_name = Path(filename).name
        target = rooms_dir / safe_name

        contents = await file.read()
        with open(target, 'wb') as f:
            f.write(contents)

        rel = f"/assets/rooms/{safe_name}"
        logger.info(f"Uploaded GLB to {target}")
        return {"path": rel}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erreur lors de l'upload GLB: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'upload du fichier")


@app.post("/api/deleteFiles")
async def delete_files(paths: List[str] = Body(...)):
    """
    Supprime des fichiers listes dans le dossier assets/rooms.
    Validation de securite pour eviter suppression arbitraire.
    """
    rooms_dir = Path(__file__).resolve().parent.parent / 'assets' / 'rooms'
    rooms_dir.mkdir(parents=True, exist_ok=True)
    deleted = []
    not_found = []
    errors = {}
    
    for p in paths:
        try:
            name = str(p or '')
            if name.startswith('/'):
                name = name.lstrip('/')
            if name.startswith('assets/rooms/'):
                name = name[len('assets/rooms/'):]
            name = Path(name).name
            target = rooms_dir / name
            
            try:
                resolved = target.resolve()
            except Exception as e:
                errors[p] = f"Invalid path: {e}"
                continue
            
            if resolved.parent != rooms_dir.resolve():
                errors[p] = 'Path outside allowed directory'
                continue
            
            if target.exists():
                target.unlink()
                deleted.append(f"/assets/rooms/{name}")
            else:
                not_found.append(p)
        except Exception as e:
            errors[p] = str(e)
    
    return {"deleted": deleted, "not_found": not_found, "errors": errors}


# ============================================================================
# ENDPOINTS ACTIONS PREVENTIVES
# ============================================================================

@app.post("/api/preventive-actions")
async def post_preventive_actions(action_data: PreventiveAction):
    """
    Endpoint pour recevoir et logger les actions preventives recommandees par le systeme ML.
    """
    try:
        action_dict = action_data.dict()
        preventive_actions_log.append(action_dict)
        
        capteur_info = f"/{action_dict.get('capteur_id', 'N/A')}" if action_dict.get('capteur_id') else ""
        logger.info(f"Actions preventives recues pour {action_dict['enseigne']}/{action_dict['salle']}{capteur_info}")
        logger.info(f"Nombre d'actions: {len(action_dict['actions'])}")
        
        for action in action_dict['actions']:
            logger.info(f"- [{action.get('priority', 'N/A')}] {action.get('metric', 'N/A')}: {action.get('action', 'N/A')}")
        
        if len(preventive_actions_log) > 1000:
            preventive_actions_log[:] = preventive_actions_log[-1000:]
        
        return {
            "status": "success",
            "message": f"Actions preventives enregistrees: {len(action_dict['actions'])} actions",
            "timestamp": action_dict['timestamp']
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement des actions preventives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/preventive-actions")
def get_preventive_actions(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None,
    capteur_id: Optional[str] = None,
    limit: int = 50
):
    """Recupere l'historique des actions preventives."""
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


@app.get("/api/preventive-actions/stats")
def get_preventive_actions_stats():
    """Retourne des statistiques sur les actions preventives."""
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


# ============================================================================
# ENDPOINTS GESTION DES MODULES ET ACTIONS
# ============================================================================

@app.get("/api/room-modules")
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
                        
                        return {
                            "enseigne": enseigne,
                            "salle": salle,
                            "piece_id": piece.get("id"),
                            "modules": modules
                        }
        
        raise HTTPException(
            status_code=404,
            detail=f"Salle '{salle}' non trouvee dans l'enseigne '{enseigne}'"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la recuperation des modules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/execute-action")
async def execute_action(action: ActionExecution):
    """
    Endpoint pour executer une action sur un module.
    Cette version simule l'execution (logs uniquement).
    """
    try:
        timestamp = datetime.now().isoformat()
        
        try:
            room_modules = get_room_modules(action.enseigne, action.salle)
            modules = room_modules.get("modules", {})
            
            module_config = modules.get(action.module_type)
            
            if not module_config:
                raise HTTPException(
                    status_code=404,
                    detail=f"Module '{action.module_type}' non trouve dans la salle '{action.salle}'"
                )
            
            if not module_config.get("controllable", False):
                raise HTTPException(
                    status_code=400,
                    detail=f"Module '{action.module_type}' n'est pas controlable"
                )
                
        except HTTPException:
            raise
        
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
            "message": "Action simulee avec succes (pas de module physique connecte)"
        }
        
        actions_execution_log.append(action_log)
        
        logger.info("="*60)
        logger.info(f"EXECUTION D'ACTION: {action.action_type.upper()}")
        logger.info(f"Enseigne: {action.enseigne}")
        logger.info(f"Salle: {action.salle}")
        logger.info(f"Module: {action.module_type}")
        logger.info(f"Priorite: {action.priority}")
        
        if action.reason:
            logger.info(f"Raison: {action.reason.get('pollutant')} = {action.reason.get('value')} ({action.reason.get('level')})")
        
        if action.parameters:
            logger.info(f"Parametres: {action.parameters}")
        
        logger.info("Status: SIMULE (TODO: integrer module physique)")
        logger.info("="*60)
        
        return {
            "success": True,
            "timestamp": timestamp,
            "action": action_log,
            "message": "Action executee avec succes (mode simulation)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'execution de l'action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/actions-log")
def get_actions_log(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None,
    limit: int = 50
):
    """Retourne l'historique des actions executees."""
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


@app.get("/api/actions-stats")
def get_actions_stats():
    """Retourne des statistiques sur les actions executees."""
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


# ============================================================================
# TACHE DE POSTING PERIODIQUE
# ============================================================================

def add_iaq_record(payload: dict):
    """Ajoute un enregistrement dans iaq_database."""
    rec = sanitize_for_storage(payload)
    if "enseigne" not in rec or rec.get("enseigne") is None:
        rec["enseigne"] = "Maison"
    if "salle" not in rec or rec.get("salle") is None:
        rec["salle"] = "Bureau"
    if "capteur_id" not in rec or rec.get("capteur_id") is None:
        rec["capteur_id"] = "Bureau1"
    iaq_database.append(rec)
    logger.info(f"Seeded IAQ record, iaq_database size={len(iaq_database)}: {rec}")
    return rec


async def post_rows_periodically(interval: int = INTERVAL_SECONDS, loop_forever: bool = True):
    """Poste les lignes du DATA_DF une par une toutes les `interval` secondes."""
    try:
        if DATA_DF is None or DATA_DF.empty:
            add_iaq_record({
                "timestamp": datetime.utcnow().isoformat(),
                "co2": 400,
                "pm25": 10,
                "tvoc": 0.5,
                "temperature": 21.0,
                "humidity": 40.0,
                "enseigne": "Maison",
                "salle": "Bureau",
                "capteur_id": "Bureau1",
            })
            logger.info("No DATA_DF found; posted a single test record")
            return

        rows = list(DATA_DF.to_dict(orient="records"))
        while True:
            for row in rows:
                payload = {}
                for k, v in row.items():
                    if k == "timestamp" and v is not None:
                        try:
                            if isinstance(v, str):
                                payload["timestamp"] = pd.to_datetime(v).strftime("%Y-%m-%dT%H:%M:%S")
                            else:
                                payload["timestamp"] = pd.to_datetime(v).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%S")
                        except Exception:
                            try:
                                payload["timestamp"] = pd.to_datetime(v).strftime("%Y-%m-%dT%H:%M:%S")
                            except Exception:
                                payload["timestamp"] = str(v)
                    else:
                        if isinstance(v, (np.generic,)):
                            try:
                                v = v.item()
                            except Exception:
                                pass
                        payload[k] = None if pd.isna(v) else v

                add_iaq_record(payload)
                try:
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    logger.info("post_rows_periodically cancelled during sleep")
                    raise

            if not loop_forever:
                logger.info("Finished posting all rows once (loop_forever=False)")
                break

    except asyncio.CancelledError:
        logger.info("post_rows_periodically task cancelled")
        raise
    except Exception as e:
        logger.exception(f"Erreur dans la tache periodique de posting: {e}")


@app.on_event("startup")
async def startup_start_periodic_posting():
    """Demarre la tache asynchrone de posting periodique au lancement."""
    global posting_task
    try:
        if iaq_database:
            logger.info(f"iaq_database non vide au startup ({len(iaq_database)} items), skip periodic posting.")
            return
        posting_task = asyncio.create_task(post_rows_periodically())
        logger.info(f"Started background posting task (interval={INTERVAL_SECONDS}s)")
    except Exception as e:
        logger.exception(f"Erreur lors du demarrage de la tache periodique: {e}")


@app.on_event("shutdown")
async def shutdown_stop_periodic_posting():
    """Annule proprement la tache periodique au shutdown de l'application."""
    global posting_task
    if posting_task is None:
        return
    try:
        posting_task.cancel()
        await posting_task
    except asyncio.CancelledError:
        logger.info("Background posting task cancelled on shutdown")
    except Exception as e:
        logger.exception(f"Erreur lors de l'arret de la tache periodique: {e}")
