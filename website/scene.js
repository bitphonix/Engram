import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

// ── Renderer ──
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;

const container = document.getElementById('webgl-container');
if (container) {
  container.appendChild(renderer.domElement);
}

// ── Scene ──
const scene = new THREE.Scene();
// removed opaque background so it blends with CSS radially
// scene.background = new THREE.Color(0x080810);
scene.fog = new THREE.FogExp2(0x080810, 0.18);

// ── Camera ──
const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, 1.2, 4.2);

// ── Interactive Cursor Tracking ──
const targetMouse = new THREE.Vector2(0, 0);
const smoothMouse = new THREE.Vector2(0, 0);
let orbitAngle = 0;

window.addEventListener('mousemove', (e) => {
  targetMouse.x = (e.clientX / window.innerWidth) * 2 - 1;
  targetMouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
});

// ── Lighting ──
const ambientLight = new THREE.AmbientLight(0x1a0a2e, 1.2);
ambientLight.name = 'ambientLight';
scene.add(ambientLight);

const mainLight = new THREE.DirectionalLight(0xffffff, 0.6);
mainLight.name = 'mainLight';
mainLight.position.set(3, 5, 3);
mainLight.castShadow = true;
mainLight.shadow.mapSize.set(1024, 1024);
mainLight.shadow.camera.near = 0.1;
mainLight.shadow.camera.far = 20;
mainLight.shadow.camera.left = -3;
mainLight.shadow.camera.right = 3;
mainLight.shadow.camera.top = 3;
mainLight.shadow.camera.bottom = -3;
mainLight.shadow.bias = -0.001;
scene.add(mainLight);

const tealFill = new THREE.PointLight(0x00ffee, 3.5, 6);
tealFill.name = 'tealFill';
tealFill.position.set(-2, 1, -1);
scene.add(tealFill);

const pinkFill = new THREE.PointLight(0xff00aa, 3.0, 6);
pinkFill.name = 'pinkFill';
pinkFill.position.set(2, -1, 1);
scene.add(pinkFill);

const orangeFill = new THREE.PointLight(0xff6600, 2.5, 5);
orangeFill.name = 'orangeFill';
orangeFill.position.set(0, 2, 2);
scene.add(orangeFill);

// ── Ground / Metallic Surface ──
const groundGeo = new THREE.PlaneGeometry(20, 20);
const groundMat = new THREE.MeshStandardMaterial({
  color: 0x0a0a12,
  metalness: 0.92,
  roughness: 0.15,
  envMapIntensity: 1.0
});
const ground = new THREE.Mesh(groundGeo, groundMat);
ground.name = 'ground';
ground.rotation.x = -Math.PI / 2;
ground.position.y = -1.5;
ground.receiveShadow = true;
scene.add(ground);

// ── Underglow ──
const underglowLight = new THREE.PointLight(0x6600ff, 4.0, 3.5);
underglowLight.name = 'underglowLight';
underglowLight.position.set(0, -1.42, 0);
scene.add(underglowLight);

const underglowGeo = new THREE.CircleGeometry(0.9, 64);
const underglowMat = new THREE.MeshBasicMaterial({
  color: 0x5500ee,
  transparent: true,
  opacity: 0.18,
  depthWrite: false,
  blending: THREE.AdditiveBlending
});
const underglowDisc = new THREE.Mesh(underglowGeo, underglowMat);
underglowDisc.name = 'underglowDisc';
underglowDisc.rotation.x = -Math.PI / 2;
underglowDisc.position.y = -1.49;
scene.add(underglowDisc);

// ── Frosted Glass Cube ──
const cubeSize = 2.2;

// Custom chromatic aberration frosted glass shader
const frostGlassVS = `
  varying vec3 vWorldPos;
  varying vec3 vNormal;
  varying vec3 vViewPos;
  void main() {
    vec4 wp = modelMatrix * vec4(position, 1.0);
    vWorldPos = wp.xyz;
    vNormal = normalize(normalMatrix * normal);
    vViewPos = (modelViewMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const frostGlassFS = `
  precision highp float;
  varying vec3 vWorldPos;
  varying vec3 vNormal;
  varying vec3 vViewPos;
  uniform float uTime;
  uniform vec3 uCamPos;

  float hash(vec3 p) {
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
  }

  float noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(mix(hash(i), hash(i+vec3(1,0,0)), f.x),
          mix(hash(i+vec3(0,1,0)), hash(i+vec3(1,1,0)), f.x), f.y),
      mix(mix(hash(i+vec3(0,0,1)), hash(i+vec3(1,0,1)), f.x),
          mix(hash(i+vec3(0,1,1)), hash(i+vec3(1,1,1)), f.x), f.y), f.z
    );
  }

  void main() {
    vec3 viewDir = normalize(uCamPos - vWorldPos);
    float fresnel = pow(1.0 - abs(dot(vNormal, viewDir)), 3.5);

    // Frost noise
    float frostN = noise(vWorldPos * 8.0 + uTime * 0.05);
    float frostN2 = noise(vWorldPos * 20.0 - uTime * 0.03);
    float frost = frostN * 0.6 + frostN2 * 0.4;

    // Chromatic aberration at edges
    float aberration = fresnel * 0.9;
    vec3 chromaR = vec3(0.15 + aberration * 0.6, 0.0, 0.02);
    vec3 chromaG = vec3(0.0, 0.15 + aberration * 0.2, 0.15);
    vec3 chromaB = vec3(0.02, 0.0, 0.18 + aberration * 0.8);

    vec3 glassColor = chromaR * 0.3 + chromaG * 0.3 + chromaB * 0.4;
    glassColor += vec3(0.6, 0.8, 1.0) * fresnel * 0.5;
    glassColor += vec3(0.4, 0.2, 0.8) * frost * 0.12;
    glassColor += vec3(0.0, 1.0, 0.9) * fresnel * fresnel * 0.3;

    float alpha = 0.08 + fresnel * 0.35 + frost * 0.04;
    alpha = clamp(alpha, 0.0, 0.72);

    gl_FragColor = vec4(glassColor, alpha);
  }
`;

const glassMat = new THREE.ShaderMaterial({
  vertexShader: frostGlassVS,
  fragmentShader: frostGlassFS,
  uniforms: {
    uTime: { value: 0 },
    uCamPos: { value: camera.position }
  },
  transparent: true,
  side: THREE.DoubleSide,
  depthWrite: false,
  blending: THREE.NormalBlending
});

// Create cube faces manually so edges render correctly
const cubeGeo = new THREE.BoxGeometry(cubeSize, cubeSize, cubeSize);
const glassCube = new THREE.Mesh(cubeGeo, glassMat);
glassCube.name = 'glassCube';
scene.add(glassCube);

// Cube wireframe edges with glow
const edgesGeo = new THREE.EdgesGeometry(new THREE.BoxGeometry(cubeSize, cubeSize, cubeSize));
const edgeMat = new THREE.LineBasicMaterial({
  color: 0x00ffee,
  transparent: true,
  opacity: 0.55,
  blending: THREE.AdditiveBlending
});
const cubeEdges = new THREE.LineSegments(edgesGeo, edgeMat);
cubeEdges.name = 'cubeEdges';
scene.add(cubeEdges);

// Thick glow edges (slightly larger)
const edgesGeo2 = new THREE.EdgesGeometry(new THREE.BoxGeometry(cubeSize * 1.002, cubeSize * 1.002, cubeSize * 1.002));
const edgeMat2 = new THREE.LineBasicMaterial({
  color: 0xaa44ff,
  transparent: true,
  opacity: 0.22,
  blending: THREE.AdditiveBlending
});
const cubeEdges2 = new THREE.LineSegments(edgesGeo2, edgeMat2);
cubeEdges2.name = 'cubeEdges2';
scene.add(cubeEdges2);

// ── Crystal geometries pool ──
const crystalGeos = [
  new THREE.OctahedronGeometry(1, 0),
  new THREE.TetrahedronGeometry(1, 0),
  new THREE.IcosahedronGeometry(1, 0),
  new THREE.DodecahedronGeometry(1, 0),
  new THREE.OctahedronGeometry(1, 1),
];

const CRYSTAL_COUNT = 28;
const HALF = cubeSize / 2 - 0.18;

// Vaporwave palette
const crystalColors = [
  0x00ffee, // electric teal
  0xff00aa, // hot pink
  0xff6600, // atomic orange
  0xaa00ff, // deep violet
  0x00ff88, // neon green
  0xff0066, // crimson pink
  0x0099ff, // ice blue
];

// Crystal state
const crystals = [];
const crystalGroup = new THREE.Group();
crystalGroup.name = 'crystalGroup';
scene.add(crystalGroup);

// Crystal shader for glowing crystals
const crystalVS = `
  varying vec3 vNormal;
  varying vec3 vWorldPos;
  varying vec2 vUv;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vec4 wp = modelMatrix * vec4(position, 1.0);
    vWorldPos = wp.xyz;
    vUv = uv;
    gl_Position = projectionMatrix * viewMatrix * wp;
  }
`;

const crystalFS = `
  precision highp float;
  varying vec3 vNormal;
  varying vec3 vWorldPos;
  varying vec2 vUv;
  uniform vec3 uColor;
  uniform float uTime;
  uniform float uPhase;
  uniform float uGlow;
  uniform vec3 uCamPos;

  void main() {
    vec3 viewDir = normalize(uCamPos - vWorldPos);
    float fresnel = pow(1.0 - abs(dot(vNormal, viewDir)), 2.2);

    float pulse = 0.75 + 0.25 * sin(uTime * 3.0 + uPhase);
    vec3 baseCol = uColor * pulse;
    vec3 glowCol = baseCol + vec3(0.3) * fresnel;

    // Interior glow
    float interior = 1.0 - fresnel;
    vec3 finalCol = mix(baseCol * 0.4, glowCol, fresnel);
    finalCol += uColor * uGlow * 0.6 * pulse;
    finalCol += vec3(1.0) * pow(fresnel, 4.0) * 1.5;

    float alpha = 0.55 + fresnel * 0.35 + uGlow * 0.1;
    gl_FragColor = vec4(finalCol, alpha);
  }
`;

function makeCrystalMaterial(colorHex, phase) {
  return new THREE.ShaderMaterial({
    vertexShader: crystalVS,
    fragmentShader: crystalFS,
    uniforms: {
      uColor: { value: new THREE.Color(colorHex) },
      uTime: { value: 0 },
      uPhase: { value: phase },
      uGlow: { value: 0.5 },
      uCamPos: { value: camera.position }
    },
    transparent: true,
    side: THREE.DoubleSide,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  });
}

// Spawn crystals
for (let i = 0; i < CRYSTAL_COUNT; i++) {
  const colorHex = crystalColors[i % crystalColors.length];
  const geoIdx = i % crystalGeos.length;
  const geo = crystalGeos[geoIdx];
  const scale = 0.04 + Math.random() * 0.14;
  const mat = makeCrystalMaterial(colorHex, Math.random() * Math.PI * 2);
  const mesh = new THREE.Mesh(geo, mat);
  mesh.name = `crystal_${i}`;
  mesh.castShadow = false;

  // Random start position inside cube
  const startPos = new THREE.Vector3(
    (Math.random() - 0.5) * 0.3,
    (Math.random() - 0.5) * 0.3,
    (Math.random() - 0.5) * 0.3
  );

  // Target settled position
  const targetPos = new THREE.Vector3(
    (Math.random() - 0.5) * 2 * HALF,
    (Math.random() - 0.5) * 2 * HALF,
    (Math.random() - 0.5) * 2 * HALF
  );

  const velocity = new THREE.Vector3(
    (Math.random() - 0.5) * 0.04,
    (Math.random() - 0.5) * 0.04,
    (Math.random() - 0.5) * 0.04
  );

  mesh.scale.setScalar(scale);
  mesh.position.copy(startPos);
  crystalGroup.add(mesh);

  crystals.push({
    mesh,
    mat,
    startPos: startPos.clone(),
    targetPos: targetPos.clone(),
    currentPos: startPos.clone(),
    velocity,
    scale,
    rotSpeed: new THREE.Vector3(
      (Math.random() - 0.5) * 2,
      (Math.random() - 0.5) * 2,
      (Math.random() - 0.5) * 2
    ),
    phase: Math.random() * Math.PI * 2,
    colorHex,
    explosionTime: 0.3 + Math.random() * 0.8, // stagger explosion
    settled: false,
    settledTime: -1,
    orbitRadius: 0.0,
    orbitAngle: Math.random() * Math.PI * 2,
    orbitSpeed: (Math.random() - 0.5) * 0.6,
    orbitAxis: new THREE.Vector3(Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5).normalize()
  });
}

// ── Neural web laser lines ──
const MAX_CONNECTIONS = 60;
const CONNECTION_DISTANCE = 1.1;

// Line geometry for neural connections
const linePositions = new Float32Array(MAX_CONNECTIONS * 6); // 2 points * 3 coords per line
const lineGeometry = new THREE.BufferGeometry();
lineGeometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));

const laserVS = `
  attribute vec3 position;
  uniform mat4 modelViewMatrix;
  uniform mat4 projectionMatrix;
  void main() {
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

// Use LineSegments with per-segment color via instancing approach
// Instead use a custom shader on a BufferGeometry with many line segments
const laserLineMat = new THREE.LineBasicMaterial({
  color: 0x00ffee,
  transparent: true,
  opacity: 0.55,
  blending: THREE.AdditiveBlending,
  depthWrite: false,
  vertexColors: true
});

const laserColors = new Float32Array(MAX_CONNECTIONS * 6); // 2 verts per segment
lineGeometry.setAttribute('color', new THREE.BufferAttribute(laserColors, 3));

const laserLines = new THREE.LineSegments(lineGeometry, laserLineMat);
laserLines.name = 'laserLines';
laserLines.frustumCulled = false;
scene.add(laserLines);

// ── Node glow spheres at connection hubs ──
const NODE_COUNT = 12;
const nodeGeo = new THREE.SphereGeometry(0.03, 8, 8);
const nodeMeshes = [];

for (let i = 0; i < NODE_COUNT; i++) {
  const col = new THREE.Color(crystalColors[i % crystalColors.length]);
  const nodeMat = new THREE.MeshBasicMaterial({
    color: col,
    transparent: true,
    opacity: 0.0,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  const nodeMesh = new THREE.Mesh(nodeGeo, nodeMat);
  nodeMesh.name = `node_${i}`;
  scene.add(nodeMesh);
  nodeMeshes.push({ mesh: nodeMesh, mat: nodeMat });
}

// ── Post-processing ──
const composer = new EffectComposer(renderer);
const renderPass = new RenderPass(scene, camera);
composer.addPass(renderPass);

const bloomPass = new UnrealBloomPass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  0.95,  // strength
  0.38,  // radius
  0.18   // threshold
);
composer.addPass(bloomPass);

// Chromatic aberration + vignette post shader
const chromaticAberrationShader = {
  uniforms: {
    tDiffuse: { value: null },
    uTime: { value: 0 },
    uStrength: { value: 0.004 }
  },
  vertexShader: `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    precision highp float;
    uniform sampler2D tDiffuse;
    uniform float uTime;
    uniform float uStrength;
    varying vec2 vUv;

    void main() {
      vec2 center = vUv - 0.5;
      float dist = length(center);
      vec2 dir = normalize(center + 0.001);

      float strength = uStrength * (1.0 + dist * 2.2);
      float angle = uTime * 0.3;
      vec2 offset = dir * strength;

      float r = texture2D(tDiffuse, vUv + offset * 1.2).r;
      float g = texture2D(tDiffuse, vUv).g;
      float b = texture2D(tDiffuse, vUv - offset * 1.0).b;

      // Vignette
      float vignette = 1.0 - smoothstep(0.45, 0.95, dist);
      vignette = pow(vignette, 1.3);

      // Scanline noise
      float scan = 1.0 + 0.012 * sin(vUv.y * 800.0 + uTime * 5.0);

      vec3 col = vec3(r, g, b) * vignette * scan;
      // Subtle purple tint in shadows
      col = mix(col, col + vec3(0.02, 0.0, 0.04), 1.0 - vignette);

      gl_FragColor = vec4(col, 1.0);
    }
  `
};

const chromaticPass = new ShaderPass(chromaticAberrationShader);
composer.addPass(chromaticPass);

const outputPass = new OutputPass();
composer.addPass(outputPass);

// ── Connection update logic ──
let activeConnections = 0;

function updateNeuralWeb(time, globalProgress) {
  activeConnections = 0;
  const posArr = lineGeometry.attributes.position.array;
  const colArr = lineGeometry.attributes.color.array;

  // Only show web after explosion phase begins
  const webStrength = Math.max(0, (globalProgress - 0.25) / 0.75);

  for (let i = 0; i < crystals.length && activeConnections < MAX_CONNECTIONS; i++) {
    for (let j = i + 1; j < crystals.length && activeConnections < MAX_CONNECTIONS; j++) {
      const a = crystals[i];
      const b = crystals[j];
      const dist = a.currentPos.distanceTo(b.currentPos);

      if (dist < CONNECTION_DISTANCE) {
        const strength = (1.0 - dist / CONNECTION_DISTANCE) * webStrength;
        if (strength < 0.05) continue;

        const idx6 = activeConnections * 6;
        posArr[idx6 + 0] = a.currentPos.x;
        posArr[idx6 + 1] = a.currentPos.y;
        posArr[idx6 + 2] = a.currentPos.z;
        posArr[idx6 + 3] = b.currentPos.x;
        posArr[idx6 + 4] = b.currentPos.y;
        posArr[idx6 + 5] = b.currentPos.z;

        // Interpolate colors between the two crystal colors
        const colA = new THREE.Color(a.colorHex);
        const colB = new THREE.Color(b.colorHex);
        const pulse = (0.5 + 0.5 * Math.sin(time * 4 + i * 0.5 + j * 0.7)) * strength;

        colArr[idx6 + 0] = colA.r * pulse;
        colArr[idx6 + 1] = colA.g * pulse;
        colArr[idx6 + 2] = colA.b * pulse;
        colArr[idx6 + 3] = colB.r * pulse;
        colArr[idx6 + 4] = colB.g * pulse;
        colArr[idx6 + 5] = colB.b * pulse;

        activeConnections++;
      }
    }
  }

  // Zero out unused connections
  for (let i = activeConnections; i < MAX_CONNECTIONS; i++) {
    const idx6 = i * 6;
    posArr[idx6] = posArr[idx6 + 1] = posArr[idx6 + 2] = 0;
    posArr[idx6 + 3] = posArr[idx6 + 4] = posArr[idx6 + 5] = 0;
  }

  lineGeometry.attributes.position.needsUpdate = true;
  lineGeometry.attributes.color.needsUpdate = true;
}

function updateNodeGlows(time, globalProgress) {
  const webStrength = Math.max(0, (globalProgress - 0.3) / 0.7);
  for (let i = 0; i < NODE_COUNT; i++) {
    const c = crystals[i % crystals.length];
    nodeMeshes[i].mesh.position.copy(c.currentPos);
    const pulse = (0.5 + 0.5 * Math.sin(time * 2.5 + i)) * webStrength;
    nodeMeshes[i].mat.opacity = pulse * 0.85;
  }
}

// ── Animation loop ──
const clock = new THREE.Clock();
let globalProgress = 0; // 0 = start, 1 = fully settled

(function animate() {
  requestAnimationFrame(animate);
  const dt = clock.getDelta();
  const time = clock.getElapsedTime();

  globalProgress = Math.min(1.0, time / 5.0); // 5 seconds to full explosion

  // ── Update glass cube shader ──
  glassMat.uniforms.uTime.value = time;
  glassMat.uniforms.uCamPos.value.copy(camera.position);

  // ── Animate edge glow ──
  const edgePulse = 0.4 + 0.15 * Math.sin(time * 1.8);
  edgeMat.opacity = edgePulse;
  edgeMat2.opacity = 0.15 + 0.1 * Math.sin(time * 2.3 + 1.0);

  // ── Underglow pulse ──
  underglowLight.intensity = 3.5 + 1.5 * Math.sin(time * 1.5);
  underglowMat.opacity = 0.12 + 0.08 * Math.sin(time * 1.5);

  // ── Dynamic lights orbit ──
  tealFill.position.set(
    Math.cos(time * 0.4) * 2.5,
    Math.sin(time * 0.3) * 1.0 + 0.5,
    Math.sin(time * 0.4) * 2.5
  );
  pinkFill.position.set(
    Math.cos(time * 0.5 + Math.PI) * 2.2,
    Math.cos(time * 0.35) * 0.8 - 0.5,
    Math.sin(time * 0.5 + Math.PI) * 2.2
  );

  // ── Crystal explosion + magnetic snap animation ──
  for (let i = 0; i < crystals.length; i++) {
    const c = crystals[i];
    const localProgress = Math.max(0, (globalProgress * 5 - c.explosionTime * 2.5));
    const explodePhase = Math.min(1.0, localProgress);

    // Explosion: crystals fly out from center
    const explosionPos = c.startPos.clone().add(
      c.velocity.clone().multiplyScalar(Math.min(localProgress, 1.0) * 18)
    );

    // Magnetic snap: pull toward target after explosion peak
    const snapPhase = Math.max(0, Math.min(1.0, (localProgress - 0.5) * 2.5));
    const easeSnap = 1.0 - Math.pow(1.0 - snapPhase, 3.0); // cubic ease out

    // Blend: explosion → target position
    c.currentPos.lerpVectors(explosionPos, c.targetPos, easeSnap);

    // Subtle float orbit when settled
    if (snapPhase > 0.85) {
      const orbitT = time * c.orbitSpeed;
      const orb = new THREE.Vector3(
        Math.cos(orbitT) * 0.018,
        Math.sin(orbitT * 1.3) * 0.015,
        Math.sin(orbitT) * 0.018
      );
      c.currentPos.add(orb);
    }

    c.mesh.position.copy(c.currentPos);

    // Spin faster during explosion, settle down
    const spinFactor = Math.max(0.1, 1.0 - snapPhase * 0.7);
    c.mesh.rotation.x += c.rotSpeed.x * dt * spinFactor;
    c.mesh.rotation.y += c.rotSpeed.y * dt * spinFactor;
    c.mesh.rotation.z += c.rotSpeed.z * dt * spinFactor;

    // Scale: burst then settle
    const burstScale = 1.0 + Math.max(0, Math.sin(explodePhase * Math.PI)) * 0.5;
    c.mesh.scale.setScalar(c.scale * burstScale);

    // Glow intensity
    const glowVal = 0.4 + 0.6 * Math.sin(time * 2.5 + c.phase);
    c.mat.uniforms.uTime.value = time;
    c.mat.uniforms.uGlow.value = glowVal * Math.min(1.0, explodePhase * 2);
    c.mat.uniforms.uCamPos.value.copy(camera.position);

    // Visibility
    c.mesh.visible = explodePhase > 0.01;
  }

  // ── Neural web connections ──
  updateNeuralWeb(time, globalProgress);
  updateNodeGlows(time, globalProgress);

  // ── Post pass time ──
  chromaticPass.uniforms.uTime.value = time;
  chromaticPass.uniforms.uStrength.value = 0.003 + 0.002 * Math.sin(time * 0.7);

  // ── Cursor interaction tracking ──
  smoothMouse.lerp(targetMouse, 0.08);
  orbitAngle += dt * 0.25;

  const radius = 4.2;
  // Parallax + Orbit combined
  camera.position.x = Math.sin(orbitAngle) * radius + smoothMouse.x * 1.5;
  camera.position.y = 1.2 + smoothMouse.y * 1.5;
  camera.position.z = Math.cos(orbitAngle) * radius;
  camera.lookAt(0, 0, 0);

  composer.render();
})();

// ── Resize ──
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});