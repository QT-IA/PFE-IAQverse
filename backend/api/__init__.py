"""
API endpoints for IAQverse
"""
from .ingest import router as ingest_router, iaq_database
from .query import router as query_router
from .actions import router as actions_router
from .modules import router as modules_router
from .models_registry import router as models_registry_router
from .config_api import router as config_router

__all__ = [
    "ingest_router",
    "query_router",
    "actions_router",
    "modules_router",
    "models_registry_router",
    "config_router",
    "iaq_database",
]
