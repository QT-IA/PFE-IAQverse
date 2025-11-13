/**
 * Script spécifique pour la page Digital Twin
 */

let currentDetailsSubject = null;
/**
 * Affiche les détails d'une alerte
 * @param {string} sujet - Le sujet de l'alerte (ex. Fenêtre, Ventilation, etc.)
 * @param {object} detail - Détails optionnels { issues: [{code,name,unit,severity,value,direction,threshold}], actionKey }
 * @param {boolean} forceRefresh - Si true, force la mise à jour sans toggle
 */
function showDetails(sujet, detail, forceRefresh = false) {
    const panel = document.getElementById("details-panel");
    const list = document.getElementById("details-list");
    if (!panel || !list) return;
    // Toggle: si on reclique sur le même sujet, on masque les détails (sauf si forceRefresh)
    if (!forceRefresh && !panel.classList.contains('hidden') && currentDetailsSubject === sujet) {
        panel.classList.add('hidden');
        list.innerHTML = '';
        currentDetailsSubject = null;
        return;
    }

    panel.classList.remove("hidden");
    list.innerHTML = "";
    currentDetailsSubject = sujet;

    // Mettre à jour le titre avec le sujet
    const subjectSpan = document.getElementById('details-subject');
    if (subjectSpan) {
        subjectSpan.textContent = sujet ? `(${sujet})` : '';
    }

    const t = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t : (()=>undefined);

    // Icônes par paramètre (alignées avec les graphiques)
        // Codes de paramètre pour appliquer une couleur dédiée via CSS (pas d'emoji)
        const knownParams = new Set(['co2','pm25','tvoc','temperature','humidity']);

    // Helper pour formatter un item de détail avec style riche
    const formatIssue = (it) => {
        if (!it) return null;
        const dirTxt = it.direction === 'low' ? (t('digitalTwin.details.low') || 'trop bas')
            : (it.direction === 'high' ? (t('digitalTwin.details.high') || 'trop élevé') : (t('digitalTwin.details.out_of_range') || 'hors plage'));
        
        // Translate parameter name using i18n
        const paramCode = (it.code || '').toLowerCase();
        const paramName = t(`digitalTwin.details.parameters.${paramCode}`) || it.name || it.code || 'Paramètre';
        
        const unit = it.unit ? ` ${it.unit}` : '';
        const thresholdLabel = it.direction === 'low' 
            ? (t('digitalTwin.details.thresholdMin') || 'seuil min')
            : (t('digitalTwin.details.thresholdMax') || 'seuil max');
        const thrTxt = (typeof it.threshold === 'number')
            ? ` <span class="param-threshold">(${thresholdLabel} : ${it.threshold}${unit})</span>`
            : '';
        return {
            html: `<span class="param-value">${paramName} ${dirTxt} : ${it.value}${unit}</span>${thrTxt}`,
            severity: it.severity || 'info',
            code: paramCode
        };
    };

    const issues = (detail && Array.isArray(detail.issues)) ? detail.issues : [];
    const hasIssues = issues.length > 0;

    if (hasIssues) {
        // Afficher toutes les issues (danger, warning ET info)
        issues.forEach(it => {
            const li = document.createElement('li');
            const formatted = formatIssue(it);
            if (formatted) {
                li.innerHTML = formatted.html;
                const sevClass = formatted.severity === 'danger' ? 'issue-danger'
                    : (formatted.severity === 'warning' ? 'issue-warning' : 'issue-info');
                li.className = sevClass;
                    const pcode = formatted.code;
                    if (pcode && knownParams.has(pcode)) {
                        li.classList.add(`param-${pcode}`);
                    }
            }
            list.appendChild(li);
        });
        // Action recommandée stylisée
        const actionKey = detail && detail.actionKey;
        if (actionKey) {
            const li = document.createElement('li');
            li.className = 'issue-action';
            const actionLabel = t && t(`digitalTwin.actionVerbs.${actionKey}`);
            li.innerHTML = `<strong>${t('digitalTwin.recommendedAction') || 'Action recommandée'} :</strong> ${actionLabel || actionKey}`;
            list.appendChild(li);
        }
    } else {
        // Pas de problème détecté - tout va bien
        const li = document.createElement('li');
        li.className = 'issue-info';
        li.innerHTML = `<span class="param-value">${t('digitalTwin.allGood') || 'Tous les paramètres sont dans les normes'}</span>`;
        list.appendChild(li);
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
    try { syncAlertPointsToTable(); } catch(e) {}
    
    // Fermer le panneau de détails lors du changement de pièce
    const panel = document.getElementById('details-panel');
    if (panel && !panel.classList.contains('hidden')) {
        panel.classList.add('hidden');
        const list = document.getElementById('details-list');
        if (list) list.innerHTML = '';
        currentDetailsSubject = null;
    }
});

document.addEventListener('enseigneChanged', () => {
    try { syncAlertPointsToTable(); } catch(e) {}
    
    // Fermer le panneau de détails lors du changement d'enseigne
    const panel = document.getElementById('details-panel');
    if (panel && !panel.classList.contains('hidden')) {
        panel.classList.add('hidden');
        const list = document.getElementById('details-list');
        if (list) list.innerHTML = '';
        currentDetailsSubject = null;
    }
});

// Export des fonctions
window.openModal = openModal;
window.closeModal = closeModal;
window.showDetails = showDetails;

/**
 * Met à jour le compteur d'alertes dans le label de la visualisation
 * Compte uniquement les alert-points actifs avec sévérité danger (points rouges uniquement)
 */
function updateAlertCountLabel() {
    const label = document.querySelector('.room-label');
    if (!label) return;
    
    const t = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t : (()=>undefined);
    
    // Compter uniquement les alert-points actifs avec sévérité danger (points rouges)
    const activeAlerts = document.querySelectorAll('.alert-point[data-active="true"][data-severity="danger"]');
    const count = activeAlerts.length;
    
    let text;
    if (count === 0) {
        text = t('digitalTwin.alertCount.zero') || 'Aucune alerte';
    } else if (count === 1) {
        text = t('digitalTwin.alertCount.one') || '1 Alerte';
    } else {
        const template = t('digitalTwin.alertCount.multiple') || '{{count}} Alertes';
        text = template.replace('{{count}}', count);
    }
    
    label.textContent = text;
}

// Exporter la fonction pour qu'elle soit accessible depuis alerts-engine
window.updateAlertCountLabel = updateAlertCountLabel;

// Sync alert-point elements into the actions table as rows
function syncAlertPointsToTable() {
    console.log('[digital-twin] syncAlertPointsToTable called');
    
    const tbody = document.querySelector('.actions-table tbody');
    if (!tbody) {
        console.warn('[digital-twin] Actions table tbody not found');
        return;
    }

    // Vérifier si le panneau de détails est ouvert et stocker le sujet actuel
    const panel = document.getElementById("details-panel");
    const isPanelOpen = panel && !panel.classList.contains('hidden');
    const previousSubject = currentDetailsSubject;

    // remove previously injected rows
    Array.from(tbody.querySelectorAll('tr.dynamic-alert')).forEach(r => r.remove());

    // Get active context (enseigne + salle)
    const getActiveContext = () => {
        try {
            const cfg = (typeof window.getConfig === 'function') ? window.getConfig() : (window.config || null);
            const activeEnseigneId = (typeof window.getActiveEnseigne === 'function') 
                ? window.getActiveEnseigne() 
                : (cfg && cfg.lieux && cfg.lieux.active);
            
            // Essayer de récupérer activeRoomId depuis le tab actif
            const tab = document.querySelector('#room-tabs .room-tab.active');
            let activeRoomId = tab ? tab.getAttribute('data-room-id') : null;
            
            // Si pas de tab actif, prendre la première pièce de l'enseigne active
            if (!activeRoomId && cfg && cfg.lieux && cfg.lieux.enseignes) {
                const ens = cfg.lieux.enseignes.find(e => e.id === activeEnseigneId);
                if (ens && ens.pieces && ens.pieces.length > 0) {
                    activeRoomId = ens.pieces[0].id;
                    console.log(`[digital-twin] No active tab, using first room: ${activeRoomId}`);
                }
            }
            
            return { activeEnseigneId, activeRoomId };
        } catch(e) {
            console.error('[digital-twin] Error getting active context:', e);
            return { activeEnseigneId: null, activeRoomId: null };
        }
    };
    
    const { activeEnseigneId, activeRoomId } = getActiveContext();
    console.log(`[digital-twin] Active context: ${activeEnseigneId}/${activeRoomId}`);

    // Only include active alert points that belong to the current enseigne/salle
    const allActivePoints = Array.from(document.querySelectorAll('.alert-point[data-active="true"]'));
    console.log(`[digital-twin] Found ${allActivePoints.length} active alert-points`);
    
    const points = allActivePoints.filter(pt => {
        const ptEnseigne = pt.getAttribute('data-enseigne');
        const ptPiece = pt.getAttribute('data-piece');
        const matches = (ptEnseigne === activeEnseigneId && ptPiece === activeRoomId);
        if (!matches) {
            console.log(`[digital-twin] Filtering out: ${ptEnseigne}/${ptPiece}`);
        }
        return matches;
    });
    
    console.log(`[digital-twin] Filtered to ${points.length} alert-points for active context`);
    
    if (!points || points.length === 0) {
        console.log('[digital-twin] No alert-points to display in table');
        return;
    }

    const t = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t : (()=>undefined);

    const builtRows = [];

    points.forEach(pt => { 
        const explicitKey = pt.getAttribute('data-i18n-key');
        const severity = pt.getAttribute('data-severity');
        console.log(`[digital-twin] Processing alert-point: ${explicitKey}, severity: ${severity}, active: ${pt.getAttribute('data-active')}`);
        
        const names = (pt.getAttribute('data-target-names') || '').split('|').map(s => s.trim()).filter(Boolean);
        if (!explicitKey && names.length === 0) {
            console.log('[digital-twin] Skipping alert-point: no key or names');
            return;
        }
        // Candidate key: use first name, sanitized to ascii lowercase
        const candidateRaw = explicitKey || names[0];
            const sanitize = (s) => {
                // remove only combining diacritics (U+0300–U+036F), not ASCII letters
                try { s = s.normalize('NFD').replace(/[\u0300-\u036f]/g, ''); } catch(e){}
            return String(s).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
        };
        const candidate = sanitize(candidateRaw);
        const subjectKey = `digitalTwin.sample.${candidate}.subject`;
        const actionKey = `digitalTwin.sample.${candidate}.action`;

        // determine severity
        const severityLower = (severity || 'danger').toLowerCase();
        const severityMap = {
            'danger': { emoji: '🔴', cls: 'alert-red' },
            'warning': { emoji: '🟠', cls: 'alert-yellow' },
            'info': { emoji: '🟢', cls: 'alert-green' }
        };
        const sev = severityMap[severityLower] || severityMap['danger'];
        console.log(`[digital-twin] Alert ${explicitKey}: severity ${severityLower} -> emoji ${sev.emoji}`);

    const tr = document.createElement('tr');
        tr.className = `dynamic-alert ${sev.cls}`;

        const tdState = document.createElement('td'); tdState.textContent = sev.emoji;
        const tdSubj = document.createElement('td');
        const tdAct = document.createElement('td');

        // If i18n keys exist, attach data-i18n so translations update automatically
        const subjTxt = (t && t(subjectKey)) || null;
        // Prefer dynamic action suggested by alerts-engine via data-action-key
    const actionKeyDyn = pt.getAttribute('data-action-key');
    const dynI18nKey = actionKeyDyn ? `digitalTwin.actionVerbs.${actionKeyDyn}` : null;
        const dynActTxt = dynI18nKey && t ? t(dynI18nKey) : null;
        const actTxtFallback = (t && t(actionKey)) || null;

        // Always attach data-i18n so later translation passes can update these cells
        tdSubj.setAttribute('data-i18n', subjectKey);
        tdSubj.textContent = (subjTxt) ? subjTxt : candidateRaw;

        // Action column shows dynamic recommendation when available, else subject default
        if (actionKeyDyn) tdAct.setAttribute('data-i18n', dynI18nKey);
        else tdAct.setAttribute('data-i18n', actionKey);
        tdAct.textContent = (dynActTxt) ? dynActTxt : (actTxtFallback ? actTxtFallback : ((t && t('digitalTwin.details')) || 'Détails'));

        // Prepare detail object from alert-point
        let detailObj = null;
        try {
            const raw = pt.getAttribute('data-details');
            detailObj = raw ? JSON.parse(raw) : null;
        } catch(e) { detailObj = null; }
        
        // Stocker les détails dans la ligne pour pouvoir les récupérer plus tard
        tr._detailsData = detailObj;
        
        // Clicking the row should open details using the visible subject text and detail object
        tr.addEventListener('click', () => {
            const subj = tdSubj.textContent.trim();
            showDetails(subj, detailObj);
        });

        tr.appendChild(tdState);
        tr.appendChild(tdSubj);
        tr.appendChild(tdAct);

        // queue row with severity weight for sorting
        const weight = severityLower === 'danger' ? 0 : (severityLower === 'warning' ? 1 : 2);
        console.log(`[digital-twin] Adding row for ${explicitKey} with weight ${weight}`);
        builtRows.push({ tr, weight });
    });

    // apply translations for newly inserted nodes
    // sort rows: danger first, then warning, then info
    builtRows.sort((a,b) => a.weight - b.weight);
    
    // Vérifier si le sujet du panneau ouvert existe encore dans les nouvelles lignes
    let newDetailsForSubject = null;
    let subjectStillExists = false;
    if (isPanelOpen && previousSubject) {
        for (const { tr } of builtRows) {
            const subjCell = tr.querySelector('td:nth-child(2)');
            if (subjCell && subjCell.textContent.trim() === previousSubject) {
                subjectStillExists = true;
                // Récupérer les nouveaux détails de cette ligne
                const clickHandler = tr._detailsData;
                if (clickHandler) {
                    newDetailsForSubject = clickHandler;
                }
                break;
            }
        }
    }
    
    builtRows.forEach(({ tr }) => tbody.appendChild(tr));
    try { if (window.i18n && typeof window.i18n._applyTranslations === 'function') window.i18n._applyTranslations(tbody); } catch(e){}
    
    // Toujours mettre à jour le panneau s'il est ouvert et que le sujet existe encore
    if (isPanelOpen && previousSubject) {
        if (subjectStillExists && newDetailsForSubject !== null) {
            console.log(`[digital-twin] Refreshing details panel for subject "${previousSubject}"`);
            showDetails(previousSubject, newDetailsForSubject, true); // forceRefresh = true
        } else if (!subjectStillExists) {
            // Si le sujet n'existe plus, fermer le panneau
            console.log(`[digital-twin] Subject "${previousSubject}" no longer exists, closing panel`);
            const panel = document.getElementById('details-panel');
            if (panel) {
                panel.classList.add('hidden');
                const list = document.getElementById('details-list');
                if (list) list.innerHTML = '';
                currentDetailsSubject = null;
            }
        }
    }
    
    // Mettre à jour le compteur d'alertes
    if (typeof window.updateAlertCountLabel === 'function') {
        window.updateAlertCountLabel();
    }
}

// run once on DOMContentLoaded and whenever language changes
document.addEventListener('DOMContentLoaded', () => { try { syncAlertPointsToTable(); } catch(e){} });
window.addEventListener('language-changed', () => { try { syncAlertPointsToTable(); } catch(e){} });
