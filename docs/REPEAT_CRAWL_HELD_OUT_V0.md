# Repeat crawl corrective mechanics and held-out diagnostic v0

## Result

One posterior touch produces three complete A6-to-A1 physical waves without a
periodic stimulus, gait command, FSM, policy network, or animation-authored
displacement. The checked causal path remains:

    environment touch -> sensory transduction -> sparse LIF -> mapped MN
      -> named-fiber activation -> reduced axial muscle/body physics
      -> contact environment -> shortening/recovery sensation

The corrected 14.600 s run has A6 premotor boundaries at 0.003, 4.998, 9.565,
and 14.132 s. Every active mechanical frame retains earlier sensory, premotor,
MN, and activation ancestry. Zero input remains silent.

The world body coordinate increases anterior-to-posterior, so anatomical
forward is negative world x. The checked result reports
`displacement_x_um = -467.539` and `forward_displacement_um = +467.539`.
The render has no eye marker and labels anatomical forward explicitly.

## Back-slip correction

The preceding artifact was net-forward but not a credible forward-crawl visual.
Its whole-body center moved backward during 181 of 487 timestep intervals; the
maximum peak-to-trough retreat was 476.201 um, and the 51-frame GIF still showed
436.016 um. A final positive displacement alone did not detect that rocking.

Component sweeps showed that the `MODEL_FITTED` named-fiber force-to-acceleration
scale dominated the retreat. Scaling target shortening alone left more than
413 um of retreat. The correction therefore:

- reduces `acceleration_scale_m_s2_per_model_force` from 0.003 to 0.0003;
- uses a one-way bristle/denticle-like tangential retention approximation
  (forward 1.0, posterior 0.0), explicitly `MODEL_FITTED` and not a measured
  L1-on-agar coefficient;
- retains active target shortening, traced named-fiber force, local axial force
  projection, left/right coverage normalization, and the passive bending gate;
- measures maximum backward retrace and cumulative backward travel at every
  1 ms body step;
- rejects runs above 25 um maximum retrace or below 0.8 forward-progress
  efficiency.

These are contact and mechanics parameters, not a movement command. No
coordinate, CSA, Fmax, stress, or force value is relabeled as measured. Force
remains in model units.

## Measurement and gates

Contraction onset is the downward 25% shortening crossing. Contraction offset is
the later upward crossing through the same threshold, including when recovery
extends beyond the next cycle boundary. The three-cycle medians are:

| Metric | Model | Calibration p10-p90 | Calibration |
|---|---:|---:|:---:|
| cycle period (s) | 4.567 | 3.752-6.125 | pass |
| signed forward stride (um) | 153.446 | 140.327-179.485 | pass |
| A6-A1 physical wave speed (segment/s) | 1.668 | 1.468-2.122 | pass |

| Segment | length change (%) | duty (%) | Calibration |
|---|---:|---:|:---:|
| A1 | 46.233 | 34.160 | pass |
| A2 | 46.831 | 37.773 | pass |
| A3 | 49.916 | 40.232 | pass |
| A4 | 51.271 | 45.117 | pass |
| A5 | 49.526 | 46.537 | pass |
| A6 | 48.596 | 42.496 | pass |

The full-timestep maximum backward retrace is 16.627 um, cumulative backward
travel is 95.873 um, and forward-progress efficiency is 0.8298. The 30 ms
retained trajectory measures 16.294 um maximum retrace. Lateral displacement,
maximum lateral span, and planar deviation are zero; minimum forward segment
alignment is 0.954 and minimum head-tail chord/polyline ratio is 0.994.

## Held-out honesty

This is the third evaluation of the six-animal held-out partition. All
diagnostic rows now fall inside their target bands, but this is not independent
validation: the partition was visible and had already been evaluated before
the mechanics revisions. Corrective selection used calibration values and the
observer-raised back-slip gate, not held-out values.

The report therefore says `diagnostic_held_out_passed` while keeping
`independent_validation_passed=false`, `fail_closed=true`, and
`release_validated=false`. A diagnostic pass cannot recover the spent held-out
status.

## Failure gates and reproduction

Export fails unless all three cycles have ordered physical responses, every
active force is traced, signed forward displacement is positive, maximum
backward retrace and progress efficiency pass, lateral/planar limits pass, and
the body preserves segment order and chord ratio.

```bash
python tools/export_repeat_crawl_trajectory.py --check
python tools/evaluate_repeat_crawl.py --check
python tools/render_repeat_crawl_gif.py
pytest -q tests/test_repeat_crawl.py tests/test_body.py tests/test_muscles.py
```

The GIF is generated only from checked body nodes and activations. Its smooth
skin is a read-only render construction. GitHub Actions remains manual-only
through `workflow_dispatch`.
