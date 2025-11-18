"""
API endpoints pour interroger les données IAQ
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import pandas as pd
from datetime import datetime
import logging

from ..core import get_influx_client, settings
from ..utils import sanitize_for_storage
from ..iaq_score import calculate_iaq_score
from .ingest import iaq_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["query"])


@router.get("/iaq/data")
def get_iaq_data(
    enseigne: Optional[str] = None,
    salle: Optional[str] = None,
    sensor_id: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    hours: Optional[int] = None,
    step: Optional[str] = None,
    raw: bool = False
):
    """
    Endpoint unifié pour récupérer les données IAQ avec filtrage et agrégation flexibles.
    
    Paramètres de filtrage:
    - enseigne: Filtrer par enseigne
    - salle: Filtrer par salle
    - sensor_id: Filtrer par capteur
    
    Paramètres temporels:
    - start: Date de début (ISO format)
    - end: Date de fin (ISO format)
    - hours: Récupère les N dernières heures (si start/end absents)
    
    Paramètres d'agrégation:
    - step: Intervalle d'agrégation (5min, daily, weekly)
    - raw: Si True, retourne les données brutes sans agrégation
    """
    # Essayer d'abord InfluxDB
    influx = get_influx_client(
        url=settings.INFLUXDB_URL,
        token=settings.INFLUXDB_TOKEN,
        org=settings.INFLUXDB_ORG,
        bucket=settings.INFLUXDB_BUCKET
    )
    
    if influx and influx.available:
        try:
            # Déterminer la période
            if hours is not None and not start and not end:
                start_time = f"-{hours}h"
            else:
                start_time = start if start else "-24h"
            
            # Construire la requête Flux
            filters = []
            if enseigne:
                filters.append(f'r.enseigne == "{enseigne}"')
            if salle:
                filters.append(f'r.salle == "{salle}"')
            if sensor_id:
                filters.append(f'r.sensor_id == "{sensor_id}"')
            
            filter_clause = " and ".join(filters) if filters else "true"
            
            flux_query = f'''
                from(bucket: "{settings.INFLUXDB_BUCKET}")
                    |> range(start: {start_time})
                    |> filter(fn: (r) => r._measurement == "iaq_raw")
                    |> filter(fn: (r) => {filter_clause})
                    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                    |> sort(columns: ["_time"])
            '''
            
            influx_data = influx.query_data(flux_query)
            
            if influx_data:
                # Ajouter global_score pour chaque point
                for record in influx_data:
                    try:
                        predictions = {
                            "co2": record.get("co2"),
                            "pm25": record.get("pm25"),
                            "tvoc": record.get("tvoc"),
                            "humidity": record.get("humidity")
                        }
                        clean_predictions = {k: (v if v is not None else 0) for k, v in predictions.items()}
                        score_data = calculate_iaq_score(clean_predictions)
                        record["global_score"] = score_data["global_score"]
                        record["global_level"] = score_data["global_level"]
                    except Exception as e:
                        logger.warning(f"Erreur calcul score: {e}")
                        record["global_score"] = None
                        record["global_level"] = "unknown"
                
                logger.info(f"✅ Données récupérées depuis InfluxDB: {len(influx_data)} points")
                return influx_data
        except Exception as e:
            logger.warning(f"Erreur requête InfluxDB, fallback mémoire: {e}")
    
    # Fallback sur la mémoire
    logger.info("📝 Utilisation fallback mémoire")
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
    
    # Filtrage
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
    
    if sensor_id:
        c = sensor_id.strip().lower()
        if "sensor_id" in df.columns:
            df = df[df["sensor_id"].astype(str).str.strip().str.lower() == c]
        else:
            return []
    
    if df.empty:
        return []
    
    # Filtrage temporel
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
    
    # Mode raw
    if raw or step is None:
        df = df.sort_values("timestamp")
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
        out = df.to_dict(orient="records")
        
        # Calculer global_score
        for record in out:
            try:
                predictions = {
                    "co2": record.get("co2"),
                    "pm25": record.get("pm25"),
                    "tvoc": record.get("tvoc"),
                    "humidity": record.get("humidity")
                }
                if any(v is not None for v in predictions.values()):
                    clean_predictions = {k: (v if v is not None else 0) for k, v in predictions.items()}
                    score_data = calculate_iaq_score(clean_predictions)
                    record["global_score"] = score_data["global_score"]
                    record["global_level"] = score_data["global_level"]
            except Exception as e:
                logger.warning(f"Erreur calcul score raw: {e}")
                record["global_score"] = None
                record["global_level"] = None
        
        return [sanitize_for_storage(r) for r in out]
    
    # Agrégation
    step_l = step.lower()
    freq_map = {"5min": "5min", "daily": "D", "weekly": "W"}
    
    if step_l not in freq_map:
        raise HTTPException(
            status_code=400,
            detail=f"Paramètre 'step' invalide. Valeurs acceptées: {', '.join(freq_map.keys())}"
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
        cols_to_keep = [c for c in ["enseigne", "salle", "sensor_id"] if c in df.columns]
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
    
    # Calculer global_score
    for record in out:
        try:
            predictions = {
                "co2": record.get("co2"),
                "pm25": record.get("pm25"),
                "tvoc": record.get("tvoc"),
                "humidity": record.get("humidity")
            }
            if any(v is not None for v in predictions.values()):
                clean_predictions = {k: (v if v is not None else 0) for k, v in predictions.items()}
                score_data = calculate_iaq_score(clean_predictions)
                record["global_score"] = score_data["global_score"]
                record["global_level"] = score_data["global_level"]
        except Exception as e:
            logger.warning(f"Erreur calcul score: {e}")
            record["global_score"] = None
            record["global_level"] = None
    
    return [sanitize_for_storage(r) for r in out]


@router.get("/iaq/debug")
def debug_iaq():
    """Endpoint de debug: affiche iaq_database dans les logs"""
    logger.info(f"iaq_database dump ({len(iaq_database)} items): {iaq_database[:5]}")
    return {"count": len(iaq_database), "sample": iaq_database[:20]}
