/**
 * Utilitaires communs pour IAQverse
 */

/**
 * Échappe les caractères HTML pour éviter les injections XSS
 * @param {string} s - La chaîne à échapper
 * @returns {string} La chaîne échappée
 */
function escapeHtml(s) {
    if (s === undefined || s === null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * Affiche une notification à l'utilisateur
 * @param {string} message - Le message à afficher
 * @param {boolean} isError - Si true, affiche une notification d'erreur
 */
function showNotification(message, isError = false) {
    const notification = document.getElementById('notification');
    if (!notification) return;

    notification.textContent = message;
    notification.className = 'notification ' + (isError ? 'error' : 'success');
    notification.style.display = 'block';

    setTimeout(() => {
        notification.style.display = 'none';
    }, 3000);
}

/**
 * Gestion des modales
 */
const ModalManager = {
    /**
     * Ouvre une modale
     * @param {string} modalId - L'ID de la modale
     */
    open(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'flex';
        }
    },

    /**
     * Ferme une modale
     * @param {string} modalId - L'ID de la modale
     */
    close(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    },

    /**
     * Initialise la fermeture des modales au clic sur l'overlay
     */
    initClickOutside() {
        window.addEventListener('click', function(event) {
            if (event.target.classList.contains('modal')) {
                event.target.style.display = 'none';
            }
        });
    }
};

/**
 * Initialisation des gestionnaires de modales au chargement
 */
document.addEventListener('DOMContentLoaded', () => {
    ModalManager.initClickOutside();

    // Ajouter les gestionnaires pour les boutons close
    document.querySelectorAll('.close').forEach(btn => {
        btn.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                modal.style.display = 'none';
            }
        });
    });
});

// Export des fonctions
window.escapeHtml = escapeHtml;
window.showNotification = showNotification;
window.ModalManager = ModalManager;
