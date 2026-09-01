# Repeat-crawl native parity v1

## Result

The dependency-free C++17 core computes the corrected repeat-crawl trajectory;
it does not replay Python frames. Both implementations consume configuration
SHA-256:

    740435586abad7735521b279ea7f73a0815adeaa31d72cee29381d94bbea774f

The 14.600 s path executes 164 LIF neurons, 307 delayed sparse synapses, 144
mapped sources, 146 named fibers, 13 body nodes, feedback, and physical cycle
detection. All 164 spike summaries and all 488 sampled node, activation, and
force frames match within their declared ceilings. Three complete cycles and
three physical waves match.

The native sampled path matches the Python sampled maximum backward retrace
(16.294 um), cumulative backward travel (81.996 um), and progress efficiency
(0.8508). The Python full-timestep gate is stricter: 16.627 um maximum retrace
and 0.8298 efficiency. All movement gates pass.

This is numerical parity for a `research_approximation`, not biological
validation. The third held-out diagnostic passes its rows but is not independent;
`release_validated=false` remains mandatory.

## Fixture and numerical acceptance

`data/parity/repeat_crawl_native_v1.tsv` carries the complete frozen neural,
sensory, force, contact, geometry, per-segment activation-decay, active-length,
and per-fiber coverage state. The fixture retains the no-action boundary.

| Quantity | Absolute tolerance | Observed maximum error |
|---|---:|---:|
| sample time (s) | 3e-15 | within tolerance |
| sampled node coordinate (um) | 5e-8 | 5.089e-10 |
| segment activation | 5.1e-10 | 4.998e-10 |
| node force (model units) | 2e-7 | 1.404e-9 |
| world-x displacement (um) | 1e-8 | 2.790e-10 |
| median signed stride (um) | 1e-8 | 4.945e-12 |
| sampled maximum retrace (um) | 1e-8 | 3.206e-11 |
| spike count | exact | all 164 exact |

Normal, no-input, A6 shortening-sensory lesion, A4 premotor lesion, all mapped
A6 MN lesion, and all A6 fiber lesion conditions match. Invalid intervention
IDs fail closed. All nonzero force frames preserve earlier ordered ancestry.

![Python and C++ repeat-crawl parity](assets/oraclarva_repeat_native_parity.gif)

## Reproduction

```bash
python tools/export_repeat_crawl_trajectory.py --check
python tools/evaluate_repeat_crawl.py --check
python tools/export_native_repeat_fixture.py --check
python tools/export_native_repeat_parity.py --check
python tools/render_native_repeat_parity_gif.py
pytest -q tests/test_native_repeat_parity.py
```

GitHub Actions remains manual-only through `workflow_dispatch`.
