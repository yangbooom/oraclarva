# Oraclarva L1 Three.js diagnostic viewer

The viewer reads the shared body hypothesis from
`../data/body/l1_body_v0.json` and the generated Python trajectory from
`../data/trajectories/l1_closed_loop_v0.json`. It has no independent gait,
Gaussian contraction wave, bend animation, or render-driven translation.

## Run

```bash
npm install
npm run dev
```

For a production bundle:

```bash
npm run build
```

Regenerate or audit the trajectory from the repository root:

```bash
python tools/export_closed_loop_trajectory.py
python tools/export_closed_loop_trajectory.py --check
python tools/check_native_viewer_trajectory.py
```

The third command compiles and runs the C++17 embodied core, then compares all
151 native frames with this viewer artifact using zero relative tolerance. The
current cross-libm maximum is 1e-9 µm for node coordinates and zero for segment
activation; CI rejects node error above 2e-9 µm or activation error above
5.1e-10.

## What playback means

- The artifact contains 151 frames sampled every 30 ms from a 4.5 s Python run.
- Each frame stores 13 internal XPBD nodes and 12 segment activation channels.
- The viewer linearly interpolates those nodes and wraps one indexed watertight
  skin around their centerline.
- Region IDs remain face labels on a continuous surface rather than separate
  balls or ellipsoids.
- Width and height share an aggregate cavity-volume scale.
- Node translation, contraction timing, and neural-causal lesion behavior come
  from the simulator; the renderer does not choose them.

The executable reference is still a research approximation. The displayed skin
profile is not measured L1 geometry, the movement is an in-sample calibrated
model rather than motion capture, and the artifact declares
`release_validated: false`. Internal physics nodes and the external render mesh
remain intentionally separate.
