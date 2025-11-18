"""
SQLite registry pour les métadonnées des modèles ML et modules
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class SQLiteRegistry:
    """
    Registry SQLite pour stocker les métadonnées des modèles ML et l'état des modules.
    """
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialise les tables de la base de données"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Table pour les modèles ML
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ml_models (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        model_name TEXT NOT NULL,
                        model_version TEXT NOT NULL,
                        model_type TEXT NOT NULL,
                        model_path TEXT NOT NULL,
                        metrics TEXT,
                        training_date TEXT NOT NULL,
                        is_active INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        UNIQUE(model_name, model_version)
                    )
                ''')
                
                # Table pour l'état des modules
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS module_states (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        enseigne TEXT NOT NULL,
                        salle TEXT NOT NULL,
                        module_type TEXT NOT NULL,
                        current_state TEXT,
                        last_action TEXT,
                        last_action_timestamp TEXT,
                        metadata TEXT,
                        updated_at TEXT NOT NULL,
                        UNIQUE(enseigne, salle, module_type)
                    )
                ''')
                
                # Table pour l'historique des entraînements
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS training_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        model_name TEXT NOT NULL,
                        model_version TEXT NOT NULL,
                        training_date TEXT NOT NULL,
                        dataset_size INTEGER,
                        training_duration REAL,
                        metrics TEXT,
                        notes TEXT,
                        created_at TEXT NOT NULL
                    )
                ''')
                
                conn.commit()
                logger.info(f"✅ SQLite registry initialisé: {self.db_path}")
                
        except Exception as e:
            logger.error(f"Erreur initialisation SQLite: {e}")
    
    # ========== Gestion des modèles ML ==========
    
    def register_model(
        self,
        model_name: str,
        model_version: str,
        model_type: str,
        model_path: str,
        metrics: Optional[Dict[str, Any]] = None,
        training_date: Optional[str] = None,
        set_active: bool = True
    ) -> bool:
        """Enregistre un nouveau modèle ML"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Désactiver les autres versions si on active celle-ci
                if set_active:
                    cursor.execute(
                        "UPDATE ml_models SET is_active = 0 WHERE model_name = ?",
                        (model_name,)
                    )
                
                # Insérer le nouveau modèle
                cursor.execute('''
                    INSERT OR REPLACE INTO ml_models 
                    (model_name, model_version, model_type, model_path, metrics, 
                     training_date, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    model_name,
                    model_version,
                    model_type,
                    model_path,
                    json.dumps(metrics) if metrics else None,
                    training_date or datetime.utcnow().isoformat(),
                    1 if set_active else 0,
                    datetime.utcnow().isoformat()
                ))
                
                conn.commit()
                logger.info(f"✅ Modèle enregistré: {model_name} v{model_version}")
                return True
                
        except Exception as e:
            logger.error(f"Erreur enregistrement modèle: {e}")
            return False
    
    def get_active_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Récupère le modèle actif pour un nom donné"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM ml_models 
                    WHERE model_name = ? AND is_active = 1
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (model_name,))
                
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    if result.get('metrics'):
                        result['metrics'] = json.loads(result['metrics'])
                    return result
                return None
                
        except Exception as e:
            logger.error(f"Erreur récupération modèle actif: {e}")
            return None
    
    def list_models(self, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Liste tous les modèles ou ceux d'un nom spécifique"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if model_name:
                    cursor.execute('''
                        SELECT * FROM ml_models 
                        WHERE model_name = ?
                        ORDER BY created_at DESC
                    ''', (model_name,))
                else:
                    cursor.execute('''
                        SELECT * FROM ml_models 
                        ORDER BY created_at DESC
                    ''')
                
                rows = cursor.fetchall()
                results = []
                for row in rows:
                    result = dict(row)
                    if result.get('metrics'):
                        result['metrics'] = json.loads(result['metrics'])
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Erreur liste modèles: {e}")
            return []
    
    def set_active_model(self, model_name: str, model_version: str) -> bool:
        """Définit un modèle comme actif"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Désactiver tous les modèles avec ce nom
                cursor.execute(
                    "UPDATE ml_models SET is_active = 0 WHERE model_name = ?",
                    (model_name,)
                )
                
                # Activer le modèle spécifié
                cursor.execute('''
                    UPDATE ml_models 
                    SET is_active = 1 
                    WHERE model_name = ? AND model_version = ?
                ''', (model_name, model_version))
                
                conn.commit()
                logger.info(f"✅ Modèle activé: {model_name} v{model_version}")
                return True
                
        except Exception as e:
            logger.error(f"Erreur activation modèle: {e}")
            return False
    
    # ========== Gestion de l'état des modules ==========
    
    def update_module_state(
        self,
        enseigne: str,
        salle: str,
        module_type: str,
        current_state: str,
        last_action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Met à jour l'état d'un module"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                timestamp = datetime.utcnow().isoformat()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO module_states 
                    (enseigne, salle, module_type, current_state, last_action, 
                     last_action_timestamp, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    enseigne,
                    salle,
                    module_type,
                    current_state,
                    last_action,
                    timestamp if last_action else None,
                    json.dumps(metadata) if metadata else None,
                    timestamp
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Erreur mise à jour état module: {e}")
            return False
    
    def get_module_state(
        self,
        enseigne: str,
        salle: str,
        module_type: str
    ) -> Optional[Dict[str, Any]]:
        """Récupère l'état d'un module"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM module_states 
                    WHERE enseigne = ? AND salle = ? AND module_type = ?
                ''', (enseigne, salle, module_type))
                
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    if result.get('metadata'):
                        result['metadata'] = json.loads(result['metadata'])
                    return result
                return None
                
        except Exception as e:
            logger.error(f"Erreur récupération état module: {e}")
            return None
    
    def list_module_states(
        self,
        enseigne: Optional[str] = None,
        salle: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Liste les états des modules"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = "SELECT * FROM module_states"
                params = []
                
                conditions = []
                if enseigne:
                    conditions.append("enseigne = ?")
                    params.append(enseigne)
                if salle:
                    conditions.append("salle = ?")
                    params.append(salle)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY updated_at DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    result = dict(row)
                    if result.get('metadata'):
                        result['metadata'] = json.loads(result['metadata'])
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Erreur liste états modules: {e}")
            return []
    
    # ========== Historique des entraînements ==========
    
    def add_training_record(
        self,
        model_name: str,
        model_version: str,
        dataset_size: int,
        training_duration: float,
        metrics: Dict[str, Any],
        notes: Optional[str] = None
    ) -> bool:
        """Ajoute un enregistrement d'entraînement"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO training_history 
                    (model_name, model_version, training_date, dataset_size, 
                     training_duration, metrics, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    model_name,
                    model_version,
                    datetime.utcnow().isoformat(),
                    dataset_size,
                    training_duration,
                    json.dumps(metrics),
                    notes,
                    datetime.utcnow().isoformat()
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Erreur ajout historique entraînement: {e}")
            return False
    
    def get_training_history(
        self,
        model_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Récupère l'historique des entraînements"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if model_name:
                    cursor.execute('''
                        SELECT * FROM training_history 
                        WHERE model_name = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    ''', (model_name, limit))
                else:
                    cursor.execute('''
                        SELECT * FROM training_history 
                        ORDER BY created_at DESC
                        LIMIT ?
                    ''', (limit,))
                
                rows = cursor.fetchall()
                results = []
                for row in rows:
                    result = dict(row)
                    if result.get('metrics'):
                        result['metrics'] = json.loads(result['metrics'])
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Erreur récupération historique: {e}")
            return []


# Instance globale
_sqlite_registry: Optional[SQLiteRegistry] = None


def get_sqlite_registry(db_path: Path = None) -> SQLiteRegistry:
    """Retourne l'instance du registry SQLite"""
    global _sqlite_registry
    
    if _sqlite_registry is None:
        from .settings import settings
        db_path = db_path or settings.SQLITE_DB_PATH
        _sqlite_registry = SQLiteRegistry(db_path)
    
    return _sqlite_registry
