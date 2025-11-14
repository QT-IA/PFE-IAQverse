/**
 * Gestion du panneau global des actions préventives
 */

/**
 * Récupère et affiche toutes les actions préventives pour toutes les pièces
 */
async function fetchAndDisplayGlobalPreventiveActions() {
    const container = document.getElementById('preventive-global-container');
    if (!container) return;
    
    try {
        // Attendre que la config soit chargée
        await loadConfig();
        const cfg = getConfig();
        
        if (!cfg || !cfg.lieux || !cfg.lieux.enseignes) {
            console.error('[preventive-global] Configuration not available:', cfg);
            container.innerHTML = '<div class="preventive-loading">Configuration non disponible</div>';
            return;
        }
        
        console.log('[preventive-global] Config loaded, enseignes:', cfg.lieux.enseignes.length);
        
        const allRoomActions = [];
        
        // Parcourir toutes les enseignes et toutes les pièces
        for (const enseigne of cfg.lieux.enseignes) {
            if (!enseigne.pieces || !Array.isArray(enseigne.pieces)) continue;
            
            for (const salle of enseigne.pieces) {
                const capteur_id = salle.capteurs?.[0] || salle.nom || 'Unknown';
                
                const actionsParams = new URLSearchParams({
                    enseigne: enseigne.nom || 'Unknown',
                    salle: salle.nom || 'Unknown',
                    capteur_id: capteur_id
                });
                
                const scoreParams = new URLSearchParams({
                    enseigne: enseigne.nom || 'Unknown',
                    salle: salle.nom || 'Unknown'
                });
                
                try {
                    // Fetch actions
                    const actionsResponse = await fetch(`http://localhost:8000/api/predict/preventive-actions?${actionsParams}`);
                    const actionsData = await actionsResponse.json();
                    
                    // Fetch score (même format que dans charts.js)
                    const scoreData = await getPredictedScore(enseigne.nom, salle.nom);
                    
                    if (!actionsData.error && actionsData.actions && actionsData.actions.length > 0) {
                        allRoomActions.push({
                            enseigne: enseigne.nom,
                            salle: salle.nom,
                            actions: actionsData.actions,
                            score: scoreData ? scoreData.predicted_score : null
                        });
                    }
                } catch (error) {
                    console.error(`[preventive-global] Error fetching actions for ${enseigne.nom}/${salle.nom}:`, error);
                }
            }
        }
        
        console.log('[preventive-global] Found actions for', allRoomActions.length, 'rooms');
        
        // Sauvegarder dans sessionStorage
        sessionStorage.setItem('globalPreventiveActions', JSON.stringify(allRoomActions));
        
        displayGlobalPreventiveActions(allRoomActions);
        
    } catch (error) {
        console.error('[preventive-global] Error fetching global actions:', error);
        // Essayer de restaurer depuis le cache
        const cached = sessionStorage.getItem('globalPreventiveActions');
        if (cached) {
            try {
                const cachedData = JSON.parse(cached);
                displayGlobalPreventiveActions(cachedData);
            } catch (e) {
                container.innerHTML = '<div class="preventive-error">Erreur lors du chargement des prédictions</div>';
            }
        } else {
            container.innerHTML = '<div class="preventive-error">Erreur lors du chargement des prédictions</div>';
        }
    }
}

/**
 * Affiche les actions préventives globales en carrousel
 */
function displayGlobalPreventiveActions(allRoomActions) {
    const container = document.getElementById('preventive-global-container');
    if (!container) return;
    
    if (!allRoomActions || allRoomActions.length === 0) {
        container.innerHTML = `
            <div class="preventive-all-good">
                Aucune action préventive nécessaire
            </div>
        `;
        return;
    }
    
    const t = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t : (()=>undefined);
    
    const deviceI18nMap = {
        'window': 'window',
        'ventilation': 'ventilation',
        'air_conditioning': 'air_conditioning',
        'radiator': 'radiator'
    };
    
    const actionI18nMap = {
        'open': 'open',
        'close': 'close',
        'turn_on': 'turn_on',
        'turn_off': 'turn_off',
        'increase': 'increase',
        'decrease': 'decrease'
    };
    
    // Créer le carrousel
    let html = '<div class="preventive-carousel">';
    
    allRoomActions.forEach((roomData, index) => {
        const actionsCount = roomData.actions.length;
        const score = roomData.score !== null && roomData.score !== undefined ? Math.round(roomData.score) : null;
        
        html += `
            <div class="preventive-room-card">
                <div class="preventive-room-header">
                    <div class="preventive-room-title-row">
                        <div class="preventive-room-title">${roomData.salle}</div>
                        ${score !== null ? `<div class="preventive-room-score">${score}</div>` : ''}
                    </div>
                    <div class="preventive-room-location">${roomData.enseigne}</div>
                    <div class="preventive-room-count">
                        ${actionsCount} action${actionsCount > 1 ? 's' : ''}
                    </div>
                </div>
                <div class="preventive-room-actions">
        `;
        
        roomData.actions.forEach((action, actionIndex) => {
            const deviceKey = deviceI18nMap[action.device] || action.device;
            const deviceName = (t && t(`digitalTwin.sample.${deviceKey}.subject`)) || action.device;
            
            const actionKey = actionI18nMap[action.action] || action.action;
            const actionVerb = (t && t(`digitalTwin.actionVerbs.${actionKey}`)) || action.action;
            
            const priorityLabel = {
                'high': 'Urgent',
                'medium': 'Recommandé',
                'low': 'Optionnel'
            }[action.priority] || action.priority;
            
            const actionId = `action-${index}-${actionIndex}`;
            
            html += `
                <div class="preventive-action-item priority-${action.priority}" id="${actionId}">
                    <div class="preventive-action-header" onclick="toggleAction('${actionId}')">
                        <span class="preventive-action-device">${deviceName}</span>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span class="preventive-action-priority">${priorityLabel}</span>
                            <span class="preventive-action-toggle">▼</span>
                        </div>
                    </div>
                    <div class="preventive-action-details">
                        <div class="preventive-action-verb">${actionVerb}</div>
                        <div class="preventive-action-reason">${action.reason}</div>
                        <div class="preventive-action-values">
                            <div>
                                <span class="preventive-value-label">${action.parameter}:</span>
                            </div>
                            <div class="preventive-value-change">
                                <span>${action.current_value} ${action.unit}</span>
                                <span class="preventive-value-arrow">→</span>
                                <span>${action.predicted_value} ${action.unit}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

/**
 * Toggle l'état d'une carte de pièce (expand/collapse)
 */
function toggleRoomCard(index) {
    const card = document.getElementById(`room-card-${index}`);
    if (card) {
        card.classList.toggle('expanded');
    }
}

/**
 * Toggle l'état d'une action individuelle (expand/collapse)
 */
function toggleAction(actionId) {
    const clickedAction = document.getElementById(actionId);
    if (!clickedAction) return;
    
    const isExpanding = !clickedAction.classList.contains('expanded');
    
    // Fermer toutes les autres actions dans la même carte
    const card = clickedAction.closest('.preventive-room-card');
    if (card && isExpanding) {
        const allActions = card.querySelectorAll('.preventive-action-item.expanded');
        allActions.forEach(action => {
            if (action.id !== actionId) {
                action.classList.remove('expanded');
            }
        });
    }
    
    // Toggle l'action cliquée
    clickedAction.classList.toggle('expanded');
}

// Rendre les fonctions accessibles globalement
window.toggleRoomCard = toggleRoomCard;
window.toggleAction = toggleAction;

// Initialiser au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    try {
        fetchAndDisplayGlobalPreventiveActions();
        // Rafraîchir toutes les minutes
        setInterval(fetchAndDisplayGlobalPreventiveActions, 60000);
    } catch (e) {
        console.error('[preventive-global] Error in DOMContentLoaded:', e);
    }
});

// Rafraîchir lors du changement de langue
window.addEventListener('language-changed', () => {
    try {
        const cached = sessionStorage.getItem('globalPreventiveActions');
        if (cached) {
            const cachedData = JSON.parse(cached);
            displayGlobalPreventiveActions(cachedData);
        }
    } catch (e) {
        console.error('[preventive-global] Error on language-changed:', e);
    }
});
