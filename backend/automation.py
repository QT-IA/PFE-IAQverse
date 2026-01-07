
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict
from .core import settings, get_websocket_manager
from .utils import load_config, save_config

logger = logging.getLogger("iaq_automation")

class AutomationManager:
    """
    Gère l'automatisation des actions préventives basées sur les prédictions ML.
    """
    def __init__(self):
        self.running = False
        self.task = None
        self.interval = 10  # Vérifier toutes les 10 secondes
        self.last_actions = {}  # Pour éviter de spammer les mêmes actions { "room_id:device_type": timestamp }
        self.cooldown = 300  # 5 minutes de cooldown entre deux actions identiques

    async def start(self):
        """Démarre la boucle d'automatisation"""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._loop())
        logger.info("🤖 Automation Manager started")

    async def stop(self):
        """Arrête la boucle d'automatisation"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("🤖 Automation Manager stopped")

    async def _loop(self):
        """Boucle principale"""
        from .main import get_ml_predictor
        
        # Attendre que l'app soit bien démarrée
        await asyncio.sleep(5)
        
        while self.running:
            try:
                predictor = get_ml_predictor()
                if not predictor:
                    logger.warning("Predictor not ready, skipping automation cycle")
                    await asyncio.sleep(self.interval)
                    continue
                
                # Récupérer la configuration pour connaître les pièces
                config = load_config()
                if not config:
                    await asyncio.sleep(self.interval)
                    continue
                
                await self._process_automation(predictor, config)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in automation loop: {e}")
            
            await asyncio.sleep(self.interval)

    async def _process_automation(self, predictor, config):
        """Traite les prédictions pour chaque pièce configurée"""
        enseignes = config.get("lieux", {}).get("enseignes", [])
        
        for enseigne in enseignes:
            enseigne_nom = enseigne.get("nom")
            if not enseigne_nom: continue
            
            for piece in enseigne.get("pieces", []):
                piece_nom = piece.get("nom")
                piece_id = piece.get("id")
                # Utiliser le premier capteur ou defaut
                capteurs = piece.get("capteurs", [])
                sensor_id = capteurs[0] if capteurs else f"{piece_nom}1"
                
                # Obtenir les actions préventives
                # On réutilise la logique du endpoint /api/predict/preventive-actions
                # Mais on appelle directement le prédicteur pour éviter un appel HTTP interne si possible
                # Cependant, la logique de transformation "Risk -> Action" est dans main.py (_generate_actions_from_ml_risk_analysis)
                # Pour éviter la duplication de code, on va faire un appel interne simulé ou importer la fonction.
                # Le plus propre ici est d'importer la fonction depuis main (attention imports circulaires)
                # OU de déplacer la logique métier dans un service.
                # Pour faire simple : on va faire un appel HTTP local ou réimplémenter une logique simplifiée spécifique à l'automatisation.
                
                # Choix: Logique simplifiée ici pour l'instance.
                # On demande juste la prédiction ML brute
                results = predictor.predict(enseigne_nom, piece_nom, sensor_id)
                logger.info(f"🔮 Automated Prediction for {piece_nom}: {len(results.get('risk_analysis', {}).get('actions_needed', []))} actions needed")
                
                if "error" in results:
                    continue
                
                # Analyser les risques pour les devices domotiques uniquement
                # (Ventilation, Radiateur, Clim, Purificateur)
                await self._evaluate_and_execute(results, piece, enseigne_nom)

    async def _evaluate_and_execute(self, prediction_result, piece, enseigne_nom):
        """Évalue les risques et exécute les actions si nécessaire"""
        risk_analysis = prediction_result.get("risk_analysis", {})
        actions_needed = risk_analysis.get("actions_needed", [])
        
        current_values = prediction_result.get("current_values", {})
        
        # Mapping Métrique -> Device Domotique
        # On ignore CO2 -> Window car c'est manuel
        # On traite TVOC -> Ventilation
        # On pourrait traiter Temp -> Radiateur / Clim
        
        AUTOMATED_DEVICES = {
            "tvoc": {"device": "ventilation", "action_high": "on", "action_low": "off", "threshold_high": 200},
            "pm25": {"device": "air_purifier", "action_high": "on", "action_low": "off", "threshold_high": 15},
            # "temperature": ... (plus complexe avec consigne)
        }
        
        for metric, rules in AUTOMATED_DEVICES.items():
            # Vérifier si une action est recommandée par le ML
            recommended = any(a.get("metric") == metric for a in actions_needed)
            
            # Ou vérifier les seuils bruts (fallback)
            val = current_values.get(metric, 0)
            
            device_type = rules["device"]
            target_state = None
            reason = ""
            
            if recommended or val > rules["threshold_high"]:
                target_state = rules["action_high"]
                reason = f"Automated: High {metric} ({val:.1f})"
            else:
                # Si tout va bien, on peut éteindre (avec hystérésis idéalement)
                # Pour simplifier: si < seuil/2
                if val < rules["threshold_high"] * 0.8:
                    target_state = rules["action_low"]
                    reason = f"Automated: {metric} normal ({val:.1f})"

            if target_state:
                await self._try_execute_action(piece, device_type, target_state, reason)

    async def _try_execute_action(self, piece, device_type, target_state, reason):
        """Tente d'exécuter l'action en vérifiant le cooldown et l'état actuel"""
        piece_id = piece.get("id")
        key = f"{piece_id}:{device_type}"
        now = datetime.now().timestamp()
        
        # Vérifier l'état actuel dans la config
        current_config_state = get_device_state(piece, device_type)
        if current_config_state == target_state:
            return # Déjà dans le bon état
            
        # Vérifier cooldown
        last_time = self.last_actions.get(key, 0)
        if now - last_time < self.cooldown:
            return # Cooldown actif

        # Exécuter
        logger.info(f"⚡ EXECUTING AUTO ACTION: {device_type} -> {target_state} for {piece.get('nom')} ({reason})")
        
        # Appel au endpoint fictif (via fonction interne pour éviter overhead HTTP)
        success = await execute_fictive_action_internal(piece_id, device_type, target_state)
        
        if success:
            self.last_actions[key] = now
            # Notification WebSocket spéciale pour l'automatisation
            ws = get_websocket_manager()
            await ws.broadcast({
                "type": "automation_event",
                "device": device_type,
                "state": target_state,
                "room": piece.get("nom"),
                "reason": reason
            })

# Fonctions helpers

def get_device_state(piece, device_type):
    """Récupère l'état d'un device dans la config de la pièce"""
    devices = piece.get("devices", {})
    # Chercher par type (clé générique)
    if device_type in devices:
        return devices[device_type].get("state")
    
    # Chercher dans les clés complexes (ex: "Clim_Salon")
    # C'est plus dur sans mapping. On suppose que la config est bien faite.
    return None

async def execute_fictive_action_internal(piece_id, device_type, state):
    """
    Exécute l'action fictive : met à jour le fichier config.json
    """
    config = load_config()
    if not config: return False
    
    updated = False
    
    # Parcourir pour trouver la pièce
    for enseigne in config.get("lieux", {}).get("enseignes", []):
        for piece in enseigne.get("pieces", []):
            if piece.get("id") == piece_id:
                # Initialiser devices si inexistant
                if "devices" not in piece:
                    piece["devices"] = {}
                
                # Mettre à jour l'état
                if device_type not in piece["devices"]:
                    piece["devices"][device_type] = {}
                
                piece["devices"][device_type]["state"] = state
                piece["devices"][device_type]["last_update"] = datetime.now().isoformat()
                updated = True
                break
        if updated: break
    
    if updated:
        result = save_config(config)
        if result:
            # Broadcast config update
            mgr = get_websocket_manager()
            await mgr.broadcast({"type": "config_updated", "config": config}, topic="all")
            logger.info(f"✅ ACTION EXECUTED (POST-like event): {device_type} set to {state} for room {piece_id}")
            return True
            
    return False

# Instance globale
automation_manager = AutomationManager()
