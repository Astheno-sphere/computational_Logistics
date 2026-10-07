# Web 3D Reference for AEC

## Three.js Scene Setup Boilerplate

### Minimal AEC Viewer

```javascript
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

class AECViewer {
    constructor(container) {
        this.container = container;

        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf5f5f5);
        this.scene.fog = new THREE.Fog(0xf5f5f5, 500, 2000);

        // Camera
        const aspect = container.clientWidth / container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 5000);
        this.camera.position.set(80, 60, 80);
        this.camera.lookAt(0, 0, 0);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: false,
            powerPreference: 'high-performance'
        });
        this.renderer.setSize(container.clientWidth, container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.2;
        container.appendChild(this.renderer.domElement);

        // Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.08;
        this.controls.maxPolarAngle = Math.PI * 0.52; // prevent below ground
        this.controls.minDistance = 5;
        this.controls.maxDistance = 500;
        this.controls.target.set(0, 10, 0);

        // Lighting
        this.setupLighting();

        // Ground
        this.setupGround();

        // Helpers
        this.setupHelpers();

        // Events
        this.setupEvents();

        // Start render loop
        this.animate();
    }

    setupLighting() {
        // Ambient fill
        const ambient = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambient);

        // Hemisphere (sky/ground)
        const hemi = new THREE.HemisphereLight(0x87ceeb, 0x8b7355, 0.3);
        this.scene.add(hemi);

        // Main directional (sun)
        this.sunLight = new THREE.DirectionalLight(0xfff5e6, 1.0);
        this.sunLight.position.set(60, 100, 40);
        this.sunLight.castShadow = true;
        this.sunLight.shadow.mapSize.set(4096, 4096);
        this.sunLight.shadow.camera.left = -120;
        this.sunLight.shadow.camera.right = 120;
        this.sunLight.shadow.camera.top = 120;
        this.sunLight.shadow.camera.bottom = -120;
        this.sunLight.shadow.camera.near = 1;
        this.sunLight.shadow.camera.far = 300;
        this.sunLight.shadow.bias = -0.001;
        this.sunLight.shadow.normalBias = 0.02;
        this.scene.add(this.sunLight);

        // Fill light (opposite side, no shadow)
        const fill = new THREE.DirectionalLight(0xc4d7ff, 0.3);
        fill.position.set(-40, 50, -30);
        this.scene.add(fill);
    }

    setupGround() {
        const groundGeo = new THREE.PlaneGeometry(2000, 2000);
        const groundMat = new THREE.MeshStandardMaterial({
            color: 0xd4c9a8,
            roughness: 1.0,
            metalness: 0.0
        });
        this.ground = new THREE.Mesh(groundGeo, groundMat);
        this.ground.rotation.x = -Math.PI / 2;
        this.ground.receiveShadow = true;
        this.scene.add(this.ground);
    }

    setupHelpers() {
        // Grid
        this.grid = new THREE.GridHelper(200, 20, 0xcccccc, 0xe0e0e0);
        this.grid.position.y = 0.01;
        this.scene.add(this.grid);

        // Axes
        this.axes = new THREE.AxesHelper(10);
        this.scene.add(this.axes);
    }

    setupEvents() {
        const resizeObserver = new ResizeObserver(() => {
            const w = this.container.clientWidth;
            const h = this.container.clientHeight;
            this.camera.aspect = w / h;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(w, h);
        });
        resizeObserver.observe(this.container);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    // Utility: fit camera to model
    fitToModel(object3d) {
        const box = new THREE.Box3().setFromObject(object3d);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const dist = maxDim / (2 * Math.tan(this.camera.fov * Math.PI / 360));

        this.controls.target.copy(center);
        this.camera.position.copy(center);
        this.camera.position.x += dist * 0.7;
        this.camera.position.y += dist * 0.5;
        this.camera.position.z += dist * 0.7;
        this.controls.update();
    }

    // Utility: set sun position by hour
    setSunPosition(hour, latitude = 45) {
        const azimuth = (hour - 12) * 15 * Math.PI / 180;
        const altitude = Math.max(10, 60 - Math.abs(hour - 12) * 7) * Math.PI / 180;
        const dist = 100;
        this.sunLight.position.set(
            dist * Math.cos(altitude) * Math.sin(azimuth),
            dist * Math.sin(altitude),
            dist * Math.cos(altitude) * Math.cos(azimuth)
        );
    }
}

// Usage
const container = document.getElementById('viewer');
const viewer = new AECViewer(container);
```

---

## Loading AEC Model Formats

### glTF / GLB (Recommended Web Format)

```javascript
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';

// Setup Draco compression decoder (optional but recommended)
const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/');

const gltfLoader = new GLTFLoader();
gltfLoader.setDRACOLoader(dracoLoader);

// Load model
gltfLoader.load(
    'building.glb',
    (gltf) => {
        const model = gltf.scene;

        // Process materials
        model.traverse((child) => {
            if (child.isMesh) {
                child.castShadow = true;
                child.receiveShadow = true;
                // Fix metalness for architectural models
                if (child.material.metalness > 0.5) {
                    child.material.metalness = 0.1;
                    child.material.roughness = 0.8;
                }
            }
        });

        scene.add(model);
        viewer.fitToModel(model);

        // Access animations if present
        if (gltf.animations.length > 0) {
            const mixer = new THREE.AnimationMixer(model);
            gltf.animations.forEach((clip) => {
                mixer.clipAction(clip).play();
            });
        }
    },
    (progress) => {
        const pct = (progress.loaded / progress.total * 100).toFixed(1);
        console.log(`Loading: ${pct}%`);
    },
    (error) => {
        console.error('Load error:', error);
    }
);
```

### IFC via web-ifc-three

```javascript
import { IFCLoader } from 'web-ifc-three/IFCLoader';

const ifcLoader = new IFCLoader();

// Point to WASM binary (must be served)
await ifcLoader.ifcManager.setWasmPath('wasm/');

// Optional: set up web workers for async loading
await ifcLoader.ifcManager.useWebWorkers(true, 'IFCWorker.js');

// Load
ifcLoader.load('model.ifc', async (ifcModel) => {
    scene.add(ifcModel);

    // Get spatial structure (building > storey > space hierarchy)
    const tree = await ifcLoader.ifcManager.getSpatialStructure(
        ifcModel.modelID
    );
    console.log('Spatial tree:', tree);

    // Get all IfcWallStandardCase elements
    const wallType = 839788812; // IFCWALLSTANDARDCASE
    const wallIDs = await ifcLoader.ifcManager.getAllItemsOfType(
        ifcModel.modelID, wallType, false
    );
    console.log(`Found ${wallIDs.length} walls`);

    // Get properties of an element
    for (const id of wallIDs) {
        const props = await ifcLoader.ifcManager.getItemProperties(
            ifcModel.modelID, id
        );
        console.log('Wall:', props.Name?.value, props);

        // Get property sets
        const psets = await ifcLoader.ifcManager.getPropertySets(
            ifcModel.modelID, id
        );
        console.log('PropertySets:', psets);
    }
});
```

### OBJ Format

```javascript
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { MTLLoader } from 'three/addons/loaders/MTLLoader.js';

// With materials
const mtlLoader = new MTLLoader();
mtlLoader.load('model.mtl', (materials) => {
    materials.preload();

    const objLoader = new OBJLoader();
    objLoader.setMaterials(materials);
    objLoader.load('model.obj', (object) => {
        object.traverse((child) => {
            if (child.isMesh) {
                child.castShadow = true;
                child.receiveShadow = true;
            }
        });
        scene.add(object);
    });
});
```

---

## Camera and Controls Setup

### Perspective vs. Orthographic

```javascript
// Perspective (realistic view)
const perspCam = new THREE.PerspectiveCamera(
    45,       // fov
    aspect,   // aspect ratio
    0.1,      // near
    5000      // far
);

// Orthographic (architectural plans/sections)
const frustumSize = 100;
const orthoCam = new THREE.OrthographicCamera(
    frustumSize * aspect / -2,   // left
    frustumSize * aspect / 2,    // right
    frustumSize / 2,             // top
    frustumSize / -2,            // bottom
    0.1,                         // near
    5000                         // far
);

// Toggle between cameras
function switchToOrtho() {
    orthoCam.position.copy(perspCam.position);
    orthoCam.lookAt(controls.target);
    controls.object = orthoCam;
    activeCamera = orthoCam;
}
```

### Preset Camera Views

```javascript
function setTopView() {
    camera.position.set(0, 200, 0.01);
    controls.target.set(0, 0, 0);
    controls.update();
}

function setFrontView() {
    camera.position.set(0, 30, 150);
    controls.target.set(0, 30, 0);
    controls.update();
}

function setSideView() {
    camera.position.set(150, 30, 0);
    controls.target.set(0, 30, 0);
    controls.update();
}

function setIsometricView() {
    const d = 100;
    camera.position.set(d, d * 0.8, d);
    controls.target.set(0, 15, 0);
    controls.update();
}

// Smooth camera transition
function animateCamera(targetPos, targetLookAt, duration = 1000) {
    const startPos = camera.position.clone();
    const startTarget = controls.target.clone();
    const startTime = Date.now();

    function update() {
        const elapsed = Date.now() - startTime;
        const t = Math.min(elapsed / duration, 1);
        const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

        camera.position.lerpVectors(startPos, targetPos, ease);
        controls.target.lerpVectors(startTarget, targetLookAt, ease);
        controls.update();

        if (t < 1) requestAnimationFrame(update);
    }
    update();
}
```

### First-Person Walkthrough

```javascript
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';

const fpControls = new PointerLockControls(camera, renderer.domElement);
scene.add(fpControls.getObject());

// Eye height
fpControls.getObject().position.y = 1.7; // 1.7m eye height

const velocity = new THREE.Vector3();
const direction = new THREE.Vector3();
let moveForward = false, moveBackward = false;
let moveLeft = false, moveRight = false;

document.addEventListener('keydown', (e) => {
    switch (e.code) {
        case 'KeyW': moveForward = true; break;
        case 'KeyS': moveBackward = true; break;
        case 'KeyA': moveLeft = true; break;
        case 'KeyD': moveRight = true; break;
    }
});

document.addEventListener('keyup', (e) => {
    switch (e.code) {
        case 'KeyW': moveForward = false; break;
        case 'KeyS': moveBackward = false; break;
        case 'KeyA': moveLeft = false; break;
        case 'KeyD': moveRight = false; break;
    }
});

function updateWalkthrough(delta) {
    velocity.x -= velocity.x * 10.0 * delta;
    velocity.z -= velocity.z * 10.0 * delta;

    direction.z = Number(moveForward) - Number(moveBackward);
    direction.x = Number(moveRight) - Number(moveLeft);
    direction.normalize();

    const speed = 5.0; // m/s
    if (moveForward || moveBackward) velocity.z -= direction.z * speed * delta;
    if (moveLeft || moveRight) velocity.x -= direction.x * speed * delta;

    fpControls.moveRight(-velocity.x * delta);
    fpControls.moveForward(-velocity.z * delta);
}
```

---

## Lighting for Architectural Visualization

### Daylight Simulation

```javascript
function setupDaylight(scene, hour = 14, month = 6, latitude = 40) {
    // Remove existing lights
    scene.children.filter(c => c.isLight).forEach(l => scene.remove(l));

    // Calculate sun position
    const declination = 23.45 * Math.sin(2 * Math.PI * (284 + (month - 1) * 30) / 365);
    const hourAngle = (hour - 12) * 15;
    const altRad = Math.asin(
        Math.sin(latitude * Math.PI / 180) * Math.sin(declination * Math.PI / 180) +
        Math.cos(latitude * Math.PI / 180) * Math.cos(declination * Math.PI / 180) *
        Math.cos(hourAngle * Math.PI / 180)
    );
    const azRad = Math.atan2(
        -Math.sin(hourAngle * Math.PI / 180),
        Math.tan(declination * Math.PI / 180) * Math.cos(latitude * Math.PI / 180) -
        Math.sin(latitude * Math.PI / 180) * Math.cos(hourAngle * Math.PI / 180)
    );

    const altitude = altRad * 180 / Math.PI;
    const dist = 200;

    if (altitude > 0) {
        // Sun is above horizon
        const sunLight = new THREE.DirectionalLight(0xffeedd, 1.2);
        sunLight.position.set(
            dist * Math.cos(altRad) * Math.sin(azRad),
            dist * Math.sin(altRad),
            dist * Math.cos(altRad) * Math.cos(azRad)
        );
        sunLight.castShadow = true;
        sunLight.shadow.mapSize.set(4096, 4096);
        sunLight.shadow.camera.left = -150;
        sunLight.shadow.camera.right = 150;
        sunLight.shadow.camera.top = 150;
        sunLight.shadow.camera.bottom = -150;
        scene.add(sunLight);

        // Sky color based on time
        const skyIntensity = Math.max(0.2, Math.sin(altRad));
        scene.add(new THREE.HemisphereLight(
            new THREE.Color().setHSL(0.6, 0.6, 0.3 + skyIntensity * 0.4),
            new THREE.Color(0x8b7355),
            0.4
        ));
    } else {
        // Night
        scene.add(new THREE.AmbientLight(0x222244, 0.3));
    }

    // Ambient occlusion fill
    scene.add(new THREE.AmbientLight(0xffffff, 0.2));
}
```

### Interior Lighting

```javascript
// Point light (lamp / ceiling fixture)
const bulb = new THREE.PointLight(0xffeecc, 1.0, 15, 2);
bulb.position.set(5, 2.8, 5); // ceiling height
bulb.castShadow = true;
scene.add(bulb);

// Spot light (track lighting / downlight)
const spot = new THREE.SpotLight(0xffffff, 1.5, 20, Math.PI / 6, 0.5, 2);
spot.position.set(3, 3, 3);
spot.target.position.set(3, 0, 3);
spot.castShadow = true;
scene.add(spot);
scene.add(spot.target);

// Rect area light (window / skylight — no shadow)
import { RectAreaLightHelper } from 'three/addons/helpers/RectAreaLightHelper.js';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';

RectAreaLightUniformsLib.init();
const rectLight = new THREE.RectAreaLight(0xffffff, 5, 4, 3);
rectLight.position.set(0, 2.5, -5); // on wall
rectLight.lookAt(0, 2.5, 0);
scene.add(rectLight);
scene.add(new RectAreaLightHelper(rectLight));
```

---

## Material Library for AEC

### Architectural Materials

```javascript
import * as THREE from 'three';

const AECMaterials = {
    // ── Glass ──
    glass: new THREE.MeshPhysicalMaterial({
        color: 0x88ccff,
        transparent: true,
        opacity: 0.25,
        roughness: 0.0,
        metalness: 0.0,
        transmission: 0.95,
        thickness: 0.01,
        ior: 1.52,
        side: THREE.DoubleSide
    }),

    glassReflective: new THREE.MeshPhysicalMaterial({
        color: 0x445566,
        transparent: true,
        opacity: 0.4,
        roughness: 0.05,
        metalness: 0.6,
        envMapIntensity: 2.0
    }),

    glassFrosted: new THREE.MeshPhysicalMaterial({
        color: 0xeeeeff,
        transparent: true,
        opacity: 0.6,
        roughness: 0.8,
        transmission: 0.5,
        ior: 1.52
    }),

    // ── Concrete ──
    concrete: new THREE.MeshStandardMaterial({
        color: 0xb0b0b0,
        roughness: 0.95,
        metalness: 0.0,
    }),

    concreteExposed: new THREE.MeshStandardMaterial({
        color: 0x999999,
        roughness: 0.85,
        metalness: 0.0,
    }),

    concreteBoardFormed: new THREE.MeshStandardMaterial({
        color: 0xa0a0a0,
        roughness: 0.9,
        metalness: 0.0,
    }),

    // ── Steel ──
    steel: new THREE.MeshStandardMaterial({
        color: 0x888888,
        roughness: 0.3,
        metalness: 0.9,
    }),

    steelCorten: new THREE.MeshStandardMaterial({
        color: 0x8b4513,
        roughness: 0.8,
        metalness: 0.6,
    }),

    steelBrushed: new THREE.MeshStandardMaterial({
        color: 0xaaaaaa,
        roughness: 0.4,
        metalness: 0.85,
    }),

    aluminum: new THREE.MeshStandardMaterial({
        color: 0xcccccc,
        roughness: 0.2,
        metalness: 0.95
    }),

    // ── Wood ──
    woodOak: new THREE.MeshStandardMaterial({
        color: 0xc4955a,
        roughness: 0.7,
        metalness: 0.0,
    }),

    woodWalnut: new THREE.MeshStandardMaterial({
        color: 0x5c3d2e,
        roughness: 0.65,
        metalness: 0.0,
    }),

    woodPine: new THREE.MeshStandardMaterial({
        color: 0xdeb887,
        roughness: 0.75,
        metalness: 0.0,
    }),

    woodCLT: new THREE.MeshStandardMaterial({
        color: 0xd2b48c,
        roughness: 0.7,
        metalness: 0.0,
    }),

    // ── Brick ──
    brickRed: new THREE.MeshStandardMaterial({
        color: 0x8b4513,
        roughness: 0.9,
        metalness: 0.0,
    }),

    brickWhite: new THREE.MeshStandardMaterial({
        color: 0xe8dcc8,
        roughness: 0.85,
        metalness: 0.0,
    }),

    // ── Stone ──
    limestone: new THREE.MeshStandardMaterial({
        color: 0xd4c9a8,
        roughness: 0.8,
        metalness: 0.0,
    }),

    granite: new THREE.MeshStandardMaterial({
        color: 0x696969,
        roughness: 0.5,
        metalness: 0.1,
    }),

    marble: new THREE.MeshStandardMaterial({
        color: 0xf5f5f0,
        roughness: 0.15,
        metalness: 0.0,
    }),

    // ── Vegetation ──
    grass: new THREE.MeshStandardMaterial({
        color: 0x4a7c3f,
        roughness: 1.0,
        metalness: 0.0,
    }),

    treeFoliage: new THREE.MeshStandardMaterial({
        color: 0x3d6b35,
        roughness: 0.9,
        metalness: 0.0,
        side: THREE.DoubleSide
    }),

    treeTrunk: new THREE.MeshStandardMaterial({
        color: 0x5c4033,
        roughness: 0.9,
        metalness: 0.0,
    }),

    // ── Other ──
    water: new THREE.MeshPhysicalMaterial({
        color: 0x006994,
        transparent: true,
        opacity: 0.7,
        roughness: 0.0,
        metalness: 0.1,
        transmission: 0.6,
    }),

    asphalt: new THREE.MeshStandardMaterial({
        color: 0x444444,
        roughness: 0.95,
        metalness: 0.0,
    }),

    plaster: new THREE.MeshStandardMaterial({
        color: 0xf0ece0,
        roughness: 0.8,
        metalness: 0.0,
    }),

    terracotta: new THREE.MeshStandardMaterial({
        color: 0xc4663a,
        roughness: 0.85,
        metalness: 0.0,
    })
};

// Apply with texture maps for realism
function applyTexturedMaterial(mesh, texturePath, normalPath, roughnessPath) {
    const textureLoader = new THREE.TextureLoader();

    const mat = mesh.material.clone();

    if (texturePath) {
        const diffuse = textureLoader.load(texturePath);
        diffuse.wrapS = diffuse.wrapT = THREE.RepeatWrapping;
        diffuse.repeat.set(4, 4);
        mat.map = diffuse;
    }
    if (normalPath) {
        const normal = textureLoader.load(normalPath);
        normal.wrapS = normal.wrapT = THREE.RepeatWrapping;
        normal.repeat.set(4, 4);
        mat.normalMap = normal;
        mat.normalScale.set(1, 1);
    }
    if (roughnessPath) {
        const rough = textureLoader.load(roughnessPath);
        rough.wrapS = rough.wrapT = THREE.RepeatWrapping;
        rough.repeat.set(4, 4);
        mat.roughnessMap = rough;
    }
    mat.needsUpdate = true;
    mesh.material = mat;
}
```

---

## Raycasting and Object Selection

### Selection System

```javascript
class SelectionManager {
    constructor(scene, camera, renderer) {
        this.scene = scene;
        this.camera = camera;
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.selected = null;
        this.hovered = null;
        this.selectables = [];

        // Original materials cache
        this.materialCache = new Map();

        // Highlight materials
        this.hoverMat = new THREE.MeshStandardMaterial({
            color: 0x4488ff,
            emissive: 0x222244,
            transparent: true,
            opacity: 0.8
        });

        this.selectMat = new THREE.MeshStandardMaterial({
            color: 0xff8844,
            emissive: 0x442211,
        });

        // Events
        renderer.domElement.addEventListener('mousemove', (e) => this.onMouseMove(e));
        renderer.domElement.addEventListener('click', (e) => this.onClick(e));
        renderer.domElement.addEventListener('dblclick', (e) => this.onDblClick(e));
    }

    addSelectable(mesh) {
        this.selectables.push(mesh);
        this.materialCache.set(mesh.uuid, mesh.material);
    }

    onMouseMove(event) {
        const rect = event.target.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.selectables, true);

        // Reset previous hover
        if (this.hovered && this.hovered !== this.selected) {
            this.hovered.material = this.materialCache.get(this.hovered.uuid);
        }

        if (intersects.length > 0) {
            const obj = intersects[0].object;
            if (obj !== this.selected) {
                this.hovered = obj;
                obj.material = this.hoverMat;
            }
            event.target.style.cursor = 'pointer';
        } else {
            this.hovered = null;
            event.target.style.cursor = 'default';
        }
    }

    onClick(event) {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.selectables, true);

        // Deselect previous
        if (this.selected) {
            this.selected.material = this.materialCache.get(this.selected.uuid);
        }

        if (intersects.length > 0) {
            this.selected = intersects[0].object;
            this.selected.material = this.selectMat;

            // Dispatch custom event with metadata
            const detail = {
                object: this.selected,
                name: this.selected.name,
                userData: this.selected.userData,
                point: intersects[0].point,
                face: intersects[0].face,
                distance: intersects[0].distance
            };
            window.dispatchEvent(new CustomEvent('objectSelected', { detail }));
        } else {
            this.selected = null;
            window.dispatchEvent(new CustomEvent('objectDeselected'));
        }
    }

    onDblClick(event) {
        if (this.selected) {
            // Zoom to selected object
            const box = new THREE.Box3().setFromObject(this.selected);
            const center = box.getCenter(new THREE.Vector3());
            // ... animate camera to center on object
        }
    }
}
```

---

## Measurement Tools Implementation

```javascript
class MeasurementTool {
    constructor(scene, camera, renderer) {
        this.scene = scene;
        this.camera = camera;
        this.renderer = renderer;
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.points = [];
        this.measurements = [];
        this.active = false;

        // Visual elements
        this.pointMaterial = new THREE.MeshBasicMaterial({ color: 0xff0000 });
        this.lineMaterial = new THREE.LineBasicMaterial({ color: 0xff4444, linewidth: 2 });
    }

    activate() {
        this.active = true;
        this.points = [];
        this.renderer.domElement.addEventListener('click', this.onMeasureClick);
        this.renderer.domElement.style.cursor = 'crosshair';
    }

    deactivate() {
        this.active = false;
        this.renderer.domElement.removeEventListener('click', this.onMeasureClick);
        this.renderer.domElement.style.cursor = 'default';
    }

    onMeasureClick = (event) => {
        const rect = event.target.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(
            this.scene.children, true
        );

        if (intersects.length > 0) {
            const point = intersects[0].point;
            this.points.push(point);

            // Add point marker
            const sphere = new THREE.Mesh(
                new THREE.SphereGeometry(0.15),
                this.pointMaterial
            );
            sphere.position.copy(point);
            this.scene.add(sphere);

            if (this.points.length === 2) {
                // Draw line
                const geometry = new THREE.BufferGeometry().setFromPoints(this.points);
                const line = new THREE.Line(geometry, this.lineMaterial);
                this.scene.add(line);

                // Calculate distance
                const distance = this.points[0].distanceTo(this.points[1]);

                // Add label using CSS2D or sprite
                this.addDistanceLabel(
                    this.points[0].clone().lerp(this.points[1], 0.5),
                    distance
                );

                this.measurements.push({
                    start: this.points[0],
                    end: this.points[1],
                    distance: distance
                });

                // Reset for next measurement
                this.points = [];
            }
        }
    }

    addDistanceLabel(position, distance) {
        // Using HTML overlay approach
        const label = document.createElement('div');
        label.className = 'measurement-label';
        label.textContent = `${distance.toFixed(2)} m`;
        label.style.cssText = `
            position: absolute; background: rgba(0,0,0,0.8);
            color: #fff; padding: 2px 8px; border-radius: 3px;
            font-size: 12px; pointer-events: none;
        `;
        document.body.appendChild(label);

        // Update position each frame
        const updateLabel = () => {
            const projected = position.clone().project(this.camera);
            const rect = this.renderer.domElement.getBoundingClientRect();
            label.style.left = ((projected.x + 1) / 2 * rect.width + rect.left) + 'px';
            label.style.top = ((-projected.y + 1) / 2 * rect.height + rect.top) + 'px';
            if (projected.z > 1) label.style.display = 'none';
            else label.style.display = 'block';
            requestAnimationFrame(updateLabel);
        };
        updateLabel();
    }

    clearAll() {
        this.measurements = [];
        // Remove measurement objects from scene
    }
}
```

---

## Section Plane Implementation

```javascript
class SectionPlane {
    constructor(scene, renderer) {
        this.scene = scene;
        this.renderer = renderer;
        this.clippingPlanes = [];
        this.helpers = [];
        this.active = false;

        renderer.localClippingEnabled = true;
    }

    addHorizontalSection(height) {
        const plane = new THREE.Plane(new THREE.Vector3(0, -1, 0), height);
        this.clippingPlanes.push(plane);

        // Apply to all meshes
        this.scene.traverse((child) => {
            if (child.isMesh) {
                child.material = child.material.clone();
                child.material.clippingPlanes = this.clippingPlanes;
                child.material.clipShadows = true;
            }
        });

        // Add section plane helper
        const helperGeo = new THREE.PlaneGeometry(200, 200);
        const helperMat = new THREE.MeshBasicMaterial({
            color: 0xff4444,
            transparent: true,
            opacity: 0.1,
            side: THREE.DoubleSide,
            depthWrite: false
        });
        const helper = new THREE.Mesh(helperGeo, helperMat);
        helper.rotation.x = -Math.PI / 2;
        helper.position.y = height;
        this.scene.add(helper);
        this.helpers.push(helper);

        return plane;
    }

    addVerticalSection(position, normal) {
        const plane = new THREE.Plane(normal.normalize(), -position);
        this.clippingPlanes.push(plane);

        this.scene.traverse((child) => {
            if (child.isMesh) {
                child.material = child.material.clone();
                child.material.clippingPlanes = this.clippingPlanes;
                child.material.clipShadows = true;
                child.material.side = THREE.DoubleSide;
            }
        });

        return plane;
    }

    setSectionHeight(index, height) {
        if (index < this.clippingPlanes.length) {
            this.clippingPlanes[index].constant = height;
            if (index < this.helpers.length) {
                this.helpers[index].position.y = height;
            }
        }
    }

    toggleSection(index) {
        if (index < this.clippingPlanes.length) {
            const plane = this.clippingPlanes[index];
            // Flip normal to toggle
            plane.negate();
        }
    }

    removeAll() {
        this.clippingPlanes.length = 0;
        this.helpers.forEach(h => this.scene.remove(h));
        this.helpers = [];
        this.scene.traverse((child) => {
            if (child.isMesh) {
                child.material.clippingPlanes = [];
            }
        });
    }
}
```

---

## Annotation and Labeling

```javascript
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

// Setup CSS2D renderer (overlays HTML on 3D scene)
const labelRenderer = new CSS2DRenderer();
labelRenderer.setSize(window.innerWidth, window.innerHeight);
labelRenderer.domElement.style.position = 'absolute';
labelRenderer.domElement.style.top = '0px';
labelRenderer.domElement.style.pointerEvents = 'none';
document.body.appendChild(labelRenderer.domElement);

// In animation loop:
// labelRenderer.render(scene, camera);

// Create label
function createLabel(text, position, className = 'label-default') {
    const div = document.createElement('div');
    div.className = className;
    div.textContent = text;
    div.style.cssText = `
        background: rgba(255,255,255,0.9);
        color: #333;
        padding: 4px 10px;
        border-radius: 4px;
        font-family: 'Helvetica Neue', sans-serif;
        font-size: 11px;
        border: 1px solid #ccc;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        white-space: nowrap;
    `;
    const label = new CSS2DObject(div);
    label.position.copy(position);
    return label;
}

// Room labels
function labelRooms(model, rooms) {
    rooms.forEach(room => {
        const label = createLabel(
            `${room.name}\n${room.area.toFixed(1)} m²`,
            new THREE.Vector3(room.x, room.z + 0.1, room.y)
        );
        model.add(label);
    });
}

// Level markers
function addLevelMarkers(levels) {
    levels.forEach((level, i) => {
        const label = createLabel(
            `Level ${i}: ${level.name} (${level.elevation.toFixed(1)}m)`,
            new THREE.Vector3(-20, level.elevation, 0)
        );
        scene.add(label);
    });
}

// Sprite-based labels (always face camera, rendered in 3D)
function createSpriteLabel(text, fontSize = 24) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 512;
    canvas.height = 128;

    ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.font = `${fontSize}px Arial`;
    ctx.fillStyle = '#333';
    ctx.textAlign = 'center';
    ctx.fillText(text, canvas.width / 2, canvas.height / 2 + fontSize / 3);

    const texture = new THREE.CanvasTexture(canvas);
    const spriteMat = new THREE.SpriteMaterial({ map: texture });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(10, 2.5, 1);
    return sprite;
}
```

---

## Performance Optimization for Large AEC Models

### Instanced Meshes (Repeated Elements)

```javascript
// Instead of adding 1000 individual column meshes, use instancing
const columnGeo = new THREE.CylinderGeometry(0.3, 0.3, 4, 12);
const columnMat = new THREE.MeshStandardMaterial({ color: 0xcccccc });

const instanceCount = 200;
const instancedMesh = new THREE.InstancedMesh(columnGeo, columnMat, instanceCount);
instancedMesh.castShadow = true;

const dummy = new THREE.Object3D();
let idx = 0;

for (let x = 0; x < 20; x++) {
    for (let y = 0; y < 10; y++) {
        dummy.position.set(x * 8, 2, y * 8);
        dummy.updateMatrix();
        instancedMesh.setMatrixAt(idx, dummy.matrix);
        idx++;
    }
}
instancedMesh.instanceMatrix.needsUpdate = true;
scene.add(instancedMesh);
```

### Level of Detail (LOD)

```javascript
const lod = new THREE.LOD();

// High detail (close)
const highGeo = new THREE.BoxGeometry(10, 30, 10, 4, 12, 4);
lod.addLevel(new THREE.Mesh(highGeo, material), 0);

// Medium detail
const medGeo = new THREE.BoxGeometry(10, 30, 10, 2, 4, 2);
lod.addLevel(new THREE.Mesh(medGeo, material), 50);

// Low detail (far)
const lowGeo = new THREE.BoxGeometry(10, 30, 10, 1, 1, 1);
lod.addLevel(new THREE.Mesh(lowGeo, material), 150);

scene.add(lod);
```

### Geometry Merging

```javascript
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

// Merge many geometries sharing the same material into one draw call
const geometries = [];
const matrix = new THREE.Matrix4();

for (let i = 0; i < 500; i++) {
    const geo = new THREE.BoxGeometry(1, 1, 1);
    matrix.makeTranslation(
        Math.random() * 100,
        Math.random() * 50,
        Math.random() * 100
    );
    geo.applyMatrix4(matrix);
    geometries.push(geo);
}

const merged = mergeGeometries(geometries);
const mergedMesh = new THREE.Mesh(merged, material);
scene.add(mergedMesh); // 1 draw call instead of 500
```

### Frustum Culling and Occlusion

```javascript
// Three.js enables frustum culling by default on all Mesh objects
// For large scenes, add manual spatial partitioning:

class OctreePartition {
    constructor(scene, maxDepth = 5) {
        this.scene = scene;
        this.bounds = new THREE.Box3().setFromObject(scene);
        // ... build octree from scene objects
    }

    getVisibleObjects(camera) {
        const frustum = new THREE.Frustum();
        const projMatrix = new THREE.Matrix4();
        projMatrix.multiplyMatrices(
            camera.projectionMatrix,
            camera.matrixWorldInverse
        );
        frustum.setFromProjectionMatrix(projMatrix);

        // Traverse octree, test nodes against frustum
        // Return only objects in visible nodes
    }
}

// Progressive loading
function loadModelProgressive(url, scene) {
    const loader = new GLTFLoader();
    loader.load(url, (gltf) => {
        const model = gltf.scene;

        // Show bounding box immediately
        const box = new THREE.Box3().setFromObject(model);
        const boxHelper = new THREE.Box3Helper(box, 0x888888);
        scene.add(boxHelper);

        // Add meshes one at a time to avoid jank
        const meshes = [];
        model.traverse(child => {
            if (child.isMesh) meshes.push(child);
        });

        let i = 0;
        function addNext() {
            if (i < meshes.length) {
                scene.add(meshes[i]);
                i++;
                requestAnimationFrame(addNext);
            } else {
                scene.remove(boxHelper);
            }
        }
        addNext();
    });
}
```

---

## IFC.js / web-ifc Usage Guide

### Full IFC Viewer Setup

```javascript
import { IfcViewerAPI } from 'web-ifc-viewer';
import { Color } from 'three';

// Create viewer
const container = document.getElementById('viewer');
const viewer = new IfcViewerAPI({
    container,
    backgroundColor: new Color(0xffffff)
});

// Add helpers
viewer.grid.setGrid(50, 50);
viewer.axes.setAxes();

// Configure clipping planes
viewer.clipper.active = true;

// Load model
async function loadIFC(url) {
    const model = await viewer.IFC.loadIfcUrl(url);

    // Generate shadow
    await viewer.shadowDropper.renderShadow(model.modelID);

    // Fit camera
    viewer.context.ifcCamera.cameraControls.fitToSphere(model, true);

    return model;
}

// Highlight on hover
window.onmousemove = () => viewer.IFC.selector.prePickIfcItem();

// Select on click
window.onclick = async () => {
    const result = await viewer.IFC.selector.pickIfcItem();
    if (result) {
        const { modelID, id } = result;
        const props = await viewer.IFC.getProperties(modelID, id, true, true);
        displayProperties(props);
    }
};

// Double click to highlight
window.ondblclick = async () => {
    const result = await viewer.IFC.selector.highlightIfcItem();
    if (result) {
        // Isolate element
        viewer.IFC.selector.unpickIfcItems();
    }
};

// Filter by IFC type
async function showOnlyWalls(modelID) {
    const wallType = 839788812; // IFCWALLSTANDARDCASE
    const wallIDs = await viewer.IFC.loader.ifcManager.getAllItemsOfType(
        modelID, wallType, false
    );

    // Hide everything
    viewer.IFC.loader.ifcManager.removeSubset(modelID);

    // Show only walls
    const wallSubset = viewer.IFC.loader.ifcManager.createSubset({
        modelID,
        ids: wallIDs,
        scene: viewer.context.getScene(),
        removePrevious: true,
        customID: 'walls-only'
    });
}

// Export properties to JSON
async function exportProperties(modelID) {
    const allIDs = await viewer.IFC.loader.ifcManager.getAllItemsOfType(
        modelID, 0, false // 0 = all types
    );

    const data = [];
    for (const id of allIDs) {
        const props = await viewer.IFC.getProperties(modelID, id, true);
        data.push(props);
    }

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ifc-properties.json';
    a.click();
}
```

---

## Speckle Viewer API

```javascript
import { Viewer, DefaultViewerParams, SpeckleLoader } from '@speckle/viewer';

async function initSpeckleViewer(containerEl, streamUrl) {
    const params = DefaultViewerParams;
    params.showStats = false;

    const viewer = new Viewer(containerEl, params);
    await viewer.init();

    // Load from Speckle stream
    const loader = new SpeckleLoader(viewer.getWorldTree(), streamUrl, '');
    await viewer.loadObject(loader, true);

    // Camera
    viewer.zoom(null, 1.2, true); // zoom to extents

    return viewer;
}

// Embed in HTML
// <div id="speckle-viewer" style="width:100%;height:600px;"></div>
const container = document.getElementById('speckle-viewer');
const viewer = await initSpeckleViewer(container,
    'https://speckle.xyz/streams/abc123/objects/def456');
```

---

## AR/VR Setup (WebXR)

```javascript
import { VRButton } from 'three/addons/webxr/VRButton.js';
import { ARButton } from 'three/addons/webxr/ARButton.js';
import { XRControllerModelFactory } from 'three/addons/webxr/XRControllerModelFactory.js';

// Enable WebXR
renderer.xr.enabled = true;

// VR Mode
document.body.appendChild(VRButton.createButton(renderer));

// AR Mode (alternative)
// document.body.appendChild(ARButton.createButton(renderer, {
//     requiredFeatures: ['hit-test'],
//     optionalFeatures: ['dom-overlay'],
//     domOverlay: { root: document.body }
// }));

// Controllers
const controllerModelFactory = new XRControllerModelFactory();

const controller1 = renderer.xr.getController(0);
controller1.addEventListener('selectstart', onSelectStart);
controller1.addEventListener('selectend', onSelectEnd);
scene.add(controller1);

const grip1 = renderer.xr.getControllerGrip(0);
grip1.add(controllerModelFactory.createControllerModel(grip1));
scene.add(grip1);

// Teleportation
function onSelectStart(event) {
    const controller = event.target;
    const raycaster = new THREE.Raycaster();
    const tempMatrix = new THREE.Matrix4();
    tempMatrix.identity().extractRotation(controller.matrixWorld);

    raycaster.ray.origin.setFromMatrixPosition(controller.matrixWorld);
    raycaster.ray.direction.set(0, 0, -1).applyMatrix4(tempMatrix);

    const intersects = raycaster.intersectObjects([ground]);
    if (intersects.length > 0) {
        // Move user to hit point
        const baseReferenceSpace = renderer.xr.getReferenceSpace();
        const offsetPosition = intersects[0].point;
        const transform = new XRRigidTransform(offsetPosition);
        const newSpace = baseReferenceSpace.getOffsetReferenceSpace(transform);
        renderer.xr.setReferenceSpace(newSpace);
    }
}

// Scale model for VR (real-world scale)
function setRealWorldScale(model, modelUnit = 'mm') {
    const scaleFactor = {
        'mm': 0.001,
        'cm': 0.01,
        'm': 1.0,
        'ft': 0.3048,
        'in': 0.0254
    }[modelUnit] || 1.0;

    model.scale.setScalar(scaleFactor);
}

// XR animation loop (replaces standard animate)
renderer.setAnimationLoop((time, frame) => {
    controls.update();
    renderer.render(scene, camera);
});
```

---

## Responsive Viewer Layout

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AEC Model Viewer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Helvetica Neue', Arial, sans-serif; overflow: hidden; }

        .app-layout {
            display: grid;
            grid-template-columns: 280px 1fr 320px;
            grid-template-rows: 48px 1fr 36px;
            height: 100vh;
        }

        .header {
            grid-column: 1 / -1;
            background: #2c3e50;
            color: white;
            display: flex;
            align-items: center;
            padding: 0 16px;
        }

        .sidebar-left {
            grid-row: 2;
            background: #f8f8f8;
            border-right: 1px solid #ddd;
            overflow-y: auto;
            padding: 12px;
        }

        .viewer-container {
            grid-row: 2;
            position: relative;
            background: #e8e8e8;
        }

        .viewer-container canvas {
            width: 100% !important;
            height: 100% !important;
            display: block;
        }

        .sidebar-right {
            grid-row: 2;
            background: #f8f8f8;
            border-left: 1px solid #ddd;
            overflow-y: auto;
            padding: 12px;
        }

        .status-bar {
            grid-column: 1 / -1;
            background: #ecf0f1;
            border-top: 1px solid #ddd;
            display: flex;
            align-items: center;
            padding: 0 12px;
            font-size: 12px;
            color: #666;
        }

        /* Toolbar */
        .toolbar {
            position: absolute;
            top: 12px;
            left: 12px;
            display: flex;
            flex-direction: column;
            gap: 4px;
            z-index: 10;
        }

        .toolbar button {
            width: 36px;
            height: 36px;
            border: 1px solid #ccc;
            background: rgba(255,255,255,0.95);
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }

        .toolbar button:hover {
            background: #e3f2fd;
            border-color: #2196f3;
        }

        .toolbar button.active {
            background: #2196f3;
            color: white;
            border-color: #1565c0;
        }

        /* Properties panel */
        .property-group {
            margin-bottom: 16px;
        }

        .property-group h3 {
            font-size: 13px;
            color: #555;
            border-bottom: 1px solid #ddd;
            padding-bottom: 4px;
            margin-bottom: 8px;
        }

        .property-row {
            display: flex;
            justify-content: space-between;
            padding: 3px 0;
            font-size: 12px;
        }

        .property-key { color: #888; }
        .property-value { color: #333; font-weight: 500; }

        /* Responsive: collapse sidebars on small screens */
        @media (max-width: 1024px) {
            .app-layout {
                grid-template-columns: 1fr;
            }
            .sidebar-left, .sidebar-right {
                display: none;
            }
        }

        @media (max-width: 768px) {
            .header { padding: 0 8px; font-size: 14px; }
            .toolbar { top: 8px; left: 8px; }
            .toolbar button { width: 32px; height: 32px; }
        }
    </style>
</head>
<body>
    <div class="app-layout">
        <div class="header">
            <strong>AEC Model Viewer</strong>
            <span style="margin-left:auto;font-size:13px;">model.ifc</span>
        </div>

        <div class="sidebar-left">
            <h3 style="font-size:14px;margin-bottom:12px;">Model Tree</h3>
            <div id="model-tree">
                <!-- Populated dynamically from IFC spatial structure -->
            </div>
        </div>

        <div class="viewer-container" id="viewer-container">
            <div class="toolbar">
                <button id="btn-select" title="Select">S</button>
                <button id="btn-measure" title="Measure">M</button>
                <button id="btn-section" title="Section">X</button>
                <button id="btn-top" title="Top View">T</button>
                <button id="btn-front" title="Front View">F</button>
                <button id="btn-fit" title="Fit All">Z</button>
            </div>
        </div>

        <div class="sidebar-right">
            <h3 style="font-size:14px;margin-bottom:12px;">Properties</h3>
            <div id="properties-panel">
                <div class="property-group">
                    <h3>Identity</h3>
                    <div class="property-row">
                        <span class="property-key">Name</span>
                        <span class="property-value" id="prop-name">—</span>
                    </div>
                    <div class="property-row">
                        <span class="property-key">Type</span>
                        <span class="property-value" id="prop-type">—</span>
                    </div>
                    <div class="property-row">
                        <span class="property-key">GUID</span>
                        <span class="property-value" id="prop-guid">—</span>
                    </div>
                </div>
                <div class="property-group">
                    <h3>Dimensions</h3>
                    <div class="property-row">
                        <span class="property-key">Width</span>
                        <span class="property-value" id="prop-width">—</span>
                    </div>
                    <div class="property-row">
                        <span class="property-key">Height</span>
                        <span class="property-value" id="prop-height">—</span>
                    </div>
                    <div class="property-row">
                        <span class="property-key">Area</span>
                        <span class="property-value" id="prop-area">—</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="status-bar">
            <span id="status-text">Ready</span>
            <span style="margin-left:auto;" id="status-stats">—</span>
        </div>
    </div>

    <script type="module">
        import { AECViewer } from './viewer.js';
        const container = document.getElementById('viewer-container');
        const viewer = new AECViewer(container);

        // Update stats
        function updateStats() {
            const info = viewer.renderer.info;
            document.getElementById('status-stats').textContent =
                `Triangles: ${info.render.triangles.toLocaleString()} | ` +
                `Draw calls: ${info.render.calls} | ` +
                `Textures: ${info.memory.textures}`;
            requestAnimationFrame(updateStats);
        }
        updateStats();
    </script>
</body>
</html>
```

---

*This reference covers the complete web 3D development ecosystem for AEC applications. For Python/Rhino scripting, see `python-rhino-reference.md`. For C#/Grasshopper development, see `csharp-grasshopper.md`.*
