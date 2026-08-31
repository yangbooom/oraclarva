# L1 visual connectome body loop v0

This research extension executes an identified first-instar path from the
Bolwig organ through an A1 premotor pair. It does not add a phototaxis command,
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
  -> declared MODEL_FITTED A03o(A1)-to-segmental-core bridge
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
already exist in the LON graph, so the runtime gains six new compartments and
contains 66 visual/path compartments total.

VFB exposes CC BY 4.0 terms for the Winding-derived records and CC BY-SA 4.0
terms for the A03o records. The manifest records the mixed license boundary;
redistributed derivatives must preserve applicable attribution and share-alike
conditions.

## What is measured and what is fitted

The following are `MEASURED_PUBLISHED`:

- the 60 LON side-scoped entries, 422 LON pairs, and 3,297 LON contacts;
- the 10 selected downstream identities and stable VFB/CATMAID IDs;
- the eight selected axon-to-dendrite edges and 98 confidence-5 contacts;
- the A1 side and premotor/pre-MN annotations of the selected A03o pair.

The source graphs deliberately store every physiological effect as `null` with
`unknown` provenance. The executable model separately declares these as
`MODEL_FITTED`:

- Rh5/Rh6 transduction and adaptation parameters;
- excitatory/inhibitory effect assumptions for all executed structural edges;
- current per structural contact, including stage-specific path currents;
- A03o activity filtering and side gains;
- crossed lateral response mapping;
- the A03o(A1)-to-all-segment spatial-core bridge.

The LIF execution uses 368 of 422 LON pairs and 3,035 of 3,297 LON contacts;
serotonergic SP2-1, octopaminergic/tyraminergic sVUM2, and Pdf-LaN outputs remain
structural-only. All eight selected downstream edges and all 98 contacts execute.
Totals are therefore 376 executed pairs and 3,133 executed contacts. A contact
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

The imported anatomy now reaches an A03o pair in A1, but it does not establish
that pair's physiological sign, steering effect, or continuation through every
abdominal segment and motor pool. The fitted bridge therefore begins only after
A03o and is labeled `fitted_a03o_to_segmental_core`. It does not claim an
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
| brighter right, intact | 1,410 | 7,048 | -15.239 | +6.231 |
| brighter left, intact | 1,119 | 2,296 | +14.957 | -6.020 |
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
fitted A03o segment bridge  0.071 s
A7 premotor core            0.074 s
A7 motor pool               0.077 s
```

Tests lesion the photoreceptors, PVL09/pOLP inputs, LHN pair, CPf pair, and A03o
pair independently. At every cut, upstream activity remains where expected and
all downstream stages stop. The A03o lesion leaves 1,669 upstream spikes but
produces zero bridge, motor, muscle, and body displacement. No fallback action
is invoked.

![L1 visual connectome body loop](assets/oraclarva_l1_visual_connectome.gif)

The GIF reads the checked 13-node physical trajectory and recorded neural audit
values. It does not author movement independently.

## Reproduce

```bash
oraclarva-visual --duration 1.5
oraclarva-visual --duration 1.5 --mirror
oraclarva-visual --duration 1.5 --lesion-class A03o_A1
python tools/compile_l1_visual_connectome.py --check
python tools/compile_l1_visual_descending_path.py --check
python tools/export_visual_trajectory.py --check
python tools/render_visual_gif.py
pytest tests/test_visual.py tests/test_sources.py
```

## Claim boundary and next scientific step

This is an embodied execution of a selected published L1 structural route to an
A1 premotor pair. It is not proof that this route alone mediates natural
phototaxis, not a population-average graph, and not a complete
sensor-to-muscle connectome. The 2-versus-11 CPf-to-A03o asymmetry is one
specimen observation.

The next scientific step is to replace part of the remaining fitted boundary:
identify A03o's public downstream A1 motor-network partners and determine which
connections can be repeated across segments only when segment-specific evidence
supports it. Physiological signs and response-direction effects should remain
fitted until direct evidence is available.
