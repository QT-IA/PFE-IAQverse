/* Alerts Engine: evaluates IAQ data against thresholds and toggles alert-points visibility/severity */
(function (window) {
    const REFRESH_MS = 5000; // polling frequency
    const API_URL_WINDOW = "http://localhost:8000/iaq/window";
    // Centralise all thresholds here to avoid magic numbers
    const THRESHOLDS = {
        CO2: { WARNING: 800, DANGER: 1200 },
        PM25: { WARNING: 5, WARNING_MED: 15, DANGER: 35 }, // keep 5 for conservative warn, 15 used in actions, 35 danger
        TVOC: { WARNING: 300, DANGER: 1000 },
        TEMP: {
            INFO_MIN: 18, INFO_MAX: 22,
            WARN_LOW_START: 16, WARN_LOW_END: 18,
            WARN_MID_START: 22, WARN_MID_END: 24,
            WARN_HIGH_START: 24, WARN_HIGH_END: 28,
            DANGER_LOW: 16, DANGER_HIGH: 28,
            ACTION_COLD: 18, ACTION_HOT: 24
        },
        HUM: {
            INFO_MIN: 40, INFO_MAX: 60,
            WARN_LOW_MIN: 20, WARN_LOW_MAX: 30,
            WARN_HIGH_MIN: 70, WARN_HIGH_MAX: 80,
            DANGER_LOW: 20, DANGER_HIGH: 80,
            ACTION_TOO_DRY: 30, ACTION_TOO_HUMID: 60, ACTION_OPEN_THRESHOLD: 70
        }
    };
    // mémorise la dernière sévérité notifiée pour éviter le spam
    let lastNotified = { temp: null, hum: null };

    // Severity helpers
    const weights = { info: 0, warning: 1, danger: 2 };
    const maxSeverity = (a, b) => (weights[a] >= weights[b] ? a : b);

    // Threshold evaluators
    function evalCO2(co2) {
        if (co2 == null || isNaN(co2)) return null;
        if (co2 >= THRESHOLDS.CO2.DANGER) return "danger";
        if (co2 >= THRESHOLDS.CO2.WARNING) return "warning";
        return "info";
    }
    function evalPM25(pm) {
        if (pm == null || isNaN(pm)) return null;
        if (pm >= THRESHOLDS.PM25.DANGER) return "danger"; // OMS 2021 jour
        if (pm >= THRESHOLDS.PM25.WARNING) return "warning"; // conservative warn
        return "info";
    }
    function evalTVOC(tvoc) {
        if (tvoc == null || isNaN(tvoc)) return null;
        if (tvoc > THRESHOLDS.TVOC.DANGER) return "danger";
        if (tvoc >= THRESHOLDS.TVOC.WARNING) return "warning"; // <200 très bon
        return "info";
    }
    function evalTemp(t) {
        if (t == null || isNaN(t)) return null;
        if (t < THRESHOLDS.TEMP.DANGER_LOW || t > THRESHOLDS.TEMP.DANGER_HIGH) return "danger"; // zones OMS extrêmes
        if ((t >= THRESHOLDS.TEMP.WARN_LOW_START && t < THRESHOLDS.TEMP.WARN_LOW_END)
            || (t > THRESHOLDS.TEMP.WARN_MID_START && t <= THRESHOLDS.TEMP.WARN_MID_END)
            || (t > THRESHOLDS.TEMP.WARN_HIGH_START && t <= THRESHOLDS.TEMP.WARN_HIGH_END)) return "warning"; // bandes intermédiaires / inconfort léger
        if (t >= THRESHOLDS.TEMP.INFO_MIN && t <= THRESHOLDS.TEMP.INFO_MAX) return "info";
        return null;
    }
    function evalHum(h) {
        if (h == null || isNaN(h)) return null;
        if (h < THRESHOLDS.HUM.DANGER_LOW || h > THRESHOLDS.HUM.DANGER_HIGH) return "danger";
        if ((h >= THRESHOLDS.HUM.WARN_LOW_MIN && h < THRESHOLDS.HUM.WARN_LOW_MAX)
            || (h > THRESHOLDS.HUM.INFO_MAX && h <= THRESHOLDS.HUM.WARN_HIGH_MIN)
            || (h > THRESHOLDS.HUM.WARN_HIGH_MIN && h <= THRESHOLDS.HUM.WARN_HIGH_MAX)) return "warning";
        if (h >= THRESHOLDS.HUM.INFO_MIN && h <= THRESHOLDS.HUM.INFO_MAX) return "info";
        return null;
    }

    // Map pollutant severities to alert-point keys
    function deriveAlertPointSeverities(last) {
        const out = {}; // key -> severity
        const push = (key, sev) => {
            if (!sev) return;
            if (!out[key]) out[key] = sev;
            else out[key] = maxSeverity(out[key], sev);
        };
    const sCO2 = evalCO2(Number(last.co2));
    const sPM = evalPM25(Number(last.pm25));
    const sTVOC = evalTVOC(Number(last.tvoc));
    const sTemp = evalTemp(Number(last.temperature));
    const sHum = evalHum(Number(last.humidity));
        // CO2: ventil + window (and door as secondary) when warning/danger
        if (sCO2 && sCO2 !== "info") {
            push("ventilation", sCO2);
            push("window", sCO2);
            push("door", sCO2);
        }
        // PM2.5: ventil
        if (sPM && sPM !== "info") {
            push("window", sPM);
            push("ventilation", sPM);
        }
        // TVOC: ventil
        if (sTVOC && sTVOC !== "info") {
            push("ventilation", sTVOC);
        }
        // Température: radiator (chauffage) & window (aération) selon extrêmes
        if (sTemp && sTemp !== 'info') {
            push('radiator', sTemp);
            push('window', sTemp);
        }
        // Humidité: ventilation & window (aérer ou déshumidifier) hors plage de confort
        if (sHum && sHum !== 'info') {
            push('ventilation', sHum);
            push('radiator', sHum);
            push('window', sHum);
        }
        return out;
    }

    function applyAlertPointsActivation(map, actionsMap) {
        // Deactivate all by default
        document.querySelectorAll(".alert-point").forEach((el) => {
            el.setAttribute("data-active", "false");
            el.removeAttribute("data-severity");
            el.removeAttribute("data-action-key");
        });
        // Activate mapped ones
        Object.keys(map || {}).forEach((key) => {
            const sev = map[key];
            const el = document.querySelector(`.alert-point[data-i18n-key="${key}"]`);
            if (el) {
                el.setAttribute("data-active", "true");
                el.setAttribute("data-severity", sev);
                if (actionsMap && actionsMap[key]) {
                    el.setAttribute("data-action-key", actionsMap[key]);
                }
            }
        });
        // Sync actions table
        try {
            if (typeof window.syncAlertPointsToTable === "function")
                window.syncAlertPointsToTable();
        } catch (e) { }
    }

    // Track active enseigne/salle
    let activeEnseigneName = null;
    let activeRoomName = null;
    function initActiveContext() {
        try {
            const cfg =
                typeof window.getConfig === "function"
                    ? window.getConfig()
                    : window.config || null;
            const activeId =
                typeof window.getActiveEnseigne === "function"
                    ? window.getActiveEnseigne()
                    : cfg && cfg.lieux && cfg.lieux.active;
            const ens =
                cfg && cfg.lieux && Array.isArray(cfg.lieux.enseignes)
                    ? cfg.lieux.enseignes.find((e) => e.id === activeId)
                    : null;
            activeEnseigneName = ens ? ens.nom || ens.id : null;
            // room: try selected tab with data-room-id carrying the piece object name; fallback to first piece name
            const tab = document.querySelector(".room-tabs .tab.active");
            activeRoomName =
                (tab &&
                    (tab.getAttribute("data-room-name") || tab.textContent.trim())) ||
                (ens && ens.pieces && ens.pieces[0] && ens.pieces[0].nom) ||
                null;
        } catch (e) { }
    }
    window.addEventListener("roomChanged", (ev) => {
        try {
            const cfg =
                typeof window.getConfig === "function"
                    ? window.getConfig()
                    : window.config || null;
            const activeId =
                typeof window.getActiveEnseigne === "function"
                    ? window.getActiveEnseigne()
                    : cfg && cfg.lieux && cfg.lieux.active;
            const ens =
                cfg && cfg.lieux && Array.isArray(cfg.lieux.enseignes)
                    ? cfg.lieux.enseignes.find((e) => e.id === activeId)
                    : null;
            const piece =
                ens && ens.pieces
                    ? ens.pieces.find((p) => p.id === ev.detail.roomId)
                    : null;
            activeEnseigneName = ens ? ens.nom || ens.id : activeEnseigneName;
            activeRoomName = piece ? piece.nom || piece.id : activeRoomName;
        } catch (e) { }
    });

    async function fetchLatestIAQ() {
        try {
            if (!activeEnseigneName || !activeRoomName) initActiveContext();
            const params = new URLSearchParams({
                enseigne: activeEnseigneName || "",
                salle: activeRoomName || "",
                hours: "1",
                step: "5min",
            });
            const url = `${API_URL_WINDOW}?${params.toString()}`;
            const res = await fetch(url, { cache: "no-store" });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (!Array.isArray(data) || data.length === 0) {
                applyAlertPointsActivation({}, {});
                return;
            }
            data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            const last = data[data.length - 1];
            const map = deriveAlertPointSeverities(last || {});
            // Build recommended actions per alert-point key
            const suggestActionFor = (key, sev, last) => {
                const t = Number(last.temperature);
                const h = Number(last.humidity);
                const co2 = Number(last.co2);
                const pm = Number(last.pm25);
                const tvoc = Number(last.tvoc);
                // defaults by device
                switch (key) {
                    case 'window':
                        // CO2 élevé => ouvrir; PM2.5 élevé sans CO2 => fermer; humidité élevée => ouvrir; humidité basse => fermer; trop chaud => ouvrir; trop froid => fermer
                        if (!isNaN(pm) && pm >= THRESHOLDS.PM25.DANGER && (isNaN(co2) || co2 < THRESHOLDS.CO2.WARNING)) return 'close';
                        if (!isNaN(h) && h < THRESHOLDS.HUM.ACTION_TOO_DRY) return 'close';
                        if (!isNaN(t) && t < THRESHOLDS.TEMP.ACTION_COLD) return 'close';
                        return 'open';
                    case 'door':
                        // CO2 élevé => ouvrir; sinon fermer par défaut
                        if (!isNaN(co2) && co2 >= THRESHOLDS.CO2.WARNING) return 'open';
                        return 'close';
                    case 'ventilation':
                        // CO2/TVOC/PM élevés ou humidité élevée => allumer/augmenter; humidité trop basse => réduire/éteindre
                        if ((!isNaN(co2) && co2 >= THRESHOLDS.CO2.WARNING)
                            || (!isNaN(tvoc) && tvoc >= THRESHOLDS.TVOC.WARNING)
                            || (!isNaN(pm) && pm >= THRESHOLDS.PM25.WARNING_MED)
                            || (!isNaN(h) && h > THRESHOLDS.HUM.ACTION_TOO_HUMID)) return 'turn_on';
                        if (!isNaN(h) && h < THRESHOLDS.HUM.ACTION_TOO_DRY) return 'turn_off';
                        return 'turn_on';
                    case 'radiator':
                        // Trop froid => augmenter; trop chaud => diminuer
                        if (!isNaN(t) && t < THRESHOLDS.TEMP.ACTION_COLD) return 'increase';
                        if (!isNaN(t) && t > THRESHOLDS.TEMP.ACTION_HOT) return 'decrease';
                        return 'decrease';
                    case 'temperature':
                        if (!isNaN(t) && t < THRESHOLDS.TEMP.ACTION_COLD) return 'increase';
                        if (!isNaN(t) && t > THRESHOLDS.TEMP.ACTION_HOT) return 'decrease';
                        return 'decrease';
                    case 'humidity':
                        if (!isNaN(h) && h < THRESHOLDS.HUM.ACTION_TOO_DRY) return 'close'; // fermer fenêtres pour conserver l'humidité
                        if (!isNaN(h) && h > THRESHOLDS.HUM.ACTION_OPEN_THRESHOLD) return 'open';
                        return 'open';
                    default:
                        return 'turn_on';
                }
            };
            const actionsMap = {};
            Object.keys(map).forEach((key) => { actionsMap[key] = suggestActionFor(key, map[key], last); });
            applyAlertPointsActivation(map, actionsMap);
            // Notifications push locales (UI) pour danger (et warning optionnel)
            try {
                const t = (window.i18n && window.i18n.t) ? window.i18n.t : (k=>k);
                const notify = (sev, label, value) => {
                    if (typeof window.showNotification !== 'function') return;
                    const keyBase = sev === 'danger' ? 'notifications.alert.danger' : 'notifications.alert.warning';
                    // Fallback si clé absente
                    const sevTxt = sev === 'danger' ? (t('severity.danger') || 'Danger') : (t('severity.warning') || 'Avertissement');
                    const msg = `${sevTxt}: ${label} = ${value}`;
                    window.showNotification(msg, sev === 'danger');
                };
                const tempSev = evalTemp(Number(last.temperature));
                const humSev = evalHum(Number(last.humidity));
                if ((tempSev === 'danger' || tempSev === 'warning') && tempSev !== lastNotified.temp) {
                    notify(tempSev, t('digitalTwin.sample.temperature') || 'Température', last.temperature);
                    lastNotified.temp = tempSev;
                }
                if ((humSev === 'danger' || humSev === 'warning') && humSev !== lastNotified.hum) {
                    notify(humSev, t('digitalTwin.sample.humidity') || 'Humidité', last.humidity);
                    lastNotified.hum = humSev;
                }
            } catch(e) {}
        } catch (e) {
            // on error, do not modify current activation state
            // console.warn('alerts-engine fetch error', e);
        }
    }

    function start() {
        // Initialiser tous les alert-points à masqué par défaut
        document.querySelectorAll(".alert-point").forEach((el) => {
            el.setAttribute("data-active", "false");
        });
        initActiveContext();
        fetchLatestIAQ();
        setInterval(fetchLatestIAQ, REFRESH_MS);
    }

    if (typeof window !== "undefined") {
        document.addEventListener("DOMContentLoaded", start);
    }
})(window);
