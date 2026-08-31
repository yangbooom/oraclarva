# Mobile core integration v1

## Result

Stage 8 exposes the frozen repeat-crawl core through a small C11 ABI backed by
the dependency-free C++17 implementation. The API advances the real simulation
one fixed 1 ms step at a time. It does not precompute and replay the Python or
C++ trajectory.

The public lifecycle is:

    load versioned fixture + declared lesions
      -> reset deterministic state
      -> submit posterior-touch environment intensity for one step
      -> advance sensory -> LIF -> MN -> muscle -> body physics
      -> read a copied state snapshot
      -> optionally derive a read-only smooth render mesh

There is no crawl, turn, stop, seek-food, animation, FSM, behavior-tree, or
policy API. The only ordinary input in this gate is a normalized posterior
touch environment intensity in `[0, 1]`. Neural, premotor, mapped-MN, and fiber
lesions are declared interventions fixed at construction.

This completes the eight-stage research-to-mobile-core roadmap. It is not yet
an Android or iOS application, and it does not repair the failed held-out
segment-amplitude or duty comparisons. `release_validated` remains `false`.

## State ownership and ABI

`RepeatSimulation` now owns all previously local Stage 7 state: sparse LIF
currents and delays, lesions, sensory adaptation, relay origins, 146 fiber
activations, attachment state, the 13-node body, causal traces, histories, and
cycle detection. `RunRepeat` is now a convenience wrapper over the same
`Reset`/`Advance` lifecycle, so one-shot and stepped paths cannot silently use
different numerical implementations.

`native/mobile_core.h` is valid C11 and exports only eight unmangled symbols:

- create/destroy;
- reset/advance;
- read metadata/read snapshot;
- read render counts/read render mesh.

The snapshot is a 3,144-byte copied value on the measured host. It contains
simulation time, exact displacement, 13 physics nodes in micrometres, six
segment activations, 13 model-unit node-force vectors, all 164 cumulative spike
counts and first-spike times, last-step spike flags, force ancestry status,
physical cycle metrics, and six trace records. Missing spike and cycle times
remain NaN at the C boundary.

The shared-library build hides C++ implementation symbols. A static library is
also produced for source-level integration. The repository does not claim an
Android NDK, iOS, JNI, Swift, app-lifecycle, GPU, thermal, or battery test; those
toolchains and devices were not available in this gate.

## Render separation

Physics exposes 13 double-precision nodes. A separate const read projects the
current snapshot through Catmull-Rom centerline sampling and elliptical rings
into a 302-vertex, 600-triangle mesh. The mesh is watertight under the checked
manifold edge test and carries interpolated activation for display.

The host harness hashes a snapshot immediately before and after every mesh
read. Any renderer mutation fails closed. The mesh uses float vertices because
it is a display projection; physics and parity continue to use the internal
double state. It does not apply displacement, a gait, or an animation.

## Numerical and causal acceptance

The checked workload uses the Stage 6 frozen configuration SHA-256:

    5cbaec6a716cf2b8dd2d8e053b00469f5e9f09389fa74645c17a148143b936e3

The environment intensity is 1.0 for steps 0 and 1, matching the frozen 2 ms
posterior touch, then zero for the remaining 15,998 steps. Body-state feedback
must generate every later wave.

Acceptance includes:

- all 535 stepped mobile frames exactly equal the Stage 7 one-shot C++ frames;
- the same frames remain inside the existing Python ceilings of 5e-8 um for
  nodes, 5.1e-10 for activation, and 2e-7 model units for node force;
- all 164 spike counts and first-spike times, three complete cycles, three
  physical waves, displacement, force-frame count, and trace validity match;
- zero input, A6 sensory, A4 premotor, all-mapped-A6-MN, and all-A6-fiber cases
  match the one-shot core;
- reset followed by the same input schedule reproduces canonical snapshot and
  render bytes with FNV-1a digest `4ffd09454349d2c7`;
- out-of-range intensity, invalid lesion IDs, invalid render sampling, short
  buffers, and step overflow fail closed.

The deterministic visualization artifact is
`data/mobile/mobile_core_integration_v1.json`. It retains 51 paired internal
physics/read-only-render frames. This is software and embodiment evidence, not
a behavioral-validation result.

## Host proxy benchmark

`data/benchmarks/mobile_core_host_v1.json` records one release-build measurement
on the available Linux aarch64 host using GCC 13.3.0, `-O3`, and `-DNDEBUG`.
Seven complete 16 s runs produced these median/current-process results:

| Quantity | Measured |
|---|---:|
| initialization | 1.133 ms |
| one 16 s simulated run | 561.784 ms |
| simulated/wall throughput | 28.48x |
| peak process RSS | 16.83 MiB |
| snapshot C struct | 3,144 bytes |
| snapshot read | 13.78 us |
| 302/600 render-mesh read | 29.58 us |
| shared library | 155,808 bytes |
| static library | 248,718 bytes |
| host harness | 224,264 bytes |

All checked engineering budgets pass. These numbers are a process-level host
proxy. Peak RSS includes the executable, C++ runtime, fixture, and measurement
process. Timing may change with host load. No Android/iOS framerate, memory,
thermal, battery, or shipping-readiness claim is permitted from this result.

## Reproduction

```bash
python tools/build_mobile_core.py --output /tmp/oraclarva-mobile-build
/tmp/oraclarva-mobile-build/oraclarva-mobile-host \
  data/parity/repeat_crawl_native_v1.tsv
pytest -q tests/test_mobile_core.py
python tools/export_mobile_core_integration.py --check
python tools/benchmark_mobile_core.py --check
python tools/render_mobile_core_gif.py
```

![Stateful mobile core and read-only render mesh](assets/oraclarva_mobile_core_integration.gif)

GitHub Actions remains manual-only through `workflow_dispatch`; Stage 8 is
verified locally and does not trigger CI.

## Remaining work after Stage 8

Product work can now add thin Android/iOS application shells around this ABI,
then measure real devices without changing the causal core. Scientific work is
still larger: improve the failed amplitude/duty mechanics, replace derived
attachments and fitted forces when measured L1 data become available, expand
the incomplete sensory/VNC/motor coverage, and validate additional environment
responses. None of those gaps may be hidden behind direct behavior commands.
