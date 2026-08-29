# Bilateral steering v0

This branch adds a research-only left/right steering capacity to the embodied L1
reference model. It does not add `turnLeft()`, `turnRight()`, an FSM, a policy
network, or a renderer-authored gait. The executed chain remains:

```text
left/right receptor current
  -> rectified sensory difference + shared posterior drive
  -> 126 sparse LIF neurons
  -> side-resolved motor pools and 58 curated motor identities
  -> 358 named A1-A6 muscle-fiber proxies
  -> bilateral activation and active-curvature XPBD
  -> side-rail shortening feedback
```

## What is source-backed

- Berni 2015 reports turn-associated unilateral output in T2, T3, A1, and A2
  and shows that appropriate midline connectivity is required for asymmetric
  output ([DOI 10.1016/j.cub.2015.03.023](https://doi.org/10.1016/j.cub.2015.03.023)).
- Pulver et al. 2015 reports fictive left-right asymmetric motor activity in the
  same anterior region as intact-larva turning
  ([DOI 10.1152/jn.00731.2015](https://doi.org/10.1152/jn.00731.2015)).
- The 58 A1/A2 motor-neuron identities and their sides retain the audited
  published mapping already used by the straight closed loop.

These papers support an anterior unilateral topology prior. Pulver et al. used
third-instar animals, and neither paper is used as an L1 numeric parameter
source. They do not provide the v0 synaptic currents, delays, L1 muscle moment
arms, or a complete identified turning circuit.

## What is approximated

The rectified left-right sensory transform, shared bilateral posterior drive,
T3-to-A2 asymmetric projection, its 0/30/60 ms delays, common LIF currents,
active-curvature gain, bending ratio, equal muscle recruitment, and virtual
side-rail proprioception are `MODEL_FITTED` or `ANATOMY_DERIVED`. Individual
attachment coordinates, CSA, force gains, and measured bending constants are
not executed.

The active-curvature gain is 0.10. It was selected as the largest tested stable
fixture before the 0.20 case showed non-monotonic progression; it is not a
measured L1 curvature coefficient. The left/right response at this setting is
an exact numerical mirror:

| receptor intensity (L/R) | x displacement | y displacement | heading change | max lateral deformation |
|---|---:|---:|---:|---:|
| 1.0 / 1.0 | about -15.8 µm | 0 | 0° | 0 |
| 1.0 / 0.0 | about -11.5 µm | about -1.8 µm | about +2.46° | about 103 µm |
| 0.0 / 1.0 | mirror of left | mirror of left | about -2.46° | about 103 µm |
| 0.0 / 0.0 | 0 | 0 | 0° | 0 |

The center-of-mass lateral sign need not match the heading sign during a soft
body pivot; direction is computed from the anterior-to-posterior body axis.
These numbers are deterministic regression outputs, not held-out biological
validation.

## Causal lesion gates

- A `T3:left` premotor lesion removes only that neural-to-motor channel and
  strongly reduces the left-turn heading change.
- An `A1:left` motor-identity lesion preserves the aggregate A1 motor-pool spike
  but removes left A1 activation through the 28 resolved A1 identities.
- An `A1:left` muscle lesion preserves upstream neural activation but removes
  the 29 left A1 fiber proxies from the applied mechanics.

Python and dependency-free C++17 execute the same 126 neurons, 130 synapses,
body mechanics, bilateral activation, and feedback. CI compares every spike,
first-spike time, activation, shortening value, and all 151 trajectory frames
in symmetric, left, right, zero-input, and three lesion conditions.

## Run and inspect

```bash
oraclarva-bilateral --left 1 --right 0 --trajectory-interval 0.03
python tools/export_bilateral_trajectory.py --check
python tools/export_native_bilateral_fixture.py --check
pytest tests/test_bilateral.py tests/test_native_bilateral_parity.py
```

The diagnostic viewer consumes
`data/trajectories/l1_bilateral_steering_v0.json`. The PR animation is generated
from the same artifact at `docs/assets/oraclarva_bilateral_steering.gif`.

`release_validated` remains `false`.
