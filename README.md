# Oraclarva

Oraclarva is an experiment in building an **on-device, connectome-driven digital organism**. The environment does not choose actions. Sensory signals enter a spiking neural network; motor-neuron activity drives muscles; body physics changes the next sensory input.

## Causal contract

```text
environment -> receptors -> neurons/synapses -> motor neurons -> muscles -> body physics
```

The simulation may contain physical and biophysical equations, but it must not contain behavioral shortcuts such as `if food: turn_left()` or animation-driven movement.

## What exists today

This repository starts with a small, auditable vertical slice:

- a unit-consistent leaky integrate-and-fire (LIF) reference simulator;
- sparse, event-driven excitatory and inhibitory synapses;
- neuron-lesion support;
- a CSV connectome audit command;
- causal tests from sensory input to motor output;
- scientific-scope and mobile-core design notes.

The current vertical slice includes a provenance-aware L1 3D body specification,
a dependency-free XPBD reference body, and one continuous watertight surface
over twelve labeled mechanical regions. Run `oraclarva-body-spec` to inspect
which parameters are observed, derived from measurements, or still hypotheses.

`data/neuromuscular/l1_motor_map_v1.json` now cross-walks 58 published CATMAID
skeleton IDs to their A1 muscle targets (MN25 is represented in A2, as in the
source). Three supplementary skeleton IDs remain unresolved in the current
public API. Muscle gains and attachment geometry are not published by this
source, so the core still refuses to let the anatomical map drive release body
physics.

The first stage-specific behavior target is also checked in. It preserves
animal-level p10/median/p90 bands from 18 first-instar L1 animals for T3-A7
length, contraction amplitude, shortening rate, duration, and phase. The gate
is deliberately a plausibility screen: it records that PSC/T1/T2/A8,
age-matching, free-surface locomotion, and L1 muscle recruitment remain absent.

The abdominal muscle atlas now enumerates 358 bilateral fiber identities across
A1-A6 (58 in A1 and 60 in each of A2-A6). It does not fabricate 3D attachments,
force gains, or thoracic/terminal homology, so it still cannot actuate the body.

This is infrastructure for a scientific model, **not yet a validated whole-brain emulation**. The included smoke circuit is synthetic and is clearly labeled as such.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
pytest
oraclarva-smoke
oraclarva-body-spec
oraclarva-motor-map-audit
oraclarva-kinematics-targets
oraclarva-muscle-atlas-audit
oraclarva-audit neurons.csv synapses.csv
```

CSV schemas are documented by `oraclarva-audit --help` and in `docs/SCIENTIFIC_SCOPE.md`.
The motor crosswalk, its exact evidence boundary, and remaining blockers are in
`docs/L1_MOTOR_CROSSWALK.md`.
The public-source manifest can be checked with `oraclarva-source-audit data/sources/source_manifest_v0.yaml`; the current file audit and exclusion decisions are in `docs/PUBLIC_SOURCE_AUDIT_2026-08-29.md`.
The kinematic screening protocol is in `docs/L1_KINEMATIC_VALIDATION.md`; the
muscle identity and geometry boundary is in `docs/L1_BODY_WALL_MUSCLE_ATLAS.md`.

## Interactive L1 body viewer

The `viewer/` app renders the same `data/body/l1_body_v0.json` bundle with
Three.js. It exposes all twelve mechanical regions on one continuous surface,
per-region nominal geometry, evidence status, orbit/zoom controls, and a
posterior-to-anterior contraction wave. Active shortening is compensated by one
aggregate body-cavity volume constraint rather than twelve sealed spherical
segments.

```bash
cd viewer
npm install
npm run dev
```

The displayed L1 length, width, and per-region profile remain explicit v0
hypotheses. The viewer does not turn them into observations.

## Non-goals for the reference core

- claiming consciousness or a complete mind upload;
- hiding missing anatomy behind behavior trees or learned control policies;
- treating anatomical connection count as proof of functional behavior;
- tuning against appearance alone without neural and behavioral validation.

The original research plan is preserved in `Drosophila Larva Whole-Brain Emulation Project.md` as historical project context.
