# Mobile core integration v1

## Result

The C11 ABI advances the real corrected C++17 simulation one fixed 1 ms step at
a time. It does not replay Python/C++ trajectories and exposes no crawl, turn,
stop, animation, FSM, behavior-tree, or policy API. Ordinary input remains a
normalized posterior-touch environment value; declared lesions are fixed
interventions.

The lifecycle is:

    load fixture -> reset -> submit environment input
      -> sensory -> LIF -> MN -> muscle activation/physics -> environment
      -> copy state snapshot -> optional read-only render projection

The standard workload is 14,600 steps (14.600 s), exactly matching the checked
three-cycle Python/native window. The full stepped path equals the native
one-shot result, and reset replay reproduces canonical FNV-1a digest
`e8a2f9fdd37bab30`.

## State, rendering, and acceptance

The 3,144-byte snapshot contains time, world-x displacement, 13 double-precision
physics nodes, six activations, 13 applied force vectors, 164 spike counts and
first times, trace state, and cycle metrics. A separate const projection creates
a watertight 302-vertex/600-triangle float mesh. Snapshot hashes before/after
mesh reads prove rendering cannot mutate physics.

Acceptance includes:

- 488 stepped frames exactly equal the one-shot native frames and remain inside
  Python parity ceilings;
- three complete cycles, three physical waves, all spike/trace summaries, and
  final world-x displacement match;
- zero input and the four causal lesion layers match the one-shot core;
- reset replay is byte-stable;
- invalid intensity, lesions, buffers, render sampling, and step overflow fail
  closed.

`data/mobile/mobile_core_integration_v1.json` retains 47 lifecycle/render sample
frames. The GIF removes the eye-like black dot and explicitly labels anatomical
forward; there is no eye marker.

## Host proxy benchmark

`data/benchmarks/mobile_core_host_v1.json` is a Linux aarch64 host proxy, not an
Android/iOS device result. Seven release-build standard runs measured:

| Quantity | Measured |
|---|---:|
| initialization | 1.021 ms |
| one 14.6 s simulated run | 564.274 ms |
| simulated/wall throughput | 25.87x |
| peak process RSS | 16.79 MiB |
| snapshot read | 12.31 us |
| 302/600 render-mesh read | 28.24 us |
| shared/static/host bytes | 155,816 / 250,342 / 224,256 |

These figures permit no device framerate, thermal, battery, or shipping claim.
The reused held-out diagnostic still fails A5/A6 duty and cannot create an
independent biological validation claim. `release_validated=false`.

![Stateful mobile core and read-only render mesh](assets/oraclarva_mobile_core_integration.gif)

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

GitHub Actions remains manual-only through `workflow_dispatch`; local validation
does not trigger CI. Android/iOS shells and real-device measurements remain
future product work.
