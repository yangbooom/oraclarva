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
