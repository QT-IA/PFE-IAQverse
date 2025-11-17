"""
Service ML autonome pour les prédictions en temps réel.

Ce service:
1. Effectue des prédictions périodiques pour tous les capteurs
2. Calcule les scores IAQ prédits
3. POST automatiquement les actions préventives via l'API
4. Tourne en arrière-plan indépendamment de l'API

Usage:
    python backend/ml_service.py --interval 300
"""

import sys
import time
import logging
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Import du prédicteur générique
from ml.ml_predict_generic import RealtimeGenericPredictor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IAQScoreCalculator:
    """Calcul des scores IAQ (copie depuis action_selector.py)."""
    
    @staticmethod
    def calculate_global_score(data: Dict) -> Dict:
        """Calcule le score IAQ global (0-100)."""
        co2 = data.get("co2", 0)
        pm25 = data.get("pm25", 0)
        tvoc = data.get("tvoc", 0)
        temp = data.get("temperature", 20)
        humidity = data.get("humidity", 50)
        
        # Scores individuels (0-100, 100 = excellent)
        co2_score = max(0, 100 - (co2 / 20))  # 2000 ppm = 0
        pm25_score = max(0, 100 - (pm25 * 2))  # 50 µg/m³ = 0
        tvoc_score = max(0, 100 - (tvoc / 10))  # 1000 ppb = 0
        
        temp_score = 100
        if temp < 18 or temp > 26:
            temp_score = max(0, 100 - abs(temp - 22) * 10)
        
        hum_score = 100
        if humidity < 30 or humidity > 70:
            hum_score = max(0, 100 - abs(humidity - 50) * 2)
        
        # Score global (moyenne pondérée)
        global_score = (
            co2_score * 0.35 +
            pm25_score * 0.25 +
            tvoc_score * 0.20 +
            temp_score * 0.10 +
            hum_score * 0.10
        )
        
        # Niveau
        if global_score >= 75:
            level = "excellent"
        elif global_score >= 50:
            level = "good"
        elif global_score >= 25:
            level = "moderate"
        else:
            level = "poor"
        
        return {
            "global_score": round(global_score, 1),
            "global_level": level,
            "details": {
                "co2_score": round(co2_score, 1),
                "pm25_score": round(pm25_score, 1),
                "tvoc_score": round(tvoc_score, 1),
                "temp_score": round(temp_score, 1),
                "humidity_score": round(hum_score, 1)
            }
        }


class MLPredictionService:
    """Service de prédiction ML autonome."""
    
    def __init__(self, model_dir: Path, api_base_url: str = "http://localhost:8000"):
        self.model_dir = model_dir
        self.api_base_url = api_base_url
        self.predictor = None
        self.score_calculator = IAQScoreCalculator()
        
        # Initialiser le prédicteur
        try:
            self.predictor = RealtimeGenericPredictor(model_dir=model_dir, api_base_url=api_base_url)
            logger.info("✅ Prédicteur ML initialisé")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation du prédicteur: {e}")
            raise
    
    def get_active_sensors(self) -> List[Dict]:
        """Récupère la liste des capteurs actifs depuis l'API."""
        try:
            response = requests.get(f"{self.api_base_url}/api/iaq/sensors", timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("sensors", [])
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des capteurs: {e}")
            return []
    
    def predict_for_sensor(self, enseigne: str, salle: str, capteur_id: str) -> Optional[Dict]:
        """Effectue une prédiction pour un capteur donné."""
        try:
            logger.info(f"Prédiction pour {enseigne}/{salle}/{capteur_id}")
            
            # Faire la prédiction
            prediction_result = self.predictor.predict(
                enseigne=enseigne,
                salle=salle,
                capteur_id=capteur_id
            )
            
            if "error" in prediction_result:
                logger.warning(f"⚠️ {prediction_result['error']}")
                return None
            
            # Calculer le score IAQ prédit
            predicted_values = prediction_result.get("predicted_values", {})
            if not predicted_values:
                logger.warning("Aucune valeur prédite disponible")
                return None
            
            score_data = self.score_calculator.calculate_global_score(predicted_values)
            
            # Construire le résultat complet
            result = {
                "timestamp": prediction_result["timestamp"],
                "enseigne": enseigne,
                "salle": salle,
                "capteur_id": capteur_id,
                "current_values": prediction_result.get("current_values", {}),
                "predicted_values": predicted_values,
                "predicted_score": score_data["global_score"],
                "predicted_level": score_data["global_level"],
                "forecast_minutes": prediction_result.get("forecast_minutes", 30),
                "risk_analysis": prediction_result.get("risk_analysis", {})
            }
            
            logger.info(f"✅ Score prédit: {score_data['global_score']:.1f} ({score_data['global_level']})")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la prédiction: {e}")
            return None
    
    def post_preventive_actions(self, prediction_result: Dict) -> bool:
        """POST les actions préventives à l'API."""
        try:
            actions = prediction_result.get("risk_analysis", {}).get("actions_needed", [])
            
            if not actions:
                logger.info("✅ Aucune action préventive nécessaire")
                return True
            
            url = f"{self.api_base_url}/api/iaq/actions/preventive"
            
            payload = {
                "timestamp": prediction_result["timestamp"],
                "enseigne": prediction_result["enseigne"],
                "salle": prediction_result["salle"],
                "capteur_id": prediction_result["capteur_id"],
                "predicted_score": prediction_result["predicted_score"],
                "predicted_level": prediction_result["predicted_level"],
                "actions": actions,
                "prediction_details": {
                    "current": prediction_result["current_values"],
                    "predicted": prediction_result["predicted_values"],
                    "forecast_minutes": prediction_result["forecast_minutes"]
                }
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"✅ {len(actions)} action(s) préventive(s) envoyée(s)")
            for action in actions:
                logger.info(f"  - [{action['priority']}] {action['metric']}: {action['action']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'envoi des actions: {e}")
            return False
    
    def run_prediction_cycle(self):
        """Effectue un cycle complet de prédictions."""
        logger.info("\n" + "="*60)
        logger.info(f"Cycle de prédiction - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*60)
        
        # Récupérer les capteurs actifs
        sensors = self.get_active_sensors()
        
        if not sensors:
            logger.warning("Aucun capteur actif trouvé")
            return
        
        logger.info(f"Capteurs actifs: {len(sensors)}")
        
        # Prédictions pour chaque capteur
        for sensor in sensors:
            enseigne = sensor.get("enseigne", "Maison")
            salle = sensor.get("salle", "")
            capteur_id = sensor.get("capteur_id", "")
            
            if not capteur_id:
                continue
            
            # Faire la prédiction
            prediction = self.predict_for_sensor(enseigne, salle, capteur_id)
            
            if prediction:
                # Envoyer les actions préventives si nécessaire
                self.post_preventive_actions(prediction)
        
        logger.info("="*60 + "\n")
    
    def start(self, interval_seconds: int = 300):
        """Démarre le service en mode continu."""
        logger.info(f"🚀 Démarrage du service ML de prédiction")
        logger.info(f"Intervalle: {interval_seconds} secondes ({interval_seconds/60:.1f} minutes)")
        logger.info(f"API: {self.api_base_url}")
        logger.info(f"Modèles: {self.model_dir}")
        logger.info("\nAppuyez sur Ctrl+C pour arrêter\n")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                logger.info(f"Itération #{iteration}")
                
                # Effectuer un cycle de prédictions
                self.run_prediction_cycle()
                
                # Attendre avant la prochaine itération
                logger.info(f"⏳ Prochaine analyse dans {interval_seconds} secondes...")
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("\n🛑 Arrêt du service ML")
        except Exception as e:
            logger.error(f"❌ Erreur fatale: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(description="Service ML de prédiction IAQ")
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Intervalle entre les prédictions en secondes (défaut: 300)"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="URL de l'API (défaut: http://localhost:8000)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Effectuer une seule prédiction puis quitter"
    )
    
    args = parser.parse_args()
    
    # Chemin vers les modèles
    base_dir = Path(__file__).parent.parent
    model_dir = base_dir / "assets" / "ml_models"
    
    if not model_dir.exists():
        logger.error(f"❌ Répertoire de modèles introuvable: {model_dir}")
        logger.error("Exécutez d'abord: python backend/ml/ml_train.py")
        sys.exit(1)
    
    if not (model_dir / "generic_training_config.json").exists():
        logger.error(f"❌ Configuration de modèle introuvable dans: {model_dir}")
        logger.error("Exécutez d'abord: python backend/ml/ml_train.py")
        sys.exit(1)
    
    # Créer et démarrer le service
    try:
        service = MLPredictionService(model_dir=model_dir, api_base_url=args.api_url)
        
        if args.once:
            logger.info("Mode: Prédiction unique")
            service.run_prediction_cycle()
        else:
            service.start(interval_seconds=args.interval)
            
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
