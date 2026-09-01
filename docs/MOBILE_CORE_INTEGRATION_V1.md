# Mobile core integration v1

## Result

The C11 ABI advances the real corrected C++17 simulation one fixed 1 ms step at
a time. It does not replay trajectories and exposes no crawl, turn, stop,
animation, FSM, behavior-tree, or policy API. Ordinary input remains a
normalized posterior-touch environment value; declared lesions are fixed
interventions.

The standard workload is 14,600 steps (14.600 s), matching the checked
three-cycle Python/native window. The full stepped path equals the native
one-shot result, and reset replay reproduces canonical FNV-1a digest
`5346167233ab168c`.

## State, rendering, and movement acceptance

The 3,144-byte snapshot contains time, world-x displacement, 13 double-precision
physics nodes, six activations, 13 force vectors, 164 spike summaries, trace
state, and cycle metrics. A separate const projection creates a watertight
302-vertex/600-triangle mesh; snapshot hashes prove rendering cannot mutate
physics.

Acceptance includes:

- 488 stepped frames equal the one-shot native frames and stay inside Python
  parity ceilings;
- three complete cycles, three physical waves, traces, and final displacement
  match;
- the Python full-timestep movement gate passes at 16.627 um maximum retrace
  and 0.8298 progress efficiency;
- the 47 retained mobile frames measure 8.957 um maximum retrace and 0.9136
  progress efficiency;
- zero input and all four causal lesion layers match;
- reset replay is byte-stable and invalid input fails closed.

The GIF has no eye marker and explicitly labels anatomical forward.

## Host proxy benchmark

`data/benchmarks/mobile_core_host_v1.json` is a Linux aarch64 host proxy, not an
Android/iOS result. Seven release-build standard runs measured:

| Quantity | Measured |
|---|---:|
| initialization | 1.005 ms |
| one 14.6 s simulated run | 567.644 ms |
| simulated/wall throughput | 25.72x |
| peak process RSS | 16.83 MiB |
| snapshot read | 13.11 us |
| 302/600 render-mesh read | 29.01 us |
| shared/static/host bytes | 155,816 / 250,342 / 224,256 |

These figures permit no device framerate, thermal, battery, or shipping claim.
The third held-out diagnostic passes its rows but is non-independent;
`independent_validation_passed=false` and `release_validated=false`.

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

GitHub Actions remains manual-only through `workflow_dispatch`. Android/iOS
shells and real-device measurements remain future work.
