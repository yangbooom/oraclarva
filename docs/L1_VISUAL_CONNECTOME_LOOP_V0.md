# L1 visual connectome body loop v0

This research extension executes an identified first-instar path from the
Bolwig organ through an A1 premotor pair and into 14 observed A1 motor-neuron
identities. A separately labeled ANATOMY_DERIVED A2-A6 projection provides
bounded homolog and motor-target hypotheses while A7 stays blocked. Together
the two motor-output branches reach 146 uniquely mapped fibers in the 358-fiber
A1-A6 atlas.

Each mapped fiber now has a one-step-delayed MODEL_FITTED activation, an
ANATOMY_DERIVED attachment geometry, and a MODEL_FITTED model-unit tension that
is projected onto the shared 13-node body. The old fitted A03o-to-generic
segmental body bridge and its downstream premotor/motor pools are disabled. No
phototaxis command, target selector, finite-state machine, behavior tree,
external policy, or renderer-authored movement is present.

Stage 5 also attaches the shared body to two published A1 `dbd` sensory
identities. The source table contains 7 direct dbd-to-MN pairs / 11 contacts;
the runtime executes only the 3 one-contact MN targets already present in the
146-fiber path. Full evidence, fitted transduction equations, perturbation and
lesion gates, and the 12/6 Greaney held-out split are documented in
`BODY_STATE_SENSORY_FEEDBACK_V0.md`.

The executed causal chain is:

    local analytic irradiance at two moving Bolwig-organ proxy positions
      -> fitted Rh5/Rh6 phototransduction
      -> published bilateral L1 LON identities and contact counts
      -> published PVL09/pOLP -> LHN -> CPf descending contacts
      -> fork A1: published CPf -> A03o(A1) -> 14 A1 motor identities
                  -> 16 published-target named-fiber mappings
      -> fork A2-A6*: ANATOMY_DERIVED CPf -> A03o homolog -> motor target
                      -> 130 derived named-fiber mappings; A7 is blocked
      -> one-step-delayed MODEL_FITTED per-fiber activation
      -> A1-left attachment hypothesis
      -> exact right mirror and A2-A6 homology, all ANATOMY_DERIVED
      -> MODEL_FITTED active/passive/damping tension in model units
      -> equal-and-opposite force projection onto shared body nodes
      -> 3D body physics
      -> next bilateral irradiance samples
      -> A1-A6 body length/strain/contact samples
      -> fitted dbd transduction
      -> published A1 dbd identities and 3 executable direct MN contacts
      -> the same MN -> named-fiber -> force path

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

### A2-A6 derived segmental projection and A7 gate

A public VFB SOLR/Owlery audit was frozen as an unmodified CC BY-SA 4.0
snapshot:

```text
data/sources/vfb_l1em_a03o_segmental_audit/
  vfb-a03o-segmental-ontology-audit-2026-08-31.tar
SHA-256:
  459763508bebc9969ae22b25697565e30001e341b363d27fe648ad429b486228
```

The label query returns seven A03o-labeled records. The generic A03o1 class and
the abdominal A1 class both resolve to the same two public L1EM instances,
`VFB_00100635` and `VFB_00100686`. The abdominal A2 A03o1 class exists but its
Owlery instance list is empty. No A3-A7 segment-specific A03o1 class appears in
the audited label result. Ontology class existence is therefore not treated as
a reconstructed neuron or measured segmental connection.

Mark et al. ([DOI](https://doi.org/10.7554/eLife.67510)) supports the A03o1
NB7-1 lineage identity. Hasegawa et al.
([DOI](https://doi.org/10.1038/srep30806)) provides only a research-case prior
that larval excitatory premotor interneurons can be segmentally arrayed; it is
not evidence that A03o has the same contacts in every segment. Zarin et al.
supports the A1 versus A2-A6 muscle identity homology boundary.

`tools/compile_l1_a03o_segmental_projection.py` consequently makes a bounded
hypothesis:

1. split each observed A1 A03o-to-MN contact mass equally among that motor neuron’s
   listed muscle targets;
2. pool both specimen sides and normalize the 13 target-muscle masses to one;
3. instantiate one ID-less A03o proxy and 13 ID-less motor-target proxies per
   side in A2-A6;
4. store every resulting node and edge as `ANATOMY_DERIVED`, with
   `synaptic_contacts: null`;
5. instantiate nothing in A7.

| derived diagnostic scope | count |
|---|---:|
| A2-A6 segments | 5 |
| bilateral A03o homolog proxies | 10 |
| bilateral motor-target proxies | 130 |
| CPf-to-A03o projection edges | 10 |
| A03o-to-motor-target projection edges | 130 |
| A7 proxies | 0 |

The executable sign and current for these 140 edges are separately
`MODEL_FITTED`. The normalized A1 target distribution is dimensionless: it is
not copied as A2-A6 contact counts, conductances, release strengths, identified
motor neurons, or NMJs.

### Neural output to the 358-fiber identity atlas

`tools/compile_l1_neural_muscle_identity.py` deterministically joins the two
motor-output branches to `l1_abdominal_muscle_template_v0.json`. For A1 it
preserves each of the 14 observed motor identities and every listed target in
the published Zarin crosswalk. Two motor identities each list two muscles, so
this produces 16 mappings. For A2-A6 it maps each of the 130 explicitly derived
motor-target proxies to the matching segment, side, muscle number, and synonym.

| identity-event scope | mapping count | provenance |
|---|---:|---|
| observed A1 motor identity to named fiber | 16 | `MEASURED_PUBLISHED` target identity |
| A2-A6 motor-target proxy to named fiber | 130 | `ANATOMY_DERIVED` |
| total uniquely mapped fibers | 146 / 358 | mixed, per mapping |
| deliberately unmapped atlas fibers | 212 / 358 | no neural evidence |
| A7 fibers or proxies | 0 | blocked |

One source-node spike emits one event to each explicitly mapped named fiber,
unless that fiber is lesioned. This event is causal bookkeeping with
`ANATOMY_DERIVED` rule provenance. No exact NMJ position is claimed.

### Individual spike-to-activation dynamics

Every mapped fiber has an independent activation `a_i` in `[0, 1]`. Events from
timestep `k` are queued and may first affect activation at `k + 1`; every
applied input stores the source node, spike time, and mapping provenance. For a
one-step target `u_i` and timestep `dt`, the exact first-order update is:

```text
tau = tau_rise  if u_i > a_i  else tau_decay
a_i(t + dt) = a_i(t) + (u_i - a_i(t)) * (1 - exp(-dt / tau))
```

| fitted parameter | value | declared calibration range |
|---|---:|---:|
| `rise_tau_s` | 0.020 s | 0.005-0.100 s |
| `decay_tau_s` | 0.080 s | 0.020-0.400 s |
| `event_target` | 1.0 | 0.1-1.0 |
| minimum delay | 1 timestep = 0.001 s | fixed causal invariant |

Zarin et al. ([DOI](https://doi.org/10.7554/eLife.51781)) imaged first- or
second-instar body-wall muscles with ratiometric GCaMP6f/mCherry, found calcium
increases correlated with contraction, and observed activation across all
imaged muscles. That supports an activation state after neural output, but the
paper does not provide per-MN spike times or L1 rise/decay constants. GCaMP6f
kinetics are not treated as muscle kinetics, and no numerical value is copied
from the paper. The values above are MODEL_FITTED for bounded, smooth, traceable signals.
The activation layer itself does not invent geometry or force; the downstream
named-fiber coupling explicitly executes both under separate provenance
boundaries.

## What is measured and what is fitted

The following are `MEASURED_PUBLISHED`:

- the 60 LON side-scoped entries, 422 LON pairs, and 3,297 LON contacts;
- the 10 selected downstream identities and stable VFB/CATMAID IDs;
- the eight selected axon-to-dendrite edges and 98 confidence-5 contacts;
- the A1 side and premotor/pre-MN annotations of the selected A03o pair;
- 14 A1 motor identities, 15 A03o-to-MN edges, and 26 confidence-5 contacts;
- the existing published motor-identity-to-muscle-target crosswalk;
- the 16 A1 motor-target-to-named-fiber identity mappings that preserve it.

The following are `ANATOMY_DERIVED` rather than measured:

- 10 ID-less bilateral A03o homolog proxies in A2-A6;
- 130 ID-less muscle-target channels covering the 13 A1-supported targets;
- 10 CPf-to-homolog and 130 homolog-to-target topology edges;
- pooled, bilateralized, normalized A1 target-distribution weights;
- the 130 A2-A6 motor-target-proxy-to-named-fiber identity mappings;
- the event bookkeeping rule used to expose causal termination before activation;
- the normalized A1-left origins and insertions in body coordinates;
- the exact right-side mirror and repeated A2-A6 attachment homology.

A7 is an explicit failed evidence gate, not a derived node.

The source graphs deliberately store every physiological effect as `null` with
`unknown` provenance. The executable model separately declares these as
`MODEL_FITTED`:

- Rh5/Rh6 transduction and adaptation parameters;
- excitatory/inhibitory effect assumptions for all executed structural edges;
- current per structural contact, including observed A03o-to-MN contacts;
- effect signs and currents for all 140 anatomy-derived projection edges;
- the per-fiber activation rise, decay, and event-target parameters;
- active-tension gain, passive stiffness, damping, and model-force-to-acceleration conversion;
- body velocity retention and directional contact-friction parameters.

The historical A03o activity filter, crossed lateral mapping, generic spatial
premotor/motor pools, and A03o-to-all-segment body bridge are retained only as
a disabled configuration tombstone and execute no value.

The LIF execution uses 368 of 422 LON pairs and 3,035 of 3,297 LON contacts;
serotonergic SP2-1, octopaminergic/tyraminergic sVUM2, and Pdf-LaN outputs remain
structural-only. All eight descending edges (98 contacts) and all 15
A03o-to-MN edges (26 contacts) execute. The runtime adds 140 derived edges but
no derived contact counts, for 220 visual/path compartments and 531 executed
pairs. The executed measured-contact total remains 3,159. The 146 identity
mappings add no LIF synapse or contact count. A contact count or dimensionless
projection weight multiplied by a fitted current is not a measured conductance,
release probability, delay, or physiological weight.

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

The imported/derived anatomy has two motor-output branches. The observed
A1 branch reaches 14 motor identities and executes their sparse contacts. At
CPf, an anatomy-derived branch reaches A2-A6 A03o and motor-target proxies.
Both terminate in named fibers and never feed motor output back into an
upstream premotor layer.

For each mapped fiber, the A1-left normalized attachment hypothesis is mirrored
to the right and repeated only through A2-A6 homology. Given current length
l_i, initial rest length l0_i, normalized segment length L, length rate v_i,
and activation a_i, the executed model-unit tension is:

    T_active  = g * a_i
    T_passive = k * max(0, (l_i - l0_i) / L)
    T_damping = c * v_i / L
    T_i       = max(0, T_active + T_passive + T_damping)

The origin and insertion receive equal-and-opposite line-of-action forces.
Each attachment is distributed barycentrically to the two shared centerline
nodes of its segment. Thus all visual body motion is downstream of an earlier
motor spike and named-fiber activation. The force unit is explicitly
model_unit_not_newton; no CSA, Fmax, specific stress, measured attachment, or
SI-valued muscle force is claimed.

Only left/right Bolwig proxies are sampled. There is no invented
dorsal-versus-ventral visual receptor pair. A7 and the 212 unmapped atlas
fibers stay silent.

## Deterministic causal and lesion checks

The checked 1.5-second artifact contains two intact mirrored fields and one
individual named-fiber lesion:

| scenario | events / inputs | activated fibers / max a | dy (um) | yaw (deg) |
|---|---:|---:|---:|---:|
| brighter right, intact | 11,778 / 11,776 | 76 / 0.634 | +35.064 | +13.914 |
| brighter left, intact | 3,430 / 3,429 | 71 / 0.367 | -21.075 | -3.377 |
| brighter right, A1:right:M10:DO2 lesion | 11,688 / 11,677 | 75 / 0.634 | +38.687 | +14.238 |

The intact fixtures reverse lateral displacement and yaw signs. Their unequal
magnitudes preserve specimen and fitted-model asymmetries and are not held-out
phototaxis validation.

For the brighter-right fixture, the earliest causal events are:

    Rh5/Rh6 photoreceptor       0.011 s
    PVL09/pOLP projection       0.029 s
    identified LHN              0.057 s
    identified CPf DN           0.061 s
    identified A03o(A1)         0.062 s
    observed A1 MN              0.063 s
    derived A03o(A2-A6)         0.063 s
    named-fiber event           0.063 s
    named-fiber activation      0.064 s
    named attachment force      0.064 s
    parallel body bridge        never
    A7 named attachment force   never

Every active force frame has an earlier source spike and its active-fiber count
equals its traced-active-fiber count. Zero irradiance produces exactly zero
spikes, activation, tension, and body displacement. Tests also verify exact
right-side coordinate mirroring and equal-and-opposite node-force balance.

Neural lesions stop their supported downstream mappings without invoking a
fallback action. A 14-MN lesion removes A1 named-fiber force while preserving
the independent A2-A6 derived branch and changes the trajectory. Lesioning
derived:right:A03o_A4 removes only right-A4 motor targets, activations, and
their physical contribution. An individual fiber lesion preserves its upstream
MN and sibling output, sets only that fiber's active tension to zero, and
changes body motion.

![L1 visual connectome body loop](assets/oraclarva_l1_visual_connectome.gif)

The GIF reads the checked 13-node physical trajectory, attachment-force values,
and neural audit overlay. It does not author movement independently.

## Reproduce

```bash
oraclarva-visual --duration 1.5
oraclarva-visual --duration 1.5 --mirror
oraclarva-visual --duration 1.5 --lesion-class A03o_A1
oraclarva-visual --duration 1.5 --lesion-muscle-fiber A1:right:M10:DO2
python tools/compile_l1_visual_connectome.py --check
python tools/compile_l1_visual_descending_path.py --check
python tools/compile_l1_a03o_motor_path.py --check
python tools/compile_l1_a03o_segmental_projection.py --check
python tools/compile_l1_neural_muscle_identity.py --check
python tools/export_visual_trajectory.py --check
python tools/render_visual_gif.py
pytest tests/test_visual.py tests/test_sources.py
```

## Claim boundary and next scientific step

This is an embodied execution of a selected published L1 structural route plus
a bounded A2-A6 anatomy-derived hypothesis. It is not proof that this route
alone mediates natural phototaxis, not a population-average graph, and not a
complete sensor-to-muscle connectome. Attachment coordinates and all mechanics
remain anatomy-derived or model-fitted rather than measured L1 constants.

The next gate is body-state feedback and calibration: expose segment strain,
contact, and pose to provenance-labeled sensory transduction, then compare wave
speed, duty cycle, stride, and segment-length change against the checked L1
kinematic dataset. No behavior command or external movement policy may be
introduced. The 212 unmapped fibers and A7 remain silent.
