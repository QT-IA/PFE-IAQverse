###
# Fichier de point d'entrée de l'API FastAPI
###

# Bibliothèques importées
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Any, List, Optional
from pathlib import Path
import pandas as pd
import math
import numpy as np
import json
import asyncio
import logging
logger = logging.getLogger("uvicorn.error")

app = FastAPI()

# Modèle de données IAQ — accepter explicitement les valeurs nulles / vides
class IAQData(BaseModel):
    timestamp: Optional[datetime] = None
    co2: Optional[float] = None
    pm25: Optional[float] = None
    tvoc: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    enseigne: Optional[str] = "Maison"
    salle: Optional[str] = "Salon"

    # pour gerer les valeurs vides / nulles (pré-validation)
    @field_validator("*", mode="before")
    def empty_to_none(cls, v: Any) -> Any:
        # convertir '', 'null' ou NaN en None
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        # gérer les floats NaN transmis
        try:
            if isinstance(v, float) and math.isnan(v):
                return None
        except Exception:
            pass
        return v

    @field_validator("timestamp", mode="before")
    def ensure_timestamp(cls, v: Any) -> datetime:
        # si pas fourni ou vide -> now en UTC (évite erreurs de validation)
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return datetime.utcnow()
        return v

# Base de données pour POSTs (données envoyées dynamiquement)
iaq_database: List[dict] = []

# chemin vers le CSV
DATA_DIR = Path(__file__).parent.parent / "assets" / "datasets" / "IoT_Indoor_Air_Quality_Dataset.csv"

##################
# traitement du CSV pour charger un DataFrame standardisé

def _find_col(cols_map, key_candidates):
    for k in key_candidates:
        for k0, v in cols_map.items():
            if k in k0:
                return v
    return None

def load_dataset_df(path: Optional[Path] = None) -> Optional[pd.DataFrame]:
    """Charge le CSV et retourne un DataFrame standardisé (colonnes: timestamp, co2, pm25, tvoc, temperature, humidity)."""
    p = Path(path) if path else DATA_DIR
    if not p or not p.exists():
        return None

    df = pd.read_csv(p)
    cols = {c.lower(): c for c in df.columns}

    ts_col = _find_col(cols, ["timestamp", "time", "date", "datetime"])
    co2_col = _find_col(cols, ["co2", "co_2"])
    pm25_col = _find_col(cols, ["pm2.5", "pm25", "pm_2_5", "pm2"])
    tvoc_col = _find_col(cols, ["tvoc"])
    temp_col = _find_col(cols, ["temperature", "temp"])
    hum_col = _find_col(cols, ["humidity", "hum"])

    out = pd.DataFrame()
    # timestamp
    if ts_col:
        out["timestamp"] = pd.to_datetime(df[ts_col], dayfirst=True, errors="coerce")
    else:
        out["timestamp"] = pd.NaT
    # numériques
    def to_num(col):
        return pd.to_numeric(df[col], errors="coerce") if col else pd.Series([pd.NA]*len(df))

    out["co2"] = to_num(co2_col)
    out["pm25"] = to_num(pm25_col)
    out["tvoc"] = to_num(tvoc_col)
    out["temperature"] = to_num(temp_col)
    out["humidity"] = to_num(hum_col)
    out["enseigne"] = "Maison"  # valeur par défaut si non présente
    out["salle"] = "Salon"    # valeur par défaut si non présente

    # supprimer lignes sans timestamp valide
    out = out.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    # rendre les timestamps cohérents (tz-aware UTC) pour comparaisons serveur
    try:
        if out["timestamp"].dt.tz is None:
            out["timestamp"] = out["timestamp"].dt.tz_localize("UTC")
        else:
            out["timestamp"] = out["timestamp"].dt.tz_convert("UTC")
    except Exception:
        # si problème, on laisse tel quel (comparaisons gérées ensuite)
        pass
    return out

# charger le DataFrame au démarrage (si présent)
DATA_DF = load_dataset_df()

def _sanitize_for_storage(d: dict) -> dict:
    """Prépare l'enregistrement pour stockage/JSON-friendly (datetime -> ISO, NaN/inf -> None, numpy -> Python)."""
    out = {}
    for k, v in d.items():
        # si datetime (déjà formaté en str pour DATA_DF), conserver tel quel
        if isinstance(v, datetime):
            out[k] = v.isoformat()
            continue
        # pandas/np missing
        try:
            if pd.isna(v):
                out[k] = None
                continue
        except Exception:
            pass
        # numpy scalar -> python
        if isinstance(v, np.generic):
            try:
                v = v.item()
            except Exception:
                pass
        # floats inf / -inf -> None
        if isinstance(v, float):
            if not math.isfinite(v):
                out[k] = None
                continue
        out[k] = v
    return out

# Edpoint qui renvoie toutes les données IAQ selon l'enseigne et la salle
@app.get("/iaq/filter")
def get_filtered_iaq(enseigne: str, salle: str):
    """
    Retourne les posts en mémoire filtrés par enseigne + salle.
    """
    if not iaq_database:
        return []
    e = (enseigne or "").strip().lower()
    s = (salle or "").strip().lower()
    def match(d):
        return (str(d.get("enseigne") or "").strip().lower() == e) and (str(d.get("salle") or "").strip().lower() == s)
    return [d for d in iaq_database if match(d)]


# Endpoint qui renvoie toutes les données IAQ — filtrage côté serveur (localement pour l'instant) avec pandas
@app.get("/iaq/all")
def get_all_iaq(start: Optional[str] = None, end: Optional[str] = None, step: str = "5min"):
    """
    Retourne les données IAQ provenant uniquement des posts reçus en mémoire (`iaq_database`).
    Paramètres:
    - start : début de l'intervalle (ISO ou format accepté par pandas)
    - end   : fin de l'intervalle
    - step  : "5min" (par défaut), "daily", "weekly"
    Le comportement de filtrage et d'agrégation est conservé.
    """
    step_l = (step or "5min").lower()
    # Utiliser 'min' (minutes) au lieu de l'alias 'T' désormais déprécié dans pandas
    freq_map = {"5min": "5min", "daily": "D", "weekly": "W"}
    if step_l not in freq_map:
        raise HTTPException(status_code=400, detail=f"Paramètre 'step' invalide. Valeurs acceptées: {', '.join(freq_map.keys())}")

    try:
        start_ts = pd.to_datetime(start, utc=True) if start else None
        end_ts = pd.to_datetime(end, utc=True) if end else None
    except Exception:
        raise HTTPException(status_code=400, detail="Format de date invalide pour 'start' ou 'end'")

    # Utiliser uniquement les données postées en mémoire
    if not iaq_database:
        return []

    try:
        posts_df = pd.DataFrame(iaq_database)
    except Exception:
        return []

    if posts_df.empty or "timestamp" not in posts_df.columns:
        return []

    posts_df["timestamp"] = pd.to_datetime(posts_df["timestamp"], errors="coerce", utc=True)
    try:
        if posts_df["timestamp"].dt.tz is None:
            posts_df["timestamp"] = posts_df["timestamp"].dt.tz_localize("UTC")
        else:
            posts_df["timestamp"] = posts_df["timestamp"].dt.tz_convert("UTC")
    except Exception:
        pass

    mask = pd.Series(True, index=posts_df.index)
    if start_ts is not None:
        try:
            mask &= posts_df["timestamp"] >= start_ts
        except Exception:
            pass
    if end_ts is not None:
        try:
            mask &= posts_df["timestamp"] <= end_ts
        except Exception:
            pass

    df_filtered = posts_df.loc[mask].copy()
    if df_filtered.empty:
        return []

    # préparer DataFrame pour resampling
    df_filtered = df_filtered.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()

    freq = freq_map[step_l]
    metrics = ["co2", "pm25", "tvoc", "temperature", "humidity"]
    # resample et moyenne
    try:
        resampled = df_filtered.resample(freq, label="left", closed="left").mean(numeric_only=True)
    except TypeError:
        resampled = df_filtered.resample(freq, label="left", closed="left").mean()

    resampled = resampled.reindex(columns=[c for c in metrics if c in resampled.columns])
    try:
        resampled = resampled.round(2)
    except Exception:
        pass

    # conserver 'enseigne' et 'salle' par période
    try:
        cols_to_keep = [c for c in ["enseigne", "salle"] if c in df_filtered.columns]
        if cols_to_keep:
            def choose_val(s):
                m = s.dropna()
                if m.empty:
                    return None
                mode = m.mode()
                return mode.iat[0] if not mode.empty else m.iat[0]

            meta = df_filtered[cols_to_keep].resample(freq, label="left", closed="left").agg(lambda s: choose_val(s))
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
    out = [_sanitize_for_storage(r) for r in out]

    return out


# Endpoint fenêtré: filtre par enseigne/salle et renvoie un intervalle temporel + agrégation
@app.get("/iaq/window")
def get_iaq_window(
    enseigne: str,
    salle: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    hours: Optional[int] = 1,
    step: str = "5min",
):
    """
    Retourne les données IAQ filtrées par enseigne+salle sur une fenêtre temporelle
    et agrégées selon `step`.

    - Paramètres:
      - enseigne (str) : nom exact (ex: "Maison")
      - salle (str)    : nom exact (ex: "Salon")
      - start/end (str, optionnels) : bornes temporelles (ISO ou parseable par pandas)
      - hours (int, optionnel, défaut 1) : si start/end absents, on prend la dernière heure disponible
      - step (str) : "5min" (défaut), "daily", "weekly"
    """
    step_l = (step or "5min").lower()
    # Utiliser 'min' (minutes) au lieu de l'alias 'T' désormais déprécié dans pandas
    freq_map = {"5min": "5min", "daily": "D", "weekly": "W"}
    if step_l not in freq_map:
        raise HTTPException(status_code=400, detail=f"Paramètre 'step' invalide. Valeurs acceptées: {', '.join(freq_map.keys())}")

    if not iaq_database:
        return []

    # DataFrame depuis les posts
    df = pd.DataFrame(iaq_database)
    if df.empty or "timestamp" not in df.columns:
        return []

    # parse timestamps et normaliser en UTC
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    try:
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        else:
            df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
    except Exception:
        pass

    # filtre enseigne/salle (case-insensitive)
    e = (enseigne or "").strip().lower()
    s = (salle or "").strip().lower()
    if "enseigne" in df.columns:
        df = df[df["enseigne"].astype(str).str.strip().str.lower() == e]
    else:
        df = df.iloc[0:0]
    if "salle" in df.columns:
        df = df[df["salle"].astype(str).str.strip().str.lower() == s]
    else:
        df = df.iloc[0:0]
    if df.empty:
        return []

    # déterminer la fenêtre temporelle
    try:
        start_ts = pd.to_datetime(start, utc=True) if start else None
        end_ts = pd.to_datetime(end, utc=True) if end else None
    except Exception:
        raise HTTPException(status_code=400, detail="Format de date invalide pour 'start' ou 'end'")

    if start_ts is None and end_ts is None:
        # par défaut: dernière 'hours' (défaut 1h) en se basant sur le max timestamp dispo
        try:
            end_ts = pd.to_datetime(df["timestamp"].max(), utc=True)
        except Exception:
            return []
        if pd.isna(end_ts):
            return []
        h = int(hours or 1)
        start_ts = end_ts - pd.Timedelta(hours=h)

    # filtrage temporel
    mask = pd.Series(True, index=df.index)
    if start_ts is not None:
        try:
            mask &= df["timestamp"] >= start_ts
        except Exception:
            pass
    if end_ts is not None:
        try:
            mask &= df["timestamp"] <= end_ts
        except Exception:
            pass
    df = df.loc[mask]
    if df.empty:
        return []

    # resampling
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

    # conserver enseigne/salle par période (mode)
    try:
        cols_to_keep = [c for c in ["enseigne", "salle"] if c in df.columns]
        if cols_to_keep:
            def choose_val(s):
                m = s.dropna()
                if m.empty:
                    return None
                mode = m.mode()
                return mode.iat[0] if not mode.empty else m.iat[0]

            meta = df[cols_to_keep].resample(freq, label="left", closed="left").agg(lambda s: choose_val(s))
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
    out = [_sanitize_for_storage(r) for r in out]
    return out


# Configuration CORS (Autorisation du Frontend à Interroger l'API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = Path(__file__).resolve().parent.parent / 'assets' / 'config.json'

def load_config():
    try:
        if not CONFIG_PATH.exists():
            print(f"Fichier de configuration introuvable: {CONFIG_PATH}")
            return None
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        return cfg
    except Exception as e:
        print(f"Erreur lors du chargement de la configuration : {e}")
        return None

def save_config(config):
    try:
        # ensure parent exists
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        # write to temp file then replace (atomic-ish)
        tmp = CONFIG_PATH.with_suffix('.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        tmp.replace(CONFIG_PATH)
        print(f"Configuration sauvegardée dans {CONFIG_PATH}")
        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde de la configuration : {e}")
        return False

@app.get("/config")
def get_config():
    config = load_config()
    if config is None:
        return {"error": "Impossible de charger la configuration"}, 500
    return config

@app.post("/api/saveConfig")
async def save_config_endpoint(updates: dict):
    print(f"Received updates: {updates}")
    config = load_config()
    if config is None:
        return {"error": "Impossible de charger la configuration"}, 500
    
    def update_config(base, updates):
        for key, value in updates.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                update_config(base[key], value)
            else:
                base[key] = value
    
    update_config(config, updates)
    
    if save_config(config):
        # return the updated config to client for confirmation
        return {"message": "Configuration mise à jour", "config": config}
    return {"error": "Erreur lors de la sauvegarde"}, 500

# Endpoint de debug pour iaq_database (local)
@app.get("/iaq/debug")
def debug_iaq():
    """Endpoint de debug : affiche iaq_database dans les logs et renvoie un résumé."""
    logger.info("iaq_database dump (%d items): %s", len(iaq_database), iaq_database)
    # sortie courte au client pour éviter d'envoyer trop de données
    return {"count": len(iaq_database), "sample": iaq_database[:20]}

def add_iaq_record(payload: dict):
    """Ajoute un enregistrement dans iaq_database en réutilisant la sanitisation."""
    rec = _sanitize_for_storage(payload)
    if "enseigne" not in rec or rec.get("enseigne") is None:
        rec["enseigne"] = "Maison"
    if "salle" not in rec or rec.get("salle") is None:
        rec["salle"] = "Salon"
    iaq_database.append(rec)
    logger.info("Seeded IAQ record, iaq_database size=%d : %s", len(iaq_database), rec)
    return rec

# Background posting task control
posting_task: Optional[asyncio.Task] = None
INTERVAL_SECONDS = 3  # intervalle entre posts (secondes)


async def _post_rows_periodically(interval: int = INTERVAL_SECONDS, loop_forever: bool = True):
    """Poste les lignes du DATA_DF une par une toutes les `interval` secondes.
    Si `loop_forever` est True, recommence au début une fois le dataset épuisé.
    """
    try:
        if DATA_DF is None or DATA_DF.empty:
            # fallback : ajouter un enregistrement de test unique
            add_iaq_record({
                "timestamp": datetime.utcnow().isoformat(),
                "co2": 400,
                "pm25": 10,
                "tvoc": 0.5,
                "temperature": 21.0,
                "humidity": 40.0,
                "enseigne": "Maison",
                "salle": "Salon",
            })
            logger.info("No DATA_DF found; posted a single test record")
            return

        # prepare rows as list of dict-like rows to avoid holding pandas iterators across await points
        rows = list(DATA_DF.to_dict(orient="records"))
        while True:
            for row in rows:
                payload = {}
                for k, v in row.items():
                    if k == "timestamp" and v is not None:
                        try:
                            # timestamp peut déjà être string ou datetime
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
                        # convertir numpy scalars en python natifs
                        if isinstance(v, (np.generic,)):
                            try:
                                v = v.item()
                            except Exception:
                                pass
                        payload[k] = None if pd.isna(v) else v

                add_iaq_record(payload)
                # attendre avant d'envoyer la ligne suivante
                try:
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    logger.info("_post_rows_periodically cancelled during sleep")
                    raise

            if not loop_forever:
                logger.info("Finished posting all rows once (loop_forever=False)")
                break

    except asyncio.CancelledError:
        logger.info("_post_rows_periodically task cancelled")
        raise
    except Exception as e:
        logger.exception("Erreur dans la tâche périodique de posting: %s", e)


@app.on_event("startup")
async def startup_start_periodic_posting():
    """Démarre la tâche asynchrone de posting périodique au lancement d'uvicorn.
    Ne démarre pas si `iaq_database` contient déjà des données (évite doublons).
    """
    global posting_task
    try:
        if iaq_database:
            logger.info("iaq_database non vide au startup (%d items), skip periodic posting.", len(iaq_database))
            return
        # créer la tâche en arrière-plan
        posting_task = asyncio.create_task(_post_rows_periodically())
        logger.info("Started background posting task (interval=%ds)", INTERVAL_SECONDS)
    except Exception as e:
        logger.exception("Erreur lors du démarrage de la tâche périodique: %s", e)


@app.on_event("shutdown")
async def shutdown_stop_periodic_posting():
    """Annule proprement la tâche périodique au shutdown de l'application."""
    global posting_task
    if posting_task is None:
        return
    try:
        posting_task.cancel()
        await posting_task
    except asyncio.CancelledError:
        logger.info("Background posting task cancelled on shutdown")
    except Exception as e:
        logger.exception("Erreur lors de l'arrêt de la tâche périodique: %s", e)