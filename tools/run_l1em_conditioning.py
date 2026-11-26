#!/usr/bin/env python3
"""In-silico odor-sugar conditioning in the fitted L1EM brain (reciprocal design).

Plasticity: dopamine-gated KC->MBON depression (``oraclarva.brain_sim.Plasticity``).
Which DAN modulates which MBON comes only from measured DAN->MBON contacts
(row-normalized).  The reward enters as a stimulus to the 4 sugar sensory
neurons; no reward scalar is injected anywhere.

Odors: A = ORN types 42a/42b/24a, B = 74a/85c/22c (both sides, 6 ORNs each).
Training (3 cycles): rewarded odor + sugar for 2 s, then the other odor alone.
Two groups: A+/B- and A-/B+.  Test (no learning): each odor alone, 3 x 2 s.

Readout ("approach drive") = mean rate of appetitive MBONs minus mean rate of
aversive MBONs (Winding/Eschbach MBON valence annotations).
  pref_A = drive(A) - drive(B);   LI = (pref_A[A+] - pref_A[B+]) / 2
LI > 0 means appetitive memory for the sugar-paired odor.

Defaults (see docs/L1EM_CONDITIONING_V0.md):
eta 2e-3, dopamine threshold 4 (DAN trace units; chosen on train sign seeds 0-3),
spontaneous Poisson input
100 Hz x 6 mV to every non-KC neuron.

Conditions: paired; unpaired (sugar 1.5 s after odor offset); learning off;
fictive punishment (DL1 DANs DAN-d1/f1/g1 stimulated with the odor, like an
optogenetic experiment; expected LI < 0).
Outputs stay under git-ignored data/local/.
"""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import numpy as np  # noqa: E402

import fit_l1em_celltype_scales as fit  # noqa: E402
from oraclarva.brain_sim import Plasticity, simulate  # noqa: E402

LOCAL = fit.LOCAL
ODOR_A = ("42a", "42b", "24a")
ODOR_B = ("74a", "85c", "22c")
PUNISH_DANS = ("MBE4a", "MBE4f", "MBE4h")  # DAN-f1, g1, d1 (c1 = MBE4g does not teach; Eschbach 2020)
TEST_TRIALS = 3
_S: dict = {}


def _setup(
    fit_path: str, eta: float, bg_hz: float = 0.0, bg_mv: float = 0.0, da_threshold: float = 0.0,
    p_exc: float | None = None, odor_a: tuple = ODOR_A, odor_b: tuple = ODOR_B,
):
    fitted = json.loads(Path(fit_path).read_text(encoding="utf-8"))
    free = tuple(fitted.get("fitted_free_signs", {}))
    if p_exc is not None:
        fit.P_EXC = p_exc  # robustness: resample unknown signs with another excitatory fraction
    state = fit.setup(free, fitted.get("shuffle"))  # a null-model fit re-creates its shuffled network
    with tarfile.open(fit.SNAPSHOT) as archive:
        raw = json.load(archive.extractfile("annotations_for_skeletons.json"))
    base = state["base"]
    compiled_names = json.loads(fit.COMPILED.read_text(encoding="utf-8"))
    name_of = {n["skid"]: n["name"] for n in compiled_names["neurons"]}
    members = lambda a: fit._members(raw, a)  # noqa: E731
    orn = members("mw ORN")
    odor = lambda types: base.ids(s for s in orn if name_of[s].split(" ")[0] in types)  # noqa: E731
    kc = base.ids(members("mw KC"))
    mbon = base.ids(members("mw MBON"))
    dan = base.ids(members("mw MBIN subclass_DAN"))
    app = set(base.ids(members("mw MBON subclass_appetitive")).tolist())
    av = set(base.ids(members("mw MBON subclass_aversive")).tolist())
    dm = base.contacts[dan][:, mbon].toarray()
    modulation = dm / np.maximum(dm.sum(axis=1, keepdims=True), 1.0)
    x = np.array(fitted["best_x"], dtype=float)
    n_scale = len(fit.CLASSES) + 1
    free_signs = np.array([fitted["fitted_free_signs"][s] for s in state["free_skids"]], dtype=np.int8) if free else None
    _S.update(
        state=state,
        scale=fit.row_scale(x[:n_scale], state),
        free_signs=free_signs,
        odor_a=odor(tuple(odor_a)),
        odor_b=odor(tuple(odor_b)),
        sugar=state["sugar"],
        punish=base.ids(s for s in members("mw MBIN subclass_DAN") if name_of[s].split(" ")[0] in PUNISH_DANS),
        kc=kc,
        mbon=mbon,
        dan=dan,
        modulation=modulation,
        app_local=np.array([i for i, m in enumerate(mbon) if m in app]),
        av_local=np.array([i for i, m in enumerate(mbon) if m in av]),
        eta=eta,
        da_threshold=da_threshold,
        bg=dict(background_hz=fit.background_rates(state, bg_hz), background_weight_mv=bg_mv),
    )


def _drive(rates_mbon):
    return float(rates_mbon[_S["app_local"]].mean() - rates_mbon[_S["av_local"]].mean())


def _group(net, rewarded, other, condition, seed):
    s = _S
    p = Plasticity(kc_idx=s["kc"], mbon_idx=s["mbon"], dan_idx=s["dan"], modulation=s["modulation"], eta=s["eta"], da_threshold=s["da_threshold"])
    stripped = p.attach(net)
    p.learn = condition != "learning_off"
    reinforcer = s["punish"] if condition == "fictive_punishment" else s["sugar"]
    r_rate = 150.0  # same Poisson drive for sugar neurons and for fictive (optogenetic-like) DAN stimulation
    for cycle in range(3):
        odor_x = {int(i): 150.0 for i in rewarded}
        odor_y = {int(i): 150.0 for i in other}
        reinf = {int(i): r_rate for i in reinforcer}
        if condition == "unpaired":
            extra = ((reinf, (3500.0, 5500.0)), (odor_y, (7000.0, 9000.0)))
            duration = 10000.0
        else:
            extra = ((reinf, (0.0, 2000.0)), (odor_y, (3000.0, 5000.0)))
            duration = 6000.0
        simulate(stripped, duration, odor_x, (0.0, 2000.0), seed=seed * 100 + cycle, plasticity=p, extra_inputs=extra, **s["bg"])
    p.learn = False
    drives = {}
    for label, ids in (("A", s["odor_a"]), ("B", s["odor_b"])):
        vals = []
        for trial in range(TEST_TRIALS):
            run = simulate(
                stripped, 2000.0, {int(i): 150.0 for i in ids}, (0.0, 2000.0),
                seed=seed * 100 + 10 + trial, plasticity=p, **s["bg"],
            )
            vals.append(_drive(run.rates_hz()[s["mbon"]]))
        drives[label] = float(np.mean(vals))
    depression = 1.0 - p.km.sum(axis=0) / np.maximum(p.km_initial.sum(axis=0), 1e-12)
    return drives, {
        "appetitive_mbon_input_depression": round(float(depression[_S["app_local"]].mean()), 4),
        "aversive_mbon_input_depression": round(float(depression[_S["av_local"]].mean()), 4),
    }


def run_seed(args):
    seed, condition = args
    s = _S
    signs = s["state"]["signs"][seed].copy()
    if s["free_signs"] is not None:
        signs[s["state"]["free_idx"]] = s["free_signs"]
    net = s["state"]["base"].reweighted(signs=signs, row_scale=s["scale"], w_syn_mv=fit.W_BASE)
    d_ap, dep_ap = _group(net, s["odor_a"], s["odor_b"], condition, seed)
    d_bp, dep_bp = _group(net, s["odor_b"], s["odor_a"], condition, seed)
    pref_ap = d_ap["A"] - d_ap["B"]
    pref_bp = d_bp["A"] - d_bp["B"]
    return {
        "seed": seed,
        "condition": condition,
        "LI": round((pref_ap - pref_bp) / 2.0, 3),
        "pref_A_after_A+": round(pref_ap, 3),
        "pref_A_after_B+": round(pref_bp, 3),
        "depression_A+": dep_ap,
        "depression_B+": dep_bp,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fit", default=str(LOCAL / "runs" / "celltype_sign_fit_v2.json"))
    parser.add_argument("--eta", type=float, default=2e-3)
    parser.add_argument("--da-threshold", type=float, default=4.0)
    parser.add_argument("--p-exc", type=float, default=None, help="excitatory fraction for unknown signs (default: fit's 0.7)")
    parser.add_argument("--odor-a", nargs="+", default=list(ODOR_A))
    parser.add_argument("--odor-b", nargs="+", default=list(ODOR_B))
    parser.add_argument("--bg-hz", type=float, default=100.0, help="spontaneous Poisson input per neuron")
    parser.add_argument("--bg-mv", type=float, default=6.0)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(fit.TEST_SEEDS))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--conditions", nargs="+", default=["paired", "unpaired", "learning_off", "fictive_punishment"])
    parser.add_argument("--out", type=Path, default=LOCAL / "runs" / "conditioning_v0.json")
    args = parser.parse_args(argv)
    jobs = [(seed, c) for c in args.conditions for seed in args.seeds]
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_setup, initargs=(args.fit, args.eta, args.bg_hz, args.bg_mv, args.da_threshold, args.p_exc, args.odor_a, args.odor_b)) as pool:
        rows = list(pool.map(run_seed, jobs))
    summary = {}
    for c in args.conditions:
        li = np.array([r["LI"] for r in rows if r["condition"] == c])
        summary[c] = {
            "LI_mean": round(float(li.mean()), 3),
            "LI_sd": round(float(li.std(ddof=1)) if li.size > 1 else 0.0, 3),
            "LI_positive": int((li > 0).sum()),
            "n": int(li.size),
        }
    report = {"fit": args.fit, "shuffle": json.loads(Path(args.fit).read_text(encoding="utf-8")).get("shuffle"), "eta": args.eta, "da_threshold": args.da_threshold, "background_hz": args.bg_hz, "background_mv": args.bg_mv, "odor_A": args.odor_a, "odor_B": args.odor_b, "p_exc": args.p_exc, "summary": summary, "runs": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
