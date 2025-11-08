/* Alerts Engine: evaluates IAQ data against thresholds and toggles alert-points visibility/severity */
(function (window) {
    const REFRESH_MS = 5000; // polling frequency
    const API_URL_WINDOW = "http://localhost:8000/iaq/window";
    // mémorise la dernière sévérité notifiée pour éviter le spam
    let lastNotified = { temp: null, hum: null };

    // Severity helpers
    const weights = { info: 0, warning: 1, danger: 2 };
    const maxSeverity = (a, b) => (weights[a] >= weights[b] ? a : b);

    // Threshold evaluators
    function evalCO2(co2) {
        if (co2 == null || isNaN(co2)) return null;
        if (co2 >= 1200) return "danger";
        if (co2 >= 800) return "warning";
        return "info";
    }
    function evalPM25(pm) {
        if (pm == null || isNaN(pm)) return null;
        if (pm >= 35) return "danger"; // OMS 2021 jour
        if (pm >= 5) return "warning"; // OMS 2021 annuel
        return "info";
    }
    function evalTVOC(tvoc) {
        if (tvoc == null || isNaN(tvoc)) return null;
        if (tvoc > 1000) return "danger";
        if (tvoc >= 300) return "warning"; // <200 très bon
        return "info";
    }
    function evalTemp(t) {
        if (t == null || isNaN(t)) return null;
        if (t < 16 || t > 28) return "danger"; // zones OMS extrêmes
        if ((t >= 16 && t < 18) || (t > 22 && t <= 24) || (t > 24 && t <= 28)) return "warning"; // bandes intermédiaires / inconfort léger
        if (t >= 18 && t <= 22) return "info";
        return null;
    }
    function evalHum(h) {
        if (h == null || isNaN(h)) return null;
        if (h < 20 || h > 80) return "danger";
        if ((h >= 20 && h < 30) || (h > 60 && h <= 70) || (h > 70 && h <= 80)) return "warning";
        if (h >= 40 && h <= 60) return "info";
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

    function applyAlertPointsActivation(map) {
        // Deactivate all by default
        document.querySelectorAll(".alert-point").forEach((el) => {
            el.setAttribute("data-active", "false");
            el.removeAttribute("data-severity");
        });
        // Activate mapped ones
        Object.keys(map || {}).forEach((key) => {
            const sev = map[key];
            const el = document.querySelector(`.alert-point[data-i18n-key="${key}"]`);
            if (el) {
                el.setAttribute("data-active", "true");
                el.setAttribute("data-severity", sev);
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
                applyAlertPointsActivation({});
                return;
            }
            data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            const last = data[data.length - 1];
            const map = deriveAlertPointSeverities(last || {});
            applyAlertPointsActivation(map);
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
