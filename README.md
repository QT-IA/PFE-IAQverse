# IAQverse – Jumeau numérique pour la qualité de l'air intérieur

> IAQverse est une plateforme immersive et intelligente dédiée à la surveillance, la visualisation et l'amélioration de la qualité de l'air intérieur (IAQ) dans les bâtiments. Grâce à l'intégration de capteurs, d'une API en temps réel, d'un service ML autonome, d'un dashboard interactif et d'une scène 3D, le projet transforme l'invisible en action.

---

## 📁 Structure du projet

```
IAQverse/
│
├── backend/                    # API FastAPI, traitement des données et ML
│   ├── main.py                 # API FastAPI (16 endpoints RESTful)
│   ├── ml_service.py           # Service ML autonome (prédictions périodiques)
│   ├── action_selector.py      # Calcul des scores IAQ
│   ├── modelsAPI.py            # Modèles Pydantic
│   ├── utils.py                # Utilitaires (config, datasets)
│   ├── requirements.txt        # Dépendances Python (API)
│   └── ml/                     # Module Machine Learning
│       ├── ml_train.py         # Entraînement des modèles ML
│       ├── ml_predict_generic.py  # Moteur de prédiction générique
│       ├── preprocess_dataset.py  # Prétraitement des données
│       ├── demo_end_to_end.py     # Démo complète du workflow ML
│       ├── requirements-ml.txt    # Dépendances Python (ML)
│       └── README_ML.md           # Documentation Machine Learning
│
├── frontend/                   # Dashboard web, jumeau numérique 3D
│   ├── index.html              # Page principale du dashboard
│   ├── digital-twin.html       # Visualisation 3D du jumeau numérique
│   ├── settings.html           # Configuration utilisateur
│   ├── style.css               # Styles globaux
│   └── js/                     # Scripts JavaScript modulaires
│       ├── api.js              # Configuration des endpoints API
│       ├── alerts-engine.js    # Moteur d'alertes
│       ├── charts.js           # Graphiques temps réel
│       ├── config-loader.js    # Chargement de la configuration
│       ├── dashboard.js        # Logique du dashboard
│       ├── digital-twin.js     # Logique du jumeau numérique
│       ├── preventive-global.js # Actions préventives globales
│       ├── i18n.js             # Internationalisation
│       ├── settings.js         # Gestion des paramètres
│       ├── tabs-manager.js     # Gestion des onglets
│       ├── theme.js            # Thème dynamique
│       ├── three-scene.js      # Scène 3D (Three.js)
│       └── utils.js            # Utilitaires
│
├── assets/                     # Ressources statiques et configuration
│   ├── config.json             # Configuration globale (utilisateurs, lieux, capteurs)
│   ├── architecture.html       # Documentation de l'architecture API
│   ├── datasets/               # Données de capteurs et ML
│   │   ├── IoT_Indoor_Air_Quality_Dataset.csv
│   │   ├── ml_data/            # Données prétraitées pour le ML
│   │   └── R1/                 # Données brutes par date
│   ├── i18n/                   # Fichiers de traduction (EN, FR, ES, DE, IT)
│   ├── icons/                  # Icônes de l'application
│   ├── ml_models/              # Modèles ML entraînés
│   │   ├── generic_multi_output.joblib  # Modèle multi-output unique
│   │   ├── generic_scaler.joblib
│   │   ├── salle_encoder.joblib
│   │   ├── capteur_encoder.joblib
│   │   └── generic_training_config.json
│   └── rooms/                  # Modèles 3D des pièces (.glb)
│
├── simulator.py                # Générateur de données capteurs simulées
├── start.bat                   # Démarrage automatique (API + Service ML)
├── README.md                   # Documentation du projet
└── VERIFICATION_FINALE.md      # Rapport de conformité de l'architecture
```

---

## 🏗️ Architecture

### Séparation des responsabilités

```
┌─────────────────────────────────────────────┐
│           Frontend (JavaScript)             │
│  - Visualisation 3D (Three.js)             │
│  - Graphiques temps réel (Plotly.js)       │
│  - Dashboard interactif                     │
└──────────────────┬──────────────────────────┘
                   │ HTTP REST API
                   ▼
┌─────────────────────────────────────────────┐
│        API FastAPI (backend/main.py)        │
│  - 16 endpoints RESTful (/api/iaq/*)       │
│  - Stockage des données en mémoire         │
│  - Configuration dynamique                  │
│  - Pas de calculs ML                       │
└──────────────────┬──────────────────────────┘
                   │ POST /api/iaq/actions/preventive
                   ▲ GET  /api/iaq/measurements/raw
                   │
┌─────────────────────────────────────────────┐
│    Service ML (backend/ml_service.py)       │
│  - Tourne en arrière-plan (indépendant)   │
│  - Prédictions toutes les 5 minutes        │
│  - Calcul des scores IAQ prédits           │
│  - POST automatique des actions            │
└──────────────────┬──────────────────────────┘
                   │ import
                   ▼
┌─────────────────────────────────────────────┐
│  Moteur ML (backend/ml/ml_predict_generic.py)│
│  - Chargement des modèles ML               │
│  - Feature engineering                      │
│  - Prédictions multi-output                │
│  - Analyse des risques                     │
└─────────────────────────────────────────────┘
```

### Endpoints API (RESTful)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/iaq/architecture` | Documentation HTML de l'architecture |
| GET | `/api/iaq/health` | Statut de santé de l'API |
| GET | `/api/iaq/measurements` | Mesures IAQ agrégées |
| GET | `/api/iaq/measurements/raw` | Données brutes de la base |
| GET | `/api/iaq/measurements/debug` | Informations de debug |
| GET | `/api/iaq/config` | Configuration de l'application |
| PUT | `/api/iaq/config` | Mise à jour de la configuration |
| GET | `/api/iaq/sensors` | Liste des capteurs configurés |
| POST | `/api/iaq/assets/rooms/files` | Upload de modèles 3D |
| DELETE | `/api/iaq/assets/rooms/files` | Suppression de fichiers 3D |
| GET | `/api/iaq/actions/preventive` | Actions préventives (prédictions ML) |
| POST | `/api/iaq/actions/preventive` | Enregistrement d'actions préventives |
| GET | `/api/iaq/actions/preventive/stats` | Statistiques des actions |
| POST | `/api/iaq/actions/executions` | Exécution d'une action |
| GET | `/api/iaq/actions/executions` | Historique des exécutions |
| GET | `/api/iaq/actions/executions/stats` | Statistiques des exécutions |
| GET | `/api/iaq/locations/{enseigne}/rooms/{salle}/modules` | Modules d'une pièce |

---

## ✨ Fonctionnalités

### 📊 Surveillance en temps réel
- **Collecte IAQ** : CO₂, PM2.5, TVOC, température, humidité
- **Multi-capteurs** : Support de plusieurs capteurs par pièce
- **Multi-enseignes** : Gestion de plusieurs bâtiments/lieux
- **Agrégation temporelle** : Données par minute, 5min, heure, jour

### 🔌 API FastAPI RESTful
- 16 endpoints documentés (conforme à `assets/architecture.html`)
- Réception et stockage des données en temps réel
- Configuration dynamique des capteurs et lieux
- Documentation interactive : `/api/iaq/docs`
- CORS configuré pour développement

### 📈 Dashboard Web Interactif
- Visualisation des indicateurs IAQ en temps réel
- Graphiques dynamiques avec Plotly.js
- Thème clair/sombre
- Multi-langue (EN, FR, ES, DE, IT)
- Vue par enseigne et par pièce
- Historique des actions préventives

### 🏠 Jumeau Numérique 3D
- Visualisation 3D des pièces avec Three.js
- Chargement de modèles .glb personnalisés
- Navigation immersive dans les espaces
- Alertes visuelles contextuelles sur les points critiques
- Score IAQ prédit affiché en temps réel

### 🤖 Intelligence Artificielle (Service autonome)
- **Architecture** : Service ML indépendant de l'API
- **Modèle** : Multi-output unique (RandomForest/GradientBoosting)
- **Prédiction** : Anticipe CO₂, PM2.5, TVOC à 30 minutes
- **Actions préventives** : Recommandations automatiques basées sur les seuils
- **Exécution** : Toutes les 5 minutes (configurable)
- **Multi-room** : Un seul modèle pour toutes les pièces
- **Score IAQ** : Calcul automatique (0-100) avec niveaux (excellent/good/moderate/poor)

### 🎯 Capteurs et Simulation
- Génération de données réalistes via `simulator.py`
- Support de capteurs réels via API POST `/api/iaq/measurements`
- Configuration flexible par pièce dans `config.json`
- Détection automatique des capteurs actifs

### 🔔 Système d'alertes
- Alertes en temps réel selon les seuils IAQ
- Notifications contextuelles sur le jumeau 3D
- Historique des actions préventives avec statistiques
- Priorisation (urgent/high/medium/low)

### ⚙️ Configuration centralisée
- Fichier `config.json` unique
- Gestion des utilisateurs et contacts
- Configuration des lieux, pièces et capteurs
- Paramètres d'affichage et notifications
- API de mise à jour dynamique

---

## 🚀 Installation et Démarrage

### Prérequis
- Python 3.11+
- Navigateur web moderne (Chrome/Firefox/Edge)

### 1. Cloner le projet

```bash
git clone https://github.com/QT-IA/PFE-IAQverse.git
cd PFE-IAQverse
```

### 2. Installer les dépendances

```bash
# API FastAPI
pip install -r backend/requirements.txt

# Machine Learning (requis pour les prédictions)
pip install -r backend/ml/requirements-ml.txt
```

### 3. Entraîner les modèles ML (première utilisation)

```bash
python backend/ml/ml_train.py
```

Cela génère les modèles dans `assets/ml_models/`.

### 4. Démarrage rapide (Recommandé)

**Windows** : Double-cliquer sur `start.bat`

Ou en ligne de commande :

```bash
start.bat
```

Cela démarre automatiquement :
1. **API FastAPI** : `http://localhost:8000`
2. **Service ML** : Prédictions toutes les 5 minutes

### 5. Démarrage manuel (Alternative)

#### Terminal 1 : API FastAPI
```bash
uvicorn backend.main:app --reload
```

#### Terminal 2 : Service ML
```bash
python backend/ml_service.py --interval 300
```

### 6. Accéder à l'application

- **Dashboard** : `http://localhost:8000/frontend/index.html`
- **Jumeau numérique 3D** : `http://localhost:8000/frontend/digital-twin.html`
- **Documentation API** : `http://localhost:8000/api/iaq/docs`
- **Architecture** : `http://localhost:8000/api/iaq/architecture`

### 7. Générer des données (Optionnel)

```bash
python simulator.py
```

Génère des données IAQ réalistes pour tester l'application.

---

## 📖 Documentation détaillée

- **Machine Learning** : `backend/ml/README_ML.md`
- **Architecture API** : `assets/architecture.html` ou `http://localhost:8000/api/iaq/architecture`
- **Vérification** : `VERIFICATION_FINALE.md`

---

## 🛠️ Technologies utilisées

### Backend
- **FastAPI** : Framework web asynchrone
- **Pydantic** : Validation des données
- **Pandas/NumPy** : Traitement des données
- **Scikit-learn** : Modèles ML (RandomForest, GradientBoosting)
- **Joblib** : Sérialisation des modèles

### Frontend
- **Three.js** : Visualisation 3D
- **Plotly.js** : Graphiques interactifs
- **Vanilla JavaScript** : Logique applicative
- **CSS3** : Design responsive

### DevOps
- **Uvicorn** : Serveur ASGI
- **Git** : Contrôle de version

---

## 🎯 Objectifs pédagogiques

- Comprendre les enjeux de la qualité de l'air intérieur
- Concevoir une architecture microservices (API + Service ML)
- Concevoir un jumeau numérique immersif et interactif
- Appliquer des modèles IA pour la prédiction environnementale
- Implémenter une API RESTful conforme aux standards
- Séparer les responsabilités (API vs calculs ML)

---

## 👥 Équipe projet

- **Arthur Parizot de Laporterie**
- **Quentin Tajchner**

---

## 📝 Licence

Projet académique - PFE 2025
