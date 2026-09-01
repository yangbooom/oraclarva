# Repeat-crawl native parity v1

## Result

The dependency-free C++17 core computes the corrected repeat-crawl trajectory;
it does not replay Python frames. Both implementations consume the generated
fixture with configuration SHA-256:

    6c6bcec355391b72e2b694c37400fc4fc8880812b78015b39bcfc0d244e11494

The 14.600 s path executes 164 LIF neurons, 307 delayed sparse synapses, 144
mapped sources, 146 named fibers, per-segment activation decay and active
length, 13 body nodes, current-force-aware contact retention, feedback, and
physical cycle detection. All 164 spike counts/first times and all 488 sampled
frames match within the declared ceilings. Three complete cycles and three
physical waves match.

This is numerical parity for a `research_approximation`, not biological
validation. The reused held-out diagnostic fails A5/A6 duty and cannot support
an independent validation claim. `release_validated=false` remains mandatory.

## Fixture and numerical acceptance

`data/parity/repeat_crawl_native_v1.tsv` explicitly carries body-segment maximum
shortening, wave-specific decay tau, and per-fiber atlas-coverage projection
scale in addition to the neural, sensory, force, contact, and geometry state.
The fixture retains the no-action boundary.

The checked report is `data/parity/repeat_crawl_native_parity_v1.json`:

| Quantity | Absolute tolerance | Observed maximum error |
|---|---:|---:|
| sample time (s) | 3e-15 | within tolerance |
| sampled node coordinate (um) | 5e-8 | 5.165e-10 |
| segment activation | 5.1e-10 | 4.998e-10 |
| node force (model units) | 2e-7 | 1.789e-9 |
| world-x displacement (um) | 1e-8 | 3.055e-10 |
| median signed stride (um) | 1e-8 | 1.569e-11 |
| spike count | exact | all 164 exact |

Normal, no-input, A6 shortening-sensory lesion, A4 premotor lesion, all mapped
A6 MN lesion, and all A6 fiber lesion conditions match. Invalid intervention
IDs fail closed. All nonzero force frames preserve ordered earlier ancestry.

The paired GIF uses 51 retained comparison frames and applies the same smooth
render construction to independently computed Python and C++ nodes. The black
head dot was removed; the figure explicitly labels anatomical forward and says
there is no eye marker.

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

GitHub Actions remains manual-only through `workflow_dispatch`; these gates are
local and do not trigger CI.
