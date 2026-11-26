# L1EM public connectome snapshot v0

Goal: move from hand-picked reduced circuits to the full public first-instar
connectome (Winding, Pedigo et al. 2023 brain plus partially reconstructed VNC).

## License boundary

The data stays out of git: `tools/fetch_l1em_public_connectome.py` writes the
snapshot under `data/local/` (ignored by git), and the repository commits only
the method, the pinned SHA-256 and the audit summary below. Every neuron's VFB
term-info is fetched so the license is recorded per neuron. The run fails if any
neuron has no license or a license other than CC BY 4.0 / CC BY-SA 4.0.

```text
.venv/bin/python -u tools/fetch_l1em_public_connectome.py   # ~35 min, resumable cache
data/local/l1em_public_connectome/l1em-public-snapshot-2026-11-25.tar
SHA-256 66acc070bac63e5a187319236408018ce404c8c7dac307309a4a3aeaf89a8c02
```

The endpoints are public read-only GETs: the L1EM CATMAID skeleton list, the VFB
cached CATMAID proxy (`annotations`, `annotations_for_skeletons`,
`neuron_names`, `connectivity`) and VFB `get_term_info`. The tool sends a
generic User-Agent, uses at most 4 concurrent term-info requests, and caches
every response so an interrupted run resumes where it stopped.

## Snapshot audit (2026-11-25)

| item | value |
|---|---:|
| public skeletons | 5,013 |
| Winding 2023 brain neurons | 3,066 |
| neurons with VFB id and license | 5,013 |
| license | CC BY 4.0 for 5,013 / 5,013 |
| neuron-level edges (outgoing, any partner) | 569,344 |
| contacts between public neurons | 428,975 |

VFB now reports CC BY 4.0 for the Zarin et al. 2019 neurons that the 2026-08-31
A03o snapshots recorded as CC BY-SA 4.0. Licenses can change upstream, so every
new snapshot is audited again.

## Neurotransmitter sign coverage

`src/oraclarva/connectome_signs.py` assigns transmitter and fast sign in tiers:
curated direct annotations (`MEASURED_PUBLISHED`); lineage consensus computed
only from this dataset, used when at least 3 directly annotated members of a
lineage all agree (`ANATOMY_DERIVED`); named cell-class rules
(`ANATOMY_DERIVED`); and everything else is `unknown`. Acetylcholine is +1.
GABA and central glutamate are -1. Dopamine, octopamine and serotonin are a
modulatory channel and carry no fast sign.

| Winding brain neurons | count |
|---|---:|
| direct annotation | 653 |
| lineage consensus | 41 |
| excitatory / inhibitory | 570 / 103 |
| modulatory | 20 |
| unresolved | 2,372 (78%) |

## VNC coverage

- Segment-labelled non-Winding neurons: A1 329, A2 94, A3 41, A4-A8 69,
  thoracic 45. Another 1,380 have no segment label.
- dVNC output contacts: 85% land on unreconstructed fragments, 6% on 267 public
  VNC neurons and 10% return to the brain.
- Among segment-labelled pairs, 36% of contacts cross segments, mainly A1-A2
  and T3-A1.

## Compiled connectome

```text
.venv/bin/python tools/compile_l1em_connectome.py
data/local/l1em_public_connectome/compiled/l1em_connectome_v0.json          (~12 MB, not committed)
data/local/l1em_public_connectome/compiled/l1em_connectome_v0.summary.json
```

The compiler checks the snapshot SHA-256 against the manifest. It takes each
directed pair once, from the pre-synaptic skeleton's outgoing query, keeps the
contacts per CATMAID confidence bin, and cross-checks every edge against the
matching incoming record (137,247 checked, 0 mismatched).

| item | value |
|---|---:|
| edges / contacts between public neurons | 137,247 / 428,975 |
| brain-to-brain (Winding) edges / contacts | 112,371 / 355,382 |
| brain contacts at confidence 5 | 355,221 (99.95%) |
| contacts to non-public fragments | 432,097 (one contact per fragment edge) |
| public contacts from excitatory / inhibitory / unresolved pre | 104,911 / 31,767 / 292,297 |

Synapse count reconciliation: Winding et al. report "~548,000 synaptic sites",
and say only about 75% of them (about 411,000) are linked to a neuron; the rest
are mostly small dendritic fragments. The 355,382 public brain-to-brain contacts
here are therefore a subset of the neuron-linked sites, not a different measure.
Part of the remaining gap is brain-to-input and brain-to-VNC edges, which this
count leaves out. Polyadic counting conventions are not stated in the text that
was checked. Winding et al. also split edges into axo-dendritic (66.6%),
axo-axonic (25.8%), dendro-dendritic (5.8%) and dendro-axonic (1.8%). This
compiler does not yet make that split.

## Neurotransmitter prediction survey (2026-11-26)

- Winding et al. 2023 publish unsigned edges. The text we checked has no
  per-neuron transmitter table and no edge signs.
- Eckstein et al. 2024 (Cell, doi:10.1016/j.cell.2024.03.016) classify
  synapses from EM by transmitter (ACh, Glu, GABA, DA, 5-HT, OA) with about 87%
  synapse-level accuracy. They cover only the adult FAFB/FlyWire and hemibrain
  volumes, and release the predictions on Zenodo (doi:10.5281/zenodo.10593546).
- We found no published transmitter prediction for the L1EM larval volume.
  Applying the Eckstein classifier would need L1EM image access at synapse
  locations and retraining or validation on this volume's 3.8 x 3.8 x 50 nm
  ssTEM, using the 653 annotated brain neurons as labels. That is a separate
  project with its own licensing and compute questions.
