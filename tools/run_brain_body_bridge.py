#!/usr/bin/env python3
"""Closed-loop co-simulation: fitted L1EM whole brain -> MDN -> axial VNC/body.

The 3,066-neuron brain (``BrainStepper``, 0.1 ms steps) and the axial
locomotion model (1 ms steps) advance together. Each 1 ms, spikes of the four
identified L1EM MDNs (MDNa/b left/right) are delivered as excitatory synaptic
current to the reduced circuit's ``descending:MDN`` node. That node starts
the A18b backward wave, as in ``docs/AXIAL_LOCOMOTION_V1.md``. No touch is
applied and no direction is sent to the body.

Conditions, per sign seed:
- spontaneous: brain with spontaneous input only;
- upstream: the top-K presynaptic partners of the MDNs (by L1EM contacts),
  stimulated at 150 Hz for 1 s, like an optogenetic line;
- fictive MDN: the four MDNs stimulated directly (positive control);
- bridge cut: the upstream stimulus with the brain->body MDN link removed.

Readout: anatomical forward displacement of the body (negative = backward),
MDN spikes in the brain, and axial MDN/A18b spikes. Outputs go to git-ignored
data/local/.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import numpy as np  # noqa: E402

import fit_l1em_celltype_scales as fit  # noqa: E402
from oraclarva.axial import AxialLocomotionLarva, load_axial_locomotion_config  # noqa: E402
from oraclarva.brain_sim import BrainStepper  # noqa: E402

LOCAL = fit.LOCAL
_S: dict = {}


def _setup(fit_path: str, top_k: int, bg_hz: float, bg_mv: float, bridge_current_a: float | None = None):
    fitted = json.loads(Path(fit_path).read_text(encoding="utf-8"))
    state = fit.setup(tuple(fitted.get("fitted_free_signs", {})), fitted.get("shuffle"))
    base = state["base"]
    names = {n["skid"]: n["name"] for n in json.loads(fit.COMPILED.read_text(encoding="utf-8"))["neurons"]}
    mdn = np.array([i for i, s in enumerate(base.skids) if names[s].startswith("MDN")], dtype=np.int64)
    into = np.asarray(base.contacts[:, mdn].sum(axis=1)).ravel()
    into[mdn] = 0
    upstream = np.argsort(-into)[:top_k]
    x = np.array(fitted["best_x"], dtype=float)
    n_scale = len(fit.CLASSES) + 1
    _S.update(
        state=state,
        scale=fit.row_scale(x[:n_scale], state),
        free_signs=np.where(x[n_scale:] >= 0, 1, -1).astype(np.int8),
        mdn=mdn,
        upstream=upstream,
        upstream_names=[names[base.skids[i]] for i in upstream],
        bg_hz=fit.background_rates(state, bg_hz),
        bg_mv=bg_mv,
        bridge_current_a=bridge_current_a,
    )


def run_one(job):
    seed, condition, duration_s = job
    s = _S
    signs = s["state"]["signs"][seed].copy()
    signs[s["state"]["free_idx"]] = s["free_signs"]
    net = s["state"]["base"].reweighted(signs=signs, row_scale=s["scale"], w_syn_mv=fit.W_BASE)
    brain = BrainStepper(net, seed=seed, background_hz=s["bg_hz"], background_weight_mv=s["bg_mv"])
    target = {"upstream": s["upstream"], "bridge_cut": s["upstream"], "fictive_mdn": s["mdn"]}.get(condition)
    stim = {int(i): 150.0 for i in target} if target is not None else None
    mdn_brain = [0]

    def source(time_s, dt_s):
        rates = stim if (stim is not None and 0.5 <= time_s < 1.5) else None
        counts = brain.advance(dt_s * 1000.0, rates)
        k = int(counts[s["mdn"]].sum())
        mdn_brain[0] += k
        return {} if condition == "bridge_cut" else {"descending:MDN": k}

    config = load_axial_locomotion_config()
    if s["bridge_current_a"] is not None:
        config["parameters"]["brain_bridge_current_a"] = s["bridge_current_a"]
    larva = AxialLocomotionLarva(config)
    result = larva.run(duration_s=duration_s, record_trajectory_interval_s=None, descending_spike_source=source)
    spikes = result.spike_counts
    return {
        "seed": seed,
        "condition": condition,
        "forward_displacement_um": round(result.anatomical_forward_displacement_um, 2),
        "mdn_brain_spikes": mdn_brain[0],
        "axial_mdn_spikes": int(spikes.get("descending:MDN", 0)),
        "axial_a18b_spikes": int(sum(v for k, v in spikes.items() if k.startswith("premotor:A18b"))),
        "axial_a27h_spikes": int(sum(v for k, v in spikes.items() if k.startswith("premotor:A27h"))),
        "all_active_forces_traced": bool(result.all_active_forces_sensory_traced),
        "untraced_active_force_frames": int(result.untraced_active_force_frames),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fit", default=str(LOCAL / "runs" / "celltype_sign_fit_v2.json"))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(fit.TEST_SEEDS[:5]))
    parser.add_argument("--conditions", nargs="+", default=["spontaneous", "upstream", "fictive_mdn", "bridge_cut"])
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--duration-s", type=float, default=5.5)
    parser.add_argument("--bg-hz", type=float, default=100.0)
    parser.add_argument("--bg-mv", type=float, default=6.0)
    parser.add_argument("--bridge-current-a", type=float, default=2e-10, help="current per brain MDN spike (default: premotor current)")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", type=Path, default=LOCAL / "runs" / "brain_body_bridge_v0.json")
    args = parser.parse_args(argv)
    jobs = [(seed, c, args.duration_s) for c in args.conditions for seed in args.seeds]
    with ProcessPoolExecutor(
        max_workers=args.workers, initializer=_setup, initargs=(args.fit, args.top_k, args.bg_hz, args.bg_mv, args.bridge_current_a)
    ) as pool:
        rows = list(pool.map(run_one, jobs))
    _setup(args.fit, args.top_k, args.bg_hz, args.bg_mv, args.bridge_current_a)
    summary = {}
    for c in args.conditions:
        sel = [r for r in rows if r["condition"] == c]
        d = np.array([r["forward_displacement_um"] for r in sel])
        summary[c] = {
            "displacement_um_mean": round(float(d.mean()), 2),
            "backward_runs": int((d < -20).sum()),
            "forward_runs": int((d > 20).sum()),
            "mdn_brain_spikes_mean": round(float(np.mean([r["mdn_brain_spikes"] for r in sel])), 1),
            "axial_mdn_spikes_mean": round(float(np.mean([r["axial_mdn_spikes"] for r in sel])), 1),
            "untraced_active_force_frames_max": int(max(r["untraced_active_force_frames"] for r in sel)),
            "n": len(sel),
        }
    report = {
        "fit": args.fit,
        "bridge_current_a": args.bridge_current_a,
        "upstream_neurons": _S["upstream_names"],
        "summary": summary,
        "runs": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "upstream": _S["upstream_names"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
