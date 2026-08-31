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
same frozen Stage 6 configuration as the Python oracle. The native program
executes rather than replays the 164-neuron/307-synapse network, sensory
adaptation, delayed shortening and recovery relays, 144 mapped sources, 146
named-fiber forces, 13-node XPBD body, feedback, trace ancestry, and physical
cycle detector.

The normal 16 s run matches all 164 spike counts and first-spike times exactly.
All 535 sampled frames remain within ceilings of 5e-8 um for nodes, 5.1e-10 for
activation, and 2e-7 model units for node force. Cycle period, stride, wave
speed, displacement, trace counts, and cycle counts match their stricter
summary gates. Zero input plus A6 sensory, A4 premotor, all-mapped-A6-MN, and
all-A6-fiber lesions preserve the expected causal boundaries in both
implementations.

This is correctness parity for the current `research_approximation`, not
biological validation or a performance result. The held-out segment-amplitude
and duty failures remain present and `release_validated` remains false. See
`docs/REPEAT_CRAWL_NATIVE_PARITY_V1.md`.

## Stage 8 mobile integration gate

The next acceptance gate must wrap the verified core in a small mobile-facing
lifecycle API with these boundaries:

- inputs alter fields, contact geometry, declared sensory stimuli, or declared
  neural/muscle lesions; no crawl/turn/stop/seek action API is permitted;
- fixed neural/body clocks, deterministic reset, versioned fixture identity,
  and replay checks remain explicit;
- the simulation returns state snapshots and trace records, while the renderer
  receives a separate smooth mesh projection and never changes physics nodes;
- a release-build target-like host benchmark records initialization time,
  simulated-time throughput, memory, and snapshot cost without weakening the
  Stage 7 numerical gate;
- mobile packaging claims only host-tested readiness until Android/iOS target
  builds and device measurements actually exist.

GitHub Actions remains manual-only through `workflow_dispatch`; local
acceptance is the default during this research phase.
