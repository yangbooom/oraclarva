#!/usr/bin/env python3
"""Fit per-cell-type synaptic scales of the L1EM brain with CMA-ES.

Parameters (log-space): one weight scale per presynaptic Winding cell class,
plus one extra gain on neurons with a known inhibitory sign.  Effective weight
per contact = 0.275 mV (Shiu w_syn) x scale(class of pre) x inhibitory_gain^[pre
is inhibitory].  Unknown signs are sampled (p_excitatory 0.7) with fixed seeds,
so the fit must work across sign samples, not one lucky draw.

Targets (MODEL_FITTED against these; provenance in docs/L1EM_CELLTYPE_FIT_V0.md):
  * no self-sustained activity after the stimulus ends (bounded network)
  * appetitive odor (left ORNs) activates 3-15% of ipsilateral KCs
    (adult ~7% sparseness used as a weak prior; larval value not found)
  * contralateral KC activation <= half of ipsilateral (L1 KC responses are
    almost entirely ipsilateral; Zimmerman et al. 2026 Sci Adv, late L1 imaging)
  * sugar sensory input activates the pPAM DANs DAN-i1/j1/k1 (MBE1c/1d/1b)
    (Weber et al. 2023 eLife, pooled pPAM imaging, 500 mM fructose; stage not
    verified verbatim, so this is a qualitative target)
  * max firing <= 300 Hz

Train: left odor + sign seeds 0-7.  Held out: right odor (mirror) + unseen seeds 100-109.
"""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from oraclarva.brain_sim import BrainParams, SignPolicy, build_network, resolve_signs, simulate  # noqa: E402
from oraclarva.cmaes import CMAES  # noqa: E402

LOCAL = ROOT / "data" / "local" / "l1em_public_connectome"
COMPILED = LOCAL / "compiled" / "l1em_connectome_v0.json"
SNAPSHOT = LOCAL / "l1em-public-snapshot-2026-11-25.tar"

# Presynaptic class, first match wins (Winding 2023 class annotations).
CLASSES = [
    ("sensory", ["mw sens"]),
    ("PN", ["mw all PNs"]),
    ("KC", ["mw KC"]),
    ("MBON", ["mw MBON"]),
    ("MBIN", ["mw MBIN"]),
    ("MB_FB_FF", ["mw FBN", "mw FB2N", "mw FFN"]),
    ("LN", ["mw LN"]),
    ("LHN", ["mw LHN"]),
    ("CN", ["mw CN"]),
    ("RGN", ["mw RGN"]),
    ("dSEZ", ["mw dSEZ"]),
    ("dVNC", ["mw dVNC"]),
    ("other", []),
]
PPAM_NAMES = ("MBE1b", "MBE1c", "MBE1d")  # DAN-k1, DAN-i1, DAN-j1
TRAIN_SEEDS = tuple(range(8))
TEST_SEEDS = tuple(range(100, 110))
REG = 0.02  # pull log-scales toward the uniform 0.6 mV start to avoid degenerate extremes
W_BASE = 0.275
P_EXC = 0.7

_STATE: dict = {}


def _members(raw, annotation):
    ids = {k for k, v in raw["annotations"].items() if v == annotation}
    return {s for s, items in raw["skeletons"].items() if any(str(a["id"]) in ids for a in items)}


def setup() -> dict:
    compiled = json.loads(COMPILED.read_text(encoding="utf-8"))
    neurons = [n for n in compiled["neurons"] if n["winding_2023"]]
    winding = {n["skid"] for n in neurons}
    with tarfile.open(SNAPSHOT) as archive:
        raw = json.load(archive.extractfile("annotations_for_skeletons.json"))
    base = build_network(compiled, SignPolicy(mode="silent"), BrainParams(), include=winding)
    cls = np.full(len(neurons), len(CLASSES) - 1)
    assigned = np.zeros(len(neurons), dtype=bool)
    for ci, (_, annotations) in enumerate(CLASSES[:-1]):
        members = set().union(*(_members(raw, a) for a in annotations))
        idx = base.ids(members)
        idx = idx[~assigned[idx]]
        cls[idx] = ci
        assigned[idx] = True
    left, right = _members(raw, "mw left"), _members(raw, "mw right")
    app = _members(raw, "mw ORN appetitive")
    kc = _members(raw, "mw KC")
    names = {n["skid"]: n["name"] for n in neurons}
    ppam = [s for s in winding if names[s].split(" ")[0] in PPAM_NAMES]
    signs = {
        seed: resolve_signs(neurons, SignPolicy(mode="sample", p_excitatory=P_EXC, seed=seed))
        for seed in TRAIN_SEEDS + TEST_SEEDS
    }
    return {
        "base": base,
        "cls": cls,
        "signs": signs,
        "inh_known": np.array([n["fast_sign"] == -1 for n in neurons]),
        "odor_left": base.ids(app & left),
        "odor_right": base.ids(app & right),
        "kc_left": base.ids(kc & left),
        "kc_right": base.ids(kc & right),
        "sugar": base.ids(_members(raw, "sugar sensory")),
        "ppam": base.ids(ppam),
        "class_sizes": {name: int((cls == i).sum()) for i, (name, _) in enumerate(CLASSES)},
    }


def _init_worker():
    _STATE.update(setup())


def _hinge(value, low=None, high=None, scale=1.0):
    loss = 0.0
    if low is not None and value < low:
        loss += ((low - value) / scale) ** 2
    if high is not None and value > high:
        loss += ((value - high) / scale) ** 2
    return loss


def evaluate(x, seeds=TRAIN_SEEDS, side="left", state=None, detail=False):
    s = state or _STATE
    x = np.asarray(x, dtype=float)
    scale = np.exp(x[: len(CLASSES)])[s["cls"]]
    scale = scale * np.where(s["inh_known"], np.exp(x[len(CLASSES)]), 1.0)
    odor = s["odor_left"] if side == "left" else s["odor_right"]
    kc_ipsi = s["kc_left"] if side == "left" else s["kc_right"]
    kc_contra = s["kc_right"] if side == "left" else s["kc_left"]
    total, rows = 0.0, []
    for seed in seeds:
        net = s["base"].reweighted(signs=s["signs"][seed], row_scale=scale, w_syn_mv=W_BASE)
        o = simulate(net, 800.0, {int(i): 150.0 for i in odor}, (0.0, 500.0), seed=seed, late_from_ms=600.0)
        g = simulate(net, 800.0, {int(i): 150.0 for i in s["sugar"]}, (0.0, 500.0), seed=seed, late_from_ms=600.0)
        ipsi = float((o.spike_counts[kc_ipsi] > 0).mean())
        contra = float((o.spike_counts[kc_contra] > 0).mean())
        ppam_rates = g.rates_hz()[s["ppam"]]
        late = (o.late_counts.sum() + g.late_counts.sum()) / max(1, o.spike_counts.sum() + g.spike_counts.sum())
        max_rate = float(max(o.rates_hz().max(), g.rates_hz().max()))
        loss = (
            50.0 * late
            + 5.0 * float(late > 0)
            + _hinge(ipsi, 0.03, 0.15, 0.03)
            + _hinge(contra, None, 0.5 * ipsi + 0.01, 0.03)
            + _hinge(float((ppam_rates > 1.0).mean()), 0.5, None, 0.25)
            + _hinge(float(ppam_rates.mean()), 5.0, None, 5.0)
            + _hinge(max_rate, None, 300.0, 50.0)
        )
        total += loss
        rows.append(
            {
                "seed": seed,
                "loss": round(loss, 4),
                "self_sustained": bool(late > 0),
                "kc_ipsi_fraction": round(ipsi, 3),
                "kc_contra_fraction": round(contra, 3),
                "ppam_active_fraction": round(float((ppam_rates > 1.0).mean()), 3),
                "ppam_mean_rate_hz": round(float(ppam_rates.mean()), 1),
                "max_rate_hz": round(max_rate, 1),
                "active_neurons_odor": int((o.spike_counts > 0).sum()),
            }
        )
    x0 = np.full(x.size, np.log(0.6 / W_BASE))
    x0[-1] = 0.0
    mean = total / len(seeds) + REG * float(np.sum((x - x0) ** 2))
    return (mean, rows) if detail else mean


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--generations", type=int, default=25)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", type=Path, default=LOCAL / "runs" / "celltype_fit_v0.json")
    args = parser.parse_args(argv)

    state = setup()
    dims = len(CLASSES) + 1
    x0 = np.full(dims, np.log(0.6 / W_BASE))  # start inside the bounded regime found by the probe
    x0[-1] = 0.0
    baseline = {
        "adult_w_syn_train": evaluate(np.zeros(dims), state=state, detail=True),
        "uniform_0.6mV_train": evaluate(x0, state=state, detail=True),
    }
    es = CMAES(mean=x0, sigma=0.4, seed=0)
    history = []
    started = time.time()
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker) as pool:
        for gen in range(args.generations):
            xs = es.ask()
            losses = np.array(list(pool.map(evaluate, xs)))
            es.tell(xs, losses)
            history.append({"generation": gen, "best": round(float(losses.min()), 4), "median": round(float(np.median(losses)), 4), "sigma": round(es.sigma, 4)})
            print(json.dumps(history[-1] | {"elapsed_s": round(time.time() - started)}), flush=True)
    best = es.best_x
    train_loss, train_rows = evaluate(best, TRAIN_SEEDS, "left", state, detail=True)
    held_loss, held_rows = evaluate(best, TEST_SEEDS, "right", state, detail=True)
    scales = {name: round(float(np.exp(best[i])), 4) for i, (name, _) in enumerate(CLASSES)}
    report = {
        "provenance": "MODEL_FITTED",
        "w_base_mv": W_BASE,
        "p_excitatory_unknown": P_EXC,
        "train_seeds": list(TRAIN_SEEDS),
        "held_out_seeds": list(TEST_SEEDS),
        "regularization": REG,
        "class_sizes": state["class_sizes"],
        "fitted_scale_by_presynaptic_class": scales,
        "fitted_mv_per_contact_by_class": {k: round(v * W_BASE, 4) for k, v in scales.items()},
        "fitted_known_inhibitory_gain": round(float(np.exp(best[-1])), 4),
        "baseline": {k: {"loss": round(v[0], 4), "runs": v[1]} for k, v in baseline.items()},
        "train": {"loss": round(train_loss, 4), "runs": train_rows},
        "held_out_right_odor_new_seeds": {"loss": round(held_loss, 4), "runs": held_rows},
        "history": history,
        "best_x": [float(v) for v in best],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("history", "best_x")}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
