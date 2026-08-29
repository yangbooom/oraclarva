# Spatial steering and synthetic 3D environment v0

This research extension adds yaw, dorsal/ventral head pitch, and passive 3D
contact to the embodied L1 reference. It does not add action commands, an FSM,
a behavior tree, a policy network, or renderer-authored motion.

The executed chain is:

```text
four environment samples (left/right/dorsal/ventral)
  -> phasic sensory transduction
  -> 168 sparse LIF neurons / 188 synapses
  -> four opposed aggregate motor pools per segment
  -> side and dorsal/ventral muscle-group activation
  -> simultaneous yaw + local-binormal pitch XPBD
  -> plane/sphere contact
  -> next four environment samples
```

## What is source-backed

- Zarin et al. preserve the dorsal longitudinal/oblique and ventral
  longitudinal/acute/oblique body-wall muscle spatial groups
  ([DOI 10.7554/eLife.51781](https://doi.org/10.7554/eLife.51781)).
- Berni and Pulver et al. support anterior unilateral activity as a horizontal
  turning topology prior. Pulver et al. used L3; neither paper supplies an L1
  numeric gain
  ([DOI 10.1016/j.cub.2015.03.023](https://doi.org/10.1016/j.cub.2015.03.023),
  [DOI 10.1152/jn.00731.2015](https://doi.org/10.1152/jn.00731.2015)).
- Tastekin et al. reconstruct an anterior path with distinct dorsal RP2 and
  ventral RP3/RP4 motor targets, while explicitly presenting their contribution
  to head sweeps as a hypothesis
  ([DOI 10.7554/eLife.38740](https://doi.org/10.7554/eLife.38740)).
- Hückesfeld et al. identify PaN motor neurons and dorsal protractor muscles
  involved in larval head tilting during feeding. This supports head-tilt
  anatomy context, not the numeric body-wall pitch model
  ([DOI 10.1371/journal.pone.0135011](https://doi.org/10.1371/journal.pone.0135011)).

The atlas spatial-group labels are `MEASURED_PUBLISHED`. The opposed circuit,
T1/T2 extension, shared recruitment, virtual rails, activation gains, sensory
phase, and all contact values remain `ANATOMY_DERIVED` or `MODEL_FITTED`.

## Planar directions and pitch

A fixed screen-space up/down action is unnecessary in the horizontal plane.
Yaw is rotationally equivariant: a complete 151-frame neural-muscle-physics
trajectory initialized at 73 degrees matches the original trajectory rotated
by exactly 73 degrees (3e-9 micrometre node-coordinate tolerance). Thus the
same left/right dynamics span every screen heading.

Pitch is a different 3D freedom. The body stores its initial nonuniform
cross-section profile as rest curvature. Dorsal/ventral activation adds a
signed local-binormal target to that baseline. In free 3D, the two fixed
receptor conditions end at approximately -6.03 and +5.55 degrees of head pitch.
On a substrate, downward motion is contact-limited while a head sweep can lift
the anterior node by more than 50 micrometres. Zero input produces exactly zero
spikes, fiber recruitment, displacement, yaw, and pitch for the full 4.5-second
fixture.

The pitch curvature gain is 0.20. It is the largest tested mirrored fixture
before 0.30 produced a non-monotonic ventral response. This is a fitting
decision, not a measured L1 coefficient.

## Contact equations

A plane collider uses signed distance

```text
phi_plane(x) = (x - x0) dot n
```

and a sphere uses

```text
phi_sphere(x) = norm(x - c) - r.
```

Each body node is projected only when `phi < clearance`. The returned contact
normal defines the 3D tangential and lateral friction basis. For a slope, the
Coulomb term cancels tangential gravity when

```text
norm(g_tangent) <= mu * abs(g_normal).
```

The current coefficient `mu = 0.35` is `MODEL_FITTED`. It is not a measured
L1-on-agar friction coefficient.

The obstacle transducer samples signed distance independently at the four head
surface points. During a fitted 0.1-second sensory window every 5 seconds,

```text
I_i = clamp(baseline + gain * (1 - distance_i / range), 0, 1)
```

with range 120 micrometres, baseline 0.5, and gain 0.5. Outside the sensory
window all four external currents are zero. This phasic equation exists because
tonic input saturates the reduced circuit; it does not select a turn or target.

## Checked regression scenarios

The checked artifact at
`data/trajectories/l1_spatial_environment_v0.json` contains 151 frames at
30 ms for each scenario.

| scenario | dx (um) | dy (um) | dz (um) | yaw | final head pitch |
|---|---:|---:|---:|---:|---:|
| simultaneous free yaw + pitch | +2.917 | +3.257 | +27.319 | -2.092 deg | -3.907 deg |
| symmetric climb on 20% slope | -37.327 | 0 | +7.582 | 0 deg | +0.015 deg |
| four-receptor offset-sphere avoidance | -72.082 | +3.145 | +0.614 | +13.084 deg | -0.005 deg |

The 20% slope test checks every final node against the plane clearance. The
offset sphere test finishes more than 5 micrometres outside the obstacle
clearance. A matched baseline without receptor-distance transduction contacts
the sphere and is deflected to the opposite side; the receptor loop instead
turns before contact.

![Free 3D, slope, and obstacle trajectories](assets/oraclarva_spatial_environment.gif)

## Reproduce

```bash
oraclarva-pitch --dorsal 1 --ventral 0 --free
oraclarva-spatial --left 1 --right 0 --dorsal 1 --ventral 0 --free
python tools/export_spatial_environment_trajectory.py --check
python tools/render_spatial_environment_gif.py
pytest tests/test_dorsoventral.py tests/test_spatial.py \
  tests/test_terrain.py tests/test_environment.py
```

The GIF reads only the checked physical-node artifact. It uses thick continuous
lines to visualize the skin and does not generate motion.

## Claim boundary

This is a connectome-driven embodied research approximation, not a complete L1
brain, a complete spatial steering connectome, a measured individual-muscle
moment-arm model, or a validated natural habitat. The ramp and sphere are
synthetic diagnostics. Roll, torsion, denticles, individually measured
attachments, and held-out 3D L1 trajectories remain absent.
