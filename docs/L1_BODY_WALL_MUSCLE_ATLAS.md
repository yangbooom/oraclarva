# L1 body-wall muscle atlas v0

## Current evidence boundary

The atlas preserves the 30 named abdominal body-wall muscle identities and
their DL, DO, VL, VA, VO, or transverse spatial groups. It expands those
identities bilaterally only where the published homology statement supports it:

| Segment | Muscles per side | Bilateral fibers | Provenance |
|---|---:|---:|---|
| A1 | 29 | 58 | observed identity; muscle 25 absent |
| A2-A6 | 30 each | 60 each | derived homology from the published A1 comparison |

The supported A1-A6 topology contains 358 left/right fiber identities. PSC,
T1-T3, A7, and A8 remain blocked because larval segment patterns are not uniform
at the thoracic and terminal ends. The code raises instead of silently cloning
the abdominal template into those regions.

## Why identities are not yet actuators

The body wall is not a row of identical axial springs. Published anatomy
describes roughly 30 muscles per abdominal hemisegment in internal, median, and
external layers. Muscles have distinct size, shape, orientation, innervation,
and direct or indirect attachment arrangements. Some internal muscles attach
through tendon arrangements to muscles in the neighboring segment.

The current atlas therefore leaves these release-critical quantities unresolved:

- quantitative 3D origin and insertion coordinates;
- individual internal, median, or external layer assignment;
- line of action and moment arm through the motion range;
- rest length and cross-sectional area;
- passive material law and active force-length-velocity law;
- motor-neuron-to-muscle gain.

Until all are source-backed or fitted against held-out L1 data,
`mechanically_executable` and `full_body_ready` remain false.

## Isolated A1-left mechanics

The v0 isolated fixture now gives the 29 A1-left identities explicit normalized
origins, insertions, rest lengths, lines of action, passive elasticity, damping,
and activation-driven tension. These coordinates are a deterministic
ANATOMY_DERIVED schematic constrained by the published spatial groups; they are
not digitized or measured attachments. The material and tension values are
MODEL_FITTED model units. Exact zero-input stability and individual-fiber lesion
locality are checked in.

This does not make the 358-fiber atlas mechanically executable. Individual
layers, direct/indirect tendon assignment, shared cuticle nodes, metric scale,
CSA, Fmax, and A2-A6 attachment homology remain unresolved. Stage 4 must project
these individual forces onto shared full-body physics without retaining the
parallel aggregate bridge. Thoracic and terminal segments still require their
own atlases rather than an A1 copy.

## Sources

- Zarin AA et al. *A multilayer circuit architecture for the generation of
  distinct locomotor behaviors in Drosophila.* eLife. 2019.
  https://doi.org/10.7554/eLife.51781
- Carayon A et al. *Intrinsic control of muscle attachment sites matching.*
  eLife. 2020. https://doi.org/10.7554/eLife.57547
- Hooper JE. *Homeotic gene function in the muscles of Drosophila larvae.*
  EMBO J. 1986. https://doi.org/10.1002/j.1460-2075.1986.tb04499.x
