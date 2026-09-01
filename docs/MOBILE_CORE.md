# Mobile simulation core

## Reference and production roles

The Python implementation is the readable scientific oracle. A Rust or C++ production core may optimize memory layout and execution, but must run the same fixtures and stay within documented numerical tolerances.

## Execution model

- Store the connectome in compressed sparse row form.
- Process outgoing synapses only when a presynaptic neuron spikes.
- Keep excitatory and inhibitory state separate, including their decay constants.
- Run neural, body-physics, and rendering clocks independently.
- Record enough state to trace every active muscle force to prior motor-neuron events.
- Use deterministic seeds and versioned parameter bundles for replay.

Indicative clocks, subject to device benchmarks:

- neural integration: 0.5–1 ms;
- body physics: 2–5 ms;
- rendering: display cadence.

## Product boundary

The player changes the environment or performs declared neural interventions. They do not directly invoke crawl, turn, stop, or seek-food actions. Animation visualizes the simulated body state and never moves the organism independently.

## First native acceptance test

Given the same network, initial state, stimulus schedule, lesion set, and floating-point mode, the native core must match the Python reference on spike counts, spike timing tolerance, membrane traces, and causal-path assertions. Performance is evaluated only after correctness passes.

The first executable gate is now `data/parity/lif_smoke_v0.tsv`. Python and the
dependency-free C++17 core consume that same synthetic fixture and compare every
step's spike identities, membrane voltages, and separate excitatory/inhibitory
currents in both normal and interneuron-lesioned conditions. This proves LIF
numerical parity independently of the embodied model.

The second executable gate compiles the repository's provenance-aware Python
configuration into `data/parity/closed_loop_native_v1.tsv`. The C++17 core then
executes the full current approximation: 91 LIF neurons, 90 sparse synapses,
58 motor identities, continuous activation through the 358-fiber aggregate
proxy, 13-node XPBD mechanics, asymmetric substrate contact, and
shortening-sensitive proprioceptive feedback. Normal, no-stimulus, A4 premotor
lesion, A4 muscle lesion, and A1 motor-identity lesion runs match Python on all
neuron spike counts and first-spike times, peak activation and shortening,
displacement, and all 151 sampled node/activation frames.

The bilateral acceptance gate is `data/parity/bilateral_native_v1.tsv`. It
executes 126 LIF neurons, 130 synapses, side-resolved motor and muscle channels,
active-curvature XPBD, local-tangent substrate friction, and bilateral rail
feedback. Symmetric, left, right, zero-input, and premotor/motor-identity/muscle
lesion cases match Python across every spike and all 151 sampled frames.

## Stage 4 native-impact audit

The visual named-fiber body path is currently a Python reference path. It adds
146 attachment geometries, per-fiber active/passive/damping tension, and shared
node-force projection, but does not change the three existing native fixture
schemas or their checked numerical outputs. The native files therefore require
no compatibility edit in Stage 4.

This is an explicit parity gap, not implied native support. A future native
gate must consume the same visual configuration and attachment fixture, match
per-step activation and model-unit node forces, preserve every upstream source
trace, and reproduce sampled 13-node trajectories within a declared tolerance
before the mobile product uses this path.

## Stage 5 native-impact audit

Body-state sensory feedback is also Python-only. It adds A1-A6 segment-state
sampling, two executable A1 dbd compartments, three direct sparse contacts,
and body-state/dbd/MN ancestry on feedback-associated fiber forces. The three
existing native fixtures and their schemas are intentionally unchanged; local
parity tests must remain bit-for-bit compatible with their checked outputs.

This is not native support by implication. A new native fixture must match the
Python reference on fitted transduction current, dbd and MN spike timing,
one-step-delayed named-fiber events, trace ordering, node-force vectors, and
13-node trajectories for zero input, stretch, and sensory/MN/fiber lesions.
Contact and contraction channels remain non-executable and must not be silently
wired by a mobile implementation.

## Stage 7 repeat-crawl numerical parity

The repeat-crawl path now has a dependency-free C++17 implementation. It
consumes `data/parity/repeat_crawl_native_v1.tsv`, which is generated from the
the same checked corrective Stage 6 configuration as the Python oracle. The native program
executes rather than replays the 164-neuron/307-synapse network, sensory
adaptation, delayed shortening and recovery relays, 144 mapped sources, 146
named-fiber forces, 13-node XPBD body, feedback, trace ancestry, and physical
cycle detector.

The normal 14.6 s run matches all 164 spike counts and first-spike times exactly.
All 488 sampled frames remain within ceilings of 5e-8 um for nodes, 5.1e-10 for
activation, and 2e-7 model units for node force. Cycle period, stride, wave
speed, displacement, trace counts, and cycle counts match their stricter
summary gates. Zero input plus A6 sensory, A4 premotor, all-mapped-A6-MN, and
all-A6-fiber lesions preserve the expected causal boundaries in both
implementations.

This is correctness parity for the current `research_approximation`, not
biological validation or a performance result. The third reused held-out diagnostic passes its rows but cannot support an
independent claim; `release_validated` remains false. See
`docs/REPEAT_CRAWL_NATIVE_PARITY_V1.md`.

## Stage 8 mobile integration gate

The gate now passes on the available host proxy. `RepeatSimulation` owns the
real sparse-LIF, adaptation, delayed relay, fiber, force, XPBD, trace, and cycle
state and advances it one fixed 1 ms causal step. The legacy one-shot runner is
a wrapper around this same lifecycle rather than a parallel implementation.

`native/mobile_core.h` is a C11 boundary with eight exported functions for
create/destroy, reset/advance, metadata/snapshot reads, and render
count/mesh reads. Ordinary input is a normalized posterior-touch environment
intensity; sensory, premotor, mapped-MN, and fiber lesions are declared
interventions. There is no action command API.

The 3,144-byte snapshot copies time, displacement, all 13 physics nodes, six
activations, 13 force vectors, 164 spike counts/first times, last-step spikes,
trace state, and physical-cycle metrics. A separate const projection returns a
watertight 302-vertex/600-triangle smooth mesh. Snapshot hashes before and after
every mesh read prove the renderer does not mutate physics.

The complete 14.6 s stepped workload exactly matches the Stage 7 one-shot
native frames and remains inside the checked Python tolerances. Reset plus the
same input schedule reproduces canonical digest `5346167233ab168c`. Zero input and
all four lesion classes continue to match.

One GCC 13.3.0 `-O3 -DNDEBUG` measurement on the available Linux aarch64 host
reported 1.005 ms initialization, 567.644 ms for 14.6 simulated seconds
(25.72x), 16.83 MiB peak process RSS, 13.11 us snapshot reads, and 29.01 us
render-mesh
reads. These are host process measurements only. Android/iOS compilation,
device CPU/GPU, thermal, battery, app lifecycle, and shipping readiness remain
untested and may not be inferred.

The third non-independent held-out diagnostic passes its rows while
`independent_validation_passed` and `release_validated` remain false. See
`docs/MOBILE_CORE_INTEGRATION_V1.md`.

GitHub Actions remains manual-only through `workflow_dispatch`; local
acceptance is the default during this research phase.

## Stage 9 integrated environment extension

`native/mobile_environment.h` adds three C11 functions without changing the
Stage 8 ABI layouts. A spatial core owns both the frozen repeat controller and a
generated 168-neuron/188-synapse light controller. Each 1 ms call samples the
input scalar field at four current head-surface locations, runs adaptive
transduction and sparse LIF dynamics, updates segment-resolved yaw/pitch muscle
activation, advances the same 13-node XPBD body, and exposes the resulting
samples, spikes, activations, heading, pitch, and 3D displacement.

Uniform light retains the Stage 8 final anatomical displacement of
467.539285 µm exactly and has zero heading change. Synthetic +Y/-Y gradients
produce mirrored -3.831016°/+3.830253° headings. A +Z gradient lifts the body
35.095957 µm with 12.738189° head pitch; the -Z response is ground-limited. A
right sensory-channel lesion reduces the +Y result to zero heading change.

These are host diagnostic gates, not a phototaxis validation. The field and
transducer parameters are `MODEL_FITTED`, the reduced spatial topology is
`ANATOMY_DERIVED`, and only light is native in this extension. Integrated
spatial proprioception is explicitly disabled because its cross-coupling to the
axial body has not been calibrated. The synapses remain serialized for future
calibration, but enabling them is outside this gate.

The checked trajectory, 1:1-scale physical-node GIF, ABI details, parity scope,
and reproduction commands are in
`docs/NATIVE_ENVIRONMENT_CLOSED_LOOP_V1.md`.
