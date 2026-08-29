# Closed-loop embodied L1 research model v0

## What now runs

`oraclarva-organism` executes one continuous causal chain:

```text
posterior environmental touch
  -> touch receptor LIF spikes
  -> A27h-like segmental premotor LIF spikes
  -> motor-pool LIF spikes + local PMSI-like inhibitory LIF spikes
  -> 58 curated MN identity LIF neurons (A1 causal, A2 diagnostic)
  -> thresholded motor-excitation and asymmetric muscle activation dynamics
  -> 358 named A1-A6 fiber proxies -> mean axial segment activation
  -> XPBD segment shortening and ground contact
  -> shortening-sensitive proprioceptor current
  -> next anterior premotor population
```

A single posterior stimulus propagates from A7 through T3. No function chooses `crawl`, a direction, a gait phase, or a prerecorded pose. Forward displacement is the numerical result of internal force, body deformation, gravity, contact, and direction-dependent tangential retention. The body coordinate increases anterior-to-posterior, so forward motion has negative x displacement.

The phase-and-contraction-fitted v0 fixture currently moves its center about 15.8 µm during a 4.5 s run. A7 motor activity begins near 0.006 s and the wave reaches T3 near 1.849 s. All seven simulated adjacent onset delays and all 24 contraction amplitude, shortening-rate, and duration comparisons fall inside the checked-in Greaney L1 animal-level p10-p90 bands. These are in-sample calibration results, not held-out validation. Each segment's PMSI-like pool inhibits its motor pool and limits repeated motor firing while preserving the A7-to-T3 wave. An A4 premotor lesion preserves A7-A5 activation but eliminates A4-T3 motor spikes and active shortening. With `--no-touch`, no neuron spikes, no muscle activates, and the body stays at rest. In the normal run, all 358 supported A1-A6 fiber identities receive the aggregate segment signal. Lesioning all 60 A4 identity proxies leaves the A4 motor pool firing but removes A4 contraction and proprioceptor spikes, so the neural wave stops before A3. The executable network now contains 91 LIF neurons: 33 reduced sensory, premotor, inhibitory, and aggregate motor units plus 58 curated motor identities. All 58 resolved CATMAID motor identities fire in the normal run. The 56 A1 identities causally drive A1 activation through a normalized mean; the two A2 MN25 identities remain diagnostic because that segment's crosswalk coverage is partial. Lesioning the 56 A1 identities preserves the aggregate A1 motor-pool spike but removes A1 contraction/proprioception and T3 firing.

## Evidence and approximation boundary

The reduced topology combines several published observations and modeling precedents:

- Fushiki et al. identified A27h as a forward-wave premotor neuron and confirmed A27h connectivity to motor neurons in L1 EM (`10.7554/eLife.13253`).
- Hughes and Thomas experimentally supported segmental proprioceptive feedback and the contraction-completion or “mission accomplished” concept (`10.1016/j.mcn.2007.04.001`).
- Kohsaka et al. showed that larval PMSIs are inhibitory segmental premotor interneurons that limit motor-burst duration (`10.1016/j.cub.2014.09.026`). This supports the motif only; it does not supply the v0 L1 current or timing.
- Pehlevan, Paoletti, and Mahadevan modeled stretch-threshold feedback to the next anterior controller together with frictional neuromechanics (`10.7554/eLife.11031`).
- Zarin et al. reconstructed a full segment of motor and premotor circuitry and showed distributed motor recruitment (`10.7554/eLife.51781`).
- Greaney et al. provide the L1 segment-level kinematic bands used for the explicit in-sample plausibility fit (`10.1523/JNEUROSCI.1623-25.2026`).

This evidence supports the architecture, not the v0 numeric values. The proprioceptor-to-next-premotor edge and PMSI-like termination motif are `ANATOMY_DERIVED`; neither is represented as a complete identified monosynaptic circuit. Every numeric neural, transduction, activation, adaptation, inhibition, and contact value in `data/organism/l1_closed_loop_v0.json` is `MODEL_FITTED`. The reduced relay delays, assumed 2.5 s cycle period, PMSI timing/current, activation thresholds, time constants, and segment shortening capacities are fitted. The capacity fit uses L1 segment kinematics; it is not a direct measurement of individual muscle maximum shortening. The A1-A6 identity expansion uses the audited muscle atlas, while equal recruitment and mean axial aggregation remain a MODEL_FITTED proxy. The 58 skeleton IDs, names, sides, and target identities are source-backed; their common LIF input and normalized A1 pooling gain are MODEL_FITTED.

## Motor-to-muscle equations

For every simulated step, a motor spike adds a dimensionless excitation impulse and the excitation state decays exponentially:

```text
e(t + dt) = e(t) exp(-dt / tau_e) + motor_spike * delta_e
u(t) = 1 when e(t) >= theta_e, otherwise 0
a(t + dt) = a(t) + (u(t) - a(t)) * (1 - exp(-dt / tau_on_or_off))
L_target_i(t) = L_rest_i * (1 - shortening_capacity_i * a_i(t))
```

The activation and relaxation time constants can differ by segment, but every value is positive, every modeled segment must be present, and each shortening capacity is rejected if it exceeds the declared body-model upper bound. These equations smooth neural events into continuous forces; they do not select a behavior or prescribe a trajectory.

## Calibration result and remaining boundary

The simulator extracts contraction amplitude, maximum shortening rate, and duration from every segment-length trace using linearly interpolated 75%-amplitude crossings. A thresholded motor-excitation state drives continuous first-order muscle activation with separate activation and relaxation time constants. Segment shortening capacities remain bounded by the body-model prior. No pose, gait phase, or displacement is prescribed.

The current in-sample screen passes all 24 T3-A7 contraction comparisons. Examples: A7 reaches 49.0% shortening, 58.7 µm/s, and 2.00 s; A4 reaches 49.3%, 61.8 µm/s, and 1.93 s; T3 reaches 33.3%, 45.4 µm/s, and 1.58 s. All are within their source animal-level p10-p90 bands. The seven adjacent onset-phase comparisons also pass.

Passing does not establish a validated L1 gait. The same Greaney cohort was used to fit these parameters, its environment was a water-saturated agarose channel rather than an unconstrained free surface, and it did not observe L1 muscle recruitment. Absolute segment rest lengths are not fitted because the v0 body segmentation remains a separate 0.9 mm geometry hypothesis. PSC, T1, T2, A8, left-right circuitry, real 3D attachments, and independent held-out animals remain absent. The runtime therefore emits `release_validated: false`.

The A1-A6 muscle layer preserves 358 left/right fiber identities, and the neural layer instantiates all 58 resolved A1/A2 CATMAID motor identities. Only A1 is a causal identity proxy: A2 contains just two MN25 identities, three supplementary skeleton IDs are unresolved, and other segments retain aggregate motor pools. Individual fiber geometry is still not executed. A deterministic 151-frame artifact now carries the Python body's 13 internal XPBD nodes into the continuous-surface viewer without a renderer-authored wave. The next iteration should establish a shared Python/native parity fixture for the mobile core.

## Commands

```bash
oraclarva-organism
oraclarva-organism --no-touch
oraclarva-organism --lesion-premotor A4
oraclarva-organism --lesion-muscle-segment A4
oraclarva-organism --lesion-motor-identity-segment A1
pytest tests/test_organism.py
```
