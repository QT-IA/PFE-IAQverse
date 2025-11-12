"""
Script d'entraînement de modèles ML pour la prédiction de qualité d'air intérieur.

Ce script entraîne un modèle capable de prédire pour N'IMPORTE QUELLE salle/capteur.
Les modèles prédisent la qualité de l'air 30 minutes à l'avance :
- CO2 (ppm)
- PM2.5 (µg/m³)
- TVOC (ppb)
- Humidité (%)

Fonctionnement :
1. Entraînement initial sur le dataset preprocessé 
2. Réentraînement automatique toutes les heures avec les nouvelles données de l'API
3. Sauvegarde automatique des modèles mis à jour
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
import json
import joblib
from datetime import datetime, timedelta
import time
import requests

# Bibliothèques Machine Learning
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

# Configuration des logs pour afficher les informations de traitement
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION

# Paramètres de prédiction
LOOKBACK_MINUTES = 12  # Nombre de points d'historique (12 x 5min = 1 heure)
FORECAST_MINUTES = 6   # Points à prédire dans le futur (6 x 5min = 30 minutes)

# Colonnes de données
COLONNES_FEATURES = ['co2', 'pm25', 'tvoc', 'temperature', 'humidity']
COLONNES_CIBLES = ['co2', 'pm25', 'tvoc', 'humidity']

# URL de l'API pour récupérer les nouvelles données
API_BASE_URL = "http://localhost:8000"

# Endpoint pour récupérer la configuration des capteurs actifs
API_SENSORS_CONFIG_URL = f"{API_BASE_URL}/api/sensors-config"

# Intervalle de réentraînement (en secondes)
INTERVALLE_REENTRAINEMENT = 3600  # 1 heure

# ============================================================================
# FONCTIONS DE CHARGEMENT DES DONNÉES

def charger_dataset_csv(chemin_csv):
    logger.info(f"Chargement du dataset: {chemin_csv}")
    df = pd.read_csv(chemin_csv)
    
    # Nettoyer les noms de colonnes (enlever les espaces et guillemets)
    df.columns = df.columns.str.strip().str.strip('"').str.strip()
    
    # Nettoyer toutes les valeurs (enlever guillemets et espaces)
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip().str.strip('"').str.strip()
    
    # Convertir les colonnes numériques
    for col in ['co2', 'pm25', 'tvoc', 'temperature', 'humidity']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Convertir le timestamp en format datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Trier par ordre chronologique
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    logger.info(f"Dataset chargé: {len(df):,} lignes")
    
    # Vérifier les colonnes nécessaires
    if 'salle' in df.columns:
        logger.info(f"Salles: {df['salle'].unique().tolist()}")
    if 'capteur_id' in df.columns:
        logger.info(f"Capteurs: {df['capteur_id'].unique().tolist()}")
    
    return df


def recuperer_config_ml():
    """
    Récupère la configuration ML depuis l'API.
    Cette configuration est extraite automatiquement de config.json (lieux.enseignes.pieces).
    
    Format attendu de la réponse:
    {
        "sensors": [
            {"enseigne": "Maison", "salle": "Bureau", "capteur_id": "Bureau1", "piece_id": "piece_xxx"},
            {"enseigne": "Maison", "salle": "Salon", "capteur_id": "Salon1", "piece_id": "piece_yyy"},
            ...
        ]
    }
    
    Returns:
        Liste de dictionnaires avec les configurations de capteurs, ou liste vide si erreur
    """
    try:
        logger.info(f"Récupération de la configuration ML depuis: {API_SENSORS_CONFIG_URL}")
        response = requests.get(API_SENSORS_CONFIG_URL, timeout=10)
        
        if response.status_code == 200:
            config = response.json()
            sensors = config.get("sensors", [])
            
            if sensors:
                logger.info(f"✓ Configuration ML récupérée: {len(sensors)} capteur(s)")
                for sensor in sensors:
                    enseigne = sensor.get("enseigne", "?")
                    salle = sensor.get("salle", "?")
                    capteur_id = sensor.get("capteur_id", "?")
                    logger.info(f"  → {enseigne}/{salle}/{capteur_id}")
                return sensors
            else:
                logger.warning("Configuration ML vide, aucun capteur configuré")
                return []
        else:
            logger.warning(f"Erreur lors de la récupération de la config ML: code {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la configuration ML: {e}")
        return []

def recuperer_nouvelles_donnees_api(enseigne="Maison", salle="Bureau"):
    """
    Récupère les nouvelles données depuis l'API via l'endpoint /iaq/window.
    Récupère la dernière heure de données avec agrégation 5min.
    
    Args:
        enseigne: Nom de l'enseigne (défaut: "Maison")
        salle: Nom de la salle (défaut: "Bureau")
    
    Returns:
        DataFrame pandas avec les nouvelles données, ou DataFrame vide si erreur
    """
    try:
        # Utiliser l'endpoint /iaq/window pour récupérer la dernière heure
        url = f"{API_BASE_URL}/iaq/window"
        params = {
            "enseigne": enseigne,
            "salle": salle,
            "hours": 1,  # Dernière heure
            "step": "5min"  # Agrégation 5 minutes
        }
        
        logger.info(f"Récupération des données depuis l'API: {url}")
        logger.info(f"Paramètres: enseigne={enseigne}, salle={salle}, hours=1, step=5min")
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            donnees = response.json()
            if donnees:
                df = pd.DataFrame(donnees)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # S'assurer que les colonnes nécessaires sont présentes
                if 'enseigne' not in df.columns:
                    df['enseigne'] = enseigne
                if 'salle' not in df.columns:
                    df['salle'] = salle
                if 'capteur_id' not in df.columns:
                    df['capteur_id'] = f"{salle}1"  # Capteur par défaut
                
                logger.info(f"✓ {len(df):,} nouvelles lignes récupérées depuis l'API")
                return df
            else:
                logger.info("Aucune nouvelle donnée disponible dans l'API")
                return pd.DataFrame()
        else:
            logger.warning(f"Erreur API: code {response.status_code}")
            return pd.DataFrame()
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des données API: {e}")
        return pd.DataFrame()

def recuperer_toutes_les_donnees_api():
    """
    Récupère les données de tous les capteurs configurés via l'API.
    Utilise l'endpoint /api/ml-config pour obtenir la liste des capteurs actifs.
    
    Returns:
        DataFrame combiné avec toutes les nouvelles données des capteurs configurés
    """
    # Récupérer la configuration des capteurs depuis l'API
    sensors_config = recuperer_config_ml()
    
    if not sensors_config:
        logger.warning("Aucun capteur configuré, utilisation des paramètres par défaut")
        return recuperer_nouvelles_donnees_api()
    
    logger.info(f"Récupération des données pour {len(sensors_config)} capteur(s) configuré(s)")
    
    dataframes = []
    
    # Récupérer les données pour chaque capteur configuré
    for sensor in sensors_config:
        enseigne = sensor.get("enseigne", "Maison")
        salle = sensor.get("salle", "Bureau")
        # capteur_id sera ajouté automatiquement par recuperer_nouvelles_donnees_api
        
        df_capteur = recuperer_nouvelles_donnees_api(enseigne, salle)
        
        if not df_capteur.empty:
            # Ajouter le capteur_id depuis la config si disponible
            if "capteur_id" in sensor:
                df_capteur["capteur_id"] = sensor["capteur_id"]
            
            dataframes.append(df_capteur)
    
    if not dataframes:
        logger.warning("Aucune nouvelle donnée récupérée depuis l'API")
        return pd.DataFrame()
    
    # Combiner tous les DataFrames
    df_combine = pd.concat(dataframes, ignore_index=True)
    df_combine = df_combine.sort_values('timestamp').reset_index(drop=True)
    
    logger.info(f"✓ Total: {len(df_combine):,} nouvelles lignes récupérées")
    
    return df_combine

def combiner_datasets(df_initial, df_nouvelles_donnees):
    """
    Combine le dataset initial avec les nouvelles données de l'API.
    
    Args:
        df_initial: DataFrame du dataset preprocessé
        df_nouvelles_donnees: DataFrame des nouvelles données de l'API
        
    Returns:
        DataFrame combiné et nettoyé
    """
    if df_nouvelles_donnees.empty:
        logger.info("Pas de nouvelles données à combiner")
        return df_initial
    
    # Combiner les deux DataFrames
    df_combine = pd.concat([df_initial, df_nouvelles_donnees], ignore_index=True)
    
    # Trier par timestamp
    df_combine = df_combine.sort_values('timestamp').reset_index(drop=True)
    
    # Supprimer les doublons (même timestamp, même salle, même capteur)
    df_combine = df_combine.drop_duplicates(
        subset=['timestamp', 'salle', 'capteur_id'],
        keep='last'  # Garder la version la plus récente
    )
    
    logger.info(f"Dataset combiné: {len(df_combine):,} lignes au total")
    
    return df_combine


# ============================================================================
# FONCTIONS DE PRÉPARATION DES FEATURES
# ============================================================================

def creer_encodeurs():
    return LabelEncoder(), LabelEncoder()

def creer_features_temporelles(dataframe):
    df = dataframe.copy()
    # Heure du jour (0-23)
    df['hour'] = df['timestamp'].dt.hour
    # Jour de la semaine (0=lundi, 6=dimanche)
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    # Weekend ou non (1=weekend, 0=semaine)
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    return df

def encoder_salles_et_capteurs(dataframe, encodeur_salle, encodeur_capteur, mode='fit'):
    df = dataframe.copy()
    if mode == 'fit':
        # Entraînement: créer les encodages
        df['salle_encoded'] = encodeur_salle.fit_transform(df['salle'].fillna('Unknown'))
        df['capteur_encoded'] = encodeur_capteur.fit_transform(df['capteur_id'].fillna('Unknown'))
    else:
        # Prédiction: utiliser les encodages existants
        df['salle_encoded'] = df['salle'].apply(
            lambda x: encodeur_salle.transform([x])[0] if x in encodeur_salle.classes_ else -1
        )
        df['capteur_encoded'] = df['capteur_id'].apply(
            lambda x: encodeur_capteur.transform([x])[0] if x in encodeur_capteur.classes_ else -1
        )  
    return df

def creer_features_statistiques(dataframe):
    df = dataframe.copy()
    # Traiter chaque capteur séparément pour calculer les features
    for (salle, capteur) in df[['salle', 'capteur_id']].drop_duplicates().values:
        masque = (df['salle'] == salle) & (df['capteur_id'] == capteur)
        df_capteur = df[masque].copy()
        
        # Pour chaque type de mesure
        for colonne in COLONNES_FEATURES:
            if colonne in df_capteur.columns:
                # Tendance: différence avec la mesure précédente
                df.loc[masque, f'{colonne}_diff'] = df_capteur[colonne].diff()
                # Moyenne mobile sur 3 points (filtre les variations brusques)
                df.loc[masque, f'{colonne}_ma3'] = df_capteur[colonne].rolling(
                    window=3, 
                    min_periods=1
                ).mean()
    # Remplir les valeurs NaN possiblement créées par les calculs
    # bfill = back fill (remplir avec la valeur suivante)
    # ffill = forward fill (remplir avec la valeur précédente)
    df = df.bfill().ffill()
    return df

def preparer_toutes_les_features(dataframe, encodeur_salle, encodeur_capteur, mode='fit'):
    """
    Applique toutes les transformations de features sur le dataset.
    Args:
        dataframe: DataFrame brut
        encodeur_salle: LabelEncoder pour les salles
        encodeur_capteur: LabelEncoder pour les capteurs
        mode: 'fit' pour entraînement, 'transform' pour prédiction
    """
    logger.info("Création des features...")
    # 1. Features temporelles
    df = creer_features_temporelles(dataframe)
    # 2. Encoder salles et capteurs
    df = encoder_salles_et_capteurs(df, encodeur_salle, encodeur_capteur, mode)
    # 3. Features statistiques
    df = creer_features_statistiques(df)
    logger.info(f"✓ Features créées: {len(df.columns)} colonnes au total")
    return df


# ============================================================================
# FONCTIONS DE PRÉPARATION DES SÉQUENCES
# ============================================================================

def preparer_sequences_entrainement(dataframe):
    """
    Prépare les séquences X (features) et y (cibles) pour l'entraînement.
    
    Pour chaque point dans le temps :
    - X : moyenne des mesures sur les LOOKBACK_MINUTES derniers points
    - y : valeurs cibles FORECAST_MINUTES points dans le futur
    
    Args:
        dataframe: DataFrame avec toutes les features
        
    Returns:
        Tuple (X, y, scaler)
        - X: array numpy des features normalisées
        - y: array numpy des cibles
        - scaler: StandardScaler utilisé pour normaliser X
    """
    
    df = dataframe.sort_values(['salle', 'capteur_id', 'timestamp']).reset_index(drop=True)
    # Colonnes à utiliser comme features (exclure les colonnes non-numériques)
    colonnes_features = [
        col for col in df.columns 
        if col not in ['timestamp', 'enseigne', 'salle', 'capteur_id']
    ]
    liste_X = []
    liste_y = []
    # Créer les séquences pour chaque capteur
    for (salle, capteur_id) in df[['salle', 'capteur_id']].drop_duplicates().values:
        masque = (df['salle'] == salle) & (df['capteur_id'] == capteur_id)
        df_capteur = df[masque].copy().reset_index(drop=True)
        
        # Pour chaque point temporel possible
        for i in range(len(df_capteur) - FORECAST_MINUTES):
            # Définir la fenêtre d'historique
            debut = max(0, i - LOOKBACK_MINUTES)
            
            # Extraire les features de la fenêtre
            fenetre = df_capteur.iloc[debut:i+1][colonnes_features].values
            
            # Calculer la moyenne de la fenêtre (résume l'historique en un vecteur)
            if len(fenetre) > 0:
                features_moyennes = np.mean(fenetre, axis=0)
            else:
                features_moyennes = df_capteur.iloc[i][colonnes_features].values
            
            # Extraire les valeurs cibles dans le futur
            index_futur = i + FORECAST_MINUTES
            if index_futur < len(df_capteur):
                valeurs_cibles = df_capteur.iloc[index_futur][COLONNES_CIBLES].values
                liste_X.append(features_moyennes)
                liste_y.append(valeurs_cibles)
    
    # Convertir en arrays numpy
    X = np.array(liste_X)
    y = np.array(liste_y)
    
    # Normaliser les features (moyenne=0, écart-type=1)
    # La normalisation aide les modèles à converger plus vite
    scaler = StandardScaler()
    X = scaler.fit_transform(X)
    
    logger.info(f"Séquences créées:")
    logger.info(f"X: {X.shape[0]:,} exemples, {X.shape[1]} features")
    logger.info(f"y: {y.shape[0]:,} exemples, {y.shape[1]} cibles")
    
    return X, y, scaler


# ============================================================================
# FONCTIONS D'ENTRAÎNEMENT DES MODÈLES
# ============================================================================

def entrainer_modele_multi_output(X_train, y_train, X_val, y_val):
    """
    Entraîne UN SEUL VotingRegressor pour TOUTES les cibles simultanément.
    
    Le VotingRegressor avec MultiOutputRegressor gère automatiquement
    les prédictions multi-cibles en entraînant un modèle par cible en interne.
    
    Args:
        X_train: Features d'entraînement
        y_train: Toutes les cibles d'entraînement (4 colonnes: CO2, PM2.5, TVOC, humidity)
        X_val: Features de validation
        y_val: Toutes les cibles de validation
        
    Returns:
        Dictionnaire avec le modèle et les métriques par cible
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Entraînement du modèle Ensemble Multi-Output")
    logger.info(f"Prédiction simultanée de: {', '.join(COLONNES_CIBLES)}")
    logger.info(f"{'='*60}")
    
    # Créer les estimateurs de base (non entraînés)
    rf_base = RandomForestRegressor(
        n_estimators=100,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    
    gb_base = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=10,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42
    )
    
    # Créer le VotingRegressor
    voting_base = VotingRegressor(
        estimators=[
            ('rf', rf_base),
            ('gb', gb_base)
        ],
        n_jobs=-1
    )
    
    # Envelopper dans MultiOutputRegressor pour gérer le multi-output
    logger.info("→ Entraînement Multi-Output Voting Regressor (RF + GB)...")
    
    modele_multi_output = MultiOutputRegressor(voting_base, n_jobs=-1)
    
    # Entraîner sur toutes les cibles en une seule fois
    modele_multi_output.fit(X_train, y_train)
    
    # Évaluer le modèle sur l'ensemble de validation
    predictions = modele_multi_output.predict(X_val)
    
    # Calculer les métriques pour chaque cible
    logger.info("\n📊 Métriques par cible:")
    
    metriques_par_cible = {}
    
    for idx, nom_cible in enumerate(COLONNES_CIBLES):
        y_val_cible = y_val[:, idx]
        pred_cible = predictions[:, idx]
        
        mse = mean_squared_error(y_val_cible, pred_cible)
        mae = mean_absolute_error(y_val_cible, pred_cible)
        r2 = r2_score(y_val_cible, pred_cible)
        
        metriques_par_cible[nom_cible] = {
            'mse': mse,
            'mae': mae,
            'r2': r2
        }
        
        logger.info(f"  • {nom_cible:12s} - R²: {r2:.3f}, MAE: {mae:6.2f}, MSE: {mse:8.2f}")
    
    # Calculer les métriques globales (moyenne)
    mse_global = mean_squared_error(y_val, predictions)
    mae_global = mean_absolute_error(y_val, predictions)
    r2_global = r2_score(y_val, predictions)
    
    logger.info(f"\n🎯 Métriques globales (moyenne):")
    logger.info(f"   R²: {r2_global:.3f}, MAE: {mae_global:.2f}, MSE: {mse_global:.2f}")
    
    # Retourner le modèle unique avec les métriques
    return {
        "model": modele_multi_output,
        "model_type": "voting_multi_output",
        "metrics_by_target": metriques_par_cible,
        "metrics_global": {
            'mse': mse_global,
            'mae': mae_global,
            'r2': r2_global
        }
    }


def entrainer_tous_les_modeles(X_train, y_train, X_val, y_val):
    """
    Entraîne UN SEUL modèle pour toutes les cibles.
    
    Args:
        X_train, y_train: Données d'entraînement
        X_val, y_val: Données de validation
        
    Returns:
        Dictionnaire avec le modèle unique et toutes les métriques
    """
    # Entraîner un seul modèle multi-output
    return entrainer_modele_multi_output(X_train, y_train, X_val, y_val)


# ============================================================================
# FONCTIONS DE SAUVEGARDE
# ============================================================================

def sauvegarder_modeles(modeles, scaler, encodeur_salle, encodeur_capteur, dossier_modeles):
    """
    Sauvegarde le modèle multi-output et objets nécessaires pour la prédiction.
    
    Args:
        modeles: Dictionnaire contenant le modèle multi-output et ses métriques
                 Format: {"model": VotingRegressor, "model_type": str, 
                         "metrics_by_target": dict, "metrics_global": dict}
        scaler: StandardScaler pour normaliser les features
        encodeur_salle: LabelEncoder pour les salles
        encodeur_capteur: LabelEncoder pour les capteurs
        dossier_modeles: Dossier où sauvegarder les fichiers
    """
    # Créer le dossier s'il n'existe pas
    dossier_modeles.mkdir(parents=True, exist_ok=True)
    
    logger.info("\nSauvegarde du modèle multi-output...")
    
    # Sauvegarder le modèle multi-output unique
    modele = modeles["model"]
    model_type = modeles["model_type"]
    chemin_modele = dossier_modeles / "generic_multi_output.joblib"
    joblib.dump(modele, chemin_modele)
    logger.info(f"  ✓ {chemin_modele.name} ({model_type})")
    
    # Sauvegarder le scaler
    chemin_scaler = dossier_modeles / "generic_scaler.joblib"
    joblib.dump(scaler, chemin_scaler)
    logger.info(f"  ✓ {chemin_scaler.name}")
    
    # Sauvegarder les encodeurs
    chemin_salle = dossier_modeles / "salle_encoder.joblib"
    joblib.dump(encodeur_salle, chemin_salle)
    logger.info(f"  ✓ {chemin_salle.name}")
    
    chemin_capteur = dossier_modeles / "capteur_encoder.joblib"
    joblib.dump(encodeur_capteur, chemin_capteur)
    logger.info(f"  ✓ {chemin_capteur.name}")
    
    # Sauvegarder la configuration avec les métriques par cible
    config = {
        "lookback_minutes": LOOKBACK_MINUTES,
        "forecast_minutes": FORECAST_MINUTES,
        "feature_columns": COLONNES_FEATURES,
        "target_columns": COLONNES_CIBLES,
        "model_type": model_type,
        "metrics_by_target": modeles["metrics_by_target"],  # Métriques de chaque cible
        "metrics_global": modeles["metrics_global"],  # Métriques moyennes globales
        "salles_trained": list(encodeur_salle.classes_),
        "capteurs_trained": list(encodeur_capteur.classes_),
        "training_date": datetime.now().isoformat(),
        "version": "3.0"  # Version multi-output
    }
    
    chemin_config = dossier_modeles / "generic_training_config.json"
    with open(chemin_config, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    logger.info(f"  ✓ {chemin_config.name}")
    
    # Afficher un résumé des métriques par cible
    logger.info("\nRésumé des performances par cible:")
    metrics_by_target = modeles["metrics_by_target"]
    for target in COLONNES_CIBLES:
        metrics = metrics_by_target[target]
        r2 = metrics.get('r2', 0)
        mae = metrics.get('mae', 0)
        logger.info(f"  • {target}: {model_type.upper()} (R²={r2:.3f}, MAE={mae:.2f})")


# ============================================================================
# PIPELINE COMPLET D'ENTRAÎNEMENT
# ============================================================================

def entrainer_modeles_complet(chemin_dataset, dossier_modeles, inclure_api=False):
    """
    Pipeline complet d'entraînement des modèles.
    
    Cette fonction orchestre tout le processus :
    1. Charge les données (CSV + optionnellement API)
    2. Prépare les features
    3. Crée les séquences d'entraînement
    4. Entraîne les modèles
    5. Sauvegarde tout
    
    Args:
        chemin_dataset: Chemin vers le CSV preprocessé
        dossier_modeles: Dossier où sauvegarder les modèles
        inclure_api: Si True, combine avec les données de l'API
        
    Returns:
        True si succès, False sinon
    """
    logger.info("\n" + "="*70)
    logger.info("ENTRAÎNEMENT DES MODÈLES ML - QUALITÉ AIR INTÉRIEUR")
    logger.info("="*70)
    
    try:
        # ===== 1. Charger les données =====
        df = charger_dataset_csv(chemin_dataset)
        
        # Ajouter les données de l'API si demandé
        if inclure_api:
            df_api = recuperer_toutes_les_donnees_api()
            df = combiner_datasets(df, df_api)
        
        if df.empty or len(df) < 100:
            logger.error("Pas assez de données pour l'entraînement (minimum 100 lignes)")
            return False
        
        # ===== 2. Préparer les features =====
        encodeur_salle, encodeur_capteur = creer_encodeurs()
        df_features = preparer_toutes_les_features(df, encodeur_salle, encodeur_capteur, mode='fit')
        
        # ===== 3. Créer les séquences =====
        X, y, scaler = preparer_sequences_entrainement(df_features)
        
        if len(X) == 0:
            logger.error("Aucune séquence créée - données insuffisantes")
            return False
        
        # ===== 4. Diviser en train/validation (80/20) =====
        # shuffle=False pour respecter l'ordre chronologique
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, shuffle=False
        )
        
        logger.info(f"\nDivision des données:")
        logger.info(f"  • Entraînement: {len(X_train):,} exemples")
        logger.info(f"  • Validation: {len(X_val):,} exemples")
        
        # ===== 5. Entraîner les modèles =====
        modeles = entrainer_tous_les_modeles(X_train, y_train, X_val, y_val)
        
        # ===== 6. Sauvegarder tout =====
        sauvegarder_modeles(modeles, scaler, encodeur_salle, encodeur_capteur, dossier_modeles)
        
        logger.info("\n" + "="*70)
        logger.info("✅ ENTRAÎNEMENT TERMINÉ AVEC SUCCÈS!")
        logger.info("="*70)
        logger.info(f"Modèles sauvegardés dans: {dossier_modeles}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur pendant l'entraînement: {e}", exc_info=True)
        return False


# ============================================================================
# RÉENTRAÎNEMENT AUTOMATIQUE
# ============================================================================

def boucle_reentrainement_automatique(chemin_dataset, dossier_modeles):
    """
    Boucle infinie qui réentraîne les modèles toutes les heures.
    
    Cette fonction :
    1. Attend INTERVALLE_REENTRAINEMENT secondes
    2. Récupère les nouvelles données de l'API
    3. Réentraîne les modèles
    4. Recommence
    
    Args:
        chemin_dataset: Chemin vers le CSV de base
        dossier_modeles: Dossier des modèles
    """
    logger.info("\n" + "="*70)
    logger.info("MODE RÉENTRAÎNEMENT AUTOMATIQUE ACTIVÉ")
    logger.info("="*70)
    logger.info(f"Intervalle: {INTERVALLE_REENTRAINEMENT} secondes ({INTERVALLE_REENTRAINEMENT/3600:.1f}h)")
    
    compteur = 1
    
    while True:
        try:
            # Attendre l'intervalle
            logger.info(f"\n⏰ Prochaine mise à jour dans {INTERVALLE_REENTRAINEMENT/60:.0f} minutes...")
            time.sleep(INTERVALLE_REENTRAINEMENT)
            
            logger.info(f"\n{'='*70}")
            logger.info(f"RÉENTRAÎNEMENT #{compteur}")
            logger.info(f"{'='*70}")
            
            # Réentraîner avec les données de l'API
            succes = entrainer_modeles_complet(
                chemin_dataset, 
                dossier_modeles, 
                inclure_api=True
            )
            
            if succes:
                logger.info(f"✅ Réentraînement #{compteur} réussi!")
                compteur += 1
            else:
                logger.warning(f"⚠️  Réentraînement #{compteur} échoué, nouvelle tentative dans {INTERVALLE_REENTRAINEMENT/60:.0f} min")
            
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Arrêt du réentraînement automatique demandé")
            break
        except Exception as e:
            logger.error(f"❌ Erreur pendant le réentraînement: {e}", exc_info=True)
            logger.info(f"Nouvelle tentative dans {INTERVALLE_REENTRAINEMENT/60:.0f} minutes...")


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def main():
    """
    Point d'entrée principal du script.
    
    Exécute:
    1. Entraînement initial sur le dataset preprocessé
    2. Lance le réentraînement automatique toutes les heures
    """
    # Définir les chemins
    dossier_base = Path(__file__).parent.parent
    chemin_dataset = dossier_base / "assets" / "datasets" / "ml_data" / "dataset_ml_5min.csv"
    dossier_modeles = dossier_base / "assets" / "ml_models"
    
    # Vérifier que le dataset existe
    if not chemin_dataset.exists():
        logger.error(f"❌ Dataset non trouvé: {chemin_dataset}")
        logger.error("⚠️  Veuillez d'abord exécuter preprocess_dataset.py")
        return
    
    # ===== Entraînement initial =====
    logger.info("🚀 Démarrage de l'entraînement initial...")
    succes = entrainer_modeles_complet(chemin_dataset, dossier_modeles, inclure_api=False)
    
    if not succes:
        logger.error("❌ Entraînement initial échoué - arrêt du programme")
        return
    
    # ===== Lancer le réentraînement automatique =====
    logger.info("\n🔄 Activation du réentraînement automatique...")
    logger.info("💡 Appuyez sur Ctrl+C pour arrêter")
    
    try:
        boucle_reentrainement_automatique(chemin_dataset, dossier_modeles)
    except KeyboardInterrupt:
        logger.info("\n\n👋 Programme terminé")


if __name__ == "__main__":
    main()
