"""
API FastAPI pour le système IAQverse - Version 2.0
Architecture modulaire et microservices
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional, List
import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime

# Import des modules core
from .core import settings, get_influx_client, get_sqlite_registry, get_websocket_manager

# Import des routers API
from .api import (
    ingest_router,
    query_router,
    actions_router,
    modules_router,
    models_registry_router,
    config_router,
    iaq_database
)

# Import des utilitaires
from .utils import load_dataset_df

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

# Création de l'application FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Plateforme IAQ avec jumeau numérique, ML et IoT"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enregistrement des routers
app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(actions_router)
app.include_router(modules_router)
app.include_router(models_registry_router)
app.include_router(config_router)

# Chargement du dataset au démarrage
DATA_DF = load_dataset_df()

# Tâche de posting périodique
posting_task: Optional[asyncio.Task] = None
INTERVAL_SECONDS = 3

# Prédicteur ML (initialisé paresseusement)
ml_predictor = None


def get_ml_predictor():
    """Initialise le prédicteur ML une seule fois"""
    global ml_predictor
    if ml_predictor is None:
        try:
            from .ml.ml_predict_generic import RealtimeGenericPredictor
            ml_predictor = RealtimeGenericPredictor(model_dir=settings.ML_MODELS_DIR)
            logger.info("✅ ML Predictor initialized")
        except Exception as e:
            logger.error(f"❌ Failed to load ML predictor: {e}")
            ml_predictor = False
    return ml_predictor if ml_predictor is not False else None


# ============================================================================
# ENDPOINTS ML PREDICTION
# ============================================================================

@app.get("/api/predict/score")
def get_predicted_score(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None,
    capteur_id: Optional[str] = None
):
    """
    Retourne le score IAQ prédit dans 30 minutes par le modèle ML.
    """
    try:
        predictor = get_ml_predictor()
        if not predictor:
            return {
                "error": "ML model not available",
                "predicted_score": None,
                "predicted_level": None
            }
        
        if not enseigne:
            enseigne = "Maison"
        
        prediction_result = predictor.predict(
            enseigne=enseigne,
            salle=salle,
            capteur_id=capteur_id
        )
        
        if "error" in prediction_result:
            return {
                "error": prediction_result["error"],
                "predicted_score": None,
                "predicted_level": None
            }
        
        predicted_values = prediction_result.get("predicted_values", {})
        
        if predicted_values:
            from .action_selector import IAQScoreCalculator
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


@app.get("/api/predict/preventive-actions")
def get_preventive_actions(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None,
    capteur_id: Optional[str] = None
):
    """
    Analyse les prédictions ML et retourne les actions préventives à prendre.
    """
    try:
        predictor = get_ml_predictor()
        if not predictor:
            return {"actions": [], "error": "ML model not available"}
        
        if not enseigne:
            enseigne = "Maison"
        
        prediction_result = predictor.predict(
            enseigne=enseigne,
            salle=salle,
            capteur_id=capteur_id
        )
        
        if "error" in prediction_result:
            return {"actions": [], "error": prediction_result["error"]}
        
        predicted_values = prediction_result.get("predicted_values", {})
        
        # Obtenir les valeurs actuelles
        current_data = None
        if iaq_database:
            for item in reversed(iaq_database):
                if (item.get("enseigne") == prediction_result.get("enseigne") and
                    item.get("salle") == prediction_result.get("salle") and
                    item.get("capteur_id") == prediction_result.get("capteur_id")):
                    current_data = item
                    break
        
        if not current_data:
            return {"actions": [], "error": "No current data available"}
        
        # Analyser et générer les actions
        actions = []
        
        THRESHOLDS = {
            "co2": {"warning": 800, "danger": 1200},
            "pm25": {"warning": 15, "danger": 35},
            "tvoc": {"warning": 300, "danger": 1000},
            "temperature": {"cold": 18, "hot": 24},
            "humidity": {"dry": 30, "humid": 70}
        }
        
        current_co2 = float(current_data.get("co2", 0))
        predicted_co2 = float(predicted_values.get("co2", 0))
        
        if predicted_co2 >= THRESHOLDS["co2"]["warning"] and predicted_co2 > current_co2:
            priority = "high" if predicted_co2 >= THRESHOLDS["co2"]["danger"] else "medium"
            actions.append({
                "device": "window",
                "action": "open",
                "parameter": "CO₂",
                "current_value": round(current_co2, 1),
                "predicted_value": round(predicted_co2, 1),
                "threshold": THRESHOLDS["co2"]["warning"],
                "unit": "ppm",
                "priority": priority,
                "reason": f"Le CO₂ va augmenter de {current_co2:.0f} à {predicted_co2:.0f} ppm"
            })
        
        current_pm = float(current_data.get("pm25", 0))
        predicted_pm = float(predicted_values.get("pm25", 0))
        
        if predicted_pm >= THRESHOLDS["pm25"]["warning"] and predicted_pm > current_pm:
            priority = "high" if predicted_pm >= THRESHOLDS["pm25"]["danger"] else "medium"
            actions.append({
                "device": "air_purifier",
                "action": "turn_on",
                "parameter": "PM2.5",
                "current_value": round(current_pm, 1),
                "predicted_value": round(predicted_pm, 1),
                "threshold": THRESHOLDS["pm25"]["warning"],
                "unit": "µg/m³",
                "priority": priority,
                "reason": f"Les particules fines vont augmenter de {current_pm:.1f} à {predicted_pm:.1f} µg/m³"
            })
        
        priority_order = {"high": 0, "medium": 1, "low": 2}
        actions.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 99))
        
        return {
            "actions": actions,
            "forecast_minutes": prediction_result.get("forecast_minutes", 30),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in preventive actions endpoint: {e}")
        return {"actions": [], "error": str(e)}


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket pour les communications en temps réel.
    Le client peut s'abonner à différents topics : measurements, predictions, actions, alerts, modules, all
    """
    ws_manager = get_websocket_manager()
    
    # Attendre la connexion et les topics
    await ws_manager.connect(websocket, topics=["all"])
    
    try:
        while True:
            # Attendre les messages du client
            data = await websocket.receive_json()
            
            # Gérer les commandes du client
            if data.get("type") == "subscribe":
                topics = data.get("topics", [])
                for topic in topics:
                    if topic in ws_manager.subscriptions:
                        ws_manager.subscriptions[topic].add(websocket)
                        logger.info(f"Client abonné au topic: {topic}")
            
            elif data.get("type") == "unsubscribe":
                topics = data.get("topics", [])
                for topic in topics:
                    if topic in ws_manager.subscriptions:
                        ws_manager.subscriptions[topic].discard(websocket)
                        logger.info(f"Client désabonné du topic: {topic}")
            
            elif data.get("type") == "ping":
                await ws_manager.send_personal_message({"type": "pong"}, websocket)
            
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("Client WebSocket déconnecté")
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}")
        ws_manager.disconnect(websocket)


@app.get("/ws/stats")
def get_websocket_stats():
    """Retourne les statistiques des connexions WebSocket"""
    ws_manager = get_websocket_manager()
    return ws_manager.get_stats()


# ============================================================================
# TÂCHE DE POSTING PÉRIODIQUE (SIMULATION)
# ============================================================================

def add_iaq_record(payload: dict):
    """Ajoute un enregistrement dans iaq_database"""
    from .utils import sanitize_for_storage
    
    rec = sanitize_for_storage(payload)
    if "enseigne" not in rec or rec.get("enseigne") is None:
        rec["enseigne"] = "Maison"
    if "salle" not in rec or rec.get("salle") is None:
        rec["salle"] = "Bureau"
    if "capteur_id" not in rec or rec.get("capteur_id") is None:
        rec["capteur_id"] = "Bureau1"
    
    iaq_database.append(rec)
    
    # Limiter la taille
    if len(iaq_database) > settings.MAX_MEMORY_RECORDS:
        iaq_database[:] = iaq_database[-settings.MAX_MEMORY_RECORDS:]
    
    logger.info(f"Seeded IAQ record, iaq_database size={len(iaq_database)}")
    return rec


async def post_rows_periodically(interval: int = INTERVAL_SECONDS, loop_forever: bool = True):
    """Poste les lignes du DATA_DF une par une toutes les `interval` secondes"""
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
        logger.exception(f"Erreur dans la tâche périodique de posting: {e}")


# ============================================================================
# ÉVÉNEMENTS DE DÉMARRAGE ET ARRÊT
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage de l'application"""
    global posting_task
    
    logger.info("="*60)
    logger.info(f"🚀 Démarrage de {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("="*60)
    
    # Initialiser InfluxDB si configuré
    if settings.INFLUXDB_ENABLED and settings.INFLUXDB_TOKEN:
        influx = get_influx_client(
            url=settings.INFLUXDB_URL,
            token=settings.INFLUXDB_TOKEN,
            org=settings.INFLUXDB_ORG,
            bucket=settings.INFLUXDB_BUCKET
        )
        if influx and influx.available:
            logger.info("✅ InfluxDB activé")
        else:
            logger.warning("⚠️  InfluxDB configuré mais non disponible")
    else:
        logger.info("ℹ️  InfluxDB désactivé - utilisation mémoire")
    
    # Initialiser SQLite registry
    registry = get_sqlite_registry()
    logger.info("✅ SQLite registry initialisé")
    
    # Initialiser WebSocket manager
    if settings.WEBSOCKET_ENABLED:
        ws_manager = get_websocket_manager()
        logger.info("✅ WebSocket manager initialisé")
    
    # Démarrer la tâche de simulation si la base est vide
    try:
        if not iaq_database:
            posting_task = asyncio.create_task(post_rows_periodically())
            logger.info(f"✅ Tâche de simulation démarrée (interval={INTERVAL_SECONDS}s)")
        else:
            logger.info(f"ℹ️  Base de données non vide ({len(iaq_database)} items), simulation désactivée")
    except Exception as e:
        logger.exception(f"Erreur lors du démarrage de la tâche périodique: {e}")
    
    logger.info("="*60)


@app.on_event("shutdown")
async def shutdown_event():
    """Nettoyage à l'arrêt de l'application"""
    global posting_task
    
    logger.info("🛑 Arrêt de l'application...")
    
    # Arrêter la tâche de simulation
    if posting_task is not None:
        try:
            posting_task.cancel()
            await posting_task
        except asyncio.CancelledError:
            logger.info("✅ Tâche de simulation arrêtée")
        except Exception as e:
            logger.exception(f"Erreur lors de l'arrêt de la tâche: {e}")
    
    # Fermer InfluxDB
    influx = get_influx_client()
    if influx:
        influx.close()
    
    logger.info("✅ Arrêt propre terminé")


# ============================================================================
# ENDPOINT ROOT
# ============================================================================

@app.get("/")
def root():
    """Endpoint racine avec informations sur l'API"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "features": {
            "influxdb": settings.INFLUXDB_ENABLED,
            "websocket": settings.WEBSOCKET_ENABLED,
            "mqtt": settings.MQTT_ENABLED
        },
        "endpoints": {
            "docs": "/docs",
            "websocket": "/ws",
            "ingest": "/api/ingest",
            "query": "/api/iaq/data",
            "config": "/config"
        }
    }


@app.get("/health")
def health_check():
    """Endpoint de santé pour monitoring"""
    influx = get_influx_client()
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "up",
            "influxdb": "up" if (influx and influx.available) else "down",
            "websocket": "up" if settings.WEBSOCKET_ENABLED else "disabled",
            "mqtt": "up" if settings.MQTT_ENABLED else "disabled"
        },
        "data": {
            "memory_records": len(iaq_database)
        }
    }
