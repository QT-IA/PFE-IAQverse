(function() {
    let lastNotificationTime = null;

    async function checkNotifications() {
        try {
            const response = await fetch('/api/notifications/latest');
            if (response.ok) {
                const notif = await response.json();
                // Si une notif existe et qu'elle est nouvelle (ou qu'on vient de charger la page et qu'elle est récente)
                if (notif && notif.timestamp) {
                    // On vérifie si c'est une nouvelle notif par rapport à ce qu'on a déjà vu
                    // Pour le premier chargement, on peut choisir de ne pas l'afficher si elle est trop vieille
                    // Ici on affiche simplement si le timestamp change en direct
                    
                    if (lastNotificationTime !== null && notif.timestamp !== lastNotificationTime) {
                            showNotificationModal(notif);
                    }
                    
                    // Initialisation du timestamp au premier passage
                    if (lastNotificationTime === null) {
                        // Optionnel: Ne pas afficher au chargement de la page pour ne pas spammer
                        // Ou afficher si < 1 minute ?
                        const notifDate = new Date(notif.timestamp);
                        const now = new Date();
                        // Si la notif a moins de 1 minute, on l'affiche au chargement
                        if ((now - notifDate) < 60000) { 
                            showNotificationModal(notif);
                        }
                    }

                    lastNotificationTime = notif.timestamp;
                }
            }
        } catch (error) {
            // Silencieux car polling fréquent
        }
    }

    function showNotificationModal(notif) {
        const modal = document.getElementById('notificationModal');
        const title = document.getElementById('notif-title');
        const message = document.getElementById('notif-message');
        
        if (modal && title && message) {
            title.textContent = notif.title || "Notification";
            message.textContent = notif.message || "";
            
            // Styliser selon le type
            const content = modal.querySelector('.modal-content');
            if (notif.type === 'syndic') {
                content.style.borderLeft = "5px solid #d9534f"; // Rouge alerte
                title.style.color = "#d9534f";
            } else {
                content.style.borderLeft = "5px solid #007bff";
                title.style.color = "#007bff";
            }

            modal.style.display = "flex"; 
        }
    }

    window.closeNotificationModal = function() {
        const modal = document.getElementById('notificationModal');
        if (modal) modal.style.display = "none";
    };

    // Démarrer après le chargement
    window.addEventListener('load', () => {
        // Premier check rapide
        checkNotifications();
        // Poll every 3 seconds
        setInterval(checkNotifications, 3000);
    });
})();
