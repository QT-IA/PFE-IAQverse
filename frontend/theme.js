/**
 * Gestion du mode sombre/clair pour IAQverse
 * Synchronisé avec la configuration (affichage.mode)
 */

// Fonction pour appliquer le thème
function applyTheme(mode) {
    const theme = mode === 'sombre' || mode === 'Sombre' ? 'sombre' : 'clair';
    
    // Appliquer l'attribut data-theme sur l'élément html
    document.documentElement.setAttribute('data-theme', theme);
    
    // Sauvegarder en localStorage pour persistance entre les pages
    localStorage.setItem('theme', theme);
    
    console.log(`Thème appliqué: ${theme}`);
}

// Fonction pour initialiser le thème au chargement de la page
function initTheme() {
    // 1. Essayer de récupérer depuis localStorage
    let savedTheme = localStorage.getItem('theme');
    
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        return;
    }
    
    // 2. Si pas de thème sauvegardé, essayer de charger depuis la config
    fetch('http://localhost:8000/config')
        .then(response => response.json())
        .then(config => {
            const mode = config?.affichage?.mode || 'clair';
            applyTheme(mode);
        })
        .catch(error => {
            console.log('Impossible de charger le thème depuis la config, utilisation du mode clair par défaut');
            applyTheme('clair');
        });
}

// Fonction pour changer le thème (appelée par le toggle)
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'clair';
    const newTheme = currentTheme === 'clair' ? 'sombre' : 'clair';
    applyTheme(newTheme);
    
    // Mettre à jour la configuration sur le serveur
    updateThemeInConfig(newTheme);
    
    // Rafraîchir les graphiques si la fonction existe (pages avec charts.js)
    if (typeof refreshChartsTheme === 'function') {
        refreshChartsTheme();
    }
}

// Mettre à jour le thème dans la configuration serveur
async function updateThemeInConfig(theme) {
    try {
        const response = await fetch('http://localhost:8000/api/saveConfig', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                affichage: {
                    mode: theme === 'sombre' ? 'Sombre' : 'Clair'
                }
            })
        });
        
        if (response.ok) {
            console.log('Thème sauvegardé dans la configuration');
        }
    } catch (error) {
        console.error('Erreur lors de la sauvegarde du thème:', error);
    }
}

// Observer les changements de la configuration pour synchroniser le thème
function observeConfigChanges() {
    // Cette fonction peut être appelée par settings.html après le chargement de la config
    if (typeof config !== 'undefined' && config?.affichage?.mode) {
        applyTheme(config.affichage.mode);
    }
}

// Initialiser le thème dès que possible (avant le chargement complet)
initTheme();

// Réinitialiser après le chargement complet de la page
document.addEventListener('DOMContentLoaded', initTheme);

// Exporter les fonctions pour utilisation globale
window.applyTheme = applyTheme;
window.toggleTheme = toggleTheme;
window.observeConfigChanges = observeConfigChanges;
