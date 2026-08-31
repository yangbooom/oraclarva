# L1 visual connectome body loop v0

This research extension executes an identified first-instar path from the
Bolwig organ through an A1 premotor pair and into 14 observed A1 motor-neuron
identities. It does not add a phototaxis command,
target selector, finite-state machine, behavior tree, external policy, or
renderer-authored movement.

The executed causal chain is:

```text
local analytic irradiance at two moving Bolwig-organ proxy positions
  -> fitted Rh5/Rh6 phototransduction
  -> published bilateral L1 LON identities and contact counts
  -> published PVL09/pOLP contacts onto a bilateral LHN pair
  -> published LHN contacts onto a bilateral CPf descending pair
  -> published CPf contacts onto an A03o premotor pair in A1
  -> fork A: published A03o contacts onto 14 mapped A1 motor identities
             (diagnostic identity/muscle-target trace; no invented A2-A7 copy)
  -> fork B: declared MODEL_FITTED A03o(A1)-to-segmental-core bridge
             -> sparse spatial premotor and motor dynamics
             -> muscle activation and 3D XPBD body physics
  -> next bilateral irradiance samples
```

## Published sources and reproducible imports

### Bilateral LON

Larderet et al. reconstructed the bilateral LON in a 6-hour-old first-instar
CNS ([article DOI](https://doi.org/10.7554/eLife.28387)). The repository bundles
the article's CC BY 4.0 Figure 2 source data 1
([source-data DOI](https://doi.org/10.7554/eLife.28387.009)):

```text
data/sources/larderet_2017_l1_visual_circuit/
  elife-28387-fig2-data1-v2.xlsx
SHA-256:
  f9c200cdea0a9a80dc1e7d48aea0a25540d7d63341f705ff7c90faed9effd08f
```

`tools/compile_l1_visual_connectome.py` deterministically regenerates
`data/connectome/l1_visual_connectome_v0.json` and checks these observed counts:

| published LON matrix scope | left | right | total |
|---|---:|---:|---:|
| side-scoped entries | 28 | 32 | 60 |
| photoreceptor entries | 13 | 16 | 29 |
| nonzero connection pairs | 197 | 225 | 422 |
| structural contacts | 1,499 | 1,798 | 3,297 |

The specimen asymmetry is preserved. The 60 entries are not asserted to be 60
unique cells because the two unpaired sVUM2 identities occur in both
side-scoped matrices. The two Tiny VLNs described in the paper are absent from
the matrix and are not invented.

### Visual path to A03o in A1

The downstream import uses the public L1EM graph hosted by Virtual Fly Brain and
the Winding et al. connectome study
([Science DOI](https://doi.org/10.1126/science.add9330)). The audited snapshot
contains the VFB term-info responses, an L1EM CATMAID connectivity response, and
the CATMAID annotations that identify the A03o pair as A1 premotor/pre-MN
interneurons:

```text
data/sources/vfb_l1em_visual_descending_path/
  vfb-l1em-api-snapshot-2026-08-31.tar
SHA-256:
  0f558cf16f30b58b760ac7053abb7cd5ccb64243de36492c937760c5642e465b
```

The exact connectivity query was:

```text
https://v3-cached.virtualflybrain.org/catmaid/l1em/connectivity?ids=9940382,8124177,9567051,9539868,11037238,7719118,5690425,19010160
```

`tools/compile_l1_visual_descending_path.py` verifies every VFB ID, CATMAID
skeleton ID, FlyBase type, required A03o annotations, confidence bin, and contact
count before regenerating
`data/connectome/l1_visual_descending_path_v0.json`.

| structural edge | left skeletons / contacts | right skeletons / contacts |
|---|---:|---:|
| pOLP -> down_PVL09_PN-OLP LHN | 9940382 -> 11037238 / 33 | 8124177 -> 7719118 / 25 |
| PVL09 -> same LHN | 9567051 -> 11037238 / 12 | 9539868 -> 7719118 / 8 |
| LHN -> CPf descending ipsilateral | 11037238 -> 5690425 / 4 | 7719118 -> 19010160 / 3 |
| CPf -> A03o A1 | 5690425 -> 4302562 / 2 | 19010160 -> 3180525 / 11 |

That is 10 identified neurons in five bilateral pairs, eight selected
axon-to-dendrite edges, and 98 confidence-5 structural contacts. PVL09 and pOLP
already exist in the LON graph, so this stage contributes six new runtime
compartments.

VFB exposes CC BY 4.0 terms for the Winding-derived records and CC BY-SA 4.0
terms for the A03o records. The manifest records the mixed license boundary;
redistributed derivatives must preserve applicable attribution and share-alike
conditions.

### A03o outputs to mapped A1 motor identities

A second audited public L1EM query follows both A03o skeletons directly:

```text
https://v3-cached.virtualflybrain.org/catmaid/l1em/connectivity?ids=4302562,3180525

data/sources/vfb_l1em_a03o_motor_path/
  vfb-l1em-a03o-motor-api-snapshot-2026-08-31.tar
SHA-256:
  07dcc865c82ebeff4e8051a7a8f6994c3f8400cdf7c6fa722f65d88a5a2e571e
```

`tools/compile_l1_a03o_motor_path.py` intersects the outgoing partners with the
56 A1 identities in `l1_motor_map_v1.json`, validates the VFB term and CATMAID
A1-motor annotations, and preserves every confidence-5 contact in that
intersection. The result is 14 identified motor neurons, 15 structural edges,
and 26 contacts. Coverage is asymmetric and is not completed by mirroring:

| observed A1 motor identities | left | right | total |
|---|---:|---:|---:|
| identities | 6 | 8 | 14 |
| DL group | | | 5 |
| DO group | | | 5 |
| transverse group | | | 4 |

One left MN9 identity receives two contacts from left A03o and one contact from
right A03o; that crossed edge is retained. Thirteen unique muscle numbers occur
in the existing Zarin target crosswalk
([eLife DOI](https://doi.org/10.7554/eLife.51781)). These identity targets do
not provide 3D attachment coordinates, CSA, line of action, or force gain.

All selected motor terms expose CC BY-SA 4.0. The bundled snapshot preserves
the unmodified connectivity, annotation, and term-info responses; derived
records retain attribution and share-alike conditions.

## What is measured and what is fitted

The following are `MEASURED_PUBLISHED`:

- the 60 LON side-scoped entries, 422 LON pairs, and 3,297 LON contacts;
- the 10 selected downstream identities and stable VFB/CATMAID IDs;
- the eight selected axon-to-dendrite edges and 98 confidence-5 contacts;
- the A1 side and premotor/pre-MN annotations of the selected A03o pair;
- 14 A1 motor identities, 15 A03o-to-MN edges, and 26 confidence-5 contacts;
- the existing published motor-identity-to-muscle-target crosswalk.

The source graphs deliberately store every physiological effect as `null` with
`unknown` provenance. The executable model separately declares these as
`MODEL_FITTED`:

- Rh5/Rh6 transduction and adaptation parameters;
- excitatory/inhibitory effect assumptions for all executed structural edges;
- current per structural contact, including A03o-to-MN contacts;
- A03o activity filtering and side gains;
- crossed lateral response mapping;
- the A03o(A1)-to-all-segment spatial-core bridge.

The LIF execution uses 368 of 422 LON pairs and 3,035 of 3,297 LON contacts;
serotonergic SP2-1, octopaminergic/tyraminergic sVUM2, and Pdf-LaN outputs remain
structural-only. All eight descending edges (98 contacts) and all 15
A03o-to-MN edges (26 contacts) execute. The visual/path runtime has 80
compartments, 391 executed pairs, and 3,159 executed contacts. A contact
count multiplied by a fitted current is not a measured conductance, release
probability, delay, or physiological weight.

## Bilateral light transduction and steering boundary

Only the body's left and right head-surface positions are sampled. There is no
invented dorsal-versus-ventral Bolwig receptor pair. For local irradiance `q`,
fitted half-saturation `h`, bilateral mean `q_mean`, and adapted irradiance `a`:

```text
ambient(q) = q / (q + h)

drive(class, side) = clamp(
    ambient_gain(class) * ambient(q)
  + spatial_gain(class) * (q - q_mean) / spatial_scale
  + temporal_gain(class) * (q - a) / temporal_scale,
  0, 1)

a(t + dt) = a(t) + (q(t) - a(t)) * (1 - exp(-dt / tau))
```

The imported anatomy now has two explicit branches after A03o. The observed
branch reaches 14 A1 motor identities and executes their sparse contacts for
causal diagnostics. It does not drive the all-segment body because A1-only
coverage cannot justify an A2-A7 locomotor wave or measured per-muscle forces.

The full-body branch remains labeled
`fitted_a03o_to_segmental_core`. It starts in parallel after A03o, does not feed
motor output back into an upstream premotor layer, and does not claim an
A03o-to-A27h synapse or an A1-to-A7 anatomical repetition.

The crossed lateral mapping still uses L2 light-avoidance direction from Kane
et al. ([DOI](https://doi.org/10.1073/pnas.1215295110)) as a response-direction
prior only. No L2 number is copied as an L1 constant. Dorsal and ventral bridge
channels receive identical common drive, so this model does not claim direct
visual pitch sensing.

## Deterministic causal and lesion checks

The checked 1.5-second artifact contains two intact mirrored fields and an
A03o-pair lesion:

| scenario | visual/path spikes | downstream spikes | dy (um) | yaw (deg) |
|---|---:|---:|---:|---:|
| brighter right, intact | 3,336 | 7,048 | -15.239 | +6.231 |
| brighter left, intact | 1,244 | 2,296 | +14.957 | -6.020 |
| brighter right, A03o pair lesion | 1,669 | 0 | 0.000 | 0.000 |

The intact fixtures reverse displacement and yaw signs. Their differing neural
counts preserve the observed specimen and fitted-model asymmetries; this is not
held-out phototaxis validation.

For the brighter-right fixture, first spikes follow the required order:

```text
Rh5/Rh6 photoreceptor       0.011 s
PVL09/pOLP projection       0.029 s
identified LHN              0.057 s
identified CPf DN           0.061 s
identified A03o(A1)         0.062 s
observed A1 MN branch       0.063 s
fitted A03o segment bridge  0.071 s
A7 premotor core            0.074 s
A7 motor pool               0.077 s
```

Tests lesion the photoreceptors, PVL09/pOLP inputs, LHN pair, CPf pair, and A03o
pair independently. At every shared-path cut, upstream activity remains where
expected and both downstream branches stop. The A03o lesion leaves 1,669
upstream spikes but produces zero A1-MN diagnostic activity, bridge, muscle, or
body displacement. A separate 14-MN lesion stops only the observed diagnostic
branch while the parallel fitted full-body branch remains active; this verifies
that motor output is not routed backward into the segmental premotor core. No
fallback action is invoked.

![L1 visual connectome body loop](assets/oraclarva_l1_visual_connectome.gif)

The GIF reads the checked 13-node physical trajectory plus a neural causal
audit overlay and recorded neural values. The physical-node count is unchanged;
it does not author movement independently.

## Reproduce

```bash
oraclarva-visual --duration 1.5
oraclarva-visual --duration 1.5 --mirror
oraclarva-visual --duration 1.5 --lesion-class A03o_A1
python tools/compile_l1_visual_connectome.py --check
python tools/compile_l1_visual_descending_path.py --check
python tools/compile_l1_a03o_motor_path.py --check
python tools/export_visual_trajectory.py --check
python tools/render_visual_gif.py
pytest tests/test_visual.py tests/test_sources.py
```

## Claim boundary and next scientific step

This is an embodied execution of a selected published L1 structural route to an
A1 premotor pair plus a sparse observed A1 motor branch. It is not proof that
this route alone mediates natural phototaxis, not a population-average graph,
and not a complete sensor-to-muscle connectome. The CPf-to-A03o and
A03o-to-MN asymmetries are one-specimen observations.

The next scientific step is segment-specific expansion: identify A03o homologs
and their motor contacts in A2-A7 only where public skeleton IDs and contact
evidence exist. After that, connect each verified motor identity through its
published NMJ target to the 358-fiber atlas while keeping attachment geometry,
CSA, force gain, and any missing segmental homology explicitly derived or
fitted. Physiological signs remain fitted until direct evidence is available.
