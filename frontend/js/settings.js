/**
 * Script de la page Paramètres: extrait depuis settings.html
 * - Aucune logique inline dans le HTML
 * - Requiert js/utils.js et js/config-loader.js
 */

let settingsConfig = null; // configuration courante (local à cette page)
let currentSection = '';

// Navigation des sections
function showSection(id) {
  document.querySelectorAll('.section').forEach(section => {
    section.classList.remove('active');
  });
  const target = document.getElementById(id);
  if (target) target.classList.add('active');

  document.querySelectorAll('.menu li').forEach(item => item.classList.remove('active'));
  const activeItem = [...document.querySelectorAll('.menu li')]
    .find(li => li.textContent.trim().toLowerCase() === id);
  if (activeItem) activeItem.classList.add('active');
}

// Modale d'info
function openModal() { ModalManager.open('infoModal'); }
function closeModal() { ModalManager.close('infoModal'); }

// Helpers chemin
function getByPath(obj, path) { return path.split('.').reduce((o, i) => (o ? o[i] : undefined), obj); }
function setByPath(obj, path, value) {
  const parts = path.split('.');
  let current = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    current[parts[i]] = current[parts[i]] || {};
    current = current[parts[i]];
  }
  current[parts[parts.length - 1]] = value;
  return obj;
}

// Groupe de champs dynamique pour la modale d'édition
function createFormGroup(label, path, value) {
  const group = document.createElement('div');
  group.className = 'form-group';

  const labelEl = document.createElement('label');
  labelEl.textContent = label;

  let input;
  if (typeof value === 'boolean') {
    const switchLabel = document.createElement('label');
    switchLabel.className = 'switch';
    input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = value;
    input.name = path;
    const slider = document.createElement('span');
    slider.className = 'slider';
    switchLabel.appendChild(input);
    switchLabel.appendChild(slider);
    input.className = 'form-control';
    group.appendChild(labelEl);
    group.appendChild(switchLabel);
    return group;
  }

  if (Array.isArray(value)) {
    input = document.createElement('input');
    input.type = 'text';
    input.value = value.join(', ');
    input.placeholder = 'Séparer les valeurs par des virgules';
  } else if (path.endsWith('.langue') || path === 'affichage.langue') {
    input = document.createElement('select');
    input.name = path;
    ['Français', 'English', 'Español', 'Deutsch', 'Italiano'].forEach(opt => {
      const o = document.createElement('option');
      o.value = opt; o.textContent = opt; if ((value || '').toString() === opt) o.selected = true; input.appendChild(o);
    });
  } else if (path.endsWith('.localisation') || path === 'affichage.localisation') {
    input = document.createElement('select');
    input.name = path;
    ['Europe, Paris', 'Europe, Lyon', 'North America, New York', 'Asia, Tokyo', 'Other'].forEach(opt => {
      const o = document.createElement('option');
      o.value = opt; o.textContent = opt; if ((value || '').toString() === opt) o.selected = true; input.appendChild(o);
    });
  } else if (path.endsWith('.email')) {
    input = document.createElement('input'); input.type = 'email'; input.value = value || '';
  } else if (path.endsWith('.telephone')) {
    input = document.createElement('input'); input.type = 'tel'; input.pattern = "[+0-9 ]{10,}"; input.value = value || '';
  } else if (path.endsWith('.date_naissance')) {
    input = document.createElement('input'); input.type = 'date'; input.value = value || '';
  } else {
    input = document.createElement('input'); input.type = 'text'; input.value = value || '';
  }

  input.className = 'form-control';
  input.name = path;
  group.appendChild(labelEl);
  group.appendChild(input);
  return group;
}

// Modale d'édition générique
function openEditModalWith(htmlTitle, formHtml, onsubmit) {
  const modal = document.getElementById('editModal');
  const form = document.getElementById('editForm');
  modal.querySelector('h2').textContent = htmlTitle;
  form.innerHTML = formHtml;
  form.onsubmit = async (e) => { e.preventDefault(); await onsubmit(new FormData(form)); };
  modal.style.display = 'flex';
}

// Ouvre le modal pour éditer un seul champ data-path
function openEditModal(element) {
  if (!element || element.dataset.readonly === 'true') return;
  const path = element.getAttribute('data-path');
  if (!path) return;
  const value = getByPath(settingsConfig, path);

  const modal = document.getElementById('editModal');
  const form = document.getElementById('editForm');
  form.innerHTML = '';

  const group = createFormGroup('Modifier', path, value);
  let inputEl = group.querySelector('input, select, textarea') || group.querySelector('.switch input');
  if (inputEl) { inputEl.dataset.path = path; inputEl.name = 'value'; }
  form.appendChild(group);

  form.onsubmit = async (e) => {
    e.preventDefault();
    let newVal;
    if (!inputEl) newVal = null;
    else if (inputEl.type === 'checkbox') newVal = !!inputEl.checked;
    else if (inputEl.tagName.toLowerCase() === 'select') newVal = inputEl.value;
    else newVal = inputEl.value;

    if (Array.isArray(value)) newVal = String(newVal || '').split(',').map(s => s.trim()).filter(Boolean);

  const updates = {}; setByPath(updates, path, newVal); setByPath(settingsConfig, path, newVal);
    try {
      const response = await fetch('http://localhost:8000/api/saveConfig', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(updates)
      });
      if (!response.ok) throw new Error('Erreur lors de la sauvegarde');
  const result = await response.json(); if (result && result.config) settingsConfig = result.config;

      if (Array.isArray(newVal)) element.textContent = newVal.join(', ');
      else if (typeof newVal === 'boolean') element.innerHTML = `<span class="badge ${newVal ? 'badge-yes' : 'badge-no'}">${newVal ? 'Oui' : 'Non'}</span>`;
      else element.textContent = newVal || '—';

      modal.style.display = 'none';
      showNotification('Modification sauvegardée');
    } catch (err) { console.error(err); showNotification('Erreur lors de la sauvegarde', true); }
  };

  modal.querySelector('h2').textContent = 'Modifier';
  modal.style.display = 'block';
}

/* ========== Gestion des enseignes & pièces ========== */
function renderEnseignes() {
  const container = document.getElementById('enseignes-list');
  if (!container || !settingsConfig || !settingsConfig.lieux || !Array.isArray(settingsConfig.lieux.enseignes)) return;

  container.innerHTML = '';
  settingsConfig.lieux.enseignes.forEach(enseigne => {
    const card = document.createElement('div');
  card.className = 'location-card' + (settingsConfig.lieux.active === enseigne.id ? ' active' : '');

    const roomsHtml = (enseigne.pieces || []).map(piece => {
      return `<span class="room-tag">${escapeHtml(piece.nom)} <button class="remove-btn" title="Supprimer" onclick="removePiece('${enseigne.id}','${piece.id}')">×</button></span>`;
    }).join('');

    card.innerHTML = `
      <div class="actions">
        <button class="edit-btn" title="Modifier" onclick="editEnseigne('${enseigne.id}')"><img src="/assets/icons/edit.png" alt="Modifier"></button>
        <button class="remove-btn" title="Supprimer" onclick="removeEnseigne('${enseigne.id}')"><img src="/assets/icons/delete.png" alt="Supprimer"></button>
      </div>
      <h3>${escapeHtml(enseigne.nom || '—')}</h3>
      <p class="muted">${escapeHtml(enseigne.adresse || '')}</p>
      <div class="rooms">${roomsHtml}</div>
      <button class="btn-room" onclick="addPiece('${enseigne.id}')"><img src="/assets/icons/add.png" alt=""> Ajouter une pièce</button>

      <div id="confirmModal" class="modal" style="display:none;">
        <div class="modal-content">
          <h3 id="confirmTitle">Confirmation</h3>
          <p id="confirmMessage">Voulez-vous vraiment supprimer ?</p>
          <div class="modal-actions">
            <button id="confirmYes">Oui</button>
            <button id="confirmNo">Annuler</button>
          </div>
        </div>
      </div>`;

    container.appendChild(card);
  });

  enableDragAndDrop();
  enablePieceDragAndDrop();
}

function enableDragAndDrop() {
  const container = document.getElementById('enseignes-list');
  if (!container) return;

  container.querySelectorAll('.location-card').forEach(card => {
    let draggedCard = null;
    card.draggable = true;

    card.addEventListener('dragstart', (e) => {
      draggedCard = card;
      e.dataTransfer.effectAllowed = 'move';
      card.classList.add('dragging');
    });

    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      draggedCard = null;

      const newOrder = Array.from(container.children).map(el => {
        const name = el.querySelector('h3')?.textContent.trim();
  return settingsConfig.lieux.enseignes.find(e => e.nom === name)?.id;
      }).filter(Boolean);

  settingsConfig.lieux.enseignes.sort((a, b) => newOrder.indexOf(a.id) - newOrder.indexOf(b.id));
  if (settingsConfig.lieux.enseignes.length > 0) settingsConfig.lieux.active = settingsConfig.lieux.enseignes[0].id;

      fetch('http://localhost:8000/api/saveConfig', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settingsConfig)
      }).then(() => showNotification('Nouvel ordre enregistré')).catch(err => console.error(err));
    });

    card.addEventListener('dragover', (e) => {
      e.preventDefault();
      const dragging = container.querySelector('.dragging');
      const afterElement = getDragAfterElementHorizontal(container, e.clientX);
      if (!afterElement) container.appendChild(dragging); else container.insertBefore(dragging, afterElement);
    });
  });

  function getDragAfterElementHorizontal(container, x) {
    const draggableElements = [...container.querySelectorAll('.location-card:not(.dragging)')];
    return draggableElements.reduce((closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = x - box.left - box.width / 2;
      if (offset < 0 && offset > closest.offset) return { offset, element: child };
      else return closest;
    }, { offset: Number.NEGATIVE_INFINITY }).element;
  }
}

function enablePieceDragAndDrop() {
  document.querySelectorAll('.rooms').forEach(roomContainer => {
    roomContainer.querySelectorAll('.room-tag').forEach(tag => {
      let draggedTag = null;
      tag.draggable = true;

      tag.addEventListener('dragstart', (e) => {
        draggedTag = tag;
        e.dataTransfer.effectAllowed = 'move';
        tag.classList.add('dragging');
      });

      tag.addEventListener('dragend', () => {
        tag.classList.remove('dragging');
        draggedTag = null;

        const enseigneCard = tag.closest('.location-card');
        const enseigneName = enseigneCard.querySelector('h3').textContent.trim();
  const enseigne = settingsConfig.lieux.enseignes.find(e => e.nom === enseigneName);
        if (!enseigne) return;

        const newOrder = Array.from(roomContainer.children).map(el => {
          const name = el.textContent.replace('×', '').trim();
          return enseigne.pieces.find(p => p.nom === name)?.id;
        }).filter(Boolean);

        enseigne.pieces.sort((a, b) => newOrder.indexOf(a.id) - newOrder.indexOf(b.id));

        fetch('http://localhost:8000/api/saveConfig', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settingsConfig)
        }).then(() => showNotification('Ordre des pièces enregistré')).catch(err => console.error(err));
      });

      tag.addEventListener('dragover', (e) => {
        e.preventDefault();
        const dragging = roomContainer.querySelector('.dragging');
        const afterElement = getDragAfterElement(roomContainer, e.clientX);
        if (!afterElement) roomContainer.appendChild(dragging); else roomContainer.insertBefore(dragging, afterElement);
      });
    });

    function getDragAfterElement(container, x) {
      const draggableElements = [...container.querySelectorAll('.room-tag:not(.dragging)')];
      return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = x - box.left - box.width / 2;
        if (offset < 0 && offset > closest.offset) return { offset, element: child };
        else return closest;
      }, { offset: Number.NEGATIVE_INFINITY }).element;
    }
  });
}

async function addEnseigne() {
  openEditModalWith('Ajouter une enseigne', `
    <div class="form-group"><label>Nom</label><input name="nom" type="text" required></div>
    <div class="form-group"><label>Adresse</label><input name="adresse" type="text"></div>
  `, async (formData) => {
  const newEn = { id: 'ens_' + Date.now(), nom: formData.get('nom'), adresse: formData.get('adresse') || '', pieces: [] };
  if (!settingsConfig.lieux) settingsConfig.lieux = { enseignes: [], active: null };
  if (!Array.isArray(settingsConfig.lieux.enseignes)) settingsConfig.lieux.enseignes = [];
  settingsConfig.lieux.enseignes.push(newEn);
  settingsConfig.lieux.active = newEn.id;

    try {
  const response = await fetch('http://localhost:8000/api/saveConfig', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settingsConfig) });
      if (!response.ok) throw new Error('Erreur lors de la sauvegarde');
  const result = await response.json(); if (result && result.config) settingsConfig = result.config;
      document.getElementById('editModal').style.display = 'none';
      showNotification('Enseigne ajoutée avec succès');
      renderEnseignes();
    } catch (err) { console.error(err); showNotification("Erreur lors de l'ajout de l'enseigne", true); }
  });
}

async function addPiece(enseigneId) {
  openEditModalWith('Ajouter une pièce', `
    <div class="form-group"><label>Nom de la pièce</label><input name="nom" type="text" required></div>
    <div class="form-group"><label>Type</label>
      <select name="type"><option value="salon">Salon</option><option value="cuisine">Cuisine</option><option value="chambre">Chambre</option><option value="bureau">Bureau</option><option value="autre">Autre</option></select>
    </div>
    <div class="form-group">
      <label>Modèle 3D (.glb)</label>
      <div id="glbDropZone" style="border: 2px dashed #ccc; padding: 20px; text-align: center; cursor: pointer;">Glissez-déposez un fichier .glb ici</div>
      <input type="file" id="glbInput" accept=".glb" style="display: none;">
      <p id="glbFileName" style="font-size: 0.9em; color: #555;"></p>
    </div>
  `, async (formData) => {
  const enseigne = (settingsConfig.lieux.enseignes || []).find(e => e.id === enseigneId);
    if (!enseigne) { showNotification('Enseigne non trouvée', true); return; }
    if (!glbFileBase64) { showNotification('Veuillez ajouter un fichier .glb avant de créer la pièce', true); return; }

    const piece = { id: 'piece_' + Date.now(), nom: formData.get('nom'), type: formData.get('type'), glbModel: glbFileBase64 || null };
    if (!Array.isArray(enseigne.pieces)) enseigne.pieces = [];
    enseigne.pieces.push(piece);

    try {
      const response = await fetch('http://localhost:8000/api/saveConfig', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settingsConfig) });
      if (!response.ok) throw new Error('Erreur lors de la sauvegarde');
      const result = await response.json(); if (result && result.config) settingsConfig = result.config;
      document.getElementById('editModal').style.display = 'none';
      showNotification('Pièce ajoutée avec succès');
      renderEnseignes();
    } catch (err) { console.error(err); showNotification("Erreur lors de l'ajout de la pièce", true); }
  });

  const dropZone = document.getElementById('glbDropZone');
  const fileInput = document.getElementById('glbInput');
  let glbFileBase64 = null;

  function handleGLBFile(file) {
    if (!file || !file.name.endsWith('.glb')) { showNotification('Fichier .glb invalide', true); return; }
    glbFileBase64 = '/assets/rooms/' + file.name;
    document.getElementById('glbFileName').textContent = file.name;
  }

  dropZone.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.style.borderColor = '#4CAF50'; });
  dropZone.addEventListener('dragleave', () => { dropZone.style.borderColor = '#ccc'; });
  dropZone.addEventListener('drop', e => { e.preventDefault(); dropZone.style.borderColor = '#ccc'; handleGLBFile(e.dataTransfer.files[0]); });
  fileInput.addEventListener('change', () => { handleGLBFile(fileInput.files[0]); });
}

async function editEnseigne(enseigneId) {
  const enseigne = (settingsConfig.lieux.enseignes || []).find(e => e.id === enseigneId);
  if (!enseigne) { showNotification('Enseigne non trouvée', true); return; }

  openEditModalWith('Modifier l\'enseigne', `
    <div class="form-group"><label>Nom</label><input name="nom" type="text" value="${escapeHtml(enseigne.nom)}" required></div>
    <div class="form-group"><label>Adresse</label><input name="adresse" type="text" value="${escapeHtml(enseigne.adresse || '')}"></div>
  `, async (formData) => {
    enseigne.nom = formData.get('nom');
    enseigne.adresse = formData.get('adresse');

    try {
      const response = await fetch('http://localhost:8000/api/saveConfig', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settingsConfig) });
      if (!response.ok) throw new Error('Erreur lors de la sauvegarde');
      const result = await response.json(); if (result && result.config) settingsConfig = result.config;
      document.getElementById('editModal').style.display = 'none';
      showNotification('Enseigne modifiée avec succès');
      renderEnseignes();
    } catch (err) { console.error(err); showNotification("Erreur lors de la modification de l'enseigne", true); loadConfigToUI(); }
  });
}

function showConfirmation(message, callback) {
  const modal = document.getElementById('confirmModal');
  if (!modal) { callback(confirm(message)); return; }
  document.getElementById('confirmMessage').textContent = message;
  modal.style.display = 'flex';
  const yesBtn = document.getElementById('confirmYes');
  const noBtn = document.getElementById('confirmNo');
  const cleanup = () => { modal.style.display = 'none'; yesBtn.onclick = null; noBtn.onclick = null; };
  yesBtn.onclick = () => { cleanup(); callback(true); };
  noBtn.onclick = () => { cleanup(); callback(false); };
}

async function removeEnseigne(enseigneId) {
  showConfirmation('Supprimer cette enseigne ?', async (confirmed) => {
    if (!confirmed) return;
  settingsConfig.lieux.enseignes = (settingsConfig.lieux.enseignes || []).filter(e => e.id !== enseigneId);
  if (settingsConfig.lieux.active === enseigneId) settingsConfig.lieux.active = (settingsConfig.lieux.enseignes[0] || {}).id || null;
    await saveConfigAll();
    renderEnseignes();
  });
}

async function removePiece(enseigneId, pieceId) {
  showConfirmation('Supprimer cette pièce ?', async (confirmed) => {
    if (!confirmed) return;
  const enseigne = (settingsConfig.lieux.enseignes || []).find(e => e.id === enseigneId);
    if (!enseigne) return;
    enseigne.pieces = (enseigne.pieces || []).filter(p => p.id !== pieceId);
    await saveConfigAll();
    renderEnseignes();
  });
}

// Enregistrement global de la configuration (envoi complet si nécessaire)
async function saveConfigAll() {
  const response = await fetch('http://localhost:8000/api/saveConfig', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settingsConfig)
  });
  if (!response.ok) throw new Error('Erreur lors de la sauvegarde');
  const result = await response.json(); if (result && result.config) settingsConfig = result.config;
}

// Édition par section (modale multi-champs)
function editSection(sectionId) {
  currentSection = sectionId;
  const modal = document.getElementById('editModal');
  const form = document.getElementById('editForm');
  form.innerHTML = '';
  form.onsubmit = async (e) => { e.preventDefault(); await saveConfigSection(); };

  const sectionConfig = {
    vous: [ ['Nom', 'vous.nom'], ['Prénom', 'vous.prenom'], ['Date de naissance', 'vous.date_naissance'], ['Email', 'vous.email'], ['Téléphone', 'vous.telephone'], ['Adresse', 'vous.adresse'] ],
    assurance: [ ['Nom', 'assurance.nom'], ['Email', 'assurance.email'], ['Téléphone', 'assurance.telephone'], ['Adresse', 'assurance.adresse'] ],
    syndicat: [ ['Nom', 'syndicat.nom'], ['Email', 'syndicat.email'], ['Téléphone', 'syndicat.telephone'], ['Adresse', 'syndicat.adresse'] ],
    mode: [ ["Mode d'affichage", 'affichage.mode'] ],
    'langue & localisation': [ ['Langue', 'affichage.langue'], ['Localisation', 'affichage.localisation'] ],
    technologies: [ ['Notifications Email', 'notifications.technologies.email'], ['Notifications SMS', 'notifications.technologies.sms'], ['Notifications Push', 'notifications.technologies.push'] ],
    type: [ ['Alertes', 'notifications.types.alertes'], ['Rappels', 'notifications.types.rappels'], ['Newsletters', 'notifications.types.newsletters'] ],
    enseigne: [ ["Nom de l'enseigne", 'lieux.enseigne'], ['Pièces', 'lieux.pieces'] ]
  };

  const fields = sectionConfig[sectionId] || [];
  fields.forEach(([label, path]) => {
    const value = getByPath(settingsConfig, path);
    form.appendChild(createFormGroup(label, path, value));
  });
  modal.style.display = 'block';
}

async function saveConfigSection() {
  const form = document.getElementById('editForm');
  const formData = new FormData(form);
  let updates = {};
  for (const [path, value] of formData.entries()) {
    const input = form.querySelector(`[name="${path}"]`);
    let finalValue = value;
    if (input.type === 'checkbox') finalValue = input.checked;
    else if (input.name.endsWith('.pieces')) finalValue = value.split(',').map(s => s.trim()).filter(Boolean);
    else if (typeof getByPath(settingsConfig, path) === 'boolean') finalValue = value.toLowerCase() === 'true' || value === '1' || value.toLowerCase() === 'oui';
    setByPath(updates, path, finalValue);
    setByPath(settingsConfig, path, finalValue);
  }

  try {
  const payload = Object.keys(updates).length === 0 ? settingsConfig : updates;
    const response = await fetch('http://localhost:8000/api/saveConfig', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Erreur lors de la sauvegarde');
  if (result && result.config) settingsConfig = result.config;
    document.getElementById('editModal').style.display = 'none';
    showNotification('Configuration sauvegardée avec succès');
    // rafraîchir affichage
    updateDataPathsDisplay();
    if (typeof renderEnseignes === 'function') renderEnseignes();
  } catch (err) { console.error(err); showNotification('Erreur lors de la sauvegarde', true); }
}

// Remplissage des spans [data-path]
function updateDataPathsDisplay() {
  document.querySelectorAll('[data-path]').forEach(el => {
    const path = el.getAttribute('data-path');
    const value = getByPath(settingsConfig, path);
    el.classList.add('value-display');

    if (typeof value === 'boolean') {
      el.innerHTML = `<span class="badge ${value ? 'badge-yes' : 'badge-no'}">${value ? 'Oui' : 'Non'}</span>`;
      el.style.cursor = 'pointer';
      el.onclick = () => openEditModal(el);
      return;
    }

    if (path === 'affichage.mode') {
      const currentMode = String(value || '').toLowerCase();
      const select = document.createElement('select');
      select.className = 'form-control';
      ['Clair', 'Sombre'].forEach(mode => {
        const option = document.createElement('option');
        option.value = mode.toLowerCase(); option.textContent = mode; if (mode.toLowerCase() === currentMode) option.selected = true; select.appendChild(option);
      });
      el.innerHTML = '';
      el.appendChild(select);
      select.addEventListener('change', async () => {
        const newMode = select.value === 'sombre' ? 'Sombre' : 'Clair';
  const updates = {}; setByPath(updates, 'affichage.mode', newMode); setByPath(settingsConfig, 'affichage.mode', newMode);
        try {
          const r = await fetch('http://localhost:8000/api/saveConfig', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(updates) });
          if (r.ok) showNotification('Mode mis à jour'); else showNotification('Erreur lors de la sauvegarde', true);
        } catch (err) { console.error(err); showNotification('Erreur lors de la sauvegarde', true); }
      });
      return;
    }

    if (Array.isArray(value)) el.textContent = value.join(', ');
    else el.textContent = value || '—';
    el.style.cursor = 'pointer';
    el.onclick = (e) => openEditModal(e.target);
  });
}

// Chargement config et initialisation UI
async function loadConfigToUI() {
  try {
  await loadConfig();
  settingsConfig = getConfig();
  if (!settingsConfig) { showNotification('Impossible de charger la configuration', true); return; }
    updateDataPathsDisplay();
    if (typeof renderEnseignes === 'function') renderEnseignes();
  if (settingsConfig?.affichage?.mode) applyTheme(settingsConfig.affichage.mode);
  } catch (error) {
    console.error('Erreur:', error);
    showNotification('Erreur lors du chargement de la configuration', true);
  }
}

// Restauration de l'état UI et listeners
document.addEventListener('DOMContentLoaded', () => {
  // Section active
  const savedSection = localStorage.getItem('lastSection') || 'compte';
  showSection(savedSection);
  document.querySelectorAll('.menu li').forEach(item => {
    item.addEventListener('click', () => {
      const id = item.textContent.trim().toLowerCase();
      localStorage.setItem('lastSection', id);
    });
  });

  // Gestion accordéon: n'autoriser qu'un seul <details> ouvert à la fois
  const allDetails = document.querySelectorAll('details.settings-section');
  allDetails.forEach(d => {
    d.addEventListener('toggle', () => {
      if (d.open) {
        // Fermer tous les autres quand celui-ci s'ouvre
        allDetails.forEach(other => { if (other !== d) other.open = false; });
        localStorage.setItem('openDetail', d.id);
      } else {
        // Si aucun n'est ouvert, nettoyer la clé
        const anyOpen = Array.from(allDetails).some(x => x.open);
        if (!anyOpen) localStorage.removeItem('openDetail');
      }
    });
  });
  const openDetail = localStorage.getItem('openDetail');
  if (openDetail) {
    const el = document.getElementById(openDetail);
    if (el && el.tagName.toLowerCase() === 'details') el.open = true;
  }

  // Cliquer hors modale -> utils.js prend en charge .close, etc.

  // Charger la config dans l'UI
  loadConfigToUI();
});

// Exposer global pour les onclick existants
window.showSection = showSection;
window.openModal = openModal;
window.closeModal = closeModal;
window.openEditModalWith = openEditModalWith;
window.openEditModal = openEditModal;
window.renderEnseignes = renderEnseignes;
window.addEnseigne = addEnseigne;
window.addPiece = addPiece;
window.editEnseigne = editEnseigne;
window.removeEnseigne = removeEnseigne;
window.removePiece = removePiece;
window.editSection = editSection;
