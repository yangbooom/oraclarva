# L1 body-state sensory feedback v0

## Result

Stage 5 closes one evidence-bounded body-state loop on the same 13-node body
used by the 146 named fibers:

```text
shared-body A1 length/strain
  -> MODEL_FITTED dbd mechanotransduction current
  -> two MEASURED_PUBLISHED A1 dbd sensory identities
  -> sparse LIF dynamics
  -> three published one-contact dbd-to-MN edges that overlap the runtime
  -> MN spikes
  -> named-fiber events and one-step-delayed activation
  -> attachment tension and shared-node physics
  -> next body-state sample
```

There is no stretch response command and no direct write to muscle activation,
body position, or velocity. Under zero light, an isolated A1 stretch produces
dbd spikes, later MN spikes, four mapped-fiber forces, and a changed physical
trajectory. Lesioning dbd preserves the measured stretch but removes downstream
spikes and active force. MN and individual-fiber lesions block only their later
causal stages.

![Body state, visual input, and named-fiber body loop](assets/oraclarva_l1_visual_connectome.gif)

## Published structural boundary

Greaney, Wreden, and Heckscher analyzed a 6-hour-old first-instar CNS EM
reconstruction ([DOI](https://doi.org/10.3389/fncir.2023.1223334), CC BY 4.0).
The paper identifies six proprioceptors per abdominal hemisegment: `dbd`,
`vbd`, `ddaD`, `ddaE`, `vpda`, and `dmd1`. `dbd` is the stretch receptor; the
other five are described as contraction-sensing proprioceptors.

Figure 7D reports seven A1 motor targets and eleven direct dbd contacts:

| observed target | dbd side | contacts | Stage 5 execution |
|---|---|---:|---|
| MN-1 L | A1L | 1 | yes; existing mapped MN |
| MN-18 L | A1L | 1 | yes; existing mapped MN |
| MN-21/22 R | A1R | 1 | yes; existing mapped MN |
| RP2 L | A1L | 1 | no; absent from current 146-fiber runtime |
| RP2 R | A1R | 2 | no; absent from current 146-fiber runtime |
| MN-4 L | A1L | 3 | no; absent from current 146-fiber runtime |
| MN-4 R | A1R | 2 | no; absent from current 146-fiber runtime |

`data/connectome/l1_dbd_motor_feedback_v0.json` preserves all 7 pairs and 11
contacts. Only the three one-contact edges whose MN identities already feed the
current named-fiber projection execute. Missing targets are not redirected to a
generic motor pool. A1 counts are not copied into A2-A6.

Structural contacts and sensory identity are `MEASURED_PUBLISHED`. The dbd
neurotransmitter remains `unknown`. Excitatory effect, current per contact, LIF
response, mechanotransduction threshold, and gain are `MODEL_FITTED`; the source
does not measure those values.

## Body-state transform

For each A1-A6 segment, the transducer measures physical node distance `L`, its
equilibrated reference `L0`, strain, and finite-difference strain rate:

```text
strain = (L - L0) / L0
strain_rate = (L(t) - L(t-dt)) / (dt * L0)
```

The fitted dbd drive is a bounded sum of thresholded positive strain and
positive strain rate. The contraction ensemble uses the same form on negative
strain and negative strain rate. Every fitted value has a declared calibration
range and the narrow objective of stable zero-input silence plus directional
perturbation response. None is labeled a measured L1 mechanotransduction
constant.

A1 sensory identity is measured. A2-A6 homolog identity is
`ANATOMY_DERIVED`, and those channels remain diagnostic because the A1 contacts
are not repeated. The shared axial body currently gives equal left/right
segment length; that is an explicit model limitation, not a measured bilateral
strain field.

Contact state and depth are read from the same ground or `ContactSurface` used
by physics. A fitted 0.25 touch drive makes exact surface contact observable;
penetration raises it toward one over a fitted 2 um range. The value stays
diagnostic, and `contact_neural_path_executed` remains `false`: no supported L1
contact-to-MN edge has been inserted. The contraction-sensing ensemble is also
recorded with zero executable current in v0.

## Force trace invariant

Every feedback-associated active fiber stores:

1. body-state sample time;
2. dbd sensory node and spike time;
3. mapped MN node and spike time;
4. activation and force-frame time.

The runtime requires
`body state <= dbd spike < MN spike <= applied source spike < force frame`. A
feedback label is retained only when the dbd-to-MN latency is within the fitted
50 ms attribution window and the recorded MN spike exactly matches the muscle
event source time. An incomplete, stale, or out-of-order trace raises an exception. This is causal audit
bookkeeping; it does not prove that a mixed-input MN spike was exclusively
caused by dbd. The zero-light stretch fixture isolates that interpretation.

## Held-out L1 kinematics

The checksum-pinned Greaney 2026 `comboResults.mat` contains 18 behavior-only
L1 animals with at least 50 accepted cycles each. Schema v2 keeps animals
intact and predeclares a source-order split:

- calibration: 12 animals;
- held-out validation: 6 animals (every third selected animal, beginning at
  source index 2);
- no cycle from one animal appears in both sets;
- target values and model output were not used to choose the split.

The artifact now includes individual-animal records, segment length change,
duty cycle, stride, crawl speed, cycle period/frequency, and a derived T3-A7
wave speed in segment intervals per second. Each target stores p10, median,
p90, and a deterministic 2,000-resample animal bootstrap 95% interval for the
median.

Selected held-out medians are:

| metric | held-out median | bootstrap 95% interval |
|---|---:|---:|
| stride | 149.495 um | 129.765–159.675 um |
| T3-A7 wave speed | 2.052 segment intervals/s | 1.931–2.598 |
| A1 duty cycle | 37.100% | 32.546–44.774% |

Stage 5 did not tune parameters against held-out animals. More importantly,
the current visual/body-feedback fixture does not generate repeatable natural
crawl cycles, so it cannot yet report a valid stride, duty cycle, or wave-speed
comparison. The split is ready, but `release_validated` remains `false`; an
unavailable metric is not converted into a pass.

## Reproduction and local gates

The raw 68 MB MAT is not vendored. Its required SHA-256 is
`b3b7f2149d6dd247064968bbd5abaf5d94ef3b945b5a3b846d3ce9ee3287bf94`.

```bash
python -m pip install -e '.[data]'
python tools/extract_greaney_2026_l1_kinematics.py \
  comboResults.mat data/validation/greaney_2026_l1_kinematics_v0.json
python tools/export_visual_trajectory.py --check
python tools/evaluate_body_feedback_held_out.py --check
python tools/render_visual_gif.py
pytest tests/test_body_sensing.py tests/test_kinematics.py tests/test_visual.py
```

GitHub Actions remains manual-only (`workflow_dispatch`). Stage 5 validation is
performed locally; this work does not trigger CI.

## Native parity impact

The three existing native fixture schemas and outputs are unchanged. This new
path adds two sensory compartments, 3 executable sparse contacts, body-state
frames, and feedback force ancestry only to the Python visual reference. It is
therefore an explicit native parity gap. A mobile core must match transduction,
dbd/MN spike timing, applied named-fiber events, per-frame feedback trace, node
forces, and 13-node trajectories before this path can be accepted for product
execution.
