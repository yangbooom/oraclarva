# Scientific scope and evidence gates

## Claim boundary

Oraclarva aims to become a connectome-driven embodied neural simulation. It does not currently reproduce a larva's mind, consciousness, or validated full behavior repertoire.

The Winding et al. dataset commonly summarized as 3,016 neurons and roughly 548,000 synapses is a larval brain connectome reconstructed within the available CNS EM volume. Before describing a model as a complete sensor-to-muscle animal, the project must verify coverage and identity across sensory neurons, descending pathways, VNC circuitry, motor neurons, neuromuscular junctions, and muscles.

The current motor crosswalk uses the broader L1 CNS CATMAID project and Zarin
et al. Table 1 rather than pretending that the 3,016-neuron brain graph alone
contains a complete whole-body motor output. It covers the published bilateral
A1 motor-neuron set, with MN25 taken from A2, not all thoracic and abdominal
segments.

The current visual extension is similarly bounded. Larderet et al. Figure 2
source data supplies first-instar bilateral LON identities and 3,297 structural
contacts. An audited VFB/L1EM snapshot adds a selected bilateral
PVL09/pOLP-to-LHN-to-CPf-to-A03o route with eight edges and 98 contacts, reaching
an annotated A1 premotor pair. Neither source supplies physiological effect
signs, photoreceptor response constants, an all-segment continuation, or a
complete route to motor neurons. A separate A2-A6 projection is explicitly
`ANATOMY_DERIVED`: its homolog and motor-target proxies have no skeleton IDs,
its 140 edges have no contact counts, and A7 is blocked. All executable effects
and currents remain `MODEL_FITTED`; source graphs retain unknown effects rather
than rewriting structural contacts or derived weights as measured physiology.

The body-state extension preserves the same boundary. A published 6-hour L1
EM analysis supplies two A1 dbd identities and 7 direct dbd-to-MN pairs / 11
contacts. Only 3 contacts overlap the current mapped motor runtime and execute;
the other 8 contacts remain recorded but unexecuted. A1-A6 strain and contact
are computed from the physical body, but transduction thresholds, currents,
effects, and gains are `MODEL_FITTED`. A2-A6 homolog channels are
`ANATOMY_DERIVED`; contraction and contact channels have no executable neural
edge. The reserved 6-animal kinematic partition was evaluated before the corrective
Stage 6 mechanics revision and is therefore no longer an untouched validation
set. Corrective selection used only the 12-animal calibration bands, where
period, signed stride, supported A6-A1 speed, amplitude, and duty now pass. The third held-out evaluation is diagnostic and passes its individual
rows. Model revision after the prior evaluations still independently blocks a
release-validation claim. The dependency-free
C++17 repeat core now matches the Python reference on exact spikes and strict
sampled-state tolerances across the normal run and five zero/lesion cases. That
is a software numerical-reproducibility result only; it does not turn fitted
parameters into measurements or restore independence to a reused held-out
partition. The
Stage 8 C ABI, deterministic reset digest, watertight render projection, and
Linux host benchmark are likewise engineering integration evidence. They do
not establish Android/iOS device performance, natural behavior validity,
measured muscle mechanics, or a complete L1 nervous system.

## Provenance labels

Every imported node, edge, parameter, and mapping must carry one of these labels:

- `observed`: directly supported by a cited dataset;
- `derived`: mechanically transformed from observed data;
- `fit`: estimated against a named experimental measurement;
- `hypothesis`: biologically plausible but not directly established;
- `synthetic`: test-only material with no biological claim.

Unknown sign, neurotransmitter, laterality, endpoint, or mapping must remain explicit. Missing data must not silently become a behavioral rule.

## Required data audit

The initial interchange format is intentionally small:

- neurons CSV: required column `neuron_id`;
- synapses CSV: `pre,post,weight,kind`;
- `kind`: `excitatory`, `inhibitory`, or `unknown`;
- `weight`: positive anatomical or modeled magnitude; its biological meaning must be declared in dataset metadata.

`oraclarva-audit` rejects missing endpoints, non-positive weights, duplicate neuron IDs, and invalid signs. Duplicate edges and self-loops are reported for review rather than automatically deleted.

## Validation gates

1. **Identity:** stable IDs and reproducible source-to-model mappings.
2. **Numerics:** unit checks, deterministic fixtures, convergence tests, and Python/native parity.
3. **Neural:** firing statistics and stimulus responses compared with held-out recordings where available.
4. **Causal:** lesions or stimulation change downstream activity in predicted ways.
5. **Embodied:** motor output drives physics without direct action commands.
6. **Behavioral:** trajectories and response distributions match experimental data, including failures.

The synthetic three-neuron smoke circuit satisfies only a software causal-path test. It is not evidence of larval behavior.
