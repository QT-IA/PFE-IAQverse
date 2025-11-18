"""
Configuration centrale pour l'application IAQverse
"""
from pathlib import Path
from typing import Optional
from pydantic import BaseSettings

class Settings(BaseSettings):
    """Configuration globale de l'application"""
    
    # Application
    APP_NAME: str = "IAQverse"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 1
    
    # CORS
    CORS_ORIGINS: list = ["*"]
    
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    ASSETS_DIR: Path = BASE_DIR / "assets"
    CONFIG_FILE: Path = ASSETS_DIR / "config.json"
    ML_MODELS_DIR: Path = ASSETS_DIR / "ml_models"
    DATASETS_DIR: Path = ASSETS_DIR / "datasets"
    ROOMS_DIR: Path = ASSETS_DIR / "rooms"
    
    # InfluxDB
    INFLUXDB_ENABLED: bool = False  # Désactivé par défaut, activé si disponible
    INFLUXDB_URL: str = "http://localhost:8086"
    INFLUXDB_TOKEN: Optional[str] = None
    INFLUXDB_ORG: str = "iaqverse"
    INFLUXDB_BUCKET: str = "iaq_data"
    
    # SQLite
    SQLITE_DB_PATH: Path = BASE_DIR / "database" / "sqlite.db"
    
    # WebSocket
    WEBSOCKET_ENABLED: bool = True
    WEBSOCKET_PING_INTERVAL: int = 30
    WEBSOCKET_PING_TIMEOUT: int = 10
    
    # MQTT (optionnel)
    MQTT_ENABLED: bool = False
    MQTT_BROKER: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None
    MQTT_TOPIC_PREFIX: str = "iaqverse"
    
    # ML Services
    ML_PREDICTOR_INTERVAL: int = 600  # 10 minutes
    ML_TRAINER_INTERVAL: int = 86400  # 24 heures
    ML_FORECAST_MINUTES: int = 30
    
    # Data retention
    DATA_RETENTION_DAYS: int = 90
    MAX_MEMORY_RECORDS: int = 10000  # Limite pour la mémoire temporaire
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Instance globale
settings = Settings()
