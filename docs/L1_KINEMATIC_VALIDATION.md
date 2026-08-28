# L1 kinematic validation target v0

## Result

Oraclarva now has a reproducible, L1-only screening target for forward crawling.
It is not a release-validation certificate. The bundle captures measured
kinematics for T3 through A7, while explicitly refusing to infer PSC, T1, T2,
A8, muscle recruitment, or unconstrained-surface locomotion.

The compact checked-in artifact is
`data/validation/greaney_2026_l1_kinematics_v0.json`. It was derived from the
upstream `comboResults.mat` at repository commit
`b9f3a82028b1223de1e5933151ad3a8ea1b10b91`. The extractor verifies the raw
file's SHA-256 before reading it, selects the 18 behavior-only first-instar
jGC7f animals with at least 50 accepted cycles, averages cycles within each
animal, and then calculates p10, median, and p90 across animals.

## What the target says

Selected population medians illustrate why a uniform-segment model is not
acceptable:

| Segment | Rest length (um) | Contraction amplitude (%) | Shortening rate (um/s) | Duration (s) | Onset phase |
|---|---:|---:|---:|---:|---:|
| T3 | 120.67 | 35.06 | 55.00 | 1.77 | 0.775 |
| A1 | 119.67 | 48.12 | 68.54 | 1.75 | 0.708 |
| A2 | 117.53 | 48.95 | 67.40 | 1.84 | 0.588 |
| A3 | 116.00 | 51.39 | 59.23 | 1.95 | 0.463 |
| A4 | 115.02 | 51.65 | 53.36 | 2.24 | 0.301 |
| A5 | 115.97 | 50.26 | 54.59 | 2.30 | 0.186 |
| A6 | 112.71 | 51.30 | 64.72 | 2.13 | 0.115 |
| A7 | 117.11 | 51.40 | 73.28 | 2.03 | 0.047 |

T3 contracts less than the abdominal regions, shortening slows near the
mid-body, and contraction duration peaks around A4-A5. Adjacent phase delays
are also nonuniform. A simulated wave must therefore be an emergent result that
is screened segment by segment, not a single animation curve copied along the
body.

## Boundary conditions that must remain visible

The source methods describe first-instar jGC7f larvae selected at an average
size of about 1 mm after 24 hours. That is not established as age-matched to the
connectome specimen, so the artifact says `age_matched_to_connectome: false`.

The animals crawled in water-saturated agarose channels, 200 or 250 um wide and
200 um deep. The source authors note that confinement, distributed friction,
water, and suppression of bending can alter coordination. The values are useful
for reproducing that preparation, not proof of free-surface behavior.

The source study's muscle-recruitment measurements came from L2 Gerry animals.
Those traces are deliberately excluded. L1 kinematics and L2 muscle recruitment
must not be merged into a single stage-specific truth bundle.

## Gate semantics

`KinematicTargetSet.screen` accepts simulated per-segment medians only when all
available metrics lie inside the observed animal-level p10-p90 bands. Missing
segments, missing metrics, and out-of-band values fail closed.

Even a perfect match returns `release_validated: false`. A release claim still
requires:

1. an age-matched L1 cohort linked to the selected connectome stage;
2. measurements for PSC, T1, T2, and A8;
3. simultaneous L1 muscle recruitment and kinematics;
4. free-surface and app-relevant substrate measurements;
5. held-out animals that were not used for parameter fitting;
6. neural and lesion predictions, not kinematic curve fitting alone.

## Reproduction

The raw MAT file is not vendored. After obtaining the exact upstream artifact:

```bash
python tools/extract_greaney_2026_l1_kinematics.py \
  comboResults.mat \
  data/validation/greaney_2026_l1_kinematics_v0.json
oraclarva-kinematics-targets
```

The extractor requires NumPy and SciPy only for regeneration; the runtime
loader and screening gate have no third-party dependency.

## Source

- Greaney MR, Heckscher ES, Kaufman MT. *Multiple Scales of Coordination
  along the Body Axis during Drosophila Larval Locomotion.* J Neurosci. 2026.
  https://doi.org/10.1523/JNEUROSCI.1623-25.2026
- Official analysis repository:
  https://github.com/kaufmanlab/larvariability-public
