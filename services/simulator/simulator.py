"""
Simulateur de données capteurs IAQ
Version 2.0 - Nouveau format standardisé
"""
import requests
import random
from datetime import datetime
import time

# Configuration
API_URL = "http://localhost:8000"
INTERVAL_SECONDS = 5

# Enseignes et salles disponibles
ENSEIGNES = {
    "Maison": {
        "salles": ["Salon", "Bureau", "Chambre"],
        "sensors": {
            "Salon": ["salon1"],
            "Bureau": ["bureau1", "bureau2"],
            "Chambre": ["chambre1"]
        }
    },
    "Boutique": {
        "salles": ["Salon", "Cuisine"],
        "sensors": {
            "Salon": ["boutique_salon1"],
            "Cuisine": ["boutique_cuisine1"]
        }
    }
}

def generate_measurement(enseigne: str, salle: str, sensor_id: str):
    """
    Génère une mesure IAQ au nouveau format.
    
    Format:
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
    return {
        "sensor_id": sensor_id,
        "enseigne": enseigne,
        "salle": salle,
        "timestamp": datetime.now().isoformat() + "Z",
        "values": {
            "CO2": round(random.uniform(400, 1200), 1),
            "PM25": round(random.uniform(5, 50), 1),
            "TVOC": round(random.uniform(0.1, 2.0), 2),
            "Temperature": round(random.uniform(18, 26), 1),
            "Humidity": round(random.uniform(30, 70), 0)
        }
    }

def send_measurement(data: dict):
    """Envoie une mesure à l'API"""
    try:
        response = requests.post(f"{API_URL}/api/ingest", json=data, timeout=5)
        if response.status_code == 200:
            print(f"✅ Mesure envoyée: {data['sensor_id']} @ {data['enseigne']}/{data['salle']}")
        else:
            print(f"❌ Erreur {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur connexion API: {e}")

def main():
    """Boucle principale du simulateur"""
    print("="*60)
    print("🚀 Simulateur IAQverse v2.0")
    print(f"📡 API: {API_URL}")
    print(f"⏱️  Intervalle: {INTERVAL_SECONDS}s")
    print("="*60)
    
    while True:
        try:
            # Choisir aléatoirement une enseigne et une salle
            enseigne = random.choice(list(ENSEIGNES.keys()))
            salle = random.choice(ENSEIGNES[enseigne]["salles"])
            
            # Choisir un capteur de cette salle
            sensors = ENSEIGNES[enseigne]["sensors"].get(salle, [f"{salle.lower()}1"])
            sensor_id = random.choice(sensors) if sensors else f"{salle.lower()}1"
            
            # Générer et envoyer la mesure
            measurement = generate_measurement(enseigne, salle, sensor_id)
            send_measurement(measurement)
            
            # Attendre avant la prochaine mesure
            time.sleep(INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            print("\n\n🛑 Simulateur arrêté par l'utilisateur")
            break
        except Exception as e:
            print(f"❌ Erreur: {e}")
            time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()