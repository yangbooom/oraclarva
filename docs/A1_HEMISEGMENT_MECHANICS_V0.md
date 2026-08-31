# Isolated A1-left hemisegment mechanics v0

## Outcome

Stage 3 makes all 29 muscles of the A1 left hemisegment mechanically explicit
without enabling whole-body movement. Each fiber has a body-fixed origin and
insertion (s, theta, d), a normalized rest length and line of action, a bounded
activation-driven tension, passive attachment elasticity and damping, and an
individual mechanics lesion.

The checked fixture proves exact zero-input equilibrium, an ordered
motor-identity spike -> delayed activation -> tension/shortening path, and local
lesion effects. It is an isolated mechanics experiment, not a metric L1 muscle
atlas.

![Isolated A1-left mechanics](assets/oraclarva_a1_hemisegment_mechanics.gif)

## Evidence boundary

[Zarin et al. 2019](https://doi.org/10.7554/eLife.51781) supports the 29-muscle
A1 identity pattern, the absence of muscle 25 in A1, and the qualitative
DL/DO/VL/VO/VA/T location-orientation groups. It does not provide quantitative
3D attachment coordinates.

[Carayon et al. 2020](https://doi.org/10.7554/eLife.57547) supports
identity-specific orientation, tendon-cell attachment, and direct/indirect
muscle-attachment topology. Its developmental and larval observations are not
an L1 metric attachment atlas.

Accordingly:

| Quantity | v0 provenance | Claim |
|---|---|---|
| muscle identity and spatial group | MEASURED_PUBLISHED | published A1 identity/layout |
| individual (s, theta, d) lanes | ANATOMY_DERIVED | deterministic schematic hypothesis |
| rest length and line of action | ANATOMY_DERIVED | computed in normalized geometry |
| stiffness, damping, inertia, active gain | MODEL_FITTED | numerical diagnostic only |
| absolute attachment, CSA, Fmax, force in N | absent | not claimed |

No coordinate is digitized from CIL:41824. That source remains stage-unknown,
reference-only, and CC BY-NC-ND.

## Coordinate and mechanics model

The local coordinate system uses s in [0,1] anterior-to-posterior, theta=0
dorsal, theta=-pi/2 left lateral, and theta=-pi ventral. Depth d is a fractional
inset from a schematic elliptical shell. The cross-section ratio and common
depth are model parameters, not L1 measurements. Individual
internal/median/external layers are deliberately unassigned.

Each fiber uses one generalized shortening coordinate q_i:

    q_ddot_i = (g*a_i - k*q_i - c*q_dot_i) / m
    L_i = L0_i - q_i

Here a_i is the stage-2 delayed activation. The g, k, c, and m values are
MODEL_FITTED values in model units, calibrated only for exact rest and a
bounded, non-oscillatory 0.5 s diagnostic response. They are not newtons,
kilograms, or measured material constants. Shortening is capped at the declared
30% model range.

The 29 coordinates are independent. They do not yet share a deformable cuticle,
tendon network, collision layers, pressure field, or pose-dependent moment
arms. The straight origin-to-insertion chord is a diagnostic line of action
rather than a reconstructed fiber volume.

## Checked results

The committed artifact runs at 1 ms for 0.599 s:

- zero input: 29 fibers remain exactly at rest;
- M1 first spike: 0.050 s;
- M1 activation and first shortening: 0.051 s;
- M10 first spike: 0.182 s;
- M10 activation and first shortening: 0.183 s;
- M1 mechanics lesion: M1 activation peak remains unchanged while its
  shortening remains exactly zero;
- the M10 sibling trajectory is unchanged by the M1 lesion.

The mechanics lesion occurs after the neural and activation stages. It therefore
does not erase upstream evidence.

    python tools/export_a1_hemisegment_fixture.py --check
    python tools/render_a1_hemisegment_gif.py
    pytest tests/test_hemisegment.py

## Stage 4 full-body integration

Stage 4 projects the supported named-fiber attachment forces onto shared
physical nodes through this executed route:

    identified/derived MN spike
      -> named-fiber activation
      -> individual attachment force
      -> shared body node and continuous skin
      -> environment/contact

The A1-left fixture remains a regression test. Full-body integration uses exact
right-side mirroring and A2-A6 homology only as ANATOMY_DERIVED hypotheses,
keeps A7 and 212 unsupported fibers silent, and executes no parallel aggregate
body bridge. MN, segment, and individual-fiber lesions now change body physics
through this path.
