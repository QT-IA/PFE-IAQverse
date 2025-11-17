@echo off
chcp 65001 >nul
title Démarrage IAQverse - API + Service ML

echo ============================================
echo    IAQverse - Démarrage des services
echo ============================================
echo.

REM Vérifier que Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installé ou n'est pas dans le PATH
    pause
    exit /b 1
)

echo [OK] Python trouvé
echo.

REM Vérifier que les modèles ML existent
if not exist "assets\ml_models\generic_training_config.json" (
    echo [ERREUR] Modèles ML non trouvés dans assets\ml_models\
    echo Exécutez d'abord: python backend\ml\ml_train.py
    pause
    exit /b 1
)

echo [OK] Modèles ML trouvés
echo.

echo ============================================
echo Démarrage de l'API FastAPI...
echo ============================================
start "IAQverse - API" cmd /k "python -m uvicorn backend.main:app --reload"

echo Attente de 3 secondes pour le démarrage de l'API...
timeout /t 3 /nobreak >nul

echo.
echo ============================================
echo Démarrage du service ML de prédiction...
echo ============================================
start "IAQverse - Service ML" cmd /k "python backend\ml_service.py --interval 300"

echo.
echo ============================================
echo [OK] Services démarrés avec succès !
echo ============================================
echo.
echo Deux fenêtres ont été ouvertes:
echo   1. API FastAPI        : http://localhost:8000
echo   2. Service ML         : Prédictions toutes les 5 minutes
echo.
echo Documentation API : http://localhost:8000/api/iaq/docs
echo Frontend          : http://localhost:8000/frontend/digital-twin.html
echo.
echo Appuyez sur une touche pour fermer cette fenêtre...
echo (Les services continueront à tourner dans leurs fenêtres respectives)
pause >nul
