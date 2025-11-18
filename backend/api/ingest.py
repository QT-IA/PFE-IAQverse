"""
API endpoints pour l'ingestion de données IAQ
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime
import logging

from ..core import get_influx_client, get_websocket_manager, settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ingest"])

# Base de données en mémoire (fallback si InfluxDB n'est pas disponible)
iaq_database = []


class IAQMeasurement(BaseModel):
    """
    Modèle pour les mesures IAQ entrantes.
    Nouveau format standardisé.
    """
    sensor_id: str = Field(..., description="ID unique du capteur")
    enseigne: str = Field(..., description="Nom de l'enseigne/bâtiment")
    salle: str = Field(..., description="Nom de la salle/pièce")
    timestamp: str = Field(..., description="Timestamp ISO 8601")
    values: Dict[str, float] = Field(..., description="Valeurs mesurées (CO2, PM25, TVOC, Temperature, Humidity)")


class LegacyIAQData(BaseModel):
    """
    Ancien format de données IAQ (pour rétrocompatibilité).
    """
    timestamp: str
    co2: Optional[float] = None
    pm25: Optional[float] = None
    tvoc: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    enseigne: Optional[str] = "Maison"
    salle: Optional[str] = "Bureau"
    capteur_id: Optional[str] = None


@router.post("/ingest")
async def ingest_measurement(measurement: IAQMeasurement):
    """
    Endpoint d'ingestion pour les nouvelles mesures IAQ.
    
    Format attendu:
    {
        "sensor_id": "bureau1",
        "enseigne": "Maison",
        "salle": "Bureau",
        "timestamp": "2025-11-18T10:05:00Z",
        "values": {
            "CO2": 645,
            "PM25": 12,
            "TVOC": 0.2,
            "Temperature": 22.3,
            "Humidity": 45
        }
    }
    """
    try:
        data = measurement.dict()
        
        # Tentative d'écriture dans InfluxDB
        influx = get_influx_client(
            url=settings.INFLUXDB_URL,
            token=settings.INFLUXDB_TOKEN,
            org=settings.INFLUXDB_ORG,
            bucket=settings.INFLUXDB_BUCKET
        )
        
        if influx and influx.available:
            influx.write_measurement(data)
        
        # Stockage en mémoire (fallback)
        # Convertir au format compatible avec l'ancien système
        memory_record = {
            "sensor_id": data["sensor_id"],
            "capteur_id": data["sensor_id"],  # Alias pour compatibilité
            "enseigne": data["enseigne"],
            "salle": data["salle"],
            "timestamp": data["timestamp"],
        }
        
        # Ajouter les valeurs individuelles
        values = data.get("values", {})
        for key, value in values.items():
            memory_record[key.lower()] = value
        
        iaq_database.append(memory_record)
        
        # Limiter la taille de la mémoire
        if len(iaq_database) > settings.MAX_MEMORY_RECORDS:
            iaq_database[:] = iaq_database[-settings.MAX_MEMORY_RECORDS:]
        
        # Diffusion WebSocket
        if settings.WEBSOCKET_ENABLED:
            ws_manager = get_websocket_manager()
            await ws_manager.broadcast_measurement(data)
        
        logger.info(f"✅ Mesure ingérée: {data['sensor_id']} @ {data['enseigne']}/{data['salle']}")
        
        return {
            "status": "success",
            "message": "Mesure enregistrée",
            "sensor_id": data["sensor_id"],
            "timestamp": data["timestamp"]
        }
        
    except Exception as e:
        logger.error(f"Erreur ingestion mesure: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/iaq")
async def ingest_legacy(data: LegacyIAQData):
    """
    Endpoint legacy pour la rétrocompatibilité.
    Convertit l'ancien format vers le nouveau format.
    """
    try:
        # Convertir vers le nouveau format
        sensor_id = data.capteur_id or f"{data.salle}1"
        
        new_measurement = IAQMeasurement(
            sensor_id=sensor_id,
            enseigne=data.enseigne or "Maison",
            salle=data.salle or "Bureau",
            timestamp=data.timestamp,
            values={
                "CO2": data.co2,
                "PM25": data.pm25,
                "TVOC": data.tvoc,
                "Temperature": data.temperature,
                "Humidity": data.humidity
            }
        )
        
        # Filtrer les valeurs None
        new_measurement.values = {
            k: v for k, v in new_measurement.values.items() 
            if v is not None
        }
        
        # Réutiliser l'endpoint principal
        return await ingest_measurement(new_measurement)
        
    except Exception as e:
        logger.error(f"Erreur ingestion legacy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/iaq-database")
def get_iaq_database(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None,
    sensor_id: Optional[str] = None,
    limit: Optional[int] = 100
):
    """
    Accès direct à la base de données en mémoire.
    Utilisé comme fallback si InfluxDB n'est pas disponible.
    """
    filtered = iaq_database
    
    if enseigne:
        e = enseigne.strip().lower()
        filtered = [d for d in filtered if str(d.get("enseigne", "")).strip().lower() == e]
    
    if salle:
        s = salle.strip().lower()
        filtered = [d for d in filtered if str(d.get("salle", "")).strip().lower() == s]
    
    if sensor_id:
        sid = sensor_id.strip().lower()
        filtered = [d for d in filtered if str(d.get("sensor_id", "")).strip().lower() == sid]
    
    try:
        filtered = sorted(filtered, key=lambda x: x.get("timestamp", ""), reverse=True)
    except Exception:
        pass
    
    if limit and limit > 0:
        return filtered[:limit]
    
    return filtered


@router.get("/ingest/stats")
def get_ingest_stats():
    """Retourne des statistiques sur l'ingestion"""
    return {
        "memory_records": len(iaq_database),
        "max_memory_records": settings.MAX_MEMORY_RECORDS,
        "influxdb_enabled": settings.INFLUXDB_ENABLED,
        "websocket_enabled": settings.WEBSOCKET_ENABLED
    }
