import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import bodySpec from "../../data/body/l1_body_v0.json";
import "./style.css";

const sceneHost = document.querySelector("#scene");
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
sceneHost.append(renderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x120e19, 0.06);

const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
camera.position.set(1.5, 3.9, 7.8);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.minDistance = 4.2;
controls.maxDistance = 13;
controls.target.set(0, 0.12, 0);

scene.add(new THREE.HemisphereLight(0xffefd0, 0x26192f, 2.8));
const key = new THREE.DirectionalLight(0xffe0a3, 5.2);
key.position.set(-3, 5, 5);
scene.add(key);
const rim = new THREE.PointLight(0xb989ff, 65, 18);
rim.position.set(4, 2, -4);
scene.add(rim);

const floor = new THREE.Mesh(
  new THREE.CircleGeometry(5.6, 96),
  new THREE.MeshStandardMaterial({ color: 0x18131f, roughness: 0.92, metalness: 0.05 }),
);
floor.rotation.x = -Math.PI / 2;
floor.position.y = -0.72;
scene.add(floor);

const rings = new THREE.Group();
for (let index = 0; index < 13; index += 1) {
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(0.37 + Math.sin((index / 12) * Math.PI) * 0.21, 0.008, 8, 64),
    new THREE.MeshBasicMaterial({ color: 0x5f4b6c, transparent: true, opacity: 0.24 }),
  );
  ring.rotation.y = Math.PI / 2;
  ring.position.set(-3.22 + index * 0.535, -0.705, 0);
  rings.add(ring);
}
scene.add(rings);

const bodyGroup = new THREE.Group();
bodyGroup.rotation.z = -0.025;
scene.add(bodyGroup);

const nominalLengthUm = bodySpec.global_geometry.total_length_m.nominal * 1e6;
const nominalWidthUm = bodySpec.global_geometry.maximum_width_m.nominal * 1e6;
const heightRatio = bodySpec.global_geometry.height_to_width_ratio.nominal;
const worldLength = 6.25;
const gap = 0.018;
const segmentMeshes = [];
const baseState = [];
let cursor = -worldLength / 2;

const materials = bodySpec.segments.map((segment, index) => new THREE.MeshPhysicalMaterial({
  color: index === 0 ? 0xd8a56c : index > 9 ? 0xb98264 : index % 2 ? 0xe5bd86 : 0xdcae75,
  roughness: 0.42,
  metalness: 0,
  clearcoat: 0.42,
  clearcoatRoughness: 0.32,
  transparent: true,
  opacity: 0.92,
  emissive: 0x2b1625,
  emissiveIntensity: 0.2,
}));

bodySpec.segments.forEach((segment, index) => {
  const length = segment.length_fraction * worldLength;
  const radius = nominalWidthUm / nominalLengthUm * worldLength * segment.width_scale * 0.5;
  const geometry = new THREE.SphereGeometry(1, 36, 24);
  geometry.scale(Math.max(length * 0.58, radius * 0.74), radius, radius * heightRatio);
  const mesh = new THREE.Mesh(geometry, materials[index]);
  const x = cursor + length / 2;
  mesh.position.set(x, 0, 0);
  mesh.userData.segmentIndex = index;
  mesh.userData.segment = segment;
  bodyGroup.add(mesh);
  segmentMeshes.push(mesh);
  baseState.push({ x, length, radius });
  cursor += length - gap;
});

const mouth = new THREE.Mesh(
  new THREE.TorusGeometry(0.14, 0.035, 12, 48),
  new THREE.MeshPhysicalMaterial({ color: 0x5f3035, roughness: 0.5, clearcoat: 0.3 }),
);
mouth.rotation.y = Math.PI / 2;
mouth.position.set(baseState[0].x - baseState[0].length * 0.62, -0.02, 0);
bodyGroup.add(mouth);

const sensoryMaterial = new THREE.MeshStandardMaterial({ color: 0x6b3442, emissive: 0x39131e, emissiveIntensity: 0.8 });
[-1, 1].forEach((side) => {
  const organ = new THREE.Mesh(new THREE.SphereGeometry(0.055, 18, 14), sensoryMaterial);
  organ.position.set(baseState[0].x - 0.16, 0.16, side * 0.22);
  bodyGroup.add(organ);
});

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let selectedIndex = 4;
let evidenceMode = true;
let playing = false;
let contraction = 0.35;
let bend = 0.18;
let phase = 0;

const anatomyLabels = {
  pseudocephalon: "pseudocephalon",
  thoracic_1: "thoracic 1",
  thoracic_2: "thoracic 2",
  thoracic_3: "thoracic 3",
  abdominal_1: "abdominal 1",
  abdominal_2: "abdominal 2",
  abdominal_3: "abdominal 3",
  abdominal_4: "abdominal 4",
  abdominal_5: "abdominal 5",
  abdominal_6: "abdominal 6",
  abdominal_7: "abdominal 7",
  terminal_abdominal: "terminal abdominal",
};

function setSelected(index) {
  selectedIndex = index;
  const segment = bodySpec.segments[index];
  document.querySelector("#segment-index").textContent = String(index + 1).padStart(2, "0");
  document.querySelector("#segment-name").textContent = segment.id;
  document.querySelector("#segment-length").textContent = `${(nominalLengthUm * segment.length_fraction).toFixed(1)} µm`;
  document.querySelector("#segment-width").textContent = `${(nominalWidthUm * segment.width_scale).toFixed(1)} µm`;
  document.querySelector("#segment-anatomy").textContent = anatomyLabels[segment.anatomy];
  document.querySelectorAll(".segment-buttons button").forEach((button, buttonIndex) => {
    button.classList.toggle("active", buttonIndex === index);
  });
}

const buttonsHost = document.querySelector("#segment-buttons");
bodySpec.segments.forEach((segment, index) => {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = segment.id;
  button.addEventListener("click", () => setSelected(index));
  buttonsHost.append(button);
});
setSelected(selectedIndex);

document.querySelector("#contraction").addEventListener("input", (event) => {
  contraction = Number(event.target.value) / 100;
  document.querySelector("#contraction-value").textContent = `${event.target.value}%`;
});
document.querySelector("#bend").addEventListener("input", (event) => {
  bend = Number(event.target.value) / 100;
  document.querySelector("#bend-value").textContent = `${event.target.value}%`;
});
document.querySelector("#play").addEventListener("click", (event) => {
  playing = !playing;
  event.currentTarget.classList.toggle("active", playing);
  event.currentTarget.setAttribute("aria-pressed", String(playing));
  event.currentTarget.querySelector("span").textContent = playing ? "Ⅱ" : "▶";
});
document.querySelector("#evidence-toggle").addEventListener("click", (event) => {
  evidenceMode = !evidenceMode;
  event.currentTarget.classList.toggle("active", evidenceMode);
  event.currentTarget.setAttribute("aria-checked", String(evidenceMode));
});

renderer.domElement.addEventListener("pointerdown", (event) => {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(segmentMeshes, false)[0];
  if (hit) setSelected(hit.object.userData.segmentIndex);
});

function updateBody(time) {
  if (playing) phase = (time * 0.00022) % 1;
  const waveCenter = playing ? 11 - phase * 14 : selectedIndex;
  let accumulatedShift = 0;
  segmentMeshes.forEach((mesh, index) => {
    const distance = Math.abs(index - waveCenter);
    const activation = Math.exp(-(distance * distance) / 1.5) * contraction;
    const shorten = 1 - activation * 0.45;
    const plump = Math.sqrt(1 / shorten);
    const base = baseState[index];
    const displayedLength = base.length * shorten;
    mesh.scale.set(shorten, plump, plump);
    const center = base.x - accumulatedShift - (base.length - displayedLength) / 2;
    const normalized = center / (worldLength / 2);
    const lateral = Math.sin((normalized + 1) * Math.PI) * bend * 0.82;
    const lift = 0.08 + Math.cos(normalized * Math.PI * 1.6) * bend * 0.16;
    mesh.position.set(center, lift, lateral);
    mesh.rotation.y = Math.cos((normalized + 1) * Math.PI) * bend * 0.18;
    mesh.rotation.z = Math.cos((normalized + 1) * Math.PI) * bend * 0.3;
    accumulatedShift += base.length - displayedLength;

    const isSelected = index === selectedIndex;
    const hypothesisColor = index === 0 ? 0xd8a56c : index > 9 ? 0xb98264 : index % 2 ? 0xe5bd86 : 0xdcae75;
    materials[index].color.setHex(evidenceMode ? hypothesisColor : 0xd9b785);
    materials[index].emissive.setHex(isSelected ? 0x6e2b31 : 0x2b1625);
    materials[index].emissiveIntensity = isSelected ? 0.85 : 0.2;
  });
}

function resize() {
  const { clientWidth, clientHeight } = sceneHost;
  renderer.setSize(clientWidth, clientHeight, false);
  camera.aspect = clientWidth / clientHeight;
  camera.updateProjectionMatrix();
}

const resizeObserver = new ResizeObserver(resize);
resizeObserver.observe(sceneHost);
resize();

function animate(time) {
  updateBody(time);
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
