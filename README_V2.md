# IAQverse 2.0 – Plateforme IAQ Intelligente avec Architecture Microservices

> **IAQverse 2.0** est une plateforme professionnelle de surveillance, visualisation et amélioration de la qualité de l'air intérieur (IAQ). Cette version majeure introduit une architecture microservices scalable, du stockage temps réel avec InfluxDB, des communications WebSocket et une orchestration Docker.

---

## 🎯 Nouveautés Version 2.0

### Architecture Refactorisée
- ✅ **Backend modulaire** : API organisée en modules fonctionnels
- ✅ **InfluxDB** : Base de données temps réel pour séries temporelles
- ✅ **SQLite Registry** : Métadonnées ML et états des modules
- ✅ **WebSocket** : Communication bidirectionnelle en temps réel
- ✅ **MQTT Ready** : Infrastructure pour contrôle IoT
- ✅ **Docker Compose** : Orchestration complète des services

### Nouveau Format de Données
```json
{
  "sensor_id": "bureau1",
  "enseigne": "Maison",
  "salle": "Bureau",
  "timestamp": "2025-11-18T10:05:00Z",
  "values": {
    "CO2": 645,
    "PM25": 12,
    "TVOC": 0.2,
    "Temperature": 22.3,
    "Humidity": 45
  }
}
```

---

## 📁 Structure du Projet 2.0

```
IAQverse/
│
├── backend/                     # API FastAPI modulaire
│   ├── core/                    # Infrastructure partagée
│   │   ├── settings.py          # Configuration centralisée
│   │   ├── influx_client.py     # Client InfluxDB
│   │   ├── sqlite_registry.py   # Registry ML et modules
│   │   └── websocket_manager.py # Gestionnaire WebSocket
│   │
│   ├── api/                     # Endpoints API modulaires
│   │   ├── ingest.py            # Ingestion de données
│   │   ├── query.py             # Requêtes et agrégation
│   │   ├── actions.py           # Exécution d'actions
│   │   ├── modules.py           # Gestion des modules IoT
│   │   ├── models_registry.py   # Registry des modèles ML
│   │   └── config_api.py        # Configuration
│   │
│   ├── ml/                      # Machine Learning
│   │   ├── ml_train.py          # Entraînement
│   │   ├── ml_predict_generic.py # Prédictions
│   │   └── ...
│   │
│   ├── main_v2.py               # Point d'entrée API v2 ✨ NEW
│   ├── main.py                  # API legacy (compatibilité)
│   └── requirements.txt
│
├── services/                    # Microservices
│   ├── simulator/               # Générateur de données
│   │   └── simulator.py         # Simulateur v2 ✨ NEW
│   │
│   ├── predictor/               # Service de prédiction (TODO)
│   │   ├── predictor.py
│   │   └── Dockerfile
│   │
│   ├── trainer/                 # Service d'entraînement (TODO)
│   │   ├── trainer.py
│   │   └── Dockerfile
│   │
│   └── alerting/                # Service d'alertes (TODO)
│       └── alert_worker.py
│
├── frontend/                    # Interface web
│   ├── index.html
│   ├── digital-twin.html
│   ├── js/
│   └── ...
│
├── assets/                      # Ressources
│   ├── config.json              # Configuration globale
│   ├── datasets/                # Données d'entraînement
│   ├── ml_models/               # Modèles ML entraînés
│   └── rooms/                   # Modèles 3D (.glb)
│
├── database/                    # Données persistantes ✨ NEW
│   ├── sqlite.db                # Registry SQLite
│   ├── influx_data/             # Données InfluxDB
│   └── mosquitto/               # Données MQTT
│
├── docker-compose.yml           # Orchestration Docker ✨ NEW
├── Makefile                     # Commandes utiles ✨ NEW
├── .env.example                 # Configuration exemple ✨ NEW
└── README.md
```

---

## 🚀 Démarrage Rapide

### Option 1 : Docker Compose (Recommandé)

```bash
# 1. Cloner le projet
git clone https://github.com/QT-IA/PFE-IAQverse.git
cd PFE-IAQverse

# 2. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env selon vos besoins

# 3. Lancer tous les services
make docker-up
# ou
docker-compose up -d

# 4. Vérifier l'état des services
make health
```

Services disponibles :
- **API Backend** : http://localhost:8000
- **API Docs** : http://localhost:8000/docs
- **Frontend** : http://localhost:8080
- **InfluxDB UI** : http://localhost:8086
- **WebSocket** : ws://localhost:8000/ws

### Option 2 : Développement Local

```bash
# 1. Installer les dépendances
make install-all

# 2. Lancer l'API
make run
# ou
uvicorn backend.main_v2:app --reload --host 0.0.0.0 --port 8000

# 3. (Terminal 2) Lancer le simulateur
make run-simulator

# 4. (Terminal 3) Lancer le frontend
make run-frontend
```

---

## 📡 API Endpoints

### Ingestion de Données

#### Nouveau Format (Recommandé)
```bash
POST /api/ingest
Content-Type: application/json

{
  "sensor_id": "bureau1",
  "enseigne": "Maison",
  "salle": "Bureau",
  "timestamp": "2025-11-18T10:05:00Z",
  "values": {
    "CO2": 645,
    "PM25": 12,
    "TVOC": 0.2,
    "Temperature": 22.3,
    "Humidity": 45
  }
}
```

#### Format Legacy (Rétrocompatibilité)
```bash
POST /iaq
Content-Type: application/json

{
  "timestamp": "2025-11-18T10:05:00Z",
  "co2": 645,
  "pm25": 12,
  "tvoc": 0.2,
  "temperature": 22.3,
  "humidity": 45,
  "enseigne": "Maison",
  "salle": "Bureau",
  "capteur_id": "bureau1"
}
```

### Requêtes de Données

```bash
# Récupérer les données brutes
GET /api/iaq/data?enseigne=Maison&salle=Bureau&raw=true

# Récupérer avec agrégation
GET /api/iaq/data?enseigne=Maison&hours=24&step=5min

# Prédictions ML
GET /api/predict/score?enseigne=Maison&salle=Bureau

# Actions préventives recommandées
GET /api/predict/preventive-actions?enseigne=Maison&salle=Bureau
```

### WebSocket

```javascript
// Connexion WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  console.log('Connecté au WebSocket');
  
  // S'abonner aux topics
  ws.send(JSON.stringify({
    type: 'subscribe',
    topics: ['measurements', 'predictions', 'actions']
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Message reçu:', data);
  
  // Types de messages:
  // - type: 'measurement' : Nouvelle mesure
  // - type: 'prediction' : Nouvelle prédiction
  // - type: 'action' : Action exécutée
  // - type: 'alert' : Alerte IAQ
  // - type: 'module_state' : Changement d'état module
};
```

### Gestion des Modules

```bash
# Obtenir les modules d'une salle
GET /api/room-modules?enseigne=Maison&salle=Bureau

# Exécuter une action
POST /api/execute-action
{
  "enseigne": "Maison",
  "salle": "Bureau",
  "module_type": "ventilation",
  "action_type": "turn_on",
  "priority": "high",
  "reason": {
    "pollutant": "CO2",
    "value": 1200,
    "level": "high"
  }
}

# États des modules
GET /api/modules/states?enseigne=Maison
```

### Registry ML

```bash
# Enregistrer un nouveau modèle
POST /api/models/register
{
  "model_name": "co2_predictor",
  "model_version": "1.0.0",
  "model_type": "RandomForest",
  "model_path": "/models/co2_rf.joblib",
  "metrics": {"r2": 0.89, "mae": 12.5},
  "set_active": true
}

# Lister les modèles
GET /api/models/list?model_name=co2_predictor

# Historique d'entraînement
GET /api/models/training-history?limit=10
```

---

## 🏗️ Architecture Technique

### Couches de l'Application

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Vue/React)                 │
│              WebSocket + REST API Clients                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│                   API Gateway (FastAPI)                  │
│                    WebSocket Manager                     │
└──────┬──────────────┬──────────────┬────────────────────┘
       │              │              │
       ↓              ↓              ↓
┌──────────┐   ┌──────────┐   ┌──────────┐
│ Ingest   │   │  Query   │   │ Actions  │
│   API    │   │   API    │   │   API    │
└────┬─────┘   └────┬─────┘   └────┬─────┘
     │              │              │
     ↓              ↓              ↓
┌─────────────────────────────────────────────────────────┐
│                  Storage Layer                           │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│   │ InfluxDB │  │  SQLite  │  │  Memory  │             │
│   │ (TimeSer)│  │ (Metadata│  │ (Fallback│             │
│   └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│              Microservices (Async Workers)               │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│   │Predictor │  │ Trainer  │  │ Alerting │             │
│   │(10 min)  │  │(24h)     │  │(1 min)   │             │
│   └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│              IoT Layer (MQTT)                            │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│   │ Capteurs │  │Actionneurs│  │ Modules  │             │
│   └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
```

### Flux de Données

1. **Ingestion** : Capteurs → API Ingest → InfluxDB + Memory
2. **Traitement** : Predictor → ML Model → Prédictions → InfluxDB
3. **Actions** : Alerting → Analyse → Actions → MQTT → Actionneurs
4. **Visualisation** : Frontend → Query API → Données + WebSocket push

---

## 🛠️ Commandes Makefile

```bash
# Installation
make install          # Installe dépendances backend
make install-ml       # Installe dépendances ML
make install-all      # Installe tout

# Développement
make run              # Lance l'API v2
make run-old          # Lance l'API legacy
make run-simulator    # Lance le simulateur
make run-frontend     # Lance le frontend

# Docker
make docker-up        # Lance tous les services
make docker-down      # Arrête les services
make docker-logs      # Affiche les logs
make docker-rebuild   # Reconstruit les services

# Base de données
make init-db          # Initialise SQLite
make clean-db         # Supprime la base

# Monitoring
make health           # Vérifie la santé de l'API
make stats            # Affiche les statistiques

# Maintenance
make clean            # Nettoie les fichiers temp
make backup           # Sauvegarde les données
```

---

## 🔧 Configuration

### Variables d'Environnement

Copier `.env.example` vers `.env` et ajuster :

```bash
# InfluxDB
INFLUXDB_ENABLED=true
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-secret-token
INFLUXDB_ORG=iaqverse
INFLUXDB_BUCKET=iaq_data

# WebSocket
WEBSOCKET_ENABLED=true

# MQTT (optionnel)
MQTT_ENABLED=true
MQTT_BROKER=localhost
MQTT_PORT=1883

# ML
ML_PREDICTOR_INTERVAL=600  # 10 minutes
ML_TRAINER_INTERVAL=86400  # 24 heures
```

---

## 📊 Features Implémentées

### Backend API v2
- ✅ Architecture modulaire (core + api)
- ✅ Ingestion nouveau format + legacy
- ✅ Requêtes avec agrégation temporelle
- ✅ WebSocket temps réel
- ✅ Registry ML avec versioning
- ✅ Gestion des modules IoT
- ✅ Actions préventives

### Storage
- ✅ InfluxDB pour séries temporelles
- ✅ SQLite pour métadonnées
- ✅ Fallback mémoire si InfluxDB indisponible

### Services
- ✅ Simulateur de données v2
- ⏳ Predictor ML (TODO)
- ⏳ Trainer ML (TODO)
- ⏳ Alerting worker (TODO)

### DevOps
- ✅ Docker Compose complet
- ✅ Makefile pour workflow
- ✅ Configuration par environnement
- ✅ Health checks

---

## 🔜 Roadmap

### Phase 1 : Microservices ML (En cours)
- [ ] Implémenter service Predictor
- [ ] Implémenter service Trainer
- [ ] Implémenter service Alerting
- [ ] Tests d'intégration

### Phase 2 : MQTT & IoT
- [ ] Client MQTT pour actionneurs
- [ ] Protocole standardisé
- [ ] Intégration modules réels

### Phase 3 : Frontend v2
- [ ] Intégration WebSocket
- [ ] Dashboard temps réel
- [ ] Gestion des actionneurs

### Phase 4 : Production
- [ ] CI/CD pipeline
- [ ] Monitoring (Prometheus/Grafana)
- [ ] Déploiement cloud

---

## 🧪 Tests

```bash
# Lancer les tests
make test

# Vérifier le code
make lint

# Formater le code
make format

# Test de l'API
curl http://localhost:8000/health

# Test WebSocket
websocat ws://localhost:8000/ws
```

---

## 📚 Documentation Technique

### InfluxDB Schema

```
Measurements:
- iaq_raw         : Mesures brutes des capteurs
- iaq_forecast    : Prédictions ML
- iaq_actions     : Actions exécutées
- iaq_scores      : Scores IAQ globaux

Tags:
- sensor_id, enseigne, salle, priority, module_type

Fields:
- co2, pm25, tvoc, temperature, humidity
```

### SQLite Tables

```sql
ml_models           -- Versions des modèles
module_states       -- États actuels des modules
training_history    -- Historique d'entraînement
```

---

## 🤝 Contribution

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

---

## 📄 License

Ce projet est sous licence MIT.

---

## 👥 Équipe

- Arthur Parizot de Laporterie
- Quentin Tajchner

---

## 📞 Support

Pour toute question ou problème :
- 📧 Email : contact@iaqverse.io
- 🐛 Issues : https://github.com/QT-IA/PFE-IAQverse/issues
- 📖 Docs : https://iaqverse.io/docs

---

## 🙏 Remerciements

- FastAPI pour le framework API
- InfluxDB pour le stockage temps réel
- Three.js pour la visualisation 3D
- La communauté open-source
