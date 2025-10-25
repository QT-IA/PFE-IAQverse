###
# Fichier de point d'entrée de l'API FastAPI
###

# Bibliothèques importées
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import pandas as pd

app = FastAPI()

# Modèle de données IAQ
class IAQData(BaseModel):
    timestamp: datetime
    co2: Optional[float] = None
    pm25: Optional[float] = None
    tvoc: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None

# Base de données pour POSTs (données envoyées dynamiquement)
iaq_database: List[dict] = []

# chemin vers le CSV
DATA_DIR = Path(__file__).parent / "data" / "IoT_Indoor_Air_Quality_Dataset.csv"

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

# Endpoint pour envoyer des données capteurs (POST manuel)
@app.post("/iaq")
def receive_iaq(data: IAQData):
    iaq_database.append(data.dict())
    return {"message": "Données IAQ enregistrées", "data": data}

# Endpoint qui renvoie toutes les données IAQ — filtrage côté serveur avec pandas
@app.get("/iaq/all")
def get_all_iaq(start: Optional[str] = None, end: Optional[str] = None):
    """
    Retourne les données IAQ. Paramètres optionnels:
    - start : début de l'intervalle (format ISO ou tout format accepté par pandas.to_datetime)
    - end   : fin de l'intervalle
    Filtrage effectué côté serveur (pandas DataFrame + données POST en mémoire).
    """
    try:
        # parser en tz-aware UTC pour éviter erreur tz-naive vs tz-aware
        start_ts = pd.to_datetime(start, utc=True) if start else None
        end_ts = pd.to_datetime(end, utc=True) if end else None
    except Exception:
        raise HTTPException(status_code=400, detail="Format de date invalide pour 'start' ou 'end'")

    parts = []
    # filtrer le DataFrame (CSV) si chargé
    if DATA_DF is not None:
        df = DATA_DF.copy()
        # garantir tz-aware UTC sur la série timestamp
        try:
            if df["timestamp"].dt.tz is None:
                df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
            else:
                df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
        except Exception:
            pass

        mask = pd.Series(True, index=df.index)
        if start_ts is not None:
            mask &= df["timestamp"] >= start_ts
        if end_ts is not None:
            mask &= df["timestamp"] <= end_ts
        df_res = df.loc[mask]
        if not df_res.empty:
            df_out = df_res.copy()
            # formater en ISO sans décalage (YYYY-MM-DDTHH:MM:SS)
            df_out["timestamp"] = df_out["timestamp"].dt.tz_convert("UTC").dt.strftime("%Y-%m-%dT%H:%M:%S")
            parts.append(df_out.to_dict(orient="records"))

    # filtrer les données dynamiques postées en mémoire
    if iaq_database:
        posts_df = pd.DataFrame(iaq_database)
        if not posts_df.empty and "timestamp" in posts_df.columns:
            posts_df["timestamp"] = pd.to_datetime(posts_df["timestamp"], errors="coerce")
            # rendre tz-aware UTC pour comparaisons
            try:
                if posts_df["timestamp"].dt.tz is None:
                    posts_df["timestamp"] = posts_df["timestamp"].dt.tz_localize("UTC")
                else:
                    posts_df["timestamp"] = posts_df["timestamp"].dt.tz_convert("UTC")
            except Exception:
                pass

            mask_p = pd.Series(True, index=posts_df.index)
            if start_ts is not None:
                mask_p &= posts_df["timestamp"] >= start_ts
            if end_ts is not None:
                mask_p &= posts_df["timestamp"] <= end_ts
            posts_filtered = posts_df.loc[mask_p].copy()
            if not posts_filtered.empty:
                posts_filtered["timestamp"] = posts_filtered["timestamp"].dt.tz_convert("UTC").dt.strftime("%Y-%m-%dT%H:%M:%S")
                parts.append(posts_filtered.to_dict(orient="records"))

    # concat lists de dicts
    results = []
    for p in parts:
        results.extend(p)
    # trier par timestamp croissant avant de renvoyer
    try:
        results = sorted(results, key=lambda x: pd.to_datetime(x.get("timestamp")))
    except Exception:
        pass

    return results

# Endpoint pour forcer le rechargement depuis le CSV (utile après mise à jour du fichier)
@app.post("/iaq/load")
def reload_from_csv(path: Optional[str] = None):
    p = Path(path) if path else DATA_DIR
    if not p or not p.exists():
        raise HTTPException(status_code=404, detail=f"Fichier introuvable: {p}")
    global DATA_DF, iaq_database
    DATA_DF = load_dataset_df(p)
    # réinitialiser les posts en mémoire (optionnel) — on vide pour éviter doublons
    iaq_database = []
    return {"message": "Dataset chargé", "count": len(DATA_DF) if DATA_DF is not None else 0}

# Configuration CORS (Autorisation du Frontend à Interroger l'API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)