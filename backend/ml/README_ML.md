# README Machine Learning — Prédiction Qualité d'Air

## Objectif

Ce projet entraîne un modèle capable de prédire la qualité de l'air intérieur **30 minutes dans le futur**. Les capteurs mesurent : CO2, PM2.5, TVOC, température et humidité. Le script est générique et fonctionne pour n'importe quelle salle ou capteur.

---

## Comment ça marche

Le script transforme les données temporelles en un problème simple de **régression** :

* Entrée : l'état récent de l'air (environ 1 heure d'historique résumé).
* Sortie : la valeur attendue **30 minutes plus tard**.

Le modèle n'apprend pas des séquences longues. Il apprend les tendances locales à partir des données récentes.

---

## Étapes détaillées

### 1. Chargement des données

Le dataset preprocessé est lu depuis un CSV. Les timestamps sont convertis en format datetime et triés dans l'ordre.

Si activé, le script ajoute aussi les nouvelles données récupérées depuis l'API.

---

### 2. Création des features (caractéristiques)

Le script enrichit les données avec trois types de features :

**A. Temporelles**

* Heure de la journée
* Jour de la semaine
* Indicateur week-end

**B. Encodage**

* Salle → entier unique
* Capteur → entier unique

**C. Statistiques locales**
Pour chaque capteur :

* Différence par rapport au point précédent
* Moyenne mobile sur 3 points

Ces éléments permettent au modèle de comprendre les tendances proches.

---

### 3. Construction des exemples d'entraînement

Pour chaque point dans le temps et pour chaque capteur :

* Le script regarde les **LOOKBACK_MINUTES** derniers points (soit environ 1 heure).
* Il calcule une **moyenne** sur cette fenêtre. Ce vecteur devient **X**.
* Il prend la valeur **FORECAST_MINUTES** plus loin (30 min). Cette valeur devient **y**.

On répète cela pour tous les capteurs et toutes les salles.

Ensuite, **X est normalisé** pour faciliter l’apprentissage.

---

### 4. Division Train / Validation

Les données sont séparées en :

* 80 % pour l’entraînement
* 20 % pour la validation

Le découpage respecte l'ordre chronologique.

---

### 5. Entraînement des modèles

Pour chaque cible (CO2, PM2.5, TVOC), deux modèles sont entraînés :

* Random Forest
* Gradient Boosting

Chaque modèle apprend à prédire **une seule variable**, à partir de la même entrée X.

Le script calcule ensuite :

* MSE (erreur quadratique)
* MAE (erreur absolue)
* R² (qualité globale de la prédiction)

---

### 6. Sauvegarde

Sont sauvegardés automatiquement dans le dossier des modèles :

* Les modèles entraînés
* Le scaler utilisé pour normaliser les données
* Les encodeurs salle / capteur
* Un fichier JSON de configuration

Ces fichiers permettent de faire des prédictions plus tard sans réentraîner.

---

## Pourquoi 1 heure d'historique suffit

La plupart des variations de CO2, PM2.5 ou TVOC se produisent rapidement (occupation, ventilation, activités). Pour prédire seulement 30 minutes dans le futur, l'information utile est généralement dans l’heure précédente.

Les tendances longues (jour/nuit, cycles hebdos) sont déjà intégrées grâce aux features temporelles.

---

## Schéma simplifié du pipeline

```
Données brutes → Features → Fenêtres glissantes (1h) → X, y
→ Modèles ML → Validation → Sauvegarde
```

---

## Réentraînement automatique

Le script peut se lancer en mode automatique. Toutes les heures :

1. Il récupère les nouvelles données via l'API.
2. Il réentraine les modèles.
3. Il écrase les anciennes versions.

---

Le script apprend comment les capteurs évoluent sur la dernière heure pour deviner comment ils seront 30 minutes plus tard.
