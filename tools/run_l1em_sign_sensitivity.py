#!/usr/bin/env python3
"""Rank unknown-sign neurons by how much they decide whole-brain stability.

Near the critical weight (default w_syn 0.8 mV, p_excitatory 0.7) runaway
depends on how unknown signs are sampled.  For each seed we drive the 42 ORNs
(100 Hz, 0-500 ms) and record which neurons keep firing after 600 ms (the
reverberating core).  Unknown-sign neurons are scored by

    score = sum over runaway runs of excitatory contacts sent into that run's core

and the ranking is validated causally: in runaway runs, forcing the top-K
unknown neurons inhibitory is compared with forcing K random unknown neurons.
Outputs stay under git-ignored data/local/.
"""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from oraclarva.brain_sim import BrainParams, SignPolicy, build_network, resolve_signs, simulate  # noqa: E402

LOCAL = ROOT / "data" / "local" / "l1em_public_connectome"
COMPILED = LOCAL / "compiled" / "l1em_connectome_v0.json"
SNAPSHOT = LOCAL / "l1em-public-snapshot-2026-11-25.tar"


def annotation_members(annotation: str) -> set[str]:
    with tarfile.open(SNAPSHOT) as archive:
        raw = json.load(archive.extractfile("annotations_for_skeletons.json"))
    target = {k for k, v in raw["annotations"].items() if v == annotation}
    return {s for s, items in raw["skeletons"].items() if any(str(a["id"]) in target for a in items)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--w-syn", type=float, default=0.8)
    parser.add_argument("--p-exc", type=float, default=0.7)
    parser.add_argument("--seeds", type=int, default=60)
    parser.add_argument("--orn-rate", type=float, default=100.0)
    parser.add_argument("--fit", type=Path, default=None, help="celltype fit JSON; applies its fitted scales (w_base 0.275)")
    parser.add_argument("--out", type=Path, default=LOCAL / "runs" / "sign_sensitivity_v0.json")
    args = parser.parse_args(argv)

    compiled = json.loads(COMPILED.read_text(encoding="utf-8"))
    neurons = [n for n in compiled["neurons"] if n["winding_2023"]]
    winding = {n["skid"] for n in neurons}
    params = BrainParams(w_syn_mv=args.w_syn)
    base = build_network(compiled, SignPolicy(mode="silent"), params=params, include=winding)
    unknown = np.array(
        [n["fast_sign"] not in (1, -1) and not n.get("modulatory") and not n.get("conflict") for n in neurons]
    )
    orn = {int(i): args.orn_rate for i in base.ids(annotation_members("mw ORN"))}
    contacts = base.contacts
    row_scale, w_eff = None, args.w_syn
    if args.fit is not None:
        sys.path.insert(0, str(ROOT / "tools"))
        import fit_l1em_celltype_scales as fit  # noqa: E402

        fitted = json.loads(args.fit.read_text(encoding="utf-8"))
        state = fit.setup()
        row_scale = fit.row_scale(np.array(fitted["best_x"]), state)
        w_eff = fit.W_BASE

    def run(signs, seed=0):
        net = base.reweighted(signs=signs, row_scale=row_scale, w_syn_mv=w_eff)
        return simulate(net, 800.0, orn, stim_window_ms=(0.0, 500.0), seed=seed, late_from_ms=600.0)

    runs = []
    score = np.zeros(len(neurons))
    core_freq = np.zeros(len(neurons))
    for seed in range(args.seeds):
        signs = resolve_signs(neurons, SignPolicy(mode="sample", p_excitatory=args.p_exc, seed=seed))
        result = run(signs)
        core = result.late_counts > 0
        runaway = bool(core.any())
        runs.append({"seed": seed, "signs": signs, "runaway": runaway, "core": core})
        if runaway:
            core_freq += core
            into_core = np.asarray(contacts[:, core].sum(axis=1)).ravel()
            score += np.where((signs == 1) & unknown, into_core, 0.0)
    runaway_runs = [r for r in runs if r["runaway"]]
    n_run = len(runaway_runs)
    score_masked = np.where(unknown, score, -1.0)
    order = np.argsort(-score_masked)
    ranked = [int(i) for i in order if unknown[i] and score[i] > 0]

    # Naive association, reported for comparison (underpowered with ~60 runs).
    sampled_exc = np.array([r["signs"] == 1 for r in runs])
    runaway_vec = np.array([r["runaway"] for r in runs], dtype=float)
    with np.errstate(invalid="ignore"):
        p_given_exc = (sampled_exc * runaway_vec[:, None]).sum(0) / sampled_exc.sum(0)
        p_given_inh = ((~sampled_exc) * runaway_vec[:, None]).sum(0) / (~sampled_exc).sum(0)

    rng = np.random.default_rng(12345)
    unknown_idx = np.flatnonzero(unknown)
    validation = {}
    for k in (10, 30, 100, 300):
        stopped_top = stopped_rand = 0
        for r in runaway_runs[:15]:
            top = [i for i in ranked if r["signs"][i] == 1][:k]
            forced = r["signs"].copy()
            forced[top] = -1
            stopped_top += not (run(forced).late_counts > 0).any()
            pool = unknown_idx[r["signs"][unknown_idx] == 1]
            rand = rng.choice(pool, size=min(k, pool.size), replace=False)
            forced = r["signs"].copy()
            forced[rand] = -1
            stopped_rand += not (run(forced).late_counts > 0).any()
        tested = min(15, n_run)
        validation[str(k)] = {
            "runaway_runs_tested": tested,
            "stopped_by_top_k_inhibitory": stopped_top,
            "stopped_by_random_k_inhibitory": stopped_rand,
        }

    names = {n["skid"]: n["name"] for n in neurons}
    top_list = [
        {
            "skid": base.skids[i],
            "name": names[base.skids[i]],
            "score_contacts_into_core": int(score[i]),
            "core_frequency": round(float(core_freq[i] / max(n_run, 1)), 3),
            "p_runaway_if_exc": round(float(p_given_exc[i]), 3),
            "p_runaway_if_inh": round(float(p_given_inh[i]), 3),
            "lineages": next(n["lineages"] for n in neurons if n["skid"] == base.skids[i]),
        }
        for i in ranked[:50]
    ]
    report = {
        "w_syn_mv": args.w_syn if args.fit is None else None,
        "fit": str(args.fit) if args.fit else None,
        "orn_rate_hz": args.orn_rate,
        "p_excitatory": args.p_exc,
        "seeds": args.seeds,
        "runaway_fraction": round(n_run / args.seeds, 3),
        "unknown_neurons": int(unknown.sum()),
        "unknown_neurons_with_positive_score": len(ranked),
        "core_size_median": float(np.median([r["core"].sum() for r in runaway_runs])) if runaway_runs else 0.0,
        "causal_validation": validation,
        "top50": top_list,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "top50"} | {"top10": top_list[:10]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
