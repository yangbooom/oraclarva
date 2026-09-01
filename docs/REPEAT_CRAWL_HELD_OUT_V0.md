# Repeat crawl corrective mechanics and held-out diagnostic v0

## Result

One posterior touch produces three complete A6-to-A1 physical waves without a
periodic stimulus, gait command, FSM, policy network, or animation-authored
displacement. The checked causal path remains:

    environment touch -> sensory transduction -> sparse LIF -> mapped MN
      -> named-fiber activation -> reduced axial muscle/body physics
      -> contact environment -> shortening/recovery sensation

The corrected 14.600 s run has A6 premotor boundaries at 0.003, 4.997,
9.715, and 14.417 s. Every active mechanical frame retains earlier sensory,
premotor, MN, and activation ancestry. Zero input remains silent.

The world body coordinate increases anterior-to-posterior, so anatomical
forward is negative world x. The checked result reports both quantities:
`displacement_x_um = -299.962` and `forward_displacement_um = +299.962`.
The render no longer draws a black head dot: it shows an explicit left-pointing
anatomical-forward label, and there is no eye marker.

## Corrected mechanics boundary

The earlier artifact was invalid as a forward-crawl visual: it accepted positive
world-x stride even though node 0 is anterior, current-step muscle acceleration
bypassed directional ground retention, and muscle activation did not update the
body's active target length. The chain could therefore translate posteriorly
while buckling laterally.

The correction is restricted to biological/physical model layers:

- directional retention acts on velocity plus current external acceleration;
- mean traced A1-A6 activation updates active segment target length;
- per-segment activation decay and maximum shortening are `MODEL_FITTED`;
- mapped-fiber left/right sums are normalized for unequal atlas coverage;
- because individual L1 3D attachment vectors are not measured, straight-crawl
  executes only the `ANATOMY_DERIVED` local-axis component of mapped tension;
- a passive planar bending constraint resists numerical chain buckling;
- signed forward, lateral span/deviation, segment alignment, and head-tail chord
  ratio are acceptance measurements, never behavior commands.

No coordinate, CSA, Fmax, stress, or force value is relabeled as measured. Force
remains in model units. The reduced shortening relays and A1 recovery relay
remain anatomy-derived circuit hypotheses, not identified complete L1 paths.

## Measurement and gates

Contraction onset is the downward 25% shortening crossing. Contraction offset is
the later upward crossing through the same threshold, including when recovery
extends beyond the next cycle boundary. Within each A6 boundary interval, the
first strictly posterior-to-anterior premotor sequence is associated with that
wave so a trailing event cannot be assigned to a newer wave.

The three-cycle medians are:

| Metric | Model | Calibration p10-p90 | Calibration |
|---|---:|---:|:---:|
| cycle period (s) | 4.718 | 3.752-6.125 | pass |
| signed forward stride (um) | 149.361 | 140.327-179.485 | pass |
| A6-A1 physical wave speed (segment/s) | 1.667 | 1.468-2.122 | pass |

| Segment | length change (%) | duty (%) | Calibration |
|---|---:|---:|:---:|
| A1 | 46.326 | 32.979 | pass |
| A2 | 46.911 | 37.284 | pass |
| A3 | 49.993 | 39.021 | pass |
| A4 | 51.344 | 43.810 | pass |
| A5 | 49.570 | 45.213 | pass |
| A6 | 48.609 | 41.486 | pass |

The directional/shape gate also passes: lateral displacement, maximum lateral
node span, and maximum planar deviation are zero; minimum forward segment
alignment is 0.953 and minimum head-tail chord/polyline ratio is 0.994.

## Held-out honesty

The model was changed after the prior held-out evaluation. Although corrective
selection used only the 12-animal calibration bands, the six held-out animals
were already visible and had already been evaluated. A new untouched held-out
claim is therefore unavailable. The second evaluation is labeled diagnostic,
not independent.

The diagnostic held-out result fails A5 and A6 duty cycle. More importantly,
`independent_validation_passed` is false and `fail_closed` is true regardless of
individual rows. `release_validated` remains false.

## Failure gates and reproduction

Export fails unless all three cycles have ordered physical responses, all active
forces are traced, signed forward displacement is positive, lateral and planar
limits pass, every segment preserves forward order, and the chord ratio stays
above its fitted floor. Sensory, premotor, mapped-MN, and fiber lesions retain
the earlier fail-closed causal boundaries.

```bash
python tools/export_repeat_crawl_trajectory.py --check
python tools/evaluate_repeat_crawl.py --check
python tools/render_repeat_crawl_gif.py
pytest -q tests/test_repeat_crawl.py tests/test_body.py tests/test_muscles.py
```

The GIF is generated only from checked body nodes and activations. Its smooth
skin is a read-only render construction over the internal mechanics.
GitHub Actions remains manual-only through `workflow_dispatch` and is not run by
this work.
