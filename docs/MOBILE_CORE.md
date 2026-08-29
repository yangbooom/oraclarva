# Mobile simulation core

## Reference and production roles

The Python implementation is the readable scientific oracle. A Rust or C++ production core may optimize memory layout and execution, but must run the same fixtures and stay within documented numerical tolerances.

## Execution model

- Store the connectome in compressed sparse row form.
- Process outgoing synapses only when a presynaptic neuron spikes.
- Keep excitatory and inhibitory state separate, including their decay constants.
- Run neural, body-physics, and rendering clocks independently.
- Record enough state to trace every muscle command to prior motor-neuron events.
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
currents in both normal and interneuron-lesioned conditions. This proves only LIF
numerical parity. The 91-neuron research network, continuous muscle activation,
XPBD body, contacts, proprioceptive feedback, and mobile performance are not yet
native-parity validated.
