# Repeat crawl and held-out evaluation v0

## Result

Stage 6 generates three complete posterior-to-anterior A6-A1 cycles after one
posterior touch. There is no periodic stimulus, gait command, finite-state
machine, policy network, or animation-authored displacement. Each repeated wave
must return through the body:

    initial posterior touch
      -> touch receptor -> sparse LIF premotor -> mapped MN identities
      -> one-step muscle activation -> 146 named-fiber attachment forces
      -> shared 13-node body shortening/recovery
      -> shortening receptor for the next anterior segment
      -> A1 recovery receptor -> delayed A6 restart

The checked 16 s run contains A6 premotor events at 0.003, 4.995, 10.006, and
15.017 s. Every nonzero attachment-force frame has an earlier body-state or
declared initial-touch sample, sensory spike, premotor spike, mapped MN spike,
and activation event. Zero input remains silent.

This is a research approximation, not validated L1 crawling. The frozen model
passes held-out timing and stride but fails every segment-shape comparison.
release_validated therefore remains false.

## Evidence and parameter boundary

The reduced shortening-to-next-premotor and A1-recovery-to-A6 topology is
ANATOMY_DERIVED. It is a segmental circuit hypothesis, not a claim that these
are identified monosynaptic L1 edges. A1 uses published mapped motor identities
where available; A2-A6 use the existing explicitly derived homolog channels.
T3 and A7 remain blocked because the attachment runtime supports A1-A6 only.

Every new current, delay, adaptation constant, sensory gain, activation
constant, attachment tension, passive stiffness, damping, acceleration scale,
and friction value is MODEL_FITTED. Tension remains in model units, never
newtons. No measured attachment coordinate, CSA, Fmax, or specific stress is
introduced.

The 12-animal Greaney calibration partition was used to select the frozen
candidate. Held-out values already existed in the repository, so the project
does not claim they were inaccessible; it records the narrower and auditable
claim that candidate selection did not use them. The frozen config SHA-256 is:

    5cbaec6a716cf2b8dd2d8e053b00469f5e9f09389fa74645c17a148143b936e3

Candidate force scales below the selected fixture produced first-cycle strides
of 51.553 µm (50x) and 111.350 µm (100x), below the calibration p10. The
selected 126x model-unit combination produced 143.397 µm on the first
calibration run. These labels describe relative model-force products, not
biological force.

## Physical metric detector

Successive body-caused A6 premotor events bound a cycle. For each traceable
segment premotor event, the detector searches only the next 0.8 s of that
segment's physical length. Onset is the first 25% shortening crossing and
contraction end is the minimum length in that response window. Missing physical
responses or a non-posterior-to-anterior onset order make physical wave speed
fail closed. The neural event speed is retained only as a diagnostic and is not
substituted for a missing physical metric.

The frozen three-cycle medians are:

| Metric | Model | Calibration p10-p90 | Held-out p10-p90 | Held-out |
|---|---:|---:|---:|:---:|
| cycle period (s) | 5.011 | 3.752-6.125 | 4.104-5.384 | pass |
| stride (µm) | 145.866 | 140.327-179.485 | 129.765-159.675 | pass |
| A6-A1 physical wave speed (segment/s) | 1.673 | 1.468-2.122 | 1.578-2.345 | pass |

Segment shape does not match:

| Segment | Model length change (%) | Held-out p10-p90 | Model duty (%) | Held-out p10-p90 |
|---|---:|---:|---:|---:|
| A1 | 0.010 | 38.984-52.688 | 7.509 | 32.546-44.774 |
| A2 | 0.113 | 44.762-52.118 | 0.133 | 35.321-48.959 |
| A3 | 0.118 | 45.757-53.757 | 0.173 | 38.201-49.580 |
| A4 | 0.092 | 48.055-54.029 | 0.173 | 43.246-52.128 |
| A5 | 0.071 | 46.707-53.192 | 12.104 | 45.825-52.538 |
| A6 | 0.025 | 48.585-53.859 | 0.473 | 41.628-47.306 |

The six-animal held-out partition was evaluated once after the config and
trajectory were frozen. Parameters were not changed afterward. Passing three
global timing metrics does not override the twelve failed amplitude/duty rows.

## Lesion and failure gates

- no initial touch: zero spikes, zero force, zero translation;
- A6 shortening-sensory lesion: A6 fires from touch, A5 and later do not;
- A4 premotor lesion: A6 and A5 remain, A4 and later do not;
- all A6 mapped-MN lesion: A6 premotor remains, MN spikes and force disappear;
- all A6 fiber lesion: premotor and MN spikes remain, force disappears;
- invalid sensory, MN, or fiber IDs are rejected;
- fewer than three complete cycles, missing trace ancestry, or failed physical
  onset order blocks export or validation.

## Reproduction

The checked artifact and reports are:

- data/trajectories/l1_repeat_crawl_v0.json
- data/validation/repeat_crawl_calibration_v0.json
- data/validation/repeat_crawl_held_out_v0.json

    python tools/export_repeat_crawl_trajectory.py --check
    python tools/evaluate_repeat_crawl.py --check
    python tools/render_repeat_crawl_gif.py
    pytest -q tests/test_repeat_crawl.py tests/test_kinematics.py

The GIF is rendered only from checked body nodes and activation values. Its
smoothed capsule-union skin is a render mesh over the internal mechanics, not
an animation that changes motion.

## Native impact and next gate

This repeat path is Python-only. Existing native fixtures are unchanged and
must continue to pass locally. Stage 7 must add a shared native fixture for the
164-node reduced repeat network, delayed sensory relays, adaptation, mapped MN
events, 146-fiber activation/force, 13-node body state, trace ancestry, all
lesion cases, and three complete cycles. Native/mobile support is not claimed
until that parity gate passes.

GitHub Actions remains manual-only through workflow_dispatch and was not run
for this stage.
