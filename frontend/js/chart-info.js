/**
 * Gestion des informations contextuelles sur les graphiques
 */

function getParamInfo(paramKey) {
    // Helper pour traduire
    const t = (key) => (window.i18n && window.i18n.t) ? window.i18n.t(key) : key;

    const data = {
        "co2": {
            title: t("modal_info.co2.title"),
            desc: t("modal_info.co2.desc"),
            thresholds: [
                { label: t("modal_info.thresholds.excellent"), value: "< 600 ppm", color: "#27ae60" },
                { label: t("modal_info.thresholds.medium"), value: "600 - 1000 ppm", color: "#f39c12" },
                { label: t("modal_info.thresholds.bad"), value: "> 1000 ppm", color: "#e74c3c" }
            ],
            actuators: [
                { name: t("modal_info.actuators.window")},
                { name: t("modal_info.actuators.ventilation")}
            ]
        },
        "pm25": {
            title: t("modal_info.pm25.title"),
            desc: t("modal_info.pm25.desc"),
            thresholds: [
                { label: t("modal_info.thresholds.excellent"), value: "< 10 µg/m³", color: "#27ae60" },
                { label: t("modal_info.thresholds.medium"), value: "10 - 25 µg/m³", color: "#f39c12" },
                { label: t("modal_info.thresholds.bad"), value: "> 25 µg/m³", color: "#e74c3c" }
            ],
            actuators: [
                { name: t("modal_info.actuators.window")},
                { name: t("modal_info.actuators.purifier")}
            ]
        },
        "tvoc": {
            title: t("modal_info.tvoc.title"),
            desc: t("modal_info.tvoc.desc"),
            thresholds: [
                { label: t("modal_info.thresholds.excellent"), value: "< 200 ppb", color: "#27ae60" },
                { label: t("modal_info.thresholds.medium"), value: "200 - 600 ppb", color: "#f39c12" },
                { label: t("modal_info.thresholds.bad"), value: "> 600 ppb", color: "#e74c3c" }
            ],
            actuators: [
                { name: t("modal_info.actuators.ventilation") },
                { name: t("modal_info.actuators.window") }
            ]
        },
        "comfort": {
            title: t("modal_info.comfort.title"),
            desc: t("modal_info.comfort.desc"),
            thresholds: [
                { label: t("modal_info.thresholds.ideal_temp"), value: "19°C - 24°C", color: "#27ae60" },
                { label: t("modal_info.thresholds.ideal_hum"), value: "40% - 60%", color: "#27ae60" }
            ],
            actuators: [
                { name: t("modal_info.actuators.heating") },
                { name: t("modal_info.actuators.ac") },
                { name: t("modal_info.actuators.window") }
            ]
        }
    };
    return data[paramKey];
}

function openParamInfo(paramKey) {
    const info = getParamInfo(paramKey);
    if (!info) return;

    document.getElementById('paramInfoTitle').textContent = info.title;
    document.getElementById('paramInfoDesc').textContent = info.desc;

    // Seuils
    const ul = document.getElementById('paramInfoThresholds');
    ul.innerHTML = '';
    info.thresholds.forEach(th => {
        const li = document.createElement('li');
        li.innerHTML = `<span style="color:${th.color};font-weight:bold;">${th.label}</span> : ${th.value}`;
        ul.appendChild(li);
    });

    // Actionneurs
    const div = document.getElementById('paramInfoActuators');
    div.innerHTML = '';
    info.actuators.forEach(act => {
        const badge = document.createElement('div');
        badge.className = 'actuator-badge';
        // Utiliser une icône générique si l'image n'existe pas, ou gérer les chemins
        // Ici on suppose que les icônes sont dans assets/icons/
        badge.innerHTML = `<img src="assets/icons/${act.icon}" onerror="this.style.display='none'">${act.name}`;
        div.appendChild(badge);
    });

    const modal = document.getElementById('paramInfoModal');
    modal.style.display = 'flex';
}

function closeParamInfoModal() {
    document.getElementById('paramInfoModal').style.display = 'none';
}

// Fermer si on clique en dehors
window.onclick = function(event) {
    const modal = document.getElementById('paramInfoModal');
    if (event.target == modal) {
        modal.style.display = "none";
    }
}

// Ajouter les icônes aux graphiques au chargement
document.addEventListener('DOMContentLoaded', () => {
    const charts = {
        'co2-chart': 'co2',
        'pm25-chart': 'pm25',
        'tvoc-chart': 'tvoc',
        'comfort-chart': 'comfort'
    };

    for (const [id, key] of Object.entries(charts)) {
        const container = document.getElementById(id);
        if (container) {
            // Créer l'icône
            const icon = document.createElement('img');
            icon.src = 'assets/icons/info.png';
            icon.className = 'chart-info-icon';
            icon.onclick = (e) => {
                e.stopPropagation(); // Éviter d'interférer avec Plotly
                openParamInfo(key);
            };
            
            // Ajouter l'icône au conteneur
            // Note: Plotly utilise le conteneur, mais on peut ajouter des éléments en absolute
            // Il faut s'assurer que le conteneur a position: relative
            container.style.position = 'relative';
            container.appendChild(icon);
            
            // Observer les changements pour réinsérer l'icône si Plotly l'écrase
            // (Plotly.newPlot vide souvent le div)
            const observer = new MutationObserver((mutations) => {
                if (!container.contains(icon)) {
                    container.appendChild(icon);
                }
            });
            observer.observe(container, { childList: true });
        }
    }
});
