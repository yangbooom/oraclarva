#!/usr/bin/env python3
"""M3 v0: odor gradient -> L1EM ORNs -> fitted brain -> descending groups -> body.

Closed loop, every 1 ms:

    odor field sampled at the current left/right head surface
      -> Poisson rate of the left / right appetitive ORNs (rate = max_hz x F)
      -> fitted 3,066-neuron L1EM brain
      -> MDN -> descending:MDN; neurons descending to A8/A9 -> A27h:A6 (crawl start)
      -> left / right soma-side brain DNs that project to T3+A1
         -> the existing side-resolved steering relay -> A1-A3 premotor -> shared MNs
      -> fibers -> body/contact -> new head position

The body receives no heading, target or turn command. The only placement
choice is that a left-soma steering DN drives the left steering relay
(ipsilateral, fixed a priori; not fitted). Whether the larva turns toward or
away from the odor is therefore decided by the brain's lateralization.

Conditions per sign seed: +y gradient, -y gradient, uniform field. A null
(shuffled-connectome) fit can be given with --fit. Outputs go to data/local/.
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

from oraclarva.brain_body import BrainContext  # noqa: E402
from oraclarva.steering import AxialSteeringLarva, PlanarLinearField  # noqa: E402

LOCAL = ROOT / "data" / "local" / "l1em_public_connectome"
STEERING_ANNOTATION = "lv dVNC to T3+A1"
_C: dict = {}


def steering_groups(ctx: BrainContext) -> dict[str, np.ndarray]:
    fit = ctx.fit
    import tarfile  # noqa: PLC0415

    with tarfile.open(fit.SNAPSHOT) as archive:
        raw = json.load(archive.extractfile("annotations_for_skeletons.json"))
    base = ctx.state["base"]
    members = lambda a: set(base.ids(fit._members(raw, a)).tolist())  # noqa: E731
    excluded = set(ctx.groups["MDN"].tolist()) | set(ctx.groups["dVNC_to_A8_A9"].tolist())
    group = members(STEERING_ANNOTATION) - excluded
    return {
        "left": np.array(sorted(group & members("mw left")), dtype=np.int64),
        "right": np.array(sorted(group & members("mw right")), dtype=np.int64),
    }


def _setup(fit_path, bg_hz, bg_mv):
    ctx = BrainContext.load(fit_path, bg_hz, bg_mv)
    _C["ctx"] = ctx
    _C["steer"] = steering_groups(ctx)


class BrainLoop:
    def __init__(self, ctx, seed, steer, orn_max_hz, bridges):
        self.ctx = ctx
        self.brain = ctx.stepper(seed)
        self.steer = steer
        self.orn_max_hz = orn_max_hz
        self.bridges = bridges
        self.left_orn = ctx.state["odor_left"]
        self.right_orn = ctx.state["odor_right"]
        self.side_counts = {"left": 0, "right": 0}
        self.pending_side = {"left": 0, "right": 0}
        self.pending: dict[str, int] = {}
        self.totals = {"left": 0, "right": 0, "MDN": 0, "forward": 0}

    def descending(self, time_s, dt_s, field_sample):
        rates = {}
        for i in self.left_orn:
            rates[int(i)] = self.orn_max_hz * field_sample.left_intensity
        for i in self.right_orn:
            rates[int(i)] = self.orn_max_hz * field_sample.right_intensity
        # Deliver the previous brain step's spikes (one-step causal delay).
        previous = self.pending
        counts = self.brain.advance(dt_s * 1000.0, rates)
        g = self.ctx.groups
        self.side_counts = self.pending_side
        self.pending_side = {side: int(counts[idx].sum()) for side, idx in self.steer.items()}
        for side in ("left", "right"):
            self.totals[side] += self.pending_side[side]
        mdn = int(counts[g["MDN"]].sum())
        fwd = int(counts[g["dVNC_to_A8_A9"]].sum())
        self.totals["MDN"] += mdn
        self.totals["forward"] += fwd
        self.pending = {k: v for k, v in {"descending:MDN": mdn, "premotor:A27h:A6": fwd}.items() if k in self.bridges}
        return previous

    def steering(self):
        return self.side_counts


def run_one(job):
    seed, condition, args = job
    ctx, steer = _C["ctx"], _C["steer"]
    gy = {"plus_y": args["gradient"], "minus_y": -args["gradient"], "uniform": 0.0}[condition]
    field = PlanarLinearField(baseline=0.5, gradient_y_per_m=gy)
    larva = AxialSteeringLarva()
    larva.config["parameters"]["brain_steering_current_a"] = args["steering_current_a"]
    larva.axial_config["parameters"]["brain_bridge_current_a_by_node"] = {
        "descending:MDN": args["mdn_current_a"],
        "premotor:A27h:A6": args["forward_current_a"],
    }
    loop = BrainLoop(ctx, seed, steer, args["orn_max_hz"], ("descending:MDN", "premotor:A27h:A6"))
    result = larva.run(
        field,
        posterior_touch=False,
        duration_s=args["duration_s"],
        record_trajectory_interval_s=None,
        descending_spike_source=loop.descending,
        steering_spike_source=loop.steering,
    )
    sign = float(np.sign(gy)) if gy else 0.0
    return {
        "seed": seed,
        "condition": condition,
        "heading_change_deg": round(result.heading_change_deg, 3),
        "displacement_y_um": round(result.displacement_y_um, 2),
        "displacement_up_gradient_um": round(sign * result.displacement_y_um, 2) if sign else None,
        "forward_displacement_um": round(result.anatomical_forward_displacement_um, 2),
        "steering_dn_spikes_left": loop.totals["left"],
        "steering_dn_spikes_right": loop.totals["right"],
        "brain_mdn_spikes": loop.totals["MDN"],
        "brain_forward_dn_spikes": loop.totals["forward"],
        "relay_spikes": {k: v for k, v in result.steering_spike_counts.items() if k.startswith("field_sensory")},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fit", default=str(LOCAL / "runs" / "celltype_motor_fit_v3b.json"))
    parser.add_argument("--seeds", type=int, nargs="+", default=[100, 101, 102, 103, 104])
    parser.add_argument("--conditions", nargs="+", default=["plus_y", "minus_y", "uniform"])
    parser.add_argument("--duration-s", type=float, default=20.0)
    parser.add_argument("--gradient", type=float, default=5000.0, help="field gradient per metre (steering-v1 fixture)")
    parser.add_argument("--orn-max-hz", type=float, default=150.0)
    parser.add_argument("--steering-current-a", type=float, default=4e-10)
    parser.add_argument("--forward-current-a", type=float, default=3e-10)
    parser.add_argument("--mdn-current-a", type=float, default=2e-10)
    parser.add_argument("--bg-hz", type=float, default=100.0)
    parser.add_argument("--bg-mv", type=float, default=6.0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", type=Path, default=LOCAL / "runs" / "odor_navigation_v0.json")
    args = parser.parse_args(argv)
    params = {k: getattr(args, k) for k in ("duration_s", "gradient", "orn_max_hz", "steering_current_a", "forward_current_a", "mdn_current_a")}
    jobs = [(seed, c, params) for c in args.conditions for seed in args.seeds]
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_setup, initargs=(args.fit, args.bg_hz, args.bg_mv)) as pool:
        rows = list(pool.map(run_one, jobs))
    summary = {}
    for c in args.conditions:
        sel = [r for r in rows if r["condition"] == c]
        h = np.array([r["heading_change_deg"] for r in sel])
        summary[c] = {
            "n": len(sel),
            "heading_change_deg_mean": round(float(h.mean()), 2),
            "displacement_y_um_mean": round(float(np.mean([r["displacement_y_um"] for r in sel])), 1),
            "forward_um_mean": round(float(np.mean([r["forward_displacement_um"] for r in sel])), 1),
            "steering_lr_spike_diff_mean": round(float(np.mean([r["steering_dn_spikes_left"] - r["steering_dn_spikes_right"] for r in sel])), 1),
        }
    paired = {}
    if {"plus_y", "minus_y"} <= set(args.conditions):
        by = {(r["seed"], r["condition"]): r for r in rows}
        d = np.array([by[(s, "plus_y")]["displacement_y_um"] - by[(s, "minus_y")]["displacement_y_um"] for s in args.seeds])
        paired = {
            "y_plus_minus_y_minus_um": d.round(1).tolist(),
            "toward_odor_runs": int((d > 0).sum()),
            "n": int(d.size),
        }
        try:
            from scipy.stats import wilcoxon  # noqa: PLC0415

            paired["wilcoxon_p"] = round(float(wilcoxon(d).pvalue), 4) if np.any(d) else 1.0
        except Exception:  # noqa: BLE001
            pass
    report = {"fit": args.fit, "parameters": params, "summary": summary, "mirror_pairs": paired, "runs": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "mirror_pairs": paired}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
