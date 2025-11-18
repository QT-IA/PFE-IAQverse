"""
Système de sélection intelligente des actions correctives.

Ce module :
1. Calcule un score IAQ global à partir des prédictions multi-polluants
2. Identifie les polluants problématiques
3. Sélectionne automatiquement les meilleures actions en fonction des modules disponibles
4. Génère les requêtes POST API pour déclencher les actions
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types d'actions disponibles."""
    OUVRIR_FENETRE = "ouvrir_fenetre"
    FERMER_FENETRE = "fermer_fenetre"
    ACTIVER_VENTILATION = "activer_ventilation"
    DESACTIVER_VENTILATION = "desactiver_ventilation"
    ACTIVER_CLIM = "activer_clim"
    DESACTIVER_CLIM = "desactiver_clim"
    ACTIVER_PURIFICATEUR = "activer_purificateur"
    DESACTIVER_PURIFICATEUR = "desactiver_purificateur"
    AUGMENTER_VENTILATION = "augmenter_ventilation"
    REDUIRE_VENTILATION = "reduire_ventilation"
    AJUSTER_TEMPERATURE = "ajuster_temperature"


class PollutantType(str, Enum):
    """Types de polluants surveillés."""
    CO2 = "co2"
    PM25 = "pm25"
    TVOC = "tvoc"
    HUMIDITY = "humidity"
    TEMPERATURE = "temperature"


@dataclass
class ModuleCapability:
    """Définit les capacités d'un module (fenêtre, clim, etc.)."""
    module_type: str  # "fenetre", "clim", "ventilation", "purificateur"
    is_available: bool
    can_control: bool  # Peut-on le contrôler via API ?
    current_state: Optional[str] = None  # "ouvert", "fermé", "actif", "inactif"
    power_levels: Optional[List[int]] = None  # [0, 1, 2, 3] pour ventilation/clim


@dataclass
class RoomModules:
    """Configuration des modules disponibles dans une salle."""
    enseigne: str
    salle: str
    modules: Dict[str, ModuleCapability]
    
    def has_module(self, module_type: str) -> bool:
        """Vérifie si un module est disponible et contrôlable."""
        module = self.modules.get(module_type)
        return module and module.is_available and module.can_control


# ============================================================================
# CALCUL DU SCORE IAQ GLOBAL
# ============================================================================

class IAQScoreCalculator:
    """Calcule un score de qualité d'air intérieur (0-100, 100 = excellent)."""
    
    # Seuils pour chaque polluant (good, moderate, poor, very_poor)
    THRESHOLDS = {
        PollutantType.CO2: {
            "excellent": (0, 600),
            "good": (600, 1000),
            "moderate": (1000, 1400),
            "poor": (1400, 2000),
            "very_poor": (2000, float('inf'))
        },
        PollutantType.PM25: {
            "excellent": (0, 12),
            "good": (12, 25),
            "moderate": (25, 50),
            "poor": (50, 100),
            "very_poor": (100, float('inf'))
        },
        PollutantType.TVOC: {
            "excellent": (0, 200),
            "good": (200, 300),
            "moderate": (300, 500),
            "poor": (500, 1000),
            "very_poor": (1000, float('inf'))
        },
        PollutantType.HUMIDITY: {
            "excellent": (40, 50),
            "good": (30, 60),
            "moderate": (20, 70),
            "poor": (10, 80),
            "very_poor": (0, 100)  # <10% ou >80%
        }
    }
    
    # Poids de chaque polluant dans le score global
    WEIGHTS = {
        PollutantType.CO2: 0.35,      # Très important pour le confort
        PollutantType.PM25: 0.30,     # Dangereux pour la santé
        PollutantType.TVOC: 0.25,     # Impact sur la santé
        PollutantType.HUMIDITY: 0.10  # Moins critique mais important
    }
    
    @staticmethod
    def get_pollutant_score(pollutant: PollutantType, value: float) -> int:
        """
        Calcule le score (0-100) pour un polluant spécifique.
        
        Returns:
            Score de 0 (très mauvais) à 100 (excellent)
        """
        thresholds = IAQScoreCalculator.THRESHOLDS[pollutant]
        
        # Cas spécial pour l'humidité (plage optimale)
        if pollutant == PollutantType.HUMIDITY:
            if 40 <= value <= 50:
                return 100
            elif 30 <= value <= 60:
                return 80
            elif 20 <= value <= 70:
                return 60
            elif 10 <= value <= 80:
                return 40
            else:
                return 20
        
        # Pour les autres polluants (plus bas = mieux)
        if value <= thresholds["excellent"][1]:
            return 100
        elif value <= thresholds["good"][1]:
            return 80
        elif value <= thresholds["moderate"][1]:
            return 60
        elif value <= thresholds["poor"][1]:
            return 40
        else:
            return 20
    
    @staticmethod
    def get_pollutant_level(pollutant: PollutantType, value: float) -> str:
        """Retourne le niveau qualitatif du polluant."""
        thresholds = IAQScoreCalculator.THRESHOLDS[pollutant]
        
        if pollutant == PollutantType.HUMIDITY:
            if 40 <= value <= 50:
                return "excellent"
            elif 30 <= value <= 60:
                return "good"
            elif 20 <= value <= 70:
                return "moderate"
            elif 10 <= value <= 80:
                return "poor"
            else:
                return "very_poor"
        
        for level, (min_val, max_val) in thresholds.items():
            if min_val <= value < max_val:
                return level
        return "very_poor"
    
    @classmethod
    def calculate_global_score(cls, predictions: Dict[str, float]) -> Dict:
        """
        Calcule le score IAQ global et identifie les polluants problématiques.
        
        Args:
            predictions: Dict avec les valeurs prédites {pollutant: value}
            
        Returns:
            Dict avec:
            - global_score: score global (0-100)
            - global_level: niveau qualitatif
            - pollutants_details: détails par polluant
            - problematic_pollutants: liste des polluants à corriger
        """
        weighted_score = 0
        pollutants_details = {}
        problematic = []
        
        for pollutant_str, value in predictions.items():
            try:
                pollutant = PollutantType(pollutant_str)
                
                if pollutant not in cls.WEIGHTS:
                    continue
                
                score = cls.get_pollutant_score(pollutant, value)
                level = cls.get_pollutant_level(pollutant, value)
                weight = cls.WEIGHTS[pollutant]
                
                weighted_score += score * weight
                
                pollutants_details[pollutant_str] = {
                    "value": round(value, 2),
                    "score": score,
                    "level": level,
                    "weight": weight
                }
                
                # Identifier les polluants problématiques (score < 60)
                if score < 60:
                    problematic.append({
                        "pollutant": pollutant_str,
                        "value": value,
                        "score": score,
                        "level": level
                    })
                    
            except ValueError:
                logger.warning(f"Polluant inconnu: {pollutant_str}")
                continue
        
        # Déterminer le niveau global
        if weighted_score >= 80:
            global_level = "good"
        elif weighted_score >= 60:
            global_level = "moderate"
        elif weighted_score >= 40:
            global_level = "poor"
        else:
            global_level = "very_poor"
        
        return {
            "global_score": round(weighted_score, 1),
            "global_level": global_level,
            "pollutants_details": pollutants_details,
            "problematic_pollutants": problematic
        }


# ============================================================================
# SÉLECTION INTELLIGENTE DES ACTIONS
# ============================================================================

class ActionSelector:
    """Sélectionne automatiquement les meilleures actions en fonction du contexte."""
    
    # Règles de décision : quel module utiliser pour quel polluant
    ACTION_RULES = {
        PollutantType.CO2: {
            # CO2 élevé → besoin de renouvellement d'air
            "primary": ["fenetre", "ventilation"],
            "actions": {
                "fenetre": [ActionType.OUVRIR_FENETRE],
                "ventilation": [ActionType.ACTIVER_VENTILATION, ActionType.AUGMENTER_VENTILATION]
            }
        },
        PollutantType.PM25: {
            # PM2.5 élevé → besoin de filtration
            "primary": ["purificateur"],
            "secondary": ["ventilation"],  # Si air extérieur propre
            "actions": {
                "purificateur": [ActionType.ACTIVER_PURIFICATEUR],
                "ventilation": [ActionType.ACTIVER_VENTILATION]
            }
        },
        PollutantType.TVOC: {
            # TVOC élevé → besoin d'évacuation + filtration
            "primary": ["fenetre", "ventilation", "purificateur"],
            "actions": {
                "fenetre": [ActionType.OUVRIR_FENETRE],
                "ventilation": [ActionType.ACTIVER_VENTILATION, ActionType.AUGMENTER_VENTILATION],
                "purificateur": [ActionType.ACTIVER_PURIFICATEUR]
            }
        },
        PollutantType.HUMIDITY: {
            # Humidité anormale → besoin de régulation
            "primary": ["ventilation", "clim"],
            "actions": {
                "ventilation": [ActionType.ACTIVER_VENTILATION],
                "clim": [ActionType.ACTIVER_CLIM]  # Mode déshumidification
            }
        }
    }
    
    @classmethod
    def select_actions(cls, iaq_analysis: Dict, room_modules: RoomModules) -> List[Dict]:
        """
        Sélectionne les actions optimales en fonction de l'analyse IAQ et des modules disponibles.
        
        Args:
            iaq_analysis: Résultat de IAQScoreCalculator.calculate_global_score()
            room_modules: Configuration des modules disponibles dans la salle
            
        Returns:
            Liste des actions à exécuter avec leurs paramètres
        """
        actions_to_execute = []
        problematic = iaq_analysis.get("problematic_pollutants", [])
        
        if not problematic:
            logger.info("✅ Qualité d'air correcte, aucune action nécessaire")
            return actions_to_execute
        
        logger.info(f"🚨 {len(problematic)} polluant(s) problématique(s) détecté(s)")
        
        # Pour chaque polluant problématique
        for problem in problematic:
            pollutant_type = problem["pollutant"]
            pollutant_value = problem["value"]
            pollutant_level = problem["level"]
            
            logger.info(f"  → {pollutant_type}: {pollutant_value} ({pollutant_level})")
            
            try:
                pollutant_enum = PollutantType(pollutant_type)
                rules = cls.ACTION_RULES.get(pollutant_enum)
                
                if not rules:
                    logger.warning(f"Aucune règle définie pour {pollutant_type}")
                    continue
                
                # Essayer les modules prioritaires
                primary_modules = rules.get("primary", [])
                secondary_modules = rules.get("secondary", [])
                
                action_found = False
                
                # Essayer d'abord les modules primaires
                for module_type in primary_modules:
                    if room_modules.has_module(module_type):
                        module_actions = rules["actions"].get(module_type, [])
                        
                        for action_type in module_actions:
                            action = cls._create_action(
                                action_type=action_type,
                                module_type=module_type,
                                pollutant=pollutant_type,
                                value=pollutant_value,
                                level=pollutant_level,
                                room_modules=room_modules
                            )
                            
                            if action:
                                actions_to_execute.append(action)
                                action_found = True
                                logger.info(f"    ✓ Action sélectionnée: {action_type.value}")
                                break  # Une action par module suffit
                        
                        if action_found:
                            break
                
                # Si pas de module primaire, essayer les secondaires
                if not action_found:
                    for module_type in secondary_modules:
                        if room_modules.has_module(module_type):
                            module_actions = rules["actions"].get(module_type, [])
                            
                            for action_type in module_actions:
                                action = cls._create_action(
                                    action_type=action_type,
                                    module_type=module_type,
                                    pollutant=pollutant_type,
                                    value=pollutant_value,
                                    level=pollutant_level,
                                    room_modules=room_modules
                                )
                                
                                if action:
                                    actions_to_execute.append(action)
                                    logger.info(f"    ✓ Action secondaire: {action_type.value}")
                                    break
                            
                            break
                
                if not action_found and not secondary_modules:
                    logger.warning(f"    ❌ Aucun module disponible pour corriger {pollutant_type}")
                    
            except ValueError:
                logger.warning(f"Polluant inconnu: {pollutant_type}")
                continue
        
        return actions_to_execute
    
    @staticmethod
    def _create_action(action_type: ActionType, module_type: str, pollutant: str,
                      value: float, level: str, room_modules: RoomModules) -> Optional[Dict]:
        """
        Crée une action avec tous ses paramètres.
        
        Returns:
            Dict prêt à être envoyé via POST API
        """
        module = room_modules.modules.get(module_type)
        
        if not module or not module.can_control:
            return None
        
        action = {
            "action_type": action_type.value,
            "module_type": module_type,
            "enseigne": room_modules.enseigne,
            "salle": room_modules.salle,
            "reason": {
                "pollutant": pollutant,
                "value": round(value, 2),
                "level": level
            },
            "priority": ActionSelector._get_priority(level),
            "parameters": {}
        }
        
        # Ajouter des paramètres spécifiques selon le type d'action
        if action_type in [ActionType.AUGMENTER_VENTILATION, ActionType.ACTIVER_VENTILATION]:
            if module.power_levels:
                # Déterminer la puissance selon la gravité
                if level == "very_poor":
                    action["parameters"]["power_level"] = max(module.power_levels)
                elif level == "poor":
                    action["parameters"]["power_level"] = max(module.power_levels) - 1
                else:
                    action["parameters"]["power_level"] = max(module.power_levels) // 2
        
        elif action_type == ActionType.AJUSTER_TEMPERATURE:
            # Exemple : ajuster la température de la clim
            action["parameters"]["target_temperature"] = 22
        
        return action
    
    @staticmethod
    def _get_priority(level: str) -> str:
        """Détermine la priorité d'une action selon le niveau de gravité."""
        priority_map = {
            "very_poor": "urgent",
            "poor": "high",
            "moderate": "medium",
            "good": "low"
        }
        return priority_map.get(level, "medium")


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

def example_usage():
    """Exemple complet d'utilisation du système."""
    
    # 1. Prédictions du modèle ML
    predictions = {
        "co2": 1450,     # Élevé
        "pm25": 15,      # Correct
        "tvoc": 650,     # Élevé
        "humidity": 45   # Correct
    }
    
    # 2. Configuration des modules disponibles dans la salle
    room_modules = RoomModules(
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
                is_available=True,
                can_control=True,
                current_state="inactif",
                power_levels=[0, 1, 2, 3]
            ),
            "purificateur": ModuleCapability(
                module_type="purificateur",
                is_available=False,  # Pas de purificateur
                can_control=False
            ),
            "clim": ModuleCapability(
                module_type="clim",
                is_available=True,
                can_control=False  # Présente mais pas contrôlable via API
            )
        }
    )
    
    # 3. Calculer le score IAQ
    iaq_analysis = IAQScoreCalculator.calculate_global_score(predictions)
    
    print("\n" + "="*60)
    print("ANALYSE DE LA QUALITÉ D'AIR")
    print("="*60)
    print(f"Score global: {iaq_analysis['global_score']}/100 ({iaq_analysis['global_level']})")
    print("\nDétails par polluant:")
    for pollutant, details in iaq_analysis['pollutants_details'].items():
        print(f"  • {pollutant}: {details['value']} → {details['score']}/100 ({details['level']})")
    
    # 4. Sélectionner les actions
    actions = ActionSelector.select_actions(iaq_analysis, room_modules)
    
    print("\n" + "="*60)
    print("ACTIONS RECOMMANDÉES")
    print("="*60)
    if actions:
        for i, action in enumerate(actions, 1):
            print(f"\n{i}. {action['action_type']} ({action['priority']})")
            print(f"   Module: {action['module_type']}")
            print(f"   Raison: {action['reason']['pollutant']} = {action['reason']['value']} ({action['reason']['level']})")
            if action['parameters']:
                print(f"   Paramètres: {action['parameters']}")
    else:
        print("✅ Aucune action nécessaire")
    
    return actions


if __name__ == "__main__":
    example_usage()
