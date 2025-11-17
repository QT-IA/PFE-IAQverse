/**
 * Configuration centralisée des endpoints API
 * Toutes les URLs de l'API sont définies ici pour faciliter la maintenance
 */

const API_BASE_URL = 'http://localhost:8000';

const API_ENDPOINTS = {
    // Documentation
    architecture: `${API_BASE_URL}/api/iaq/architecture`,
    
    // Health & Monitoring
    health: `${API_BASE_URL}/api/iaq/health`,
    
    // Mesures IAQ
    measurements: `${API_BASE_URL}/api/iaq/measurements`,
    measurementsRaw: `${API_BASE_URL}/api/iaq/measurements/raw`,
    measurementsDebug: `${API_BASE_URL}/api/iaq/measurements/debug`,
    
    // Configuration
    config: `${API_BASE_URL}/api/iaq/config`,
    sensors: `${API_BASE_URL}/api/iaq/sensors`,
    
    // Assets (fichiers 3D)
    assetsRoomsFiles: `${API_BASE_URL}/api/iaq/assets/rooms/files`,
    
    // Actions préventives
    preventiveActions: `${API_BASE_URL}/api/iaq/actions/preventive`,
    preventiveActionsStats: `${API_BASE_URL}/api/iaq/actions/preventive/stats`,
    
    // Exécutions d'actions
    actionsExecutions: `${API_BASE_URL}/api/iaq/actions/executions`,
    actionsExecutionsStats: `${API_BASE_URL}/api/iaq/actions/executions/stats`,
    
    // Lieux et modules
    locations: (enseigne, salle) => `${API_BASE_URL}/api/iaq/locations/${encodeURIComponent(enseigne)}/rooms/${encodeURIComponent(salle)}/modules`,
};

// Note: Les prédictions ML sont maintenant effectuées par un service autonome
// qui POST les résultats dans /api/iaq/actions/preventive.
// Le frontend récupère ces prédictions via GET /api/iaq/actions/preventive.
