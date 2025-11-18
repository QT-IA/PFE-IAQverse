import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Initialisation du conteneur
const container = document.getElementById('blender-viewer');
if (container) {
  if (!container.style.position) container.style.position = 'relative';
  if (!container.style.width) container.style.width = '700px';
  if (!container.style.height) container.style.height = '400px';
}

const width = (container && container.clientWidth) || 700;
const height = (container && container.clientHeight) || 400;

// Renderer
const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
renderer.setPixelRatio(window.devicePixelRatio || 1);
renderer.setSize(width, height);
if (container) container.appendChild(renderer.domElement);

// Scene & Camera
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 2000);

// Lumières
const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
scene.add(ambientLight);
const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
dirLight.position.set(5, 10, 7.5);
scene.add(dirLight);

// Contrôles
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.screenSpacePanning = false;
controls.minDistance = 0.5;
controls.maxDistance = 500;
controls.maxPolarAngle = Math.PI / 2.1;

const loader = new GLTFLoader();
let modelRoot = null;
let isLoading = false; // prevent concurrent loads
let animationStarted = false; // ensure only one animate loop

function frameModel(object3d, offsetFactor = 1.5) {
  // Chercher un objet nommé "Camera" dans le modèle
  let cameraObject = null;
  const foundObjects = [];

  object3d.traverse(obj => {
    if (obj.name) {
      foundObjects.push(obj.name);
      // Chercher exactement "Camera" ou contenant "camera"
      if (obj.name === 'Camera' || obj.name.toLowerCase().includes('camera')) {
        cameraObject = obj;
      }
    }
  });

  console.log('[three-scene] All objects in model:', foundObjects);
  console.log('[three-scene] Camera object found:', cameraObject ? cameraObject.name : 'none');

  if (cameraObject) {
    // Centrer sur l'objet "Camera" trouvé
    const cameraWorldPos = new THREE.Vector3();
    cameraObject.getWorldPosition(cameraWorldPos);

    console.log('[three-scene] Camera object world position:', cameraWorldPos);

    // Positionner la caméra pour regarder vers l'objet Camera
    const distance = 1; // Distance encore plus réduite pour zoomer davantage
    camera.position.set(
      cameraWorldPos.x + distance,
      cameraWorldPos.y + distance * 0.6,
      cameraWorldPos.z + distance
    );

    // Orienter les contrôles vers l'objet Camera
    controls.target.copy(cameraWorldPos);

    console.log('[three-scene] Centered view on Camera object at:', cameraWorldPos);
    console.log('[three-scene] Camera position set to:', camera.position);
  } else {
    // Comportement par défaut : centrer sur le modèle entier
    const box = new THREE.Box3().setFromObject(object3d);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);

    // Centrer les objets
    object3d.position.x = object3d.position.x - center.x;
    object3d.position.y = object3d.position.y - center.y;
    object3d.position.z = object3d.position.z - center.z;

    // Position de la caméra
    const cameraZ = maxDim * offsetFactor;
    camera.position.set(cameraZ, cameraZ * 0.6, cameraZ);
    camera.near = Math.max(0.1, maxDim / 100);
    camera.far = Math.max(1000, maxDim * 10);
    camera.updateProjectionMatrix();

    // Centrer le modèle
    controls.target.set(0, 0, 0);
  }

  controls.update();
}

function disposeObject(root) {
  if (!root) return;
  root.traverse(obj => {
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) {
      if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose());
      else obj.material.dispose();
    }
  });
}

function loadPieceModel(roomId) {
  // Prevent concurrent loads
  if (isLoading) {
    console.warn('Un modèle est déjà en cours de chargement, appel ignoré');
    return;
  }

  // Utiliser la config globale remplie par config-loader.js / tabs-manager.js
  try {
    const cfg = typeof getConfig === 'function' ? getConfig() : window.config;
    const activeEnseigne = typeof getActiveEnseigne === 'function' ? getActiveEnseigne() : window.activeEnseigne;
    if (!cfg || !cfg.lieux || !cfg.lieux.enseignes || !activeEnseigne) return;

    const enseigne = cfg.lieux.enseignes.find(e => e.id === activeEnseigne);
    if (!enseigne) return;

    const piece = enseigne.pieces?.find(p => p.id === roomId);
    if (!piece || !piece.glbModel) {
      console.warn('Modèle GLB non défini pour cette pièce');

      // Clear existing model
      if (modelRoot) {
        scene.remove(modelRoot);
        disposeObject(modelRoot);
        modelRoot = null;
      }
      renderer.render(scene, camera);
      return;
    }

    const glbPath = piece.glbModel;

    // Clear existing model before loading new one
    if (modelRoot) {
      scene.remove(modelRoot);
      disposeObject(modelRoot);
      modelRoot = null;
    }

    isLoading = true;
    loader.load(
      glbPath,
      function (gltf) {
        isLoading = false;
        modelRoot = gltf.scene;
        scene.add(modelRoot);
        frameModel(modelRoot, 1.1);
        
        // Générer automatiquement les alert-points pour les objets numérotés
        autoGenerateAlertPoints(modelRoot);
        
        // Start animation loop only once
        if (!animationStarted) {
          animationStarted = true;
          animate();
        }
      },
      function (xhr) {
        if (xhr.lengthComputable) {
          console.log('Chargement GLB: ' + Math.round((xhr.loaded / xhr.total) * 100) + '%');
        }
      },
      function (error) {
        isLoading = false;
        console.error('Erreur de chargement du modèle:', error);
      }
    );
  } catch (e) {
    isLoading = false;
    console.error('loadPieceModel error:', e);
  }
}

// Points d'alertes : recherche d'objet par noms
function findTargetObjectByNames(root, names) {
  const lowerNames = names.map(n => n.trim().toLowerCase()).filter(Boolean);
  let found = null;
  let bestMatch = null;
  let bestScore = 0;
  
  root.traverse((child) => {
    if (!child.name) return;
    const lname = child.name.toLowerCase();
    
    for (const n of lowerNames) {
      // Score de correspondance : 3 = exact match, 2 = contient, 1 = contenu dans
      let score = 0;
      if (lname === n) {
        score = 3;
      } else if (lname.indexOf(n) !== -1) {
        score = 2;
      } else if (n.indexOf(lname) !== -1) {
        score = 1;
      }
      
      if (score > bestScore) {
        bestScore = score;
        bestMatch = child;
      }
      
      // Si match exact, prendre immédiatement
      if (score === 3) {
        found = child;
        return;
      }
    }
  });
  
  // Retourner le meilleur match trouvé, ou null
  return found || bestMatch;
}

function autoGenerateAlertPoints(modelRoot) {
  console.log('[three-scene] autoGenerateAlertPoints called with modelRoot:', !!modelRoot);
  if (!modelRoot) return;
  
  // Supprimer les anciens alert-points générés automatiquement
  const existingAutoPoints = document.querySelectorAll('.alert-point[data-auto-generated="true"]');
  console.log('[three-scene] Removing', existingAutoPoints.length, 'existing auto-generated points');
  existingAutoPoints.forEach(point => point.remove());
  
  const alertPointsContainer = document.getElementById('alert-points-container');
  if (!alertPointsContainer) return;
  
  // Patterns à rechercher dans les noms d'objets (ajustés selon les vrais noms du GLB)
  const patterns = {
    'window': /Window/i,  // Cherche "Window" n'importe où dans le nom
    'door': /Door/i,     // Cherche "Door" n'importe où dans le nom
    'ventilation': /Clim/i, // Cherche "Clim" n'importe où dans le nom
    'radiator': /Radiator/i // Cherche "Radiator" n'importe où dans le nom
  };
  
  // Collecter tous les objets correspondants (stocker les objets Three.js, pas juste les noms)
  const foundObjects = {};
  Object.keys(patterns).forEach(key => foundObjects[key] = []);
  
  modelRoot.traverse(obj => {
    if (obj.isMesh && obj.name) {
      Object.entries(patterns).forEach(([type, pattern]) => {
        if (pattern.test(obj.name)) {
          foundObjects[type].push(obj); // Stocker l'objet Three.js complet
        }
      });
    }
  });
  
  // Créer les alert-points pour chaque type trouvé
  const typePositions = {
    'window': { top: '20%', left: '30%' },
    'door': { top: '30%', left: '10%' }, // Remonté pour être au milieu de la porte
    'ventilation': { top: '10%', left: '50%' },
    'radiator': { top: '80%', left: '20%' }
  };
  
  Object.entries(foundObjects).forEach(([type, objects]) => {
    if (objects.length > 0) {
      // Créer un alert-point pour CHAQUE objet trouvé
      objects.forEach((obj, index) => {
        const severity = type === 'radiator' ? 'warning' : 'info';
        const position = typePositions[type] || { top: '50%', left: '50%' };
        
        // Ajouter un petit offset pour éviter que les points se superposent
        const offsetX = (index % 3 - 1) * 5; // -5%, 0%, 5%
        const offsetY = Math.floor(index / 3) * 5; // 0%, 5%, 10%, etc.
        const finalTop = `calc(${position.top} + ${offsetY}%)`;
        const finalLeft = `calc(${position.left} + ${offsetX}%)`;
        
        const alertPoint = document.createElement('div');
        alertPoint.className = 'alert-point';
        alertPoint.setAttribute('data-i18n-key', type);
        alertPoint.setAttribute('data-target-names', obj.name); // Garder le nom pour compatibilité
        alertPoint.setAttribute('data-severity', severity);
        alertPoint.setAttribute('data-auto-generated', 'true');
        alertPoint.style.cssText = `top: ${finalTop}; left: ${finalLeft}; transform: translate(-50%, -50%);`;
        
        // Stocker une référence directe à l'objet Three.js
        alertPoint._threeObject = obj;
        
        alertPointsContainer.appendChild(alertPoint);
      });
    }
  });
  
  console.log('[three-scene] Auto-generated alert-points:', foundObjects);
  
  // Compter le nombre total de points créés
  const totalPointsCreated = Object.values(foundObjects).reduce((sum, arr) => sum + arr.length, 0);
  console.log('[three-scene] Total points created:', totalPointsCreated);
  
  // Mettre à jour le compteur d'alertes après création
  console.log('[three-scene] Calling updateAlertCountLabel after creating points');
  if (typeof window.updateAlertCountLabel === 'function') {
    console.log('[three-scene] updateAlertCountLabel function exists, calling it');
    window.updateAlertCountLabel();
  } else {
    console.error('[three-scene] updateAlertCountLabel function not found on window');
  }
}

function updateAlertPoints() {
  const points = document.querySelectorAll('.alert-point');
  if (!modelRoot || points.length === 0 || !container) return;

  points.forEach(el => {
    el.style.position = 'absolute';

    // Utiliser la référence directe à l'objet Three.js si disponible
    let target = el._threeObject;
    
    // Fallback vers la recherche par nom si pas de référence directe
    if (!target) {
      const targetNames = (el.getAttribute('data-target-names') || '').split('|').map(s => s.trim()).filter(Boolean);
      if (targetNames.length === 0) return;
      target = findTargetObjectByNames(modelRoot, targetNames);
    }
    
    if (!target) {
      console.log('[three-scene] No target found for point:', el.getAttribute('data-i18n-key'), '- hiding');
      el.style.display = 'none';
      return;
    }

    console.log('[three-scene] Found target for', el.getAttribute('data-i18n-key'), '->', target.name);

    const worldPos = new THREE.Vector3();
    target.getWorldPosition(worldPos);

    // Ajuster la position verticale pour certains types d'objets
    const i18nKey = el.getAttribute('data-i18n-key');
    if (i18nKey === 'door') {
      // Remonter le point de la porte d'environ 1.0 unités dans l'espace 3D
      worldPos.y += 1.0;
    }

    const ndc = worldPos.clone().project(camera);

    const rectW = container.clientWidth || 700;
    const rectH = container.clientHeight || 400;
    
    // Clamp les coordonnées NDC pour garder les points dans le viewport
    const clampedNdc = {
      x: Math.max(-1, Math.min(1, ndc.x)),
      y: Math.max(-1, Math.min(1, ndc.y))
    };
    
    const x = (clampedNdc.x * 0.5 + 0.5) * rectW;
    const y = (-clampedNdc.y * 0.5 + 0.5) * rectH;

    el.style.left = x + 'px';
    el.style.top = y + 'px';
    el.style.display = 'block';
    
    // Ajouter une classe pour indiquer si le point est clamped (hors viewport original)
    if (ndc.z > 1 || ndc.z < -1 || ndc.x !== clampedNdc.x || ndc.y !== clampedNdc.y) {
      el.classList.add('alert-point-clamped');
      console.log('[three-scene] Point clamped for', target.name, 'original ndc:', ndc, 'clamped:', clampedNdc);
    } else {
      el.classList.remove('alert-point-clamped');
    }
    
    console.log('[three-scene] Positioned point for', target.name, 'at', x, y);
  });
  
  // Mettre à jour le compteur d'alertes après repositionnement
  if (typeof window.updateAlertCountLabel === 'function') {
    // Petit délai pour laisser le DOM se mettre à jour
    setTimeout(() => window.updateAlertCountLabel(), 50);
  }
}

// Animation loop
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  updateAlertPoints();
  renderer.render(scene, camera);
}

// Resize
window.addEventListener('resize', () => {
  const w = (container && container.clientWidth) || 800;
  const h = (container && container.clientHeight) || 600;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
});

// Raccourci clavier pour centrer le modèle (F)
window.addEventListener('keydown', (e) => {
  if (e.key === 'f' && modelRoot) {
    frameModel(modelRoot, 1.1);
  }
});

// Bouton pour centrer le modèle
const frameBtn = document.getElementById('frame-btn');
if (frameBtn) {
  frameBtn.addEventListener('click', () => {
    if (modelRoot) frameModel(modelRoot, 1.1);
  });
}

// Exporter vers le scope global pour usage par d'autres scripts
window.loadPieceModel = loadPieceModel;
window.frameModel = frameModel;
