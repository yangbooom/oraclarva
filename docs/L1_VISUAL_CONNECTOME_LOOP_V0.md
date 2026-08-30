# L1 visual connectome body loop v0

This research extension replaces the anonymous four-probe light injection with
explicit first-instar photoreceptor and larval-optic-neuropil (LON) neurons. It
does not add a phototaxis command, target selector, finite-state machine,
behavior tree, external policy, or renderer-authored movement.

The executed causal chain is:

```text
local analytic irradiance at two moving Bolwig-organ proxy positions
  -> fitted Rh5/Rh6 phototransduction
  -> published bilateral L1 LON identities and contact counts
  -> published non-circadian visual projection-neuron identities
  -> declared MODEL_FITTED descending bridge
  -> existing sparse spatial premotor and motor dynamics
  -> muscle activation and 3D XPBD body physics
  -> next bilateral irradiance samples
```

## Published source and reproducible import

Larderet et al. reconstructed the bilateral LON from an ssTEM volume of a
6-hour-old first-instar CNS. The paper reports 50 nm sections and 4 nm image
pixels, separates Rh5- and Rh6-expressing photoreceptors, and maps their local
and projection-neuron partners
([article DOI 10.7554/eLife.28387](https://doi.org/10.7554/eLife.28387)).

The repository bundles the article's CC BY 4.0 Figure 2 source data 1,
"Complete synaptic connection matrices from both LONs"
([source-data DOI 10.7554/eLife.28387.009](https://doi.org/10.7554/eLife.28387.009)):

```text
data/sources/larderet_2017_l1_visual_circuit/
  elife-28387-fig2-data1-v2.xlsx
SHA-256:
  f9c200cdea0a9a80dc1e7d48aea0a25540d7d63341f705ff7c90faed9effd08f
```

`tools/compile_l1_visual_connectome.py` parses XLSX ZIP/XML with the Python
standard library and deterministically regenerates
`data/connectome/l1_visual_connectome_v0.json`. Its CI gate verifies the source
checksum and these source counts:

| published matrix scope | left LON | right LON | total |
|---|---:|---:|---:|
| side-scoped matrix entries | 28 | 32 | 60 |
| photoreceptor entries | 13 | 16 | 29 |
| nonzero connection pairs | 197 | 225 | 422 |
| within-LON synaptic contacts | 1,499 | 1,798 | 3,297 |

The left matrix has four Rh5 and nine Rh6 PR entries; the right has six Rh5
and ten Rh6 entries. These are the observed specimen values, not a forced
bilateral copy.

Two counting cautions are preserved in the generated data. `sVUM2md` and
`sVUM2mx` are unpaired neurons represented in both side-scoped matrices, so the
60 matrix entries are not 60 unique biological cells. Conversely, the two Tiny
VLNs described in the article are absent from this connection matrix and are
not invented by the compiler.

## What is measured and what is fitted

The 60 side-scoped compartments, identities, transmitters, 422 connection
pairs, and 3,297 contact counts are `MEASURED_PUBLISHED`. The source data leaves
each physiological effect unknown. This distinction matters: the article and
its peer review explicitly caution that a cholinergic or glutamatergic label by
itself does not establish the postsynaptic effect in this circuit.

The executable reference therefore stores two separate facts:

```text
published: pre, post, number of structural contacts, transmitter label
fitted:    excitatory/inhibitory LIF effect and current per contact
```

The current LIF execution uses 368 of the 422 connection pairs and 3,035 of the
3,297 contacts. Outputs from serotonergic SP2-1,
octopaminergic/tyraminergic sVUM2, and Pdf-LaNs remain structural-only because a
two-current LIF synapse cannot honestly represent their unresolved modulatory
dynamics. No published contacts are removed from the compiled source graph.

Every executed effect sign and the 10 pA current per observed contact are
`MODEL_FITTED`. Multiplying contact count by that current is a numerical model;
it does not claim a measured conductance, release probability, or linear
physiological weight.

## Bilateral Bolwig-organ transduction

Only the body's left and right head-surface positions are sampled. The previous
virtual dorsal and ventral light probes are not used by this model. For local
irradiance `q`, fitted half-saturation `h`, bilateral mean `q_mean`, and adapted
irradiance `a`, each PR-class drive is:

```text
ambient(q) = q / (q + h)

drive(class, side) = clamp(
    ambient_gain(class) * ambient(q)
  + spatial_gain(class) * (q - q_mean) / spatial_scale
  + temporal_gain(class) * (q - a) / temporal_scale,
  0, 1)

a(t + dt) = a(t) + (q(t) - a(t)) * (1 - exp(-dt / tau))
```

Rh5 is currently ambient-weighted and Rh6 temporal-weighted. This is a
connectome-motivated hypothesis, not measured L1 photoreceptor physiology. The
half-saturation, gains, adaptation constant, maximum external current, and
virtual receptor positions are all `MODEL_FITTED`.

Because this model has no direct dorsal-versus-ventral visual receptor pair,
the descending bridge supplies identical common drive to dorsal and ventral
channels. It cannot claim direct visually sensed vertical steering. A later
head-sweep/temporal-comparison circuit would be required for that.

## The explicit missing link

The published matrix follows visual information to LON projection neurons. It
does not identify their beyond-LON targets as a path to VNC premotor neurons.
The model reads the non-circadian projection classes `VPLN`, `nc-LaN`,
`5th-LaN`, `PVL09`, and `pOLP`, low-pass filters their spikes independently by
side, and passes the result through a `MODEL_FITTED` bridge into the existing
spatial premotor core.

This bridge is never labeled as a measured synapse or a direct VPN-to-A27h
edge. Its left/right gains also compensate the published specimen's asymmetric
cell and contact counts for the diagnostic fixture; they are not biological
hemispheric gains.

The crossed lateral mapping uses the light-avoidance response direction in
Kane et al. ([DOI 10.1073/pnas.1215295110](https://doi.org/10.1073/pnas.1215295110))
as an L2 response prior only. No numeric value or anatomical L1 descending
connection is copied from that study. The mapping remains `MODEL_FITTED` until
an L1 path beyond the LON is identified.

## Deterministic causal and lesion checks

The checked 1.5-second artifact contains intact positive and negative lateral
gradients plus a 12-compartment non-circadian visual-readout lesion.

| scenario | visual spikes | downstream spikes | dy (um) | yaw (deg) |
|---|---:|---:|---:|---:|
| brighter right, intact | 1,127 | 1,125 | -14.824 | +5.965 |
| brighter left, intact | 1,039 | 1,272 | +14.859 | -5.991 |
| brighter right, VPN readout lesion | 1,296 | 0 | 0.000 | 0.000 |

The two intact fixtures reverse displacement and yaw signs while preserving
the source matrix's real bilateral asymmetry. Near balance is an in-sample
fitting target, not held-out phototaxis validation.

For the brighter-right intact fixture, first spikes follow this trace:

```text
Rh5/Rh6 photoreceptor       0.011 s
visual projection readout   0.027 s
fitted descending bridge    0.100 s
A7 premotor                 0.103 s
A7 motor pool               0.106 s
```

Rh5 can reach VPNs directly, while the Rh6/local-interneuron pathway operates
in parallel; a local-interneuron spike is therefore not required to precede
the first direct VPN spike. Lesioning all photoreceptors eliminates all visual
and downstream spikes. Lesioning all readout compartments preserves upstream
photoreceptor/LON activity but produces zero bridge, premotor, motor, muscle,
and body displacement. No fallback action is invoked.

![L1 visual connectome body loop](assets/oraclarva_l1_visual_connectome.gif)

The GIF reads the checked 13-node body frames and neural audit values. It does
not move the organism independently.

## Reproduce

```bash
oraclarva-visual --duration 1.5
oraclarva-visual --duration 1.5 --mirror
oraclarva-visual --duration 1.5 --lesion-class Rh5-PR
python tools/compile_l1_visual_connectome.py --check
python tools/export_visual_trajectory.py --check
python tools/render_visual_gif.py
pytest tests/test_visual.py tests/test_sources.py
```

## Claim boundary and next step

This result is an embodied execution of published L1 early-visual topology,
not validated natural phototaxis and not a complete visual-to-muscle
connectome. Published LON contact counts do not validate the fitted
phototransduction, physiological signs, or descending bridge.

The next scientific step is to identify and import the actual beyond-LON
partners of the non-circadian VPNs and determine whether a defensible route to
descending/VNC premotor neurons can replace any part of the fitted bridge. If
that public path is incomplete, the missing edges must remain explicitly
fitted rather than acquiring invented cell identities.
