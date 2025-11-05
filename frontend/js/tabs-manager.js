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
        
        // Activer la première enseigne par défaut ou l'ancienne sélectionnée
        const savedEnseigne = localStorage.getItem('activeEnseigne');
        const savedRoom = localStorage.getItem('activeRoom');

        if (config.lieux.enseignes.length > 0) {
            const defaultEnseigne = savedEnseigne ||
                (config.lieux.enseignes.find(e => e.id === config.lieux.active) || config.lieux.enseignes[0]).id;

            switchEnseigne(defaultEnseigne);

            if (savedRoom) {
                const enseigne = config.lieux.enseignes.find(e => e.id === defaultEnseigne);
                if (enseigne?.pieces?.some(p => p.id === savedRoom)) {
                    switchRoom(savedRoom);
                }
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
             data-id="${piece.id}">
            <img src="/assets/icons/${piece.type || 'room'}.png" alt="${piece.type || 'Pièce'}">
            ${escapeHtml(piece.nom)}
        </div>
    `).join('');

    // Si aucune pièce n'est active, activer la première
    if (!activeRoom && enseigne.pieces.length > 0) {
        switchRoom(enseigne.pieces[0].id);
    }
}

/**
 * Change l'enseigne active
 * @param {string} enseigneId - L'ID de l'enseigne
 */
function switchEnseigne(enseigneId) {
    activeEnseigne = enseigneId;
    activeRoom = null; // Réinitialiser la pièce active
    localStorage.setItem('activeEnseigne', enseigneId);
    
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
