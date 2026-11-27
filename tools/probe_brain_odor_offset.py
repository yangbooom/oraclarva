#!/usr/bin/env python3
"""Does the fitted L1EM brain code an odor *decrease* in its descending output?

L1 chemotaxis relies on temporal comparison: an odor decrease raises PDM-DN
activity, which stops the larva and starts a head cast (Tastekin et al. 2018).
Before building head-cast mechanics in the body, this checks whether the
brain itself shows that response. It runs brain only, with no body.

Protocol per sign seed, 8 s:
- spontaneous input only for 0-3 s;
- appetitive ORNs on both sides at ``--high-hz`` for 3-6 s;
- the same ORNs at ``--low-hz`` from 6 s (a step decrease; 0 = odor off).

A matched no-odor run with the same seed is the control. Readouts are mean
rates per neuron in fixed windows, for PDM-DN, MDN, the forward-initiation
group and MBONs:
- step response = rate in [6, 7) s minus rate in [5, 6) s;
- control-corrected = that difference minus the same difference in the
  no-odor run.

Outputs go to the git-ignored data/local/.
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

from oraclarva.brain_body import BrainContext, BrainSpikeSource, OrnTransducer, Stimulus  # noqa: E402

LOCAL = ROOT / "data" / "local" / "l1em_public_connectome"
GROUPS = ("PDM-DN", "SEZ-DN1", "MDN", "dVNC_to_A8_A9", "MBON", "ORN_appetitive")
WINDOWS = {"baseline": (1.0, 3.0), "on_early": (3.0, 4.0), "on_late": (5.0, 6.0), "after_step": (6.0, 7.0), "late_after": (7.0, 8.0)}
_C: dict = {}


def _setup(fit_path, bg_hz, bg_mv):
    _C["ctx"] = BrainContext.load(fit_path, bg_hz, bg_mv)


def window_rates(source, name, n):
    per_ms = np.asarray(source.per_ms[name], dtype=float)
    return {w: float(per_ms[int(a * 1000) : int(b * 1000)].sum() / (b - a) / n) for w, (a, b) in WINDOWS.items()}


def run_one(job):
    seed, odor, high, low, transducer = job
    ctx = _C["ctx"]
    orns = np.concatenate([ctx.state["odor_left"], ctx.state["odor_right"]])
    groups = dict(ctx.groups, ORN_appetitive=orns)
    brain = ctx.stepper(seed)
    schedule, dynamic = [], None
    if transducer:
        # Concentration 0 -> 1 at 3 s -> low/high at 6 s, through the ORN model.
        orn = OrnTransducer(brain, orns, gain_hz=high)
        level = lambda t: 0.0 if (not odor or t < 3.0) else (1.0 if t < 6.0 else low / high)  # noqa: E731
        dynamic = lambda t: orn(level(t), 1e-3)  # noqa: E731
    elif odor:
        schedule.append(Stimulus(orns, high, 3.0, 6.0))
        if low > 0:
            schedule.append(Stimulus(orns, low, 6.0, 8.0))
    source = BrainSpikeSource(brain, groups, {}, schedule, dynamic_rates=dynamic, record=GROUPS)
    for step in range(8000):
        source(step * 1e-3, 1e-3)
    return {
        "seed": seed,
        "odor": odor,
        **{g: window_rates(source, g, len(groups[g])) for g in GROUPS},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fit", required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(100, 110)))
    parser.add_argument("--high-hz", type=float, default=150.0)
    parser.add_argument("--low-hz", type=float, default=0.0)
    parser.add_argument("--transducer", action="store_true", help="drive ORNs through OrnTransducer (adaptation + offset inhibition)")
    parser.add_argument("--bg-hz", type=float, default=100.0)
    parser.add_argument("--bg-mv", type=float, default=6.0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    jobs = [(s, odor, args.high_hz, args.low_hz, args.transducer) for s in args.seeds for odor in (True, False)]
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_setup, initargs=(args.fit, args.bg_hz, args.bg_mv)) as pool:
        rows = list(pool.map(run_one, jobs))
    summary = {}
    for g in GROUPS:
        step, corrected, onset = [], [], []
        for s in args.seeds:
            o = next(r for r in rows if r["seed"] == s and r["odor"])[g]
            c = next(r for r in rows if r["seed"] == s and not r["odor"])[g]
            d_odor = o["after_step"] - o["on_late"]
            d_ctrl = c["after_step"] - c["on_late"]
            step.append(d_odor)
            corrected.append(d_odor - d_ctrl)
            onset.append((o["on_early"] - o["baseline"]) - (c["on_early"] - c["baseline"]))
        summary[g] = {
            "step_response_hz_median": round(float(np.median(step)), 2),
            "step_response_control_corrected_hz": [round(v, 2) for v in corrected],
            "step_response_control_corrected_median": round(float(np.median(corrected)), 2),
            "seeds_increase_gt_1hz": int(sum(v > 1.0 for v in corrected)),
            "seeds_decrease_lt_minus_1hz": int(sum(v < -1.0 for v in corrected)),
            "onset_response_control_corrected_median": round(float(np.median(onset)), 2),
        }
    report = {"fit": args.fit, "transducer": args.transducer, "high_hz": args.high_hz, "low_hz": args.low_hz, "windows_s": WINDOWS, "summary": summary, "runs": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
