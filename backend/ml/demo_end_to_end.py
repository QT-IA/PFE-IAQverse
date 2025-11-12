"""
Démo End-to-End du Système IAQverse.

Ce script démontre le flux complet :
1. Génération de données IAQ simulées
2. Prédictions ML
3. Calcul du score IAQ
4. Sélection d'actions correctives
5. Envoi via API

Usage:
    python demo_end_to_end.py
"""

import sys
from pathlib import Path
import logging
import json
from datetime import datetime
import time

# Ajouter le répertoire backend au path
sys.path.insert(0, str(Path(__file__).parent))

from action_selector import (
    IAQScoreCalculator,
    ActionSelector,
    RoomModules,
    ModuleCapability
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IAQDemoScenario:
    """Scénario de démonstration du système IAQ."""
    
    def __init__(self):
        self.scenarios = self.create_scenarios()
    
    def create_scenarios(self):
        """Crée différents scénarios de test."""
        return {
            "normal": {
                "name": "Qualité d'air normale",
                "description": "Tous les paramètres sont dans les normes",
                "predictions": {
                    "co2": 750,
                    "pm25": 12,
                    "tvoc": 200,
                    "humidity": 45
                }
            },
            "high_co2": {
                "name": "CO2 élevé",
                "description": "Besoin d'aération - CO2 trop élevé",
                "predictions": {
                    "co2": 1450,
                    "pm25": 15,
                    "tvoc": 250,
                    "humidity": 45
                }
            },
            "pollution": {
                "name": "Pollution de l'air",
                "description": "PM2.5 et TVOC élevés",
                "predictions": {
                    "co2": 800,
                    "pm25": 60,
                    "tvoc": 650,
                    "humidity": 45
                }
            },
            "critical": {
                "name": "Situation critique",
                "description": "Plusieurs polluants à des niveaux dangereux",
                "predictions": {
                    "co2": 1800,
                    "pm25": 85,
                    "tvoc": 950,
                    "humidity": 75
                }
            },
            "humidity": {
                "name": "Humidité excessive",
                "description": "Taux d'humidité trop élevé",
                "predictions": {
                    "co2": 750,
                    "pm25": 15,
                    "tvoc": 200,
                    "humidity": 85
                }
            }
        }
    
    def create_room_modules(self, scenario_name: str = "full"):
        """Crée la configuration des modules selon le scénario."""
        
        if scenario_name == "limited":
            # Salle avec modules limités
            return RoomModules(
                enseigne="Maison",
                salle="Chambre",
                modules={
                    "fenetre": ModuleCapability(
                        module_type="fenetre",
                        is_available=True,
                        can_control=True,
                        current_state="fermé"
                    ),
                    "ventilation": ModuleCapability(
                        module_type="ventilation",
                        is_available=False,
                        can_control=False
                    ),
                    "purificateur": ModuleCapability(
                        module_type="purificateur",
                        is_available=False,
                        can_control=False
                    ),
                    "clim": ModuleCapability(
                        module_type="clim",
                        is_available=False,
                        can_control=False
                    )
                }
            )
        
        # Configuration complète (défaut)
        return RoomModules(
            enseigne="Maison",
            salle="Bureau",
            modules={
                "fenetre": ModuleCapability(
                    module_type="fenetre",
                    is_available=True,
                    can_control=True,
                    current_state="fermé"
                ),
                "ventilation": ModuleCapability(
                    module_type="ventilation",
                    is_available=True,
                    can_control=True,
                    current_state="inactif",
                    power_levels=[0, 1, 2, 3]
                ),
                "purificateur": ModuleCapability(
                    module_type="purificateur",
                    is_available=True,
                    can_control=True,
                    current_state="inactif",
                    power_levels=[0, 1, 2, 3]
                ),
                "clim": ModuleCapability(
                    module_type="clim",
                    is_available=True,
                    can_control=True,
                    current_state="inactif"
                )
            }
        )
    
    def run_scenario(self, scenario_key: str, module_config: str = "full"):
        """Exécute un scénario complet."""
        
        if scenario_key not in self.scenarios:
            logger.error(f"Scénario inconnu: {scenario_key}")
            return None
        
        scenario = self.scenarios[scenario_key]
        
        logger.info("\n" + "="*80)
        logger.info(f"SCÉNARIO: {scenario['name'].upper()}")
        logger.info("="*80)
        logger.info(f"Description: {scenario['description']}")
        logger.info(f"Configuration: {module_config}")
        
        # 1. Prédictions (simulées pour la démo)
        predictions = scenario['predictions']
        logger.info("\n📊 ÉTAPE 1: Prédictions ML")
        logger.info("-"*80)
        logger.info(f"CO2:         {predictions['co2']} ppm")
        logger.info(f"PM2.5:       {predictions['pm25']} µg/m³")
        logger.info(f"TVOC:        {predictions['tvoc']} ppb")
        logger.info(f"Humidité:    {predictions['humidity']} %")
        
        # 2. Calcul du score IAQ
        logger.info("\n🎯 ÉTAPE 2: Calcul du Score IAQ")
        logger.info("-"*80)
        
        iaq_analysis = IAQScoreCalculator.calculate_global_score(predictions)
        
        score = iaq_analysis['global_score']
        level = iaq_analysis['global_level']
        
        # Emoji selon le niveau
        level_emoji = {
            "good": "✅",
            "moderate": "⚠️",
            "poor": "🚨",
            "very_poor": "🔴"
        }
        
        logger.info(f"{level_emoji.get(level, '❓')} Score global: {score}/100 ({level})")
        
        logger.info("\nDétails par polluant:")
        for pollutant, details in iaq_analysis['pollutants_details'].items():
            emoji = "✅" if details['score'] >= 60 else "⚠️" if details['score'] >= 40 else "🚨"
            logger.info(f"  {emoji} {pollutant:12s}: {details['value']:6.1f} → {details['score']:3d}/100 ({details['level']})")
        
        problematic = iaq_analysis['problematic_pollutants']
        if problematic:
            logger.info(f"\n⚠️ {len(problematic)} polluant(s) problématique(s) détecté(s):")
            for p in problematic:
                logger.info(f"  - {p['pollutant']}: {p['value']} ({p['level']})")
        else:
            logger.info("\n✅ Aucun polluant problématique")
        
        # 3. Sélection des actions
        logger.info("\n🎬 ÉTAPE 3: Sélection des Actions Correctives")
        logger.info("-"*80)
        
        room_modules = self.create_room_modules(module_config)
        
        logger.info(f"Salle: {room_modules.enseigne}/{room_modules.salle}")
        logger.info(f"Modules disponibles: {', '.join(k for k, v in room_modules.modules.items() if v.is_available and v.can_control)}")
        
        actions = ActionSelector.select_actions(iaq_analysis, room_modules)
        
        if actions:
            logger.info(f"\n✅ {len(actions)} action(s) sélectionnée(s):")
            for i, action in enumerate(actions, 1):
                logger.info(f"\n  {i}. {action['action_type'].upper()}")
                logger.info(f"     Module:   {action['module_type']}")
                logger.info(f"     Priorité: {action['priority']}")
                logger.info(f"     Raison:   {action['reason']['pollutant']} = {action['reason']['value']} ({action['reason']['level']})")
                if action['parameters']:
                    logger.info(f"     Params:   {action['parameters']}")
        else:
            logger.info("\n✅ Aucune action nécessaire")
        
        # 4. Simulation d'envoi API
        logger.info("\n📡 ÉTAPE 4: Envoi via API")
        logger.info("-"*80)
        
        if actions:
            logger.info("Actions qui seraient envoyées à l'API:")
            for action in actions:
                logger.info(f"  POST /api/execute-action")
                logger.info(f"       {json.dumps(action, indent=8)[:200]}...")
        else:
            logger.info("Aucune action à envoyer")
        
        # Résultat
        logger.info("\n" + "="*80)
        logger.info("RÉSULTAT DU SCÉNARIO")
        logger.info("="*80)
        logger.info(f"Score IAQ:       {score}/100 ({level})")
        logger.info(f"Problèmes:       {len(problematic)}")
        logger.info(f"Actions:         {len(actions)}")
        logger.info(f"Statut:          {'🔴 ACTION REQUISE' if actions else '✅ SITUATION NORMALE'}")
        logger.info("="*80 + "\n")
        
        return {
            "scenario": scenario,
            "predictions": predictions,
            "iaq_analysis": iaq_analysis,
            "actions": actions,
            "room_modules": {
                "enseigne": room_modules.enseigne,
                "salle": room_modules.salle,
                "modules": list(room_modules.modules.keys())
            }
        }
    
    def run_all_scenarios(self):
        """Exécute tous les scénarios."""
        logger.info("\n" + "="*80)
        logger.info("DÉMONSTRATION END-TO-END DU SYSTÈME IAQverse")
        logger.info("="*80)
        logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("\n🎯 Flux complet: Prédictions → Score IAQ → Sélection Actions → API\n")
        
        results = {}
        
        for key in self.scenarios.keys():
            results[key] = self.run_scenario(key)
            time.sleep(1)  # Pause entre scénarios
        
        # Résumé final
        logger.info("\n" + "="*80)
        logger.info("RÉSUMÉ DE TOUS LES SCÉNARIOS")
        logger.info("="*80)
        
        for key, result in results.items():
            if result:
                score = result['iaq_analysis']['global_score']
                actions_count = len(result['actions'])
                level = result['iaq_analysis']['global_level']
                
                status_emoji = "✅" if actions_count == 0 else "🚨"
                logger.info(f"{status_emoji} {result['scenario']['name']:25s} | Score: {score:5.1f}/100 ({level:10s}) | Actions: {actions_count}")
        
        logger.info("="*80 + "\n")


def main():
    """Fonction principale."""
    
    demo = IAQDemoScenario()
    
    print("\n" + "="*80)
    print("DÉMO END-TO-END - SYSTÈME IAQverse")
    print("="*80)
    print("\nChoisissez un mode:")
    print("  1. Scénario unique")
    print("  2. Tous les scénarios")
    print("  3. Mode interactif")
    
    choice = input("\nVotre choix (1-3): ").strip()
    
    if choice == "1":
        print("\nScénarios disponibles:")
        for i, (key, scenario) in enumerate(demo.scenarios.items(), 1):
            print(f"  {i}. {scenario['name']} - {scenario['description']}")
        
        scenario_num = input("\nNuméro du scénario: ").strip()
        try:
            scenario_key = list(demo.scenarios.keys())[int(scenario_num) - 1]
            demo.run_scenario(scenario_key)
        except (ValueError, IndexError):
            logger.error("Choix invalide")
    
    elif choice == "2":
        demo.run_all_scenarios()
    
    elif choice == "3":
        # Mode interactif
        print("\nMode interactif - Entrez vos valeurs:")
        try:
            co2 = float(input("CO2 (ppm): "))
            pm25 = float(input("PM2.5 (µg/m³): "))
            tvoc = float(input("TVOC (ppb): "))
            humidity = float(input("Humidité (%): "))
            
            custom_scenario = {
                "name": "Scénario personnalisé",
                "description": "Valeurs saisies par l'utilisateur",
                "predictions": {
                    "co2": co2,
                    "pm25": pm25,
                    "tvoc": tvoc,
                    "humidity": humidity
                }
            }
            
            demo.scenarios["custom"] = custom_scenario
            demo.run_scenario("custom")
        
        except ValueError:
            logger.error("Valeurs invalides")
    
    else:
        logger.error("Choix invalide")


if __name__ == "__main__":
    main()
