# Scientific 3D body model v0

## Decision

Oraclarva uses a genuinely 3D physical body. Neural output may set continuous
muscle activation only. There are no runtime crawl, turn, stop, or pose commands.

The first reference body contains twelve mechanical regions: pseudocephalon,
T1–T3, and A1–A8. `build_surface_mesh` places one continuous watertight skin over
them. Region IDs label surface faces for diagnostics; they are not independent
balls, capsules, or rigid bodies. Rendering must not translate or rotate the
simulated body independently.

## What is actually known

Heckscher et al. studied newly hatched L1 larvae reported as less than 1000 um
in average length. Whole-animal crawling was recorded in 200 x 200 um channels;
segment and muscle recordings generally used 100 x 150 um channels. These are
stage-specific size constraints, not direct measurements of each unloaded 3D
cross-section. The study identifies the segment boundaries and muscle timing
used by the model.

Greaney et al. measured first-instar jGC7f larvae selected at an average size
of about 1 mm after 24 hours and provides a larger, stage-specific T3-A7
kinematic target. Across 18 L1 animals, T3 contraction amplitude was lower than
the abdomen, shortening was slowest around A4-A5, contraction duration peaked
around A4-A5, and adjacent phase delays were nonuniform. The experiment used
water-saturated linear channels, not free-surface crawling, and is not known to
be age-matched to the connectome specimen. It constrains validation without
turning the current geometry hypotheses into measurements.

Sun et al. directly measured third-instar larvae, not L1. Their animals were
3.53 +/- 0.12 mm long. The study inferred 11.2 +/- 0.2 effective crawling
segments and measured a standard-linear-solid whole-body response. Converted
to its eleven-segment model, the published values are:

| Quantity | L3 value | Evidence |
|---|---:|---|
| Segment equilibrium spring `k1` | 40.7 N/m | measured, then divided into 11 serial segments |
| Segment Maxwell spring `k2` | 58.3 N/m | measured, then divided into 11 serial segments |
| Segment dashpot `c` | 2640 N s/m | measured, then divided into 11 serial segments |
| Maximum whole-body muscle force | 6.7 mN | optogenetic maximum |
| Whole-body mass | 1.14 mg | measured, 99% CI 1.12–1.15 mg |

The paper explicitly notes that extension measurements were used to
approximate compression and that nonlinearity may occur at crawling strains.
The model must retain that limitation.

## L3-to-L1 scaling used in v0

Let `s = L_L1 / L_L3`. With nominal lengths 0.9 and 3.5 mm, `s = 0.2571`.
Assuming geometric similarity and unchanged effective material properties:

- axial stiffness and viscous coefficient scale as `s` (`EA/L` and `eta A/L`);
- muscle force scales as `s^2` (cross-sectional area);
- mass scales as `s^3` (volume).

This produces useful priors, not L1 observations. Every scaled value is
`derived`, and should carry broad uncertainty until L1 force-relaxation data
exist.

## Geometry policy

The current 0.9 mm nominal length, 0.15 mm nominal maximum width, segment
length fractions, and axial width profile are hypotheses or experimental
constraints. They deliberately are not labeled observed.

Before a release claims anatomically calibrated geometry, collect a staged L1
cohort and preregister the pipeline:

1. synchronized newly hatched L1 animals and record age, temperature, food,
   genotype, and sex when knowable;
2. acquire calibrated dorsal and lateral images at rest and during crawling;
3. label PSC, T1–T3, and A1–A8 boundaries blind to model output;
4. measure per-segment length, maximum width, height, curvature, and contact
   patch over multiple strides;
5. publish individual-level data, not only averages;
6. fit a population distribution and hold out animals for validation;
7. version the parameter bundle and never overwrite the raw measurements.

The current body geometry is not overwritten by the Greaney segment lengths.
Those lengths were measured during channel crawling in a distinct cohort and
their T3-A7 sum is inconsistent with treating the existing 0.9 mm global prior
as an exact decomposition. The measurement definition, age, and boundary
registration must be reconciled against calibrated raw images first.

## Numerical representation

The diagnostic viewer consumes a deterministic 30 ms trajectory exported from
this Python solver. It interpolates 13 internal nodes beneath a separate
continuous skin and no longer synthesizes its own contraction wave or bend.
The generated artifact is model output, not measured motion capture.

`ScientificBody3D` is a dependency-free XPBD axial reference. It uses the
instantaneous SLS stiffness (`k1 + k2`) for stable compliant length constraints.
Active shortening changes region target length. Because Drosophila abdominal
regions are not sealed by septa, one aggregate body-cavity scale preserves total
reference volume across all regions. This is still a hypothesis: it removes the
incorrect per-region sealed-volume assumption but does not yet simulate measured
pressure or viscera motion.

## Neuromuscular integration gate

The v1 crosswalk preserves the published muscle spatial groups (DL, DO, VL, VA,
VO, T, and Broad), individual muscle numbers and synonyms, synapse types, side,
segment, and exact CATMAID skeleton IDs. It does not collapse these anatomical
groups into a made-up longitudinal/transverse actuator. The current A1/A2 map is
therefore identity-curated but not yet mechanically executable for release.
The full-body research fixture still uses its `MODEL_FITTED` aggregate proxy.
Separately, the isolated A1-left fixture executes all 29 normalized lines of
action, rest lengths, passive elasticity, damping, and activation-driven
tension without feeding them into the body. Its coordinates are
`ANATOMY_DERIVED`, its mechanics are `MODEL_FITTED` model units, and it does not
fill metric attachments, layers, CSA, Fmax, or shared-cuticle mechanics.

Synthetic mappings are permitted only when a test explicitly opts in. A release
simulation fails closed until every enabled projection carries an observed
source, the connectome IDs match the selected dataset, motor-to-muscle gains are
measured or fitted, and each muscle has an auditable mechanical line of action.

It is not yet a complete soft-body model. The next body milestone must add:

- SLS internal state rather than instantaneous stiffness alone;
- bending and torsional constraints;
- individually curated left/right muscle identities beyond the initial A1-A6
  topology, including three-layer 3D attachment geometry;
- denticle/contact geometry and measured substrate interaction;
- proprioceptive readout from strain and curvature;
- native-core parity fixtures and device benchmarks.

## Sources

- Heckscher ES, Lockery SR, Doe CQ. *Characterization of Drosophila Larval
  Crawling at the Level of Organism, Segment, and Somatic Body Wall
  Musculature.* J Neurosci. 2012. https://doi.org/10.1523/JNEUROSCI.0222-12.2012
- Sun X et al. *A neuromechanical model for Drosophila larval crawling based
  on physical measurements.* BMC Biology. 2022.
  https://doi.org/10.1186/s12915-022-01336-w
- Kohsaka H et al. *Regulation of forward and backward locomotion through
  intersegmental feedback circuits in Drosophila larvae.* Nature Communications.
  2019. https://doi.org/10.1038/s41467-019-10695-y
- Greaney MR, Heckscher ES, Kaufman MT. *Multiple Scales of Coordination along
  the Body Axis during Drosophila Larval Locomotion.* J Neurosci. 2026.
  https://doi.org/10.1523/JNEUROSCI.1623-25.2026
