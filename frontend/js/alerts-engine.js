/* Alerts Engine: evaluates IAQ data against thresholds and toggles alert-points visibility/severity */
(function (window) {
    const REFRESH_MS = 5000; // polling frequency
    const API_URL_WINDOW = "http://localhost:8000/iaq/window";
    // last IAQ sample for current context
    let latestSample = null;
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
        // CO2: ventil + window (and door as secondary)
        if (sCO2) {
            push("ventilation", sCO2);
            push("window", sCO2);
            push("door", sCO2);
        }
        // PM2.5: ventil + window
        if (sPM) {
            push("window", sPM);
            push("ventilation", sPM);
        }
        // TVOC: ventil
        if (sTVOC) {
            push("ventilation", sTVOC);
        }
        // Température: radiator (chauffage) & window (aération) selon extrêmes
        if (sTemp) {
            push('radiator', sTemp);
            push('window', sTemp);
        }
        // Humidité: ventilation & window (aérer ou déshumidifier) hors plage de confort
        if (sHum) {
            push('ventilation', sHum);
            push('radiator', sHum);
            push('window', sHum);
        }
        return out;
    }

    function applyAlertPointsActivation(map, actionsMap) {
        console.log('[alerts-engine] applyAlertPointsActivation called', { map, activeEnseigneId, activeRoomId });
        
        // Récupérer tous les alert-points
        const allAlertPoints = document.querySelectorAll(".alert-point");
        console.log(`[alerts-engine] Found ${allAlertPoints.length} alert-points in DOM`);
        
        if (!activeEnseigneId || !activeRoomId) {
            console.warn('[alerts-engine] No active context, deactivating all');
            // Pas de contexte actif, désactiver tous les alert-points
            allAlertPoints.forEach((el) => {
                el.setAttribute("data-active", "false");
                el.removeAttribute("data-severity");
                el.removeAttribute("data-action-key");
            });
            try {
                if (typeof window.syncAlertPointsToTable === "function")
                    window.syncAlertPointsToTable();
            } catch (e) { }
            return;
        }
        
        let activatedCount = 0;
        // Helper: build details for a given device key based on latestSample
        function buildDetailsForKey(deviceKey) {
            const issues = [];
            if (!latestSample) return { issues, actionKey: actionsMap && actionsMap[deviceKey] };
            const last = latestSample;
            const pushIssue = (code, name, unit, sev, value, dir, threshold) => {
                if (!sev || sev === 'info') return;
                issues.push({ code, name, unit, severity: sev, value, direction: dir, threshold });
            };
            // Compute severities
            const sCO2 = evalCO2(Number(last.co2));
            const sPM = evalPM25(Number(last.pm25));
            const sTVOC = evalTVOC(Number(last.tvoc));
            const sTemp = evalTemp(Number(last.temperature));
            const sHum = evalHum(Number(last.humidity));

            const addCO2 = () => {
                if (!sCO2 || sCO2 === 'info') return; const thr = (sCO2 === 'danger') ? THRESHOLDS.CO2.DANGER : THRESHOLDS.CO2.WARNING; pushIssue('co2', 'CO₂', 'ppm', sCO2, Number(last.co2), 'high', thr);
            };
            const addPM = () => {
                if (!sPM || sPM === 'info') return; const thr = (sPM === 'danger') ? THRESHOLDS.PM25.DANGER : THRESHOLDS.PM25.WARNING; pushIssue('pm25', 'PM2.5', 'µg/m³', sPM, Number(last.pm25), 'high', thr);
            };
            const addTVOC = () => {
                if (!sTVOC || sTVOC === 'info') return; const thr = (sTVOC === 'danger') ? THRESHOLDS.TVOC.DANGER : THRESHOLDS.TVOC.WARNING; pushIssue('tvoc', 'TVOC', 'mg/m³', sTVOC, Number(last.tvoc), 'high', thr);
            };
            const addTemp = () => {
                if (!sTemp || sTemp === 'info') return; const t = Number(last.temperature);
                let dir = null, thr = null;
                if (t < THRESHOLDS.TEMP.WARN_LOW_END) { dir = 'low'; thr = THRESHOLDS.TEMP.WARN_LOW_END; }
                else if (t > THRESHOLDS.TEMP.WARN_HIGH_START) { dir = 'high'; thr = THRESHOLDS.TEMP.WARN_HIGH_START; }
                pushIssue('temperature', 'Température', '°C', sTemp, t, dir, thr);
            };
            const addHum = () => {
                if (!sHum || sHum === 'info') return; const h = Number(last.humidity);
                let dir = null, thr = null;
                if (h < THRESHOLDS.HUM.WARN_LOW_MAX) { dir = 'low'; thr = THRESHOLDS.HUM.WARN_LOW_MAX; }
                else if (h > THRESHOLDS.HUM.WARN_HIGH_MIN) { dir = 'high'; thr = THRESHOLDS.HUM.WARN_HIGH_MIN; }
                pushIssue('humidity', 'Humidité', '%', sHum, h, dir, thr);
            };

            switch (deviceKey) {
                case 'window':
                    addCO2(); addPM(); addTemp(); addHum(); break;
                case 'ventilation':
                    addCO2(); addPM(); addTVOC(); addHum(); break;
                case 'radiator':
                    addTemp(); addHum(); break;
                case 'door':
                    addCO2(); break;
                default:
                    addCO2(); addPM(); addTVOC(); addTemp(); addHum(); break;
            }
            return { issues, actionKey: actionsMap && actionsMap[deviceKey] };
        }

        // Filtrer et activer uniquement les alert-points de la pièce active
        allAlertPoints.forEach((el) => {
            const pointEnseigne = el.getAttribute('data-enseigne');
            const pointPiece = el.getAttribute('data-piece');
            const key = el.getAttribute('data-i18n-key');
            
            // Vérifier que l'alert-point appartient à la pièce active
            if (pointEnseigne !== activeEnseigneId || pointPiece !== activeRoomId) {
                el.setAttribute("data-active", "false");
                el.removeAttribute("data-severity");
                el.removeAttribute("data-action-key");
                return;
            }
            
            // Activer ou désactiver selon la map
            if (map && map[key]) {
                const severity = map[key];
                el.setAttribute("data-active", "true");
                el.setAttribute("data-severity", severity);
                if (actionsMap && actionsMap[key]) {
                    el.setAttribute("data-action-key", actionsMap[key]);
                }
                try {
                    const det = buildDetailsForKey(key);
                    el.setAttribute('data-details', JSON.stringify(det));
                } catch (e) { /* ignore JSON issues */ }
                
                // Masquer les alert-points de type "info" dans la 3D (mais garder data-active pour le tableau)
                if (severity === 'info') {
                    el.style.display = 'none';
                    console.log(`[alerts-engine] Alert ${key} is info severity - hidden in 3D but will appear in table`);
                } else {
                    el.style.display = ''; // Afficher les autres sévérités
                    activatedCount++;
                    console.log(`[alerts-engine] Activated ${key} with severity ${severity}`);
                }
            } else {
                el.setAttribute("data-active", "false");
                el.removeAttribute("data-severity");
                el.removeAttribute("data-action-key");
                el.removeAttribute("data-details");
                el.style.display = 'none';
            }
        });
        
        console.log(`[alerts-engine] Activated ${activatedCount}/${allAlertPoints.length} alert-points`);
        
        // Sync actions table
        try {
            if (typeof window.syncAlertPointsToTable === "function")
                window.syncAlertPointsToTable();
        } catch (e) { }
    }

    // Définition des alert-points par défaut (positions et cibles)
    const DEFAULT_ALERT_POINTS = [
        {
            key: 'window',
            targetNames: 'Window|Fenetre|Fenêtre|window|fenetre',
            style: 'top: 20%; left: 30%; transform: translate(-50%, -50%);'
        },
        {
            key: 'door',
            targetNames: 'Door|Porte|porte|door',
            style: 'top: 50%; left: 10%; transform: translate(-50%, -50%);'
        },
        {
            key: 'ventilation',
            targetNames: 'Ventilation|VMC|ventilation|vmc|extracteur',
            style: 'top: 10%; left: 50%; transform: translate(-50%, -50%);'
        },
        {
            key: 'radiator',
            targetNames: 'Radiator|Chauffage|radiateur|chauffage|heater',
            style: 'top: 80%; left: 20%; transform: translate(-50%, -50%);'
        }
    ];

    /**
     * Génère les alert-points pour une pièce spécifique
     */
    function renderAlertPoints(enseigneId, pieceId) {
        console.log(`[alerts-engine] renderAlertPoints called for ${enseigneId}/${pieceId}`);
        
        const container = document.getElementById('alert-points-container');
        if (!container) {
            console.error('[alerts-engine] alert-points-container not found in DOM!');
            return;
        }
        
        console.log('[alerts-engine] Container found, clearing and generating alert-points...');
        
        // Vider le conteneur
        container.innerHTML = '';
        
        // Créer les alert-points pour cette pièce
        DEFAULT_ALERT_POINTS.forEach(point => {
            const alertPoint = document.createElement('div');
            alertPoint.className = 'alert-point';
            alertPoint.setAttribute('data-i18n-key', point.key);
            alertPoint.setAttribute('data-target-names', point.targetNames);
            alertPoint.setAttribute('data-enseigne', enseigneId);
            alertPoint.setAttribute('data-piece', pieceId);
            alertPoint.setAttribute('data-active', 'false');
            alertPoint.setAttribute('style', point.style);
            container.appendChild(alertPoint);
            console.log(`[alerts-engine] Created alert-point: ${point.key}`);
        });
        
        console.log(`[alerts-engine] Successfully generated ${DEFAULT_ALERT_POINTS.length} alert-points`);
    }

    // Track active enseigne/salle
    let activeEnseigneName = null;
    let activeRoomName = null;
    let activeEnseigneId = null;
    let activeRoomId = null;
    
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
            
            activeEnseigneId = ens ? ens.id : null;
            activeEnseigneName = ens ? ens.nom || ens.id : null;
            
            // room: try selected tab with data-room-id
            const tab = document.querySelector("#room-tabs .room-tab.active");
            const roomId = tab ? tab.getAttribute("data-room-id") : null;
            const piece = ens && ens.pieces && roomId 
                ? ens.pieces.find(p => p.id === roomId)
                : (ens && ens.pieces && ens.pieces[0]);
            
            activeRoomId = piece ? piece.id : null;
            activeRoomName = piece ? piece.nom || piece.id : null;
            
            console.log(`[alerts-engine] Context: ${activeEnseigneId}/${activeRoomId} (${activeEnseigneName}/${activeRoomName})`);
        } catch (e) { 
            console.error('[alerts-engine] initActiveContext error:', e);
        }
    }
    document.addEventListener("roomChanged", (ev) => {
        console.log('[alerts-engine] roomChanged event received', ev.detail);
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
            
            activeEnseigneId = ens ? ens.id : activeEnseigneId;
            activeEnseigneName = ens ? ens.nom || ens.id : activeEnseigneName;
            activeRoomId = piece ? piece.id : activeRoomId;
            activeRoomName = piece ? piece.nom || piece.id : activeRoomName;
            
            console.log(`[alerts-engine] Room changed to ${activeEnseigneId}/${activeRoomId} (${activeEnseigneName}/${activeRoomName})`);
            
            // Régénérer les alert-points pour la nouvelle pièce
            if (activeEnseigneId && activeRoomId) {
                console.log('[alerts-engine] Regenerating alert-points for new room...');
                renderAlertPoints(activeEnseigneId, activeRoomId);
            }
            
            // Rafraîchir immédiatement les alertes
            console.log('[alerts-engine] Fetching IAQ data for new room...');
            fetchLatestIAQ();
        } catch (e) { 
            console.error('[alerts-engine] roomChanged error:', e);
        }
    });

    document.addEventListener("enseigneChanged", (ev) => {
        console.log('[alerts-engine] enseigneChanged event received', ev.detail);
        try {
            initActiveContext();
            
            console.log(`[alerts-engine] Enseigne changed to ${activeEnseigneId}/${activeRoomId}`);
            
            // Régénérer les alert-points pour la nouvelle enseigne
            if (activeEnseigneId && activeRoomId) {
                console.log('[alerts-engine] Regenerating alert-points for new enseigne...');
                renderAlertPoints(activeEnseigneId, activeRoomId);
            }
            
            // Rafraîchir immédiatement les alertes
            console.log('[alerts-engine] Fetching IAQ data for new enseigne...');
            fetchLatestIAQ();
        } catch (e) { 
            console.error('[alerts-engine] enseigneChanged error:', e);
        }
    });

    async function fetchLatestIAQ() {
        try {
            if (!activeEnseigneName || !activeRoomName) {
                console.log('[alerts-engine] fetchLatestIAQ: No context, re-initializing...');
                initActiveContext();
            }
            
            console.log(`[alerts-engine] fetchLatestIAQ for: ${activeEnseigneName}/${activeRoomName} (${activeEnseigneId}/${activeRoomId})`);
            
            const params = new URLSearchParams({
                enseigne: activeEnseigneName || "",
                salle: activeRoomName || "",
                hours: "1",
                step: "5min",
            });
            const url = `${API_URL_WINDOW}?${params.toString()}`;
            console.log(`[alerts-engine] API URL: ${url}`);
            
            const res = await fetch(url, { cache: "no-store" });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            
            console.log(`[alerts-engine] Received ${data.length} data points`);
            
            if (!Array.isArray(data) || data.length === 0) {
                console.log('[alerts-engine] No data, deactivating all alert-points');
                applyAlertPointsActivation({}, {});
                return;
            }
            data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            const last = data[data.length - 1];
            latestSample = last;
            try { window.latestIAQLastSample = last; } catch(e){}
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

    async function start() {
        console.log('[alerts-engine] Starting initialization...');
        
        // Attendre que la config soit chargée
        try {
            if (typeof window.loadConfig === 'function') {
                await window.loadConfig();
                console.log('[alerts-engine] Config loaded');
            }
        } catch (e) {
            console.warn('[alerts-engine] Could not load config:', e);
        }
        
        // Petit délai pour laisser tabs-manager s'initialiser
        await new Promise(resolve => setTimeout(resolve, 100));
        
        initActiveContext();
        
        // Attendre le premier roomChanged pour être sûr que le contexte est correctement restauré
        let isFirstLoad = true;
        const handleFirstRoomChange = () => {
            if (isFirstLoad) {
                isFirstLoad = false;
                console.log('[alerts-engine] First roomChanged received, starting alert checks');
                fetchLatestIAQ();
                setInterval(fetchLatestIAQ, REFRESH_MS);
            }
        };
        
        // Écouter le premier roomChanged
        document.addEventListener('roomChanged', handleFirstRoomChange, { once: true });
        
        // Fallback: si aucun roomChanged après 1 seconde, démarrer quand même
        setTimeout(() => {
            if (isFirstLoad) {
                console.log('[alerts-engine] No roomChanged after 1s, starting anyway');
                // Générer les alert-points pour la pièce active
                if (activeEnseigneId && activeRoomId) {
                    console.log(`[alerts-engine] Generating alert-points for ${activeEnseigneId}/${activeRoomId}`);
                    renderAlertPoints(activeEnseigneId, activeRoomId);
                }
                handleFirstRoomChange();
            }
        }, 1000);
    }

    if (typeof window !== "undefined") {
        document.addEventListener("DOMContentLoaded", start);
    }
})(window);
