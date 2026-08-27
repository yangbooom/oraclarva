# Oraclarva L1 Three.js viewer

This viewer reads `../data/body/l1_body_v0.json`; it does not keep an independent
copy of the morphology parameters.

## Run

```bash
npm install
npm run dev
```

For a production bundle:

```bash
npm run build
```

## What the animation means

- The wave travels from posterior to anterior.
- A contracting region shortens by up to the configured 45% active limit.
- Width and height grow with `sqrt(1 / axial_scale)`, an approximate
  volume-preservation relation.
- Rendering never moves the simulated body independently of body state.

The current body surface is a visualization of the v0 parameter bundle, not a
measured L1 mesh. Evidence status stays visible because nominal length, maximum
width, height ratio, length fractions, and width scales are hypotheses or
constraints pending a calibrated L1 image cohort.
