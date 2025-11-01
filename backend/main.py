###
# Fichier de point d'entrée de l'API FastAPI
###

# Bibliothèques importées
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import json
from pathlib import Path

app = FastAPI()

# Modèle de données IAQ
class IAQData(BaseModel):
    timestamp: datetime
    co2: float
    pm25: float
    tvoc: float
    temperature: float
    humidity: float

# Base de données simulée
iaq_database = [] 

# Endpoint pour envoyer des données capteurs
@app.post("/iaq")
def receive_iaq(data: IAQData):
    iaq_database.append(data)
    return {"message": "Données IAQ enregistrées", "data": data}

# Edpoint qui renvoie toutes les données IAQ
@app.get("/iaq/all")
def get_all_iaq():
    return iaq_database

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

# Configuration CORS (Autorisation du Frontend à Interroger l'API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)