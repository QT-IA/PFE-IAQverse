"""
Service de prédiction en temps réel avec accès DIRECT à iaq_database.

Ce service:
1. Charge le modèle ML générique
2. Lit les données DIRECTEMENT depuis iaq_database (pas via API)
3. Prédit les valeurs futures (CO2, PM2.5, TVOC) pour N'IMPORTE QUELLE salle/capteur
4. Détecte si les seuils critiques seront dépassés
5. POST des actions préventives via l'API
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import logging
import json
import joblib
import requests
from datetime import datetime, timedelta
import time
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Seuils critiques pour la qualité de l'air
CRITICAL_THRESHOLDS = {
    "co2": {
        "warning": 1000,
        "critical": 1400,
        "danger": 2000
    },
    "pm25": {
        "warning": 25,
        "critical": 50,
        "danger": 100
    },
    "tvoc": {
        "warning": 300,
        "critical": 500,
        "danger": 1000
    },
    "humidity": {
        "warning": 60,
        "critical": 80,
        "danger": 90
    },
    "temperature": {
        "warning": 25,
        "critical": 30,
        "danger": 35
    }
}

# Actions recommandées
RECOMMENDED_ACTIONS = {
    "co2": {
        "warning": "Augmenter la ventilation",
        "critical": "Ouvrir les fenêtres immédiatement",
        "danger": "Évacuer la pièce et aérer complètement"
    },
    "pm25": {
        "warning": "Activer le purificateur d'air",
        "critical": "Purificateur à puissance maximale + ventilation",
        "danger": "Éviter la pièce, purification intensive requise"
    },
    "tvoc": {
        "warning": "Aérer la pièce pendant 15 minutes",
        "critical": "Ventilation intensive + identifier la source",
        "danger": "Évacuer et ventiler complètement la zone"
    }
}


class RealtimeGenericPredictor:
    """Service de prédiction générique avec accès direct à iaq_database."""
    
    def __init__(self, model_dir: Path, api_base_url: str = "http://localhost:8000"):
        """
        Args:
            model_dir: Répertoire contenant les modèles génériques entraînés
            api_base_url: URL de base de l'API FastAPI
        """
        self.model_dir = model_dir
        self.api_base_url = api_base_url
        self.models = {}
        self.scaler = None
        self.salle_encoder = None
        self.capteur_encoder = None
        self.config = None
        
        self.load_models()
    
    def load_models(self):
        """Charge le modèle générique et les encoders."""
        logger.info("Chargement du modèle générique...")
        
        # Charger la configuration
        config_path = self.model_dir / "generic_training_config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration non trouvée: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        logger.info(f"Configuration: {self.config['model_type']}")
        logger.info(f"Salles entraînées: {self.config['salles_trained']}")
        logger.info(f"Capteurs entraînés: {self.config['capteurs_trained']}")
        
        # Charger le scaler
        scaler_path = self.model_dir / "generic_scaler.joblib"
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)
            logger.info("✓ Scaler chargé")
        
        # Charger les encoders
        salle_encoder_path = self.model_dir / "salle_encoder.joblib"
        if salle_encoder_path.exists():
            self.salle_encoder = joblib.load(salle_encoder_path)
            logger.info("✓ Salle encoder chargé")
        
        capteur_encoder_path = self.model_dir / "capteur_encoder.joblib"
        if capteur_encoder_path.exists():
            self.capteur_encoder = joblib.load(capteur_encoder_path)
            logger.info("✓ Capteur encoder chargé")
        
        # Charger le modèle multi-output unique
        model_path = self.model_dir / "generic_multi_output.joblib"
        if model_path.exists():
            self.models["multi_output"] = joblib.load(model_path)
            logger.info(f"✓ Modèle multi-output chargé ({self.config.get('model_type', 'unknown')})")
        else:
            raise FileNotFoundError(f"Modèle multi-output non trouvé: {model_path}")
        
        logger.info("✅ Modèle générique prêt")
    
    def fetch_recent_data_direct(self, enseigne: Optional[str] = None, 
                                 salle: Optional[str] = None, 
                                 capteur_id: Optional[str] = None,
                                 limit: int = 100) -> pd.DataFrame:
        """
        Récupère les données DIRECTEMENT depuis iaq_database via l'API.
        
        Args:
            enseigne: Filtrer par enseigne
            salle: Filtrer par salle
            capteur_id: Filtrer par capteur
            limit: Nombre de lignes à récupérer
            
        Returns:
            DataFrame avec les données récentes
        """
        try:
            url = f"{self.api_base_url}/api/iaq-database"
            params = {}
            if enseigne:
                params['enseigne'] = enseigne
            if salle:
                params['salle'] = salle
            if capteur_id:
                params['capteur_id'] = capteur_id
            if limit:
                params['limit'] = limit
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if not data:
                logger.warning(f"Aucune donnée pour enseigne={enseigne}, salle={salle}, capteur={capteur_id}")
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            logger.info(f"Données récupérées: {len(df)} points")
            return df
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données: {e}")
            return pd.DataFrame()
    
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Crée les mêmes features que lors de l'entraînement."""
        df = df.copy()
        
        # Features temporelles
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        
        # Encodage salle/capteur (gérer les valeurs inconnues)
        df['salle_encoded'] = df['salle'].apply(
            lambda x: self.salle_encoder.transform([x])[0] 
            if x in self.salle_encoder.classes_ else -1
        )
        df['capteur_encoded'] = df['capteur_id'].apply(
            lambda x: self.capteur_encoder.transform([x])[0] 
            if x in self.capteur_encoder.classes_ else -1
        )
        
        # Tendances et moyennes mobiles PAR CAPTEUR
        for (salle, capteur) in df[['salle', 'capteur_id']].drop_duplicates().values:
            mask = (df['salle'] == salle) & (df['capteur_id'] == capteur)
            sensor_df = df[mask].copy()
            
            for col in ['co2', 'pm25', 'tvoc', 'temperature', 'humidity']:
                if col in sensor_df.columns:
                    df.loc[mask, f'{col}_diff'] = sensor_df[col].diff()
                    df.loc[mask, f'{col}_ma3'] = sensor_df[col].rolling(window=3, min_periods=1).mean()
        
        # Remplir les NaN
        df = df.fillna(method='bfill').fillna(method='ffill')
        
        return df
    
    def predict(self, enseigne: str = "Maison", salle: Optional[str] = None, 
                capteur_id: Optional[str] = None) -> Dict:
        """
        Effectue une prédiction pour une salle/capteur donné.
        
        Args:
            enseigne: Nom de l'enseigne
            salle: Nom de la salle (optionnel si capteur_id fourni)
            capteur_id: ID du capteur
            
        Returns:
            Dict avec les prédictions et recommandations
        """
        # Récupérer les données récentes directement de iaq_database
        df = self.fetch_recent_data_direct(enseigne, salle, capteur_id, limit=100)
        
        if df.empty or len(df) < 3:
            return {
                "error": "Not enough recent data for prediction",
                "enseigne": enseigne,
                "salle": salle,
                "capteur_id": capteur_id
            }
        
        # Prendre le dernier capteur s'il y en a plusieurs
        if capteur_id is None and 'capteur_id' in df.columns:
            capteur_id = df['capteur_id'].iloc[-1]
        if salle is None and 'salle' in df.columns:
            salle = df['salle'].iloc[-1]
        
        # Filtrer pour ce capteur spécifique
        df = df[(df['salle'] == salle) & (df['capteur_id'] == capteur_id)]
        
        if df.empty:
            return {"error": f"No data for capteur {capteur_id} in room {salle}"}
        
        # Créer les features
        df_features = self.create_features(df)
        
        # Préparer les features pour la prédiction
        feature_cols = [col for col in df_features.columns 
                       if col not in ['timestamp', 'enseigne', 'salle', 'capteur_id']]
        
        # Prendre la moyenne des dernières lignes (lookback window)
        lookback = min(self.config['lookback_minutes'], len(df_features))
        X_recent = df_features.tail(lookback)[feature_cols].values
        X_input = np.mean(X_recent, axis=0).reshape(1, -1)
        
        # Normaliser
        if self.scaler:
            X_input = self.scaler.transform(X_input)
        
        # Prédiction avec le modèle multi-output (4 cibles en une fois)
        model = self.models.get("multi_output")
        if not model:
            return {"error": "Multi-output model not loaded"}
        
        # Une seule prédiction pour les 4 cibles
        preds_array = model.predict(X_input)[0]  # Shape: (4,)
        
        # Associer les prédictions aux noms de cibles
        predictions = {
            target: float(preds_array[idx]) 
            for idx, target in enumerate(self.config['target_columns'])
        }
        
        # Valeurs actuelles
        current_values = {
            "co2": float(df['co2'].iloc[-1]) if 'co2' in df.columns else None,
            "pm25": float(df['pm25'].iloc[-1]) if 'pm25' in df.columns else None,
            "tvoc": float(df['tvoc'].iloc[-1]) if 'tvoc' in df.columns else None,
        }
        
        # Analyser les risques
        risk_analysis = self.analyze_risks(current_values, predictions)
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "enseigne": enseigne,
            "salle": salle,
            "capteur_id": capteur_id,
            "current_values": current_values,
            "predicted_values": predictions,
            "forecast_minutes": self.config['forecast_minutes'] * 5,  # Convertir en minutes
            "risk_analysis": risk_analysis
        }
        
        return result
    
    def analyze_risks(self, current: Dict, predicted: Dict) -> Dict:
        """Analyse les risques et génère les actions recommandées."""
        risks = {}
        actions_needed = []
        
        for metric in ['co2', 'pm25', 'tvoc']:
            current_val = current.get(metric)
            predicted_val = predicted.get(metric)
            
            if current_val is None or predicted_val is None:
                continue
            
            thresholds = CRITICAL_THRESHOLDS[metric]
            
            current_level = self._get_risk_level(current_val, thresholds)
            predicted_level = self._get_risk_level(predicted_val, thresholds)
            
            risks[metric] = {
                "current_value": round(current_val, 2),
                "predicted_value": round(predicted_val, 2),
                "current_level": current_level,
                "predicted_level": predicted_level,
                "trend": "increasing" if predicted_val > current_val else "decreasing",
                "change_percent": round(((predicted_val - current_val) / current_val * 100), 2) if current_val > 0 else 0
            }
            
            if predicted_level in ["critical", "danger"]:
                action = {
                    "metric": metric,
                    "level": predicted_level,
                    "action": RECOMMENDED_ACTIONS[metric][predicted_level],
                    "priority": "high" if predicted_level == "danger" else "medium",
                    "estimated_time_to_critical": f"{self.config['forecast_minutes'] * 5} minutes"
                }
                actions_needed.append(action)
            elif current_level in ["critical", "danger"]:
                action = {
                    "metric": metric,
                    "level": current_level,
                    "action": RECOMMENDED_ACTIONS[metric][current_level],
                    "priority": "urgent",
                    "estimated_time_to_critical": "Now - already critical"
                }
                actions_needed.append(action)
        
        return {
            "metrics": risks,
            "actions_needed": actions_needed,
            "overall_status": self._get_overall_status(risks)
        }
    
    def _get_risk_level(self, value: float, thresholds: Dict) -> str:
        """Détermine le niveau de risque."""
        if value >= thresholds['danger']:
            return "danger"
        elif value >= thresholds['critical']:
            return "critical"
        elif value >= thresholds['warning']:
            return "warning"
        else:
            return "good"
    
    def _get_overall_status(self, risks: Dict) -> str:
        """Détermine le statut global."""
        levels = [risk['predicted_level'] for risk in risks.values()]
        
        if "danger" in levels:
            return "danger"
        elif "critical" in levels:
            return "critical"
        elif "warning" in levels:
            return "warning"
        else:
            return "good"
    
    def post_preventive_actions(self, prediction_result: Dict) -> bool:
        """POST les actions préventives à l'API."""
        actions = prediction_result.get('risk_analysis', {}).get('actions_needed', [])
        
        if not actions:
            logger.info("✅ Aucune action préventive nécessaire")
            return True
        
        try:
            url = f"{self.api_base_url}/api/preventive-actions"
            
            payload = {
                "timestamp": prediction_result['timestamp'],
                "enseigne": prediction_result['enseigne'],
                "salle": prediction_result['salle'],
                "capteur_id": prediction_result.get('capteur_id'),
                "actions": actions,
                "prediction_details": {
                    "current": prediction_result['current_values'],
                    "predicted": prediction_result['predicted_values'],
                    "forecast_minutes": prediction_result['forecast_minutes']
                }
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"✅ Actions préventives envoyées: {len(actions)} actions")
            for action in actions:
                logger.info(f"  - [{action['priority']}] {action['metric']}: {action['action']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'envoi des actions: {e}")
            return False
    
    def monitor_continuous(self, enseigne: str = "Maison", 
                          capteurs: List[str] = None, 
                          interval_seconds: int = 300):
        """
        Surveillance continue avec prédictions périodiques.
        
        Args:
            enseigne: Nom de l'enseigne
            capteurs: Liste des IDs de capteurs à surveiller
            interval_seconds: Intervalle entre les prédictions
        """
        logger.info(f"🔄 Démarrage de la surveillance continue")
        logger.info(f"Enseigne: {enseigne}, Capteurs: {capteurs or 'TOUS'}")
        logger.info(f"Intervalle: {interval_seconds} secondes")
        
        iteration = 0
        while True:
            try:
                iteration += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"Itération #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*60}")
                
                # Si aucun capteur spécifié, récupérer tous les capteurs actifs
                if not capteurs:
                    df_all = self.fetch_recent_data_direct(enseigne=enseigne, limit=50)
                    if not df_all.empty:
                        capteurs = df_all['capteur_id'].unique().tolist()
                        logger.info(f"Capteurs détectés: {capteurs}")
                
                for capteur_id in (capteurs or []):
                    logger.info(f"\n📊 Analyse de {capteur_id}...")
                    
                    # Prédiction
                    result = self.predict(enseigne=enseigne, capteur_id=capteur_id)
                    
                    if "error" in result:
                        logger.warning(f"⚠️ {result['error']}")
                        continue
                    
                    # Afficher le résumé
                    logger.info(f"Statut: {result['risk_analysis']['overall_status'].upper()}")
                    
                    # Envoyer les actions si nécessaires
                    if result['risk_analysis']['actions_needed']:
                        self.post_preventive_actions(result)
                    else:
                        logger.info("✅ Qualité de l'air correcte")
                
                # Attendre avant la prochaine itération
                logger.info(f"\n⏳ Prochaine analyse dans {interval_seconds} secondes...")
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Arrêt de la surveillance")
                break
            except Exception as e:
                logger.error(f"❌ Erreur: {e}")
                time.sleep(interval_seconds)


def main():
    """Fonction principale."""
    
    base_dir = Path(__file__).parent.parent
    model_dir = base_dir / "assets" / "ml_models"
    
    if not model_dir.exists() or not (model_dir / "generic_training_config.json").exists():
        logger.error(f"Modèles non trouvés dans: {model_dir}")
        logger.error("Exécutez d'abord: python ml_train_generic.py")
        return
    
    # Créer le prédicteur
    predictor = RealtimeGenericPredictor(model_dir, api_base_url="http://localhost:8000")
    
    # Mode
    print("\n" + "="*60)
    print("Service de Prédiction Générique en Temps Réel")
    print("="*60)
    print("\n1. Prédiction unique")
    print("2. Surveillance continue")
    
    choice = input("\nChoisir le mode (1 ou 2): ").strip()
    
    if choice == "1":
        enseigne = input("Enseigne (défaut: Maison): ").strip() or "Maison"
        capteur_id = input("Capteur ID (ex: Bureau1): ").strip()
        
        if not capteur_id:
            print("❌ Capteur ID requis")
            return
        
        logger.info(f"\n🔮 Prédiction pour {capteur_id}...")
        result = predictor.predict(enseigne=enseigne, capteur_id=capteur_id)
        
        if "error" in result:
            logger.error(f"❌ {result['error']}")
        else:
            print("\n" + "="*60)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print("="*60)
            
            if result['risk_analysis']['actions_needed']:
                predictor.post_preventive_actions(result)
    
    elif choice == "2":
        enseigne = input("Enseigne (défaut: Maison): ").strip() or "Maison"
        capteurs_input = input("Capteurs séparés par virgules (vide = TOUS): ").strip()
        capteurs = [c.strip() for c in capteurs_input.split(",")] if capteurs_input else None
        
        interval = input("Intervalle en secondes (défaut: 300): ").strip()
        interval_seconds = int(interval) if interval.isdigit() else 300
        
        predictor.monitor_continuous(enseigne, capteurs, interval_seconds)
    
    else:
        print("Choix invalide")


if __name__ == "__main__":
    main()
