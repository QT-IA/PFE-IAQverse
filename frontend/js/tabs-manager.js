/**
 * Gestionnaire des onglets d'enseignes et de pièces
 */

let activeEnseigne = null;
let activeRoom = null;

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
