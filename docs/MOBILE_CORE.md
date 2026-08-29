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

This is correctness parity for the current `research_approximation`, not
biological validation or a performance result. The full brain/VNC, individual
muscle attachments and force gains, held-out behavior validation, and mobile
device benchmarks remain absent.
