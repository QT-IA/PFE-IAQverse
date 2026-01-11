import sys
import os

# Tenter de charger les variables d'environnement pour le test local
try:
    from dotenv import load_dotenv
    load_dotenv() # Charge le fichier .env s'il existe
    print("Fichier .env chargé (si présent).")
except ImportError:
    print("python-dotenv non installé, les variables du .env ne seront pas chargées automatiquement.")

# Ajouter le dossier courant au path pour trouver les modules backend
sys.path.append(os.getcwd())

from backend.core.syndic_alert import SyndicAlerter

print("Test de la simulation d'alerte syndic...")

# Initialisation (va utiliser le mode simulation par défaut car pas de .env chargé ici avec un vrai mdp)
alerter = SyndicAlerter()

# Envoi d'une fausse alerte
success = alerter.send_alert(
    building_name="Résidence Les Lilas",
    issue_details="Taux de CO2 > 1500ppm depuis 4h. Ventilation max inefficace.",
    duration_hours=4
)

if success:
    print("✅ Email envoyé avec succès par le script.")
    
    # --- SIMULATION API NOTIFICATION ---
    print("Tentative de notification au backend pour l'affichage frontend...")
    try:
        import requests
        resp = requests.post(
            "http://localhost:8000/api/notifications/",
            json={
                "title": "Alerte Syndic Envoyée (Test Manuel)",
                "message": "Ceci est un test manuel déclenché depuis le script de simulation.",
                "type": "syndic"
            },
            timeout=2
        )
        if resp.status_code == 200:
            print("📢 Notification envoyée au backend ! Vérifiez le Dashboard.")
        else:
            print(f"⚠️ Erreur backend: {resp.status_code}")
    except ImportError:
        print("⚠️ Module 'requests' manquant. Installez-le (pip install requests) pour tester la notif web.")
    except Exception as e:
        print(f"⚠️ Impossible de contacter le backend (est-il lancé ?) : {e}")

print("Test terminé.")
