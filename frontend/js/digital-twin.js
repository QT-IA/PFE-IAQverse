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

// Sync alert-point elements into the actions table as rows
function syncAlertPointsToTable() {
    const tbody = document.querySelector('.actions-table tbody');
    if (!tbody) return;

    // remove previously injected rows
    Array.from(tbody.querySelectorAll('tr.dynamic-alert')).forEach(r => r.remove());

    // Only include active alert points (set by alerts-engine)
    const points = Array.from(document.querySelectorAll('.alert-point[data-active="true"]'));
    if (!points || points.length === 0) return;

    const t = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t : (()=>undefined);

    const builtRows = [];

    points.forEach(pt => { const explicitKey = pt.getAttribute('data-i18n-key');
        const names = (pt.getAttribute('data-target-names') || '').split('|').map(s => s.trim()).filter(Boolean);
        if (!explicitKey && names.length === 0) return;
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
        const severity = (pt.getAttribute('data-severity') || 'danger').toLowerCase();
        const severityMap = {
            'danger': { emoji: '🔴', cls: 'alert-red' },
            'warning': { emoji: '🟠', cls: 'alert-yellow' },
            'info': { emoji: '🟢', cls: 'alert-green' }
        };
        const sev = severityMap[severity] || severityMap['danger'];

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

        // Clicking the row should open details using the visible subject text
        tr.addEventListener('click', () => { const subj = tdSubj.textContent.trim(); showDetails(subj); });

        tr.appendChild(tdState);
        tr.appendChild(tdSubj);
        tr.appendChild(tdAct);

        // queue row with severity weight for sorting
        const weight = severity === 'danger' ? 0 : (severity === 'warning' ? 1 : 2);
        builtRows.push({ tr, weight });
    });

    // apply translations for newly inserted nodes
    // sort rows: danger first, then warning, then info
    builtRows.sort((a,b) => a.weight - b.weight);
    builtRows.forEach(({ tr }) => tbody.appendChild(tr));
    try { if (window.i18n && typeof window.i18n._applyTranslations === 'function') window.i18n._applyTranslations(tbody); } catch(e){}
}

// run once on DOMContentLoaded and whenever language changes
document.addEventListener('DOMContentLoaded', () => { try { syncAlertPointsToTable(); } catch(e){} });
window.addEventListener('language-changed', () => { try { syncAlertPointsToTable(); } catch(e){} });
