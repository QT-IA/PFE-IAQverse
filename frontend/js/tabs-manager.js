/**
 * Gestionnaire des onglets d'enseignes et de pièces
 */

let activeEnseigne = null;
let activeRoom = null;

// Store room scores for alert highlighting: key = "enseigneId:roomId", value = score
const roomScores = new Map();

/**
 * Initialise le gestionnaire de tabs
 */
async function initTabsManager() {
    try {
        await loadConfig();
        const config = getConfig();

        if (!config || !config.lieux || !config.lieux.enseignes) {
            console.error('Pas d\'enseignes trouvées dans la configuration');
            return;
        }

        renderLocationTabs();
        
        // Restaurer l'enseigne et la pièce sauvegardées AVANT de rendre les tabs
        const savedEnseigne = localStorage.getItem('activeEnseigne');
        const savedRoom = localStorage.getItem('activeRoom');
        console.log('[tabs-manager] Restauration depuis localStorage:', { savedEnseigne, savedRoom });

        if (config.lieux.enseignes.length > 0) {
            const defaultEnseigne = savedEnseigne ||
                (config.lieux.enseignes.find(e => e.id === config.lieux.active) || config.lieux.enseignes[0]).id;

            // Définir activeRoom AVANT d'appeler switchEnseigne pour éviter l'auto-sélection de la première pièce
            const enseigne = config.lieux.enseignes.find(e => e.id === defaultEnseigne);
            if (savedRoom && enseigne?.pieces?.some(p => p.id === savedRoom)) {
                activeRoom = savedRoom;
                    console.log('[tabs-manager] activeRoom défini avant switchEnseigne:', activeRoom);
            }

                // Passer keepActiveRoom=true pour ne pas écraser activeRoom qui vient d'être restauré
                switchEnseigne(defaultEnseigne, activeRoom !== null);

            // Si savedRoom a été défini, émettre roomChanged explicitement
            if (activeRoom) {
                document.dispatchEvent(new CustomEvent('roomChanged', { 
                    detail: { roomId: activeRoom, enseigneId: defaultEnseigne } 
                }));
            }
        }
    } catch (error) {
        console.error('Erreur lors de l\'initialisation des tabs:', error);
    }
}

/**
 * Affiche les onglets des enseignes
 */
function renderLocationTabs() {
    const tabsContainer = document.getElementById('location-tabs');
    if (!tabsContainer) return;

    const config = getConfig();
    
    tabsContainer.innerHTML = config.lieux.enseignes.map(enseigne => `
        <div class="location-tab${enseigne.id === activeEnseigne ? ' active' : ''}" 
                onclick="switchEnseigne('${enseigne.id}')"
                data-id="${enseigne.id}">
            <img src="/assets/icons/building.png" alt="Enseigne">
            ${escapeHtml(enseigne.nom)}
        </div>
    `).join('');
    
    // Reapply alerts to all enseigne tabs based on stored scores
    config.lieux.enseignes.forEach(ens => {
        let enseigneHasAlert = false;
        for (const [storedKey, storedScore] of roomScores.entries()) {
            if (storedKey.startsWith(ens.id + ':') && storedScore < 70) {
                enseigneHasAlert = true;
                break;
            }
        }
        const enseigneTab = document.querySelector(`.location-tab[data-id="${ens.id}"]`);
        if (enseigneTab) {
            if (enseigneHasAlert) {
                enseigneTab.classList.add('has-alert');
            } else {
                enseigneTab.classList.remove('has-alert');
            }
        }
    });
}

/**
 * Affiche les onglets des pièces pour une enseigne
 * @param {string} enseigneId - L'ID de l'enseigne
 */
function renderRoomTabs(enseigneId) {
    console.log('[tabs-manager] renderRoomTabs:', { enseigneId, currentActiveRoom: activeRoom });
    const roomTabs = document.getElementById('room-tabs');
    if (!roomTabs) return;

    const config = getConfig();
    const enseigne = config.lieux.enseignes.find(e => e.id === enseigneId);
    
    if (!enseigne || !Array.isArray(enseigne.pieces)) {
        roomTabs.innerHTML = '<div class="room-tab">Aucune pièce</div>';
        return;
    }

    roomTabs.innerHTML = enseigne.pieces.map(piece => `
        <div class="room-tab${piece.id === activeRoom ? ' active' : ''}" 
                onclick="switchRoom('${piece.id}')"
                data-id="${piece.id}"
                data-room-id="${piece.id}">
            <img src="/assets/icons/${piece.type || 'room'}.png" alt="${piece.type || 'Pièce'}">
            ${escapeHtml(piece.nom)}
        </div>
    `).join('');

    // Reapply alerts to all room tabs based on stored scores
    enseigne.pieces.forEach(piece => {
        const pieceKey = `${enseigneId}:${piece.id}`;
        const pieceScore = roomScores.get(pieceKey);
        if (pieceScore !== undefined) {
            const roomTab = document.querySelector(`.room-tab[data-room-id="${piece.id}"]`);
            if (roomTab) {
                if (pieceScore < 70) {
                    roomTab.classList.add('has-alert');
                } else {
                    roomTab.classList.remove('has-alert');
                }
            }
        }
    });

    // Si aucune pièce n'est active, activer la première SEULEMENT si pas en cours de restauration localStorage
    if (!activeRoom && enseigne.pieces.length > 0) {
        console.log('[tabs-manager] No activeRoom, auto-selecting first piece');
        // N'auto-sélectionner que si on n'est pas en train de restaurer depuis localStorage
        // (activeRoom sera déjà défini par initTabsManager dans ce cas)
        switchRoom(enseigne.pieces[0].id);
    } else {
        console.log('[tabs-manager] activeRoom already set, skipping auto-selection');
    }
}

/**
 * Change l'enseigne active
 * @param {string} enseigneId - L'ID de l'enseigne
 * @param {boolean} keepActiveRoom - Si true, ne pas réinitialiser activeRoom (utilisé lors de la restauration depuis localStorage)
 */
function switchEnseigne(enseigneId, keepActiveRoom = false) {
    console.log('[tabs-manager] switchEnseigne:', { enseigneId, keepActiveRoom, currentActiveRoom: activeRoom });
    activeEnseigne = enseigneId;
    if (!keepActiveRoom) {
        activeRoom = null; // Réinitialiser la pièce active (sauf si on restaure depuis localStorage)
    }
    localStorage.setItem('activeEnseigne', enseigneId);
    console.log('[tabs-manager] After switchEnseigne, activeRoom:', activeRoom);
    
    // Mettre à jour l'apparence des onglets d'enseignes
    document.querySelectorAll('.location-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.id === enseigneId);
    });

    // Mettre à jour les onglets des pièces pour l'enseigne sélectionnée
    renderRoomTabs(enseigneId);

    // Émettre un événement personnalisé pour notifier le changement
    document.dispatchEvent(new CustomEvent('enseigneChanged', { 
        detail: { enseigneId } 
    }));
}

/**
 * Change la pièce active
 * @param {string} roomId - L'ID de la pièce
 */
function switchRoom(roomId) {
    activeRoom = roomId;
    localStorage.setItem('activeRoom', roomId);
    
    // Mettre à jour l'apparence des onglets
    document.querySelectorAll('.room-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.id === roomId);
    });

    // Émettre un événement personnalisé pour notifier le changement
    document.dispatchEvent(new CustomEvent('roomChanged', { 
        detail: { roomId, enseigneId: activeEnseigne } 
    }));
}

/**
 * Obtient l'enseigne active
 * @returns {string} L'ID de l'enseigne active
 */
function getActiveEnseigne() {
    return activeEnseigne;
}

/**
 * Obtient la pièce active
 * @returns {string} L'ID de la pièce active
 */
function getActiveRoom() {
    return activeRoom;
}

// Initialiser au chargement de la page
document.addEventListener('DOMContentLoaded', initTabsManager);

// Export des fonctions
window.switchEnseigne = switchEnseigne;
window.switchRoom = switchRoom;
window.getActiveEnseigne = getActiveEnseigne;
window.getActiveRoom = getActiveRoom;
window.renderLocationTabs = renderLocationTabs;
window.renderRoomTabs = renderRoomTabs;

/**
 * Background monitoring service for all rooms
 * Fetches data and calculates scores for all rooms periodically
 */
let monitoringInterval = null;

async function fetchRoomScore(enseigneNom, roomNom) {
    try {
        const url = `http://localhost:8000/api/iaq/measurements?enseigne=${encodeURIComponent(enseigneNom)}&salle=${encodeURIComponent(roomNom)}&hours=1`;
        console.log(`[tabs-manager] Fetching score for ${enseigneNom}:${roomNom} from ${url}`);
        
        const response = await fetch(url);
        if (!response.ok) {
            console.warn(`[tabs-manager] HTTP ${response.status} for ${enseigneNom}:${roomNom}`);
            return null;
        }
        
        const data = await response.json();
        console.log(`[tabs-manager] Received ${data?.length || 0} data points for ${enseigneNom}:${roomNom}`);
        
        if (!Array.isArray(data) || data.length === 0) {
            console.warn(`[tabs-manager] No data for ${enseigneNom}:${roomNom}`);
            return null;
        }
        
        const latest = data[data.length - 1];
        console.log(`[tabs-manager] Latest data for ${enseigneNom}:${roomNom}:`, latest);
        
        // Utiliser global_score de l'API backend
        if (typeof latest.global_score === 'number') {
            console.log(`[tabs-manager] ✅ Score from API for ${enseigneNom}:${roomNom}: ${latest.global_score}`);
            return latest.global_score;
        } else {
            console.warn(`[tabs-manager] ⚠️ No global_score in API response for ${enseigneNom}:${roomNom}`);
            console.warn(`[tabs-manager] Available data:`, Object.keys(latest));
            // Retourner null pour éviter de bloquer le monitoring, mais logger clairement le problème
            return null;
        }
    } catch (error) {
        console.error(`[tabs-manager] ❌ Error fetching score for ${enseigneNom}:${roomNom}:`, error);
    }
    return null;
}

async function updateAllRoomScores() {
    const config = getConfig();
    if (!config || !config.lieux || !config.lieux.enseignes) return;
    
    console.log('[tabs-manager] Updating scores for all rooms...');
    
    // Fetch scores for ALL rooms in parallel (including active one to ensure consistency)
    const promises = [];
    config.lieux.enseignes.forEach(enseigne => {
        if (Array.isArray(enseigne.pieces)) {
            enseigne.pieces.forEach(piece => {
                promises.push(
                    fetchRoomScore(enseigne.nom, piece.nom).then(score => ({
                        enseigneId: enseigne.id,
                        roomId: piece.id,
                        score
                    }))
                );
            });
        }
    });
    
    const results = await Promise.all(promises);
    
    // Update scores and tab alerts
    let scoresUpdated = 0;
    results.forEach(({ enseigneId, roomId, score }) => {
        if (score !== null) {
            const key = `${enseigneId}:${roomId}`;
            const oldScore = roomScores.get(key);
            if (oldScore !== score) {
                console.log(`[tabs-manager] Score changed for ${key}: ${oldScore} -> ${score}`);
            }
            roomScores.set(key, score);
            scoresUpdated++;
        }
    });
    
    console.log(`[tabs-manager] Updated ${scoresUpdated} room scores, total stored: ${roomScores.size}`);
    
    // Always refresh UI to ensure consistency
    refreshAllTabAlerts();
}

function refreshAllTabAlerts() {
    const config = getConfig();
    if (!config || !config.lieux || !config.lieux.enseignes) return;
    
    console.log('[tabs-manager] Refreshing all tab alerts with scores:', Array.from(roomScores.entries()));
    
    // Update ALL room tabs that exist in the DOM (not just for active enseigne)
    document.querySelectorAll('.room-tab[data-room-id]').forEach(roomTab => {
        const roomId = roomTab.getAttribute('data-room-id');
        // Find which enseigne this room belongs to by checking all enseignes
        let roomScore = null;
        for (const [key, score] of roomScores.entries()) {
            if (key.endsWith(':' + roomId)) {
                roomScore = score;
                break;
            }
        }
        
        if (roomScore !== null && roomScore !== undefined) {
            if (roomScore < 70) {
                roomTab.classList.add('has-alert');
                console.log(`[tabs-manager] Added alert to room tab ${roomId}, score: ${roomScore}`);
            } else {
                roomTab.classList.remove('has-alert');
                console.log(`[tabs-manager] Removed alert from room tab ${roomId}, score: ${roomScore}`);
            }
        }
    });
    
    // Update all enseigne tabs
    config.lieux.enseignes.forEach(ens => {
        let enseigneHasAlert = false;
        for (const [storedKey, storedScore] of roomScores.entries()) {
            if (storedKey.startsWith(ens.id + ':') && storedScore < 70) {
                enseigneHasAlert = true;
                break;
            }
        }
        const enseigneTab = document.querySelector(`.location-tab[data-id="${ens.id}"]`);
        if (enseigneTab) {
            if (enseigneHasAlert) {
                enseigneTab.classList.add('has-alert');
                console.log(`[tabs-manager] Added alert to enseigne tab ${ens.id}`);
            } else {
                enseigneTab.classList.remove('has-alert');
                console.log(`[tabs-manager] Removed alert from enseigne tab ${ens.id}`);
            }
        }
    });
}

function startBackgroundMonitoring() {
    if (monitoringInterval) return; // Already running
    
    console.log('[tabs-manager] Starting background monitoring service');
    
    // Initial update
    updateAllRoomScores();
    
    // Update every 5 seconds (same frequency as charts.js updates)
    monitoringInterval = setInterval(updateAllRoomScores, 5000);
}

function stopBackgroundMonitoring() {
    if (monitoringInterval) {
        clearInterval(monitoringInterval);
        monitoringInterval = null;
        console.log('[tabs-manager] Stopped background monitoring service');
    }
}

// Start monitoring after initialization
document.addEventListener('DOMContentLoaded', () => {
    // Start monitoring as soon as tabs are initialized
    setTimeout(startBackgroundMonitoring, 500);
});

// Stop monitoring when page is hidden/unloaded
if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopBackgroundMonitoring();
        } else {
            startBackgroundMonitoring();
        }
    });
}

window.startBackgroundMonitoring = startBackgroundMonitoring;
window.stopBackgroundMonitoring = stopBackgroundMonitoring;

/**
 * Updates tab alert styling based on room score
 * @param {number} score - The room IAQ score (0-100)
 */
window.updateTabAlerts = function(score) {
    if (!activeEnseigne || !activeRoom) return;
    
    const key = `${activeEnseigne}:${activeRoom}`;
    roomScores.set(key, score);
    
    // Refresh all tab alerts (will be updated by background service too)
    if (typeof refreshAllTabAlerts === 'function') {
        refreshAllTabAlerts();
    }
};
