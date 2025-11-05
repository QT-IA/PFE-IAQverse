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

function frameModel(object3d, offsetFactor = 1.5) {
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

      if (modelRoot) {
        scene.remove(modelRoot);
        disposeObject(modelRoot);
        modelRoot = null;
      }
      renderer.render(scene, camera);
      return;
    }

    const glbPath = piece.glbModel;

    if (modelRoot) {
      scene.remove(modelRoot);
      disposeObject(modelRoot);
      modelRoot = null;
    }

    loader.load(
      glbPath,
      function (gltf) {
        modelRoot = gltf.scene;
        scene.add(modelRoot);
        frameModel(modelRoot, 1.1);
        animate();
      },
      function (xhr) {
        if (xhr.lengthComputable) {
          console.log('Chargement GLB: ' + Math.round((xhr.loaded / xhr.total) * 100) + '%');
        }
      },
      function (error) {
        console.error('Erreur de chargement du modèle:', error);
      }
    );
  } catch (e) {
    console.error('loadPieceModel error:', e);
  }
}

// Points d'alertes : recherche d'objet par noms
function findTargetObjectByNames(root, names) {
  const lowerNames = names.map(n => n.trim().toLowerCase()).filter(Boolean);
  let found = null;
  root.traverse((child) => {
    if (found) return;
    if (!child.name) return;
    const lname = child.name.toLowerCase();
    for (const n of lowerNames) {
      if (lname === n || lname.indexOf(n) !== -1) {
        found = child;
        return;
      }
    }
  });
  return found;
}

function updateAlertPoints() {
  const points = document.querySelectorAll('.alert-point');
  if (!modelRoot || points.length === 0 || !container) return;

  points.forEach(el => {
    el.style.position = 'absolute';

    const targetNames = (el.getAttribute('data-target-names') || '').split('|').map(s => s.trim()).filter(Boolean);
    if (targetNames.length === 0) return;

    const target = findTargetObjectByNames(modelRoot, targetNames);
    if (!target) {
      el.style.display = 'none';
      return;
    }

    const worldPos = new THREE.Vector3();
    target.getWorldPosition(worldPos);

    const ndc = worldPos.clone().project(camera);

    if (ndc.z > 1 || ndc.z < -1) {
      el.style.display = 'none';
      return;
    }

    const rectW = container.clientWidth || 700;
    const rectH = container.clientHeight || 400;
    const x = (ndc.x * 0.5 + 0.5) * rectW;
    const y = (-ndc.y * 0.5 + 0.5) * rectH;

    el.style.left = x + 'px';
    el.style.top = y + 'px';
    el.style.display = 'block';
  });
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
