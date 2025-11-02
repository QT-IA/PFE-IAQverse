###
# Fichier temporaire pour simuler l'envoi de données capteurs IAQ
###

# Bibliothèques importées
import requests
import random
from datetime import datetime
import time

ENSEIGNES = {
    "Maison": ["Salon"],
    "Boutique": ["Salon", "Cuisine", "Chambre"],
}

# Simulateur
while True:
    
    enseigne = random.choice(list(ENSEIGNES.keys()))
    salle = random.choice(ENSEIGNES[enseigne])

    data = {
        "timestamp": datetime.now().isoformat(),
        "co2": random.uniform(400, 800),
        "pm25": random.uniform(5, 30),
        "tvoc": random.uniform(0.1, 0.5),
        "temperature": random.uniform(20, 25),
        "humidity": random.uniform(40, 60),
        "enseigne": enseigne,
        "salle": salle
    }
    requests.post("http://localhost:8000/iaq", json=data)
    print("Donnée simulée envoyée pour ", enseigne, "-", salle)
    time.sleep(5)