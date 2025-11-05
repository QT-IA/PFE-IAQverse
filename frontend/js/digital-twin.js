/**
 * Script spécifique pour la page Digital Twin
 */

/**
 * Affiche les détails d'une alerte
 * @param {string} sujet - Le sujet de l'alerte
 */
function showDetails(sujet) {
    const panel = document.getElementById("details-panel");
    const list = document.getElementById("details-list");
    
    if (!panel || !list) return;
    
    panel.classList.remove("hidden");
    list.innerHTML = "";

    switch(sujet) {
        case "Fenêtre":
            list.innerHTML = `
                <li>Taux anormal de CO₂ au niveau de la fenêtre</li>
                <li>Forte concentration de PM2.5</li>
            `;
            break;
        case "Tableau":
            list.innerHTML = `<li>Légère accumulation de poussière détectée</li>`;
            break;
        case "Sol":
            list.innerHTML = `<li>Sol propre, aucune alerte détectée</li>`;
            break;
        default:
            list.innerHTML = `<li>Aucun détail disponible</li>`;
    }
}

/**
 * Gestion de la modale d'info
 */
function openModal() {
    ModalManager.open('infoModal');
}

function closeModal() {
    ModalManager.close('infoModal');
}

// Écouter les changements de pièce pour charger le modèle 3D
document.addEventListener('roomChanged', (event) => {
    const { roomId } = event.detail;
    if (typeof window.loadPieceModel === 'function') {
        window.loadPieceModel(roomId);
    }
});

// Export des fonctions
window.openModal = openModal;
window.closeModal = closeModal;
window.showDetails = showDetails;
