# Closed-loop embodied L1 research model v0

## What now runs

`oraclarva-organism` executes one continuous causal chain:

```text
posterior environmental touch
  -> touch receptor LIF spikes
  -> A27h-like segmental premotor LIF spikes
  -> motor-pool LIF spikes
  -> low-pass muscle activation
  -> XPBD segment shortening and ground contact
  -> shortening-sensitive proprioceptor current
  -> next anterior premotor population
```

A single posterior stimulus propagates from A7 through T3. No function chooses `crawl`, a direction, a gait phase, or a prerecorded pose. Forward displacement is the numerical result of internal force, body deformation, gravity, contact, and direction-dependent tangential retention. The body coordinate increases anterior-to-posterior, so forward motion has negative x displacement.

The v0 fixture currently moves its center about 9 µm during a 2.5 s run. An A4 premotor lesion preserves A7-A5 activation but eliminates A4-T3 motor spikes and active shortening, establishing a traceable neural lesion effect. With `--no-touch`, no neuron spikes, no muscle activates, and the body stays at rest.

## Evidence and approximation boundary

The reduced topology combines several published observations and modeling precedents:

- Fushiki et al. identified A27h as a forward-wave premotor neuron and confirmed A27h connectivity to motor neurons in L1 EM (`10.7554/eLife.13253`).
- Hughes and Thomas experimentally supported segmental proprioceptive feedback and the contraction-completion or “mission accomplished” concept (`10.1016/j.mcn.2007.04.001`).
- Pehlevan, Paoletti, and Mahadevan modeled stretch-threshold feedback to the next anterior controller together with frictional neuromechanics (`10.7554/eLife.11031`).
- Zarin et al. reconstructed a full segment of motor and premotor circuitry and showed distributed motor recruitment (`10.7554/eLife.51781`).
- Greaney et al. provide the L1 segment-level kinematic bands that future fitting must target (`10.1523/JNEUROSCI.1623-25.2026`).

This evidence supports the architecture, not the v0 numeric values. The proprioceptor-to-next-premotor edge is `ANATOMY_DERIVED`; it is not represented as an identified monosynaptic connection. Every numeric neural, transduction, activation, adaptation, and contact value in `data/organism/l1_closed_loop_v0.json` is `MODEL_FITTED` with status `engineering_baseline_not_kinematically_fitted`.

## Known failures and next calibration

The current intersegment onset delay is about 7 ms, much faster than the observed L1 phase structure. The motor pools collapse many bilateral neurons and muscles into one longitudinal actuator per region. GDL/PMSI inhibition, relaxation timing, left-right circuits, T1/T2/PSC/A8 coverage, full connectome identities, real attachment geometry, and free-surface friction measurements are absent.

Therefore this is evidence of a working embodied neural causal loop, not a validated L1 brain or gait. The next iteration must fit sensory adaptation and excitation/inhibition dynamics against the checked-in Greaney animal-level bands, then expand each reduced motor pool through the curated MN-muscle identities without relabeling fitted gains as measurements.

## Commands

```bash
oraclarva-organism
oraclarva-organism --no-touch
oraclarva-organism --lesion-premotor A4
pytest tests/test_organism.py
```
