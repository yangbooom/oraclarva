#!/usr/bin/env python3
"""First whole-brain probes on the compiled L1EM connectome (Winding 2023 brain).

1. Stability: drive the 42 ORNs and check whether activity stays bounded and
   stops after the stimulus (self-sustained activity = runaway).
2. Learning-pathway readiness for odor + sugar conditioning:
   structural hop distances ORN -> KC, sugar sensory -> DAN, KC -> MBON,
   MBON -> dVNC; functional responses of KCs to appetitive ORNs and of
   DANs to sugar sensory neurons.

Every probe runs across sign policies for the ~78% of neurons with unknown
transmitter, so results report sensitivity to that assumption.  Inputs and
outputs live under git-ignored data/local/.
"""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from oraclarva.brain_sim import BrainParams, SignPolicy, build_network, simulate  # noqa: E402

LOCAL = ROOT / "data" / "local" / "l1em_public_connectome"
COMPILED = LOCAL / "compiled" / "l1em_connectome_v0.json"
SNAPSHOT = LOCAL / "l1em-public-snapshot-2026-11-25.tar"

GROUPS = {
    "ORN": "mw ORN",
    "ORN_appetitive": "mw ORN appetitive",
    "sugar_sensory": "sugar sensory",
    "PN_upstream_KC": "mw PNs upstream KCs",
    "KC": "mw KC",
    "MBON": "mw MBON",
    "MBIN": "mw MBIN",
    "DAN": "mw MBIN subclass_DAN",
    "dVNC": "mw dVNC",
}

POLICIES = [("excitatory", SignPolicy(mode="excitatory"))]
POLICIES += [("silent", SignPolicy(mode="silent"))]
POLICIES += [
    (f"sample_p{p}_s{s}", SignPolicy(mode="sample", p_excitatory=p, seed=s))
    for p in (0.6, 0.7, 0.85)
    for s in (0, 1, 2)
]


def load_groups(winding: set[str]) -> dict[str, list[str]]:
    with tarfile.open(SNAPSHOT) as archive:
        raw = json.load(archive.extractfile("annotations_for_skeletons.json"))
    names = raw["annotations"]
    groups: dict[str, list[str]] = {key: [] for key in GROUPS}
    wanted = {annotation: key for key, annotation in GROUPS.items()}
    for skid, items in raw["skeletons"].items():
        if skid not in winding:
            continue
        for item in items:
            key = wanted.get(names.get(str(item["id"])))
            if key:
                groups[key].append(skid)
    return {k: sorted(set(v), key=int) for k, v in groups.items()}


def hop_distances(edges, sources, min_contacts=2):
    adjacency = defaultdict(list)
    for edge in edges:
        if sum(edge["contacts_by_confidence"]) >= min_contacts:
            adjacency[edge["pre"]].append(edge["post"])
    dist = {s: 0 for s in sources}
    queue = deque(sources)
    while queue:
        node = queue.popleft()
        for nxt in adjacency[node]:
            if nxt not in dist:
                dist[nxt] = dist[node] + 1
                queue.append(nxt)
    return dist


def structural(compiled, groups):
    edges = compiled["edges"]
    out = {}
    for name, src, dst in (
        ("ORN->KC", "ORN", "KC"),
        ("sugar->DAN", "sugar_sensory", "DAN"),
        ("sugar->MBIN", "sugar_sensory", "MBIN"),
        ("KC->MBON", "KC", "MBON"),
        ("MBON->dVNC", "MBON", "dVNC"),
    ):
        dist = hop_distances(edges, groups[src])
        hops = [dist[t] for t in groups[dst] if t in dist]
        out[name] = {
            "targets": len(groups[dst]),
            "reached": len(hops),
            "min_hops": min(hops) if hops else None,
            "median_hops": float(np.median(hops)) if hops else None,
            "reached_within_2_hops": sum(h <= 2 for h in hops),
        }
    return out


def probe(compiled, winding, groups, names, w_syn_mv, duration_ms=1000.0, stim=(0.0, 500.0)):
    params = BrainParams(w_syn_mv=w_syn_mv)  # Poisson input weight stays at Shiu value
    results = {}
    for label, policy in POLICIES:
        net = build_network(compiled, policy, params=params, include=winding)

        def run(group, rate, seed=0):
            idx = net.ids(groups[group])
            return simulate(
                net, duration_ms, {int(i): rate for i in idx}, stim_window_ms=stim, seed=seed
            )

        stability = run("ORN", 100.0)
        bins_after = stability.spikes_per_bin[int(stim[1] / stability.bin_ms) + 5 :]
        rates = stability.rates_hz()
        odor = run("ORN_appetitive", 100.0)
        sugar = run("sugar_sensory", 100.0)
        dan_idx = net.ids(groups["DAN"])
        sugar_rates = sugar.rates_hz()
        dvnc_idx = net.ids(groups["dVNC"])
        results[label] = {
            "dVNC_active_ORN": int((stability.spike_counts[dvnc_idx] > 0).sum()),
            "stability_ORN_100Hz": {
                "active_neurons": int((rates > 0).sum()),
                "active_fraction": round(float((rates > 0).mean()), 4),
                "mean_rate_hz_active": round(float(rates[rates > 0].mean()), 2) if (rates > 0).any() else 0.0,
                "max_rate_hz": round(float(rates.max()), 1),
                "spikes_after_offset_50ms": int(bins_after.sum()),
                "self_sustained": bool(bins_after.sum() > 0),
            },
            "KC_active_appetitive_odor": int((odor.spike_counts[net.ids(groups["KC"])] > 0).sum()),
            "MBON_active_appetitive_odor": int((odor.spike_counts[net.ids(groups["MBON"])] > 0).sum()),
            "DAN_active_sugar": int((sugar_rates[dan_idx] > 0).sum()),
            "DAN_rates_sugar_hz": {
                names.get(net.skids[i], net.skids[i]): round(float(sugar_rates[i]), 1)
                for i in dan_idx
                if sugar_rates[i] > 0
            },
        }
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=LOCAL / "runs" / "brain_probe_v0.json")
    parser.add_argument("--w-syn", type=float, nargs="+", default=[0.275, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0])
    args = parser.parse_args(argv)
    compiled = json.loads(COMPILED.read_text(encoding="utf-8"))
    winding = {n["skid"] for n in compiled["neurons"] if n["winding_2023"]}
    names = {n["skid"]: n["name"] for n in compiled["neurons"]}
    groups = load_groups(winding)
    report = {
        "group_sizes": {k: len(v) for k, v in groups.items()},
        "structural_min_contacts_2": structural(compiled, groups),
        "probes_by_w_syn_mv": {
            str(w): probe(compiled, winding, groups, names, w) for w in args.w_syn
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
