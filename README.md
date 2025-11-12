# IAQverse – Jumeau numérique pour la qualité de l'air intérieur

> IAQverse est une plateforme immersive et intelligente dédiée à la surveillance, la visualisation et l'amélioration de la qualité de l'air intérieur (IAQ) dans les bâtiments. Grâce à l'intégration de capteurs, d'une API en temps réel, d'un dashboard interactif et d'une scène VR, le projet transforme l'invisible en action.

---

## 📁 Structure du projet

```
IAQverse/
│
├── backend/                    # API FastAPI, traitement des données et ML
│   ├── main.py                 # Point d'entrée API FastAPI
│   ├── ml_train.py             # Entraînement des modèles ML (auto-réentraînement)
│   ├── ml_predict_generic.py  # Prédictions et actions préventives
│   ├── preprocess_dataset.py  # Prétraitement des données pour le ML
│   ├── test_api_endpoints.py  # Tests des endpoints API
│   ├── requirements.txt        # Dépendances Python (API)
│   ├── requirements-ml.txt     # Dépendances Python (ML)
│   ├── README_ML.md            # Documentation Machine Learning
│   └── README_ML_CONFIG.md     # Documentation configuration capteurs ML
│
├── frontend/                   # Dashboard web, jumeau numérique 3D
│   ├── index.html              # Page principale du dashboard
│   ├── digital-twin.html       # Visualisation 3D du jumeau numérique
│   ├── settings.html           # Configuration utilisateur
│   ├── style.css               # Styles globaux
│   ├── theme.js                # Gestion du thème (clair/sombre)
│   ├── charts.js               # Graphiques et visualisations
│   └── js/                     # Scripts JavaScript modulaires
│       ├── alerts-engine.js    # Moteur d'alertes
│       ├── charts.js           # Gestion des graphiques
│       ├── config-loader.js    # Chargement de la configuration
│       ├── dashboard.js        # Logique du dashboard
│       ├── digital-twin.js     # Logique du jumeau numérique
│       ├── i18n.js             # Internationalisation
│       ├── settings.js         # Gestion des paramètres
│       ├── tabs-manager.js     # Gestion des onglets
│       ├── theme.js            # Thème dynamique
│       ├── three-scene.js      # Scène 3D (Three.js)
│       └── utils.js            # Utilitaires
│
├── assets/                     # Ressources statiques et configuration
│   ├── config.json             # Configuration globale (utilisateurs, lieux, capteurs)
│   ├── datasets/               # Données de capteurs et ML
│   │   ├── IoT_Indoor_Air_Quality_Dataset.csv
│   │   ├── ml_data/            # Données prétraitées pour le ML
│   │   └── R1/                 # Données brutes par date
│   ├── i18n/                   # Fichiers de traduction
│   │   ├── en.json
│   │   ├── fr.json
│   │   ├── es.json
│   │   ├── de.json
│   │   └── it.json
│   ├── icons/                  # Icônes de l'application
│   ├── ml_models/              # Modèles ML entraînés
│   │   ├── generic_co2_rf.joblib
│   │   ├── generic_co2_gb.joblib
│   │   ├── generic_pm25_rf.joblib
│   │   ├── generic_pm25_gb.joblib
│   │   ├── generic_tvoc_rf.joblib
│   │   ├── generic_tvoc_gb.joblib
│   │   ├── generic_scaler.joblib
│   │   ├── salle_encoder.joblib
│   │   ├── capteur_encoder.joblib
│   │   └── generic_training_config.json
│   └── rooms/                  # Modèles 3D des pièces (.glb)
│
├── simulator.py                # Générateur de données capteurs simulées
│
└── README.md                   # Documentation du projet
```

---
## ✨ Fonctionnalités

### 📊 Surveillance en temps réel
- **Collecte IAQ** : CO₂, PM2.5, TVOC, température, humidité
- **Multi-capteurs** : Support de plusieurs capteurs par pièce
- **Multi-enseignes** : Gestion de plusieurs bâtiments/lieux

### 🔌 API FastAPI
- Réception et stockage des données en temps réel
- Endpoints IAQ avec filtrage et agrégation temporelle
- Configuration dynamique des capteurs
- Historique des actions préventives

### 📈 Dashboard Web Interactif
- Visualisation des indicateurs IAQ en temps réel
- Graphiques dynamiques avec Plotly.js
- Thème clair/sombre
- Multi-langue (EN, FR, ES, DE, IT)
- Vue par enseigne et par pièce

### 🏠 Jumeau Numérique 3D
- Visualisation 3D des pièces avec Three.js
- Chargement de modèles .glb personnalisés
- Navigation immersive dans les espaces
- Alertes visuelles contextuelles

### 🤖 Intelligence Artificielle
- **Modèles ML** : Random Forest et Gradient Boosting
- **Prédiction** : Anticipe la qualité de l'air 30 minutes à l'avance
- **Actions préventives** : Recommandations automatiques
- **Réentraînement automatique** : Toutes les heures avec nouvelles données
- **Multi-room** : Un seul modèle pour toutes les pièces

### 🎯 Capteurs et Simulation
- Génération de données réalistes via `simulator.py`
- Support de capteurs réels via API
- Configuration flexible par pièce

### 🔔 Système d'alertes
- Alertes en temps réel selon les seuils IAQ
- Notifications contextuelles
- Historique des actions préventives
- Statistiques par métrique et priorité

### ⚙️ Configuration centralisée
- Fichier `config.json` unique
- Gestion des utilisateurs et contacts
- Configuration des lieux et capteurs
- Paramètres d'affichage et notifications

---

## 🚀 Installation

### 1. Cloner le projet

```bash
git clone https://github.com/QT-IA/PFE-IAQverse.git
cd PFE-IAQverse
```

### 2. Installer les dépendances Python

#### Backend API
```bash
pip install -r backend/requirements.txt
```

#### Machine Learning (optionnel)
```bash
pip install -r backend/requirements-ml.txt
```

### 3. Lancer l'API FastAPI

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

L'API sera accessible sur : `http://localhost:8000`

### 4. Ouvrir le dashboard

Ouvrir `frontend/index.html` dans votre navigateur ou utiliser un serveur local :

```bash
# Avec Python
python -m http.server 8080

# Ou avec Node.js
npx http-server frontend -p 8080
```

Dashboard accessible sur : `http://localhost:8080`

### 5. Simuler des données (optionnel)

```bash
python simulator.py
```

---

## Technologies utilisées

* **Python** : FastAPI, Pydantic, SQLAlchemy, TensorFlow
* **JavaScript** : Plotly.js, A-Frame, WebSocket
* **HTML/CSS** : Interface responsive
* **SQLite / Firebase** : Stockage des données
* **VR** : Insta360, WebXR
* **Agenda** : Microsoft Graph API, Google Calendar API

## Objectifs pédagogiques

* Comprendre les enjeux de la qualité de l’air intérieur
* Concevoir un jumeau numérique immersif et interactif
* Appliquer des modèles IA pour la prédiction environnementale
* Automatiser des actions techniques et administratives

## Équipe projet

* Arthur Parizot de Laporterie
* Quentin Tajchner
