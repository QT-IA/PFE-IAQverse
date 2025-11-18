# Guide de Migration IAQverse v1 → v2

Ce document explique comment migrer de l'ancienne architecture vers la nouvelle architecture modulaire.

---

## 📋 Vue d'Ensemble

### Changements Majeurs

| Aspect | v1 | v2 |
|--------|----|----|
| **Architecture** | Monolithique | Modulaire + Microservices |
| **Storage** | Mémoire uniquement | InfluxDB + SQLite + Mémoire |
| **Communication** | HTTP Poll | HTTP + WebSocket |
| **ML** | Intégré dans API | Services séparés |
| **Format données** | Flat JSON | Structured JSON |
| **Orchestration** | Manuel | Docker Compose |

---

## 🔄 Migration de l'API

### Endpoints Changés

#### Ingestion de Données

**Ancien format (v1) - TOUJOURS SUPPORTÉ**
```json
POST /iaq
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

**Nouveau format (v2) - RECOMMANDÉ**
```json
POST /api/ingest
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

#### Requêtes de Données

Les endpoints de requête restent **identiques** :
```bash
GET /api/iaq/data?enseigne=Maison&salle=Bureau
```

Nouveaux paramètres disponibles :
- `sensor_id` : Alternative à `capteur_id`
- Support amélioré de l'agrégation temporelle

---

## 🗄️ Migration des Données

### Étape 1 : Préparation

```bash
# 1. Sauvegarder les données existantes
make backup

# 2. Initialiser la nouvelle base de données
make init-db
```

### Étape 2 : Import depuis l'Ancienne Version

Si vous avez des données en mémoire à migrer :

```python
# script_migration.py
import requests
import json

# Charger les anciennes données
with open('old_data.json', 'r') as f:
    old_data = json.load(f)

# Convertir et envoyer au nouveau format
for record in old_data:
    new_record = {
        "sensor_id": record.get("capteur_id") or f"{record['salle']}1",
        "enseigne": record.get("enseigne", "Maison"),
        "salle": record.get("salle", "Bureau"),
        "timestamp": record["timestamp"],
        "values": {
            "CO2": record.get("co2"),
            "PM25": record.get("pm25"),
            "TVOC": record.get("tvoc"),
            "Temperature": record.get("temperature"),
            "Humidity": record.get("humidity")
        }
    }
    
    # Filtrer les valeurs None
    new_record["values"] = {
        k: v for k, v in new_record["values"].items() 
        if v is not None
    }
    
    # Envoyer à la nouvelle API
    response = requests.post(
        "http://localhost:8000/api/ingest",
        json=new_record
    )
    print(f"Migré : {record['timestamp']}")
```

---

## 🔌 Migration du Code Client

### Frontend JavaScript

**Avant (v1) - Polling HTTP**
```javascript
// Ancien code
setInterval(async () => {
  const response = await fetch('/api/iaq/data?enseigne=Maison');
  const data = await response.json();
  updateDashboard(data);
}, 5000);
```

**Après (v2) - WebSocket**
```javascript
// Nouveau code avec WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    topics: ['measurements', 'predictions']
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'measurement') {
    updateDashboard(data);
  } else if (data.type === 'prediction') {
    updatePredictions(data);
  }
};

// Garder un fallback HTTP pour les données historiques
async function loadHistory() {
  const response = await fetch('/api/iaq/data?hours=24');
  const data = await response.json();
  renderHistoricalData(data);
}
```

### Backend Python (Simulateur)

**Avant (v1)**
```python
data = {
    "timestamp": datetime.now().isoformat(),
    "co2": 645,
    "pm25": 12,
    "tvoc": 0.2,
    "temperature": 22.3,
    "humidity": 45,
    "enseigne": "Maison",
    "salle": "Bureau"
}
requests.post("http://localhost:8000/iaq", json=data)
```

**Après (v2)**
```python
data = {
    "sensor_id": "bureau1",
    "enseigne": "Maison",
    "salle": "Bureau",
    "timestamp": datetime.now().isoformat() + "Z",
    "values": {
        "CO2": 645,
        "PM25": 12,
        "TVOC": 0.2,
        "Temperature": 22.3,
        "Humidity": 45
    }
}
requests.post("http://localhost:8000/api/ingest", json=data)
```

---

## 🚀 Déploiement

### Option 1 : Migration Douce (Recommandée)

Maintenir les deux versions en parallèle pendant la transition :

```yaml
# docker-compose.migration.yml
services:
  backend-v1:
    build: .
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
  
  backend-v2:
    build: .
    command: uvicorn backend.main_v2:app --host 0.0.0.0 --port 8001
    ports:
      - "8001:8001"
```

Étapes :
1. Déployer v2 sur port différent
2. Tester tous les endpoints
3. Migrer les clients progressivement
4. Retirer v1 une fois tous les clients migrés

### Option 2 : Migration Directe

```bash
# 1. Arrêter l'ancienne version
pkill -f "uvicorn backend.main"

# 2. Lancer la nouvelle version
make docker-up
# ou
uvicorn backend.main_v2:app --host 0.0.0.0 --port 8000
```

---

## ✅ Checklist de Migration

### Préparation
- [ ] Sauvegarder les données existantes
- [ ] Lire cette documentation complète
- [ ] Tester la v2 en environnement de dev
- [ ] Préparer les scripts de migration

### Backend
- [ ] Installer les nouvelles dépendances
- [ ] Configurer `.env` avec les variables InfluxDB/MQTT
- [ ] Initialiser la base de données SQLite
- [ ] Migrer les données existantes
- [ ] Tester les endpoints v2

### Frontend
- [ ] Adapter le code pour WebSocket
- [ ] Conserver fallback HTTP
- [ ] Tester la réception des messages temps réel
- [ ] Vérifier la compatibilité des graphiques

### Simulateur/Capteurs
- [ ] Mettre à jour le format des données envoyées
- [ ] Tester l'envoi vers `/api/ingest`
- [ ] Vérifier la réception dans InfluxDB

### Services
- [ ] Déployer InfluxDB
- [ ] Déployer MQTT (si utilisé)
- [ ] Configurer les services ML (predictor, trainer)
- [ ] Vérifier les logs

### Tests
- [ ] Tester ingestion de données
- [ ] Tester requêtes et agrégation
- [ ] Tester WebSocket
- [ ] Tester actions sur modules
- [ ] Tester prédictions ML
- [ ] Tester health checks

### Production
- [ ] Configurer le monitoring
- [ ] Configurer les backups
- [ ] Documenter la nouvelle architecture pour l'équipe
- [ ] Former les utilisateurs

---

## ⚠️ Points d'Attention

### Compatibilité

✅ **Compatible :**
- L'ancien endpoint `/iaq` continue de fonctionner
- Les requêtes `/api/iaq/data` fonctionnent à l'identique
- La structure du fichier `config.json` reste la même

❌ **Non compatible :**
- Les services ML ne sont plus dans le même processus
- Le stockage en mémoire seul n'est plus la seule option
- Les WebSocket nécessitent adaptation du frontend

### Performance

**Améliorations v2 :**
- Stockage temps réel avec InfluxDB (plus rapide)
- WebSocket (push vs poll, moins de charge)
- Services ML découplés (pas de blocage de l'API)

**À surveiller :**
- Latence WebSocket vs HTTP
- Usage mémoire InfluxDB
- Temps de démarrage des services

### Sécurité

**Nouvelles considérations :**
- Tokens InfluxDB à sécuriser
- Credentials MQTT à protéger
- WebSocket CORS à configurer
- Variables d'environnement sensibles

---

## 🆘 Résolution de Problèmes

### InfluxDB ne démarre pas

```bash
# Vérifier les logs
docker-compose logs influxdb

# Réinitialiser
docker-compose down -v
docker-compose up influxdb
```

### API ne se connecte pas à InfluxDB

```bash
# Vérifier la configuration
cat .env | grep INFLUX

# Tester la connexion
curl http://localhost:8086/ping

# Mode fallback (sans InfluxDB)
INFLUXDB_ENABLED=false uvicorn backend.main_v2:app
```

### WebSocket se déconnecte

```javascript
// Ajouter reconnexion automatique
function connectWebSocket() {
  const ws = new WebSocket('ws://localhost:8000/ws');
  
  ws.onclose = () => {
    console.log('WebSocket fermé, reconnexion dans 5s...');
    setTimeout(connectWebSocket, 5000);
  };
  
  return ws;
}
```

### Données manquantes après migration

```bash
# Vérifier la base mémoire
curl http://localhost:8000/api/iaq-database | jq

# Vérifier InfluxDB
curl -G http://localhost:8086/api/v2/query \
  --data-urlencode "org=iaqverse" \
  --data-urlencode "bucket=iaq_data" \
  -H "Authorization: Token YOUR_TOKEN"
```

---

## 📞 Support

Si vous rencontrez des problèmes :

1. Vérifier les logs : `make docker-logs`
2. Vérifier la santé : `make health`
3. Consulter la documentation : `README_V2.md`
4. Ouvrir une issue : https://github.com/QT-IA/PFE-IAQverse/issues

---

## 📝 Notes

- **Temps estimé de migration** : 2-4 heures
- **Downtime estimé** : 10-30 minutes (selon la méthode)
- **Rollback possible** : Oui (garder backup v1)

---

## ✨ Bénéfices Après Migration

- 🚀 Performance améliorée (InfluxDB)
- 📡 Temps réel (WebSocket)
- 🔧 Maintenance facilitée (architecture modulaire)
- 📈 Scalabilité (microservices)
- 🐳 Déploiement simplifié (Docker)
- 🔒 Sécurité renforcée (tokens, isolation)
