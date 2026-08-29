import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import bodySpec from "../../data/body/l1_body_v0.json";
import closedLoopTrajectory from "../../data/trajectories/l1_closed_loop_v0.json";
import "./style.css";

const expectedSegmentIds = bodySpec.segments.map((segment) => segment.id);
if (
  closedLoopTrajectory.schema_version !== 1
  || closedLoopTrajectory.node_count !== expectedSegmentIds.length + 1
  || closedLoopTrajectory.body_segment_ids.join(",") !== expectedSegmentIds.join(",")
  || closedLoopTrajectory.frames.length < 2
  || closedLoopTrajectory.release_validated !== false
) {
  throw new Error("closed-loop trajectory does not match the body/viewer contract");
}

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

const nominalLengthUm = bodySpec.global_geometry.total_length_m.nominal * 1e6;
const nominalWidthUm = bodySpec.global_geometry.maximum_width_m.nominal * 1e6;
const heightRatio = bodySpec.global_geometry.height_to_width_ratio.nominal;
const worldLength = 6.25;
const radialSamples = 28;
const axialSubdivisions = 6;
const ringCount = bodySpec.segments.length * axialSubdivisions + 1;
const bodyGroup = new THREE.Group();
bodyGroup.rotation.z = 0;
scene.add(bodyGroup);

const baseLengths = bodySpec.segments.map((segment) => segment.length_fraction * worldLength);
const baseWidths = bodySpec.segments.map(
  (segment) => (nominalWidthUm / nominalLengthUm) * worldLength * segment.width_scale,
);
const baseHeights = baseWidths.map((width) => width * heightRatio);
const nodeProfile = (values) => [
  values[0] * 0.55,
  ...values.slice(1).map((value, index) => (values[index] + value) / 2),
  values.at(-1) * 0.45,
];
const nodeWidths = nodeProfile(baseWidths);
const nodeHeights = nodeProfile(baseHeights);

const materials = bodySpec.segments.map((segment, index) => new THREE.MeshPhysicalMaterial({
  color: index === 0 ? 0xd8a56c : index > 9 ? 0xb98264 : index % 2 ? 0xe5bd86 : 0xdcae75,
  roughness: 0.44,
  metalness: 0,
  clearcoat: 0.38,
  clearcoatRoughness: 0.34,
  transparent: true,
  opacity: 0.94,
  emissive: 0x2b1625,
  emissiveIntensity: 0.2,
  side: THREE.DoubleSide,
}));

const positionArray = new Float32Array((ringCount * radialSamples + 2) * 3);
const geometry = new THREE.BufferGeometry();
geometry.setAttribute("position", new THREE.BufferAttribute(positionArray, 3));
const indices = [];
for (let segmentIndex = 0; segmentIndex < bodySpec.segments.length; segmentIndex += 1) {
  const groupStart = indices.length;
  for (let localSpan = 0; localSpan < axialSubdivisions; localSpan += 1) {
    const spanIndex = segmentIndex * axialSubdivisions + localSpan;
    const leftStart = spanIndex * radialSamples;
    const rightStart = (spanIndex + 1) * radialSamples;
    for (let radialIndex = 0; radialIndex < radialSamples; radialIndex += 1) {
      const following = (radialIndex + 1) % radialSamples;
      indices.push(
        leftStart + radialIndex,
        rightStart + radialIndex,
        rightStart + following,
        leftStart + radialIndex,
        rightStart + following,
        leftStart + following,
      );
    }
  }
  geometry.addGroup(groupStart, indices.length - groupStart, segmentIndex);
}

const startCapOffset = indices.length;
const startCenterIndex = ringCount * radialSamples;
const endCenterIndex = startCenterIndex + 1;
const lastRingStart = (ringCount - 1) * radialSamples;
for (let radialIndex = 0; radialIndex < radialSamples; radialIndex += 1) {
  const following = (radialIndex + 1) % radialSamples;
  indices.push(startCenterIndex, radialIndex, following);
}
geometry.addGroup(startCapOffset, indices.length - startCapOffset, 0);
const endCapOffset = indices.length;
for (let radialIndex = 0; radialIndex < radialSamples; radialIndex += 1) {
  const following = (radialIndex + 1) % radialSamples;
  indices.push(endCenterIndex, lastRingStart + following, lastRingStart + radialIndex);
}
geometry.addGroup(endCapOffset, indices.length - endCapOffset, bodySpec.segments.length - 1);
geometry.setIndex(indices);

const bodyMesh = new THREE.Mesh(geometry, materials);
bodyMesh.userData.continuousSurface = true;
bodyGroup.add(bodyMesh);

const boundaryMaterial = new THREE.LineBasicMaterial({ color: 0x6f5362, transparent: true, opacity: 0.28 });
const boundaryRings = Array.from({ length: bodySpec.segments.length + 1 }, () => {
  const ringGeometry = new THREE.BufferGeometry();
  ringGeometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(radialSamples * 3), 3));
  const line = new THREE.LineLoop(ringGeometry, boundaryMaterial);
  bodyGroup.add(line);
  return line;
});

const mouth = new THREE.Mesh(
  new THREE.TorusGeometry(0.14, 0.035, 12, 48),
  new THREE.MeshPhysicalMaterial({ color: 0x5f3035, roughness: 0.5, clearcoat: 0.3 }),
);
mouth.rotation.y = Math.PI / 2;
bodyGroup.add(mouth);
const sensoryMaterial = new THREE.MeshStandardMaterial({ color: 0x6b3442, emissive: 0x39131e, emissiveIntensity: 0.8 });
const sensoryOrgans = [-1, 1].map((side) => {
  const organ = new THREE.Mesh(new THREE.SphereGeometry(0.055, 18, 14), sensoryMaterial);
  organ.userData.side = side;
  bodyGroup.add(organ);
  return organ;
});

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let selectedIndex = 4;
let evidenceMode = true;
let playing = false;
let playbackTimeS = 0;
let playbackSpeed = 1;
let previousAnimationTimeMs = null;
const trajectoryDurationS = closedLoopTrajectory.frames.at(-1).time_s;
const trajectoryInitialCenterXUm = closedLoopTrajectory.frames[0].nodes_um.reduce(
  (sum, node) => sum + node[0],
  0,
) / closedLoopTrajectory.node_count;
const worldPerUm = worldLength / nominalLengthUm;

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

document.querySelector("#timeline").addEventListener("input", (event) => {
  playbackTimeS = trajectoryDurationS * Number(event.target.value) / 1000;
  document.querySelector("#time-value").textContent = playbackTimeS.toFixed(2) + " s";
});
document.querySelector("#speed").addEventListener("input", (event) => {
  playbackSpeed = Number(event.target.value) / 100;
  document.querySelector("#speed-value").textContent = playbackSpeed.toFixed(2) + "×";
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
  const hit = raycaster.intersectObject(bodyMesh, false)[0];
  if (hit?.face) setSelected(hit.face.materialIndex);
});

function smoothstep(amount) {
  return amount * amount * (3 - 2 * amount);
}

function sampleTrajectory(timeS) {
  const framePosition = timeS / closedLoopTrajectory.sample_interval_s;
  const leftIndex = Math.min(
    Math.floor(framePosition),
    closedLoopTrajectory.frames.length - 1,
  );
  const rightIndex = Math.min(
    leftIndex + 1,
    closedLoopTrajectory.frames.length - 1,
  );
  const amount = Math.min(1, Math.max(0, framePosition - leftIndex));
  const left = closedLoopTrajectory.frames[leftIndex];
  const right = closedLoopTrajectory.frames[rightIndex];
  return {
    nodes: left.nodes_um.map((node, nodeIndex) => node.map(
      (value, axis) => value * (1 - amount) + right.nodes_um[nodeIndex][axis] * amount,
    )),
    activations: left.segment_activation.map(
      (value, segmentIndex) => (
        value * (1 - amount) + right.segment_activation[segmentIndex] * amount
      ),
    ),
  };
}

function physicsNodeToWorld(nodeUm) {
  return [
    (nodeUm[0] - trajectoryInitialCenterXUm) * worldPerUm,
    floor.position.y + nodeUm[2] * worldPerUm,
    nodeUm[1] * worldPerUm,
  ];
}

function writeRing(ringIndex, center, width, height) {
  for (let radialIndex = 0; radialIndex < radialSamples; radialIndex += 1) {
    const angle = (2 * Math.PI * radialIndex) / radialSamples;
    const offset = (ringIndex * radialSamples + radialIndex) * 3;
    positionArray[offset] = center[0];
    positionArray[offset + 1] = center[1] + Math.sin(angle) * height * 0.5;
    positionArray[offset + 2] = center[2] + Math.cos(angle) * width * 0.5;
  }
}

function updateBody(timeMs) {
  if (previousAnimationTimeMs === null) previousAnimationTimeMs = timeMs;
  const elapsedS = Math.max(0, (timeMs - previousAnimationTimeMs) / 1000);
  previousAnimationTimeMs = timeMs;
  if (playing) {
    playbackTimeS = (playbackTimeS + elapsedS * playbackSpeed) % trajectoryDurationS;
  }
  document.querySelector("#timeline").value = String(
    Math.round(playbackTimeS / trajectoryDurationS * 1000),
  );
  document.querySelector("#time-value").textContent = playbackTimeS.toFixed(2) + " s";

  const sample = sampleTrajectory(playbackTimeS);
  const nodeCenters = sample.nodes.map(physicsNodeToWorld);
  const currentLengths = bodySpec.segments.map((segment, index) => {
    const delta = nodeCenters[index + 1].map(
      (value, axis) => value - nodeCenters[index][axis],
    );
    return Math.hypot(...delta);
  });
  const restVolumeProxy = baseLengths.reduce(
    (sum, length, index) => sum + length * baseWidths[index] * baseHeights[index],
    0,
  );
  const currentVolumeProxy = currentLengths.reduce(
    (sum, length, index) => sum + length * baseWidths[index] * baseHeights[index],
    0,
  );
  const cavityScale = Math.sqrt(restVolumeProxy / currentVolumeProxy);

  let ringIndex = 0;
  bodySpec.segments.forEach((segment, segmentIndex) => {
    for (let step = 0; step < axialSubdivisions; step += 1) {
      const amount = step / axialSubdivisions;
      const profile = smoothstep(amount);
      const width = (
        nodeWidths[segmentIndex] * (1 - profile) + nodeWidths[segmentIndex + 1] * profile
      ) * cavityScale;
      const height = (
        nodeHeights[segmentIndex] * (1 - profile) + nodeHeights[segmentIndex + 1] * profile
      ) * cavityScale;
      const center = nodeCenters[segmentIndex].map(
        (value, axis) => (
          value * (1 - amount) + nodeCenters[segmentIndex + 1][axis] * amount
        ),
      );
      writeRing(ringIndex, center, width, height);
      ringIndex += 1;
    }
  });
  writeRing(
    ringIndex,
    nodeCenters.at(-1),
    nodeWidths.at(-1) * cavityScale,
    nodeHeights.at(-1) * cavityScale,
  );

  for (let boundaryIndex = 0; boundaryIndex < boundaryRings.length; boundaryIndex += 1) {
    const sourceRing = boundaryIndex * axialSubdivisions;
    const boundaryPositions = boundaryRings[boundaryIndex].geometry.attributes.position.array;
    for (let radialIndex = 0; radialIndex < radialSamples; radialIndex += 1) {
      const sourceOffset = (sourceRing * radialSamples + radialIndex) * 3;
      const targetOffset = radialIndex * 3;
      boundaryPositions[targetOffset] = positionArray[sourceOffset];
      boundaryPositions[targetOffset + 1] = positionArray[sourceOffset + 1];
      boundaryPositions[targetOffset + 2] = positionArray[sourceOffset + 2];
    }
    boundaryRings[boundaryIndex].geometry.attributes.position.needsUpdate = true;
  }

  const startCenter = nodeCenters[0];
  const endCenter = nodeCenters.at(-1);
  positionArray[startCenterIndex * 3] = startCenter[0];
  positionArray[startCenterIndex * 3 + 1] = startCenter[1];
  positionArray[startCenterIndex * 3 + 2] = startCenter[2];
  positionArray[endCenterIndex * 3] = endCenter[0];
  positionArray[endCenterIndex * 3 + 1] = endCenter[1];
  positionArray[endCenterIndex * 3 + 2] = endCenter[2];
  geometry.attributes.position.needsUpdate = true;
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();

  mouth.position.set(startCenter[0] - 0.03, startCenter[1], startCenter[2]);
  sensoryOrgans.forEach((organ) => {
    organ.position.set(
      startCenter[0] + 0.15,
      startCenter[1] + 0.16,
      startCenter[2] + organ.userData.side * nodeWidths[0] * cavityScale * 0.3,
    );
  });

  materials.forEach((material, index) => {
    const isSelected = index === selectedIndex;
    const hypothesisColor = index === 0 ? 0xd8a56c : index > 9 ? 0xb98264 : index % 2 ? 0xe5bd86 : 0xdcae75;
    material.color.setHex(evidenceMode ? hypothesisColor : 0xd9b785);
    material.emissive.setHex(isSelected ? 0x6e2b31 : 0x2b1625);
    material.emissiveIntensity = isSelected
      ? 0.85
      : 0.2 + sample.activations[index] * 0.45;
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
