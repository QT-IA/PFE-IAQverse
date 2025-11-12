# Modèles ML pour IAQverse

## Fichier manquant : `generic_multi_output.joblib`

Le fichier `generic_multi_output.joblib` (228 MB) est trop volumineux pour être stocké sur GitHub.

### Options pour obtenir le modèle :

1. **Générer le modèle localement** :
   ```bash
   cd backend/ml
   python ml_train.py
   ```
   Cela créera un nouveau modèle dans `assets/ml_models/`

2. **Télécharger depuis un service de stockage externe** (à configurer) :
   - Google Drive
   - Dropbox
   - AWS S3
   - Autre service de stockage cloud

3. **Utiliser Git LFS** (Large File Storage) :
   Si votre organisation a Git LFS activé, vous pouvez l'utiliser pour gérer ce fichier.

## Fichiers présents

- `capteur_encoder.joblib` - Encodeur pour les IDs de capteurs
- `salle_encoder.joblib` - Encodeur pour les noms de salles
- `generic_scaler.joblib` - Scaler pour la normalisation des données
- `generic_training_config.json` - Configuration d'entraînement du modèle
- `generic_multi_output.joblib` - **Modèle principal (NON INCLUS - voir ci-dessus)**

## Note importante

Sans le fichier `generic_multi_output.joblib`, les fonctionnalités de prédiction ML ne fonctionneront pas. Assurez-vous de l'avoir avant d'utiliser les endpoints ML de l'API.
