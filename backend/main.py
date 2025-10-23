###
# Fichier de point d'entrée de l'API FastAPI
###

# Bibliothèques importées
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

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

# Configuration CORS (Autorisation du Frontend à Interroger l'API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)