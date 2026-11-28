#!/usr/bin/env python3
"""Run one fit protocol on the intact and the block-shuffled connectomes, then
test which behaviours need the measured wiring.

Rule (docs/L1_SCORECARD_AND_CONNECTOME_SPECIFICITY_V0.md): a behaviour counts
toward the north star only if the intact network passes it and every shuffled
network fails it under the same protocol.

Every network gets the same treatment:

1. the same fit, from its own starting point (``--init`` for intact,
   ``--shuffle-init`` with ``{k}`` for shuffle k), or an existing fit;
2. conditioning parameters (DA threshold, eta) chosen on train seeds 0-3 by
   paired - unpaired LI, then held-out seeds;
3. the forward bridge current chosen on train seeds 0-3 by mean displacement,
   then held-out spontaneous crawling and PDM-DN activation;
4. the odor-offset probe (does an odor decrease raise PDM-DN?) on held-out
   seeds, and odor-gradient navigation with the steering current chosen on
   train seeds 0-3 by the mean mirror-pair difference, then held-out seeds.

Outputs (fits, runs, summary) go to the git-ignored
``data/local/l1em_public_connectome/runs/control/<tag>/``. A stage whose output
exists is skipped, so an interrupted run resumes.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "local" / "l1em_public_connectome" / "runs"
PY = sys.executable
TRAIN = [0, 1, 2, 3]
HELD_OUT = list(range(100, 110))
LEARNING_GRID = [(0.0, 1e-4), (2.0, 5e-4), (4.0, 2e-3), (8.0, 2e-3)]
FORWARD_GRID = [1e-10, 1.4e-10, 2e-10, 3e-10, 4e-10]
STEERING_GRID = [2e-10, 4e-10, 8e-10]
NAV_ARGS = ["--forward-current-a", "2e-10", "--mdn-current-a", "1.5e-10", "--bg-hz", "100", "--bg-mv", "6"]

# Pass criteria. They match tools/build_l1_scorecard.py.
CRITERIA = {
    "paired_LI": ("> 0.3", lambda v: v > 0.3),
    "fictive_punishment_LI": ("< -0.3", lambda v: v < -0.3),
    "spontaneous_forward_runs": (">= 8 of 10", lambda v: v >= 8),
    "pdm_stop_waves": ("== 0", lambda v: v == 0),
    "toward_odor_runs": (">= 8 of 10", lambda v: v >= 8),
    "odor_offset_pdm_seeds": (">= 5 of 10", lambda v: v >= 5),
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def run(cmd: list[str], log: Path) -> None:
    print("  $", " ".join(shlex.quote(c) for c in cmd[1:]), flush=True)
    with log.open("a", encoding="utf-8") as fh:
        subprocess.run(cmd, cwd=ROOT, check=True, stdout=fh, stderr=subprocess.STDOUT)


def once(out: Path, cmd: list[str], log: Path):
    if not out.exists():
        run(cmd + ["--out", str(out)], log)
    return load(out)


def network_fit(args, net: str, out_dir: Path, log: Path) -> Path:
    given = args.intact_fit if net == "intact" else (args.shuffle_fit.format(k=net) if args.shuffle_fit else None)
    if given:
        return Path(given)
    out = out_dir / f"fit_{net}.json"
    if not out.exists():
        init = args.init if net == "intact" else args.shuffle_init.format(k=net)
        cmd = [PY, "tools/fit_l1em_celltype_scales.py", *shlex.split(args.fit_args), "--init", init, "--out", str(out)]
        if net != "intact":
            cmd += ["--shuffle", f"block:{net}"]
        run(cmd, log)
    return out


def conditioning(fit: Path, net: str, out_dir: Path, log: Path, workers: int):
    best = None
    for th, eta in LEARNING_GRID:
        d = once(out_dir / f"cond_select_{net}_{th}_{eta}.json",
                 [PY, "tools/run_l1em_conditioning.py", "--fit", str(fit), "--da-threshold", str(th), "--eta", str(eta),
                  "--seeds", *map(str, TRAIN), "--conditions", "paired", "unpaired", "--workers", str(workers)], log)["summary"]
        diff = d["paired"]["LI_mean"] - d["unpaired"]["LI_mean"]
        if best is None or diff > best[0]:
            best = (diff, th, eta)
    _, th, eta = best
    d = once(out_dir / f"cond_{net}.json",
             [PY, "tools/run_l1em_conditioning.py", "--fit", str(fit), "--da-threshold", str(th), "--eta", str(eta),
              "--workers", str(workers)], log)
    return {"da_threshold": th, "eta": eta, "train_diff": round(best[0], 3), "summary": d["summary"]}


def crawl(fit: Path, net: str, out_dir: Path, log: Path, workers: int, bridge: list[str]):
    best = None
    for fwd in FORWARD_GRID:
        d = once(out_dir / f"crawl_select_{net}_{fwd}.json",
                 [PY, "tools/run_brain_body_crawl.py", "--fit", str(fit), "--seeds", *map(str, TRAIN),
                  "--conditions", "spontaneous", "--forward-current-a", str(fwd), *bridge, "--workers", str(workers)], log)
        disp = d["summary"]["spontaneous"]["displacement_um_mean"]
        if best is None or disp > best[0]:
            best = (disp, fwd)
    d = once(out_dir / f"crawl_{net}.json",
             [PY, "tools/run_brain_body_crawl.py", "--fit", str(fit), "--seeds", *map(str, HELD_OUT),
              "--conditions", "spontaneous", "pdm_activation", "--forward-current-a", str(best[1]), *bridge,
              "--workers", str(workers)], log)
    return {"forward_current_a": best[1], "summary": d["summary"]}


def odor(fit: Path, net: str, out_dir: Path, log: Path, workers: int):
    probe = once(out_dir / f"probe_{net}.json",
                 [PY, "tools/probe_brain_odor_offset.py", "--fit", str(fit), "--transducer", "--bg-hz", "100",
                  "--bg-mv", "6", "--workers", str(workers)], log)["summary"]["PDM-DN"]
    best = None
    for steer in STEERING_GRID:
        d = once(out_dir / f"nav_select_{net}_{steer}.json",
                 [PY, "tools/run_brain_odor_navigation.py", "--fit", str(fit), "--seeds", *map(str, TRAIN),
                  "--conditions", "plus_y", "minus_y", "--steering-current-a", str(steer), *NAV_ARGS,
                  "--workers", str(workers)], log)
        dy = d["mirror_pairs"]["y_plus_minus_y_minus_um"]
        score = sum(dy) / len(dy)
        if best is None or score > best[0]:
            best = (score, steer)
    d = once(out_dir / f"nav_{net}.json",
             [PY, "tools/run_brain_odor_navigation.py", "--fit", str(fit), "--seeds", *map(str, HELD_OUT),
              "--conditions", "plus_y", "minus_y", "--steering-current-a", str(best[1]), *NAV_ARGS,
              "--workers", str(workers)], log)
    return {"steering_current_a": best[1], "navigation": d["mirror_pairs"], "odor_offset_pdm": probe}


def behaviour(net_result) -> dict[str, float]:
    c, w = net_result["conditioning"]["summary"], net_result["crawl"]["summary"]
    return {
        "paired_LI": c["paired"]["LI_mean"],
        "unpaired_LI": c["unpaired"]["LI_mean"],
        "fictive_punishment_LI": c["fictive_punishment"]["LI_mean"],
        "spontaneous_forward_runs": w["spontaneous"]["runs_net_forward"],
        "cycle_speed_um_s": w["spontaneous"].get("cycle_speed_um_s_median"),
        "pdm_stop_waves": w["pdm_activation"]["waves_to_A5_in_stop_window_mean"],
        "toward_odor_runs": net_result["odor"]["navigation"]["toward_odor_runs"],
        "odor_offset_pdm_seeds": net_result["odor"]["odor_offset_pdm"]["seeds_increase_gt_1hz"],
        "held_out_fit_loss": net_result["fit_held_out_loss"],
    }


def judge(behaviours: dict[str, dict[str, float]], shuffles: list[str]) -> dict[str, dict]:
    """A behaviour is connectome-specific if intact passes and no shuffle does."""
    verdicts = {}
    for key, (text, ok) in CRITERIA.items():
        intact = ok(behaviours["intact"][key])
        shuffles_pass = [s for s in shuffles if ok(behaviours[s][key])]
        verdicts[key] = {
            "criterion": text,
            "intact_passes": intact,
            "shuffles_passing": shuffles_pass,
            "connectome_specific": intact and not shuffles_pass,
        }
    return verdicts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="name of this protocol, e.g. joint_v5")
    parser.add_argument("--fit-args", default="", help="options passed to fit_l1em_celltype_scales.py (no --init/--out/--shuffle)")
    parser.add_argument("--init", help="starting fit for the intact network")
    parser.add_argument("--shuffle-init", help="starting fit for shuffle k, with {k}")
    parser.add_argument("--intact-fit", help="use this existing intact fit instead of fitting")
    parser.add_argument("--shuffle-fit", help="use these existing shuffle fits ({k}) instead of fitting")
    parser.add_argument("--shuffles", nargs="+", default=["1", "2", "3"])
    parser.add_argument("--bridge-args", default="--mdn-current-a 1.5e-10 --sez-current-a 9e-10",
                        help="extra options for run_brain_body_crawl.py")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    if not args.intact_fit and not (args.init and args.fit_args):
        parser.error("give --intact-fit, or --init with --fit-args")
    if not args.shuffle_fit and not (args.shuffle_init and args.fit_args):
        parser.error("give --shuffle-fit, or --shuffle-init with --fit-args")

    out_dir = RUNS / "control" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / "log.txt"
    bridge = shlex.split(args.bridge_args)
    results = {}
    for net in ["intact", *args.shuffles]:
        print(f"[{args.tag}] network {net}", flush=True)
        fit = network_fit(args, net, out_dir, log)
        results[net] = {
            "fit": str(fit.relative_to(ROOT) if fit.is_absolute() else fit),
            "fit_held_out_loss": load(ROOT / fit)["held_out_right_odor_new_seeds"]["loss"],
            "conditioning": conditioning(fit, net, out_dir, log, args.workers),
            "crawl": crawl(fit, net, out_dir, log, args.workers, bridge),
            "odor": odor(fit, net, out_dir, log, args.workers),
        }
        results[net]["behaviour"] = behaviour(results[net])
        print(f"  {json.dumps(results[net]['behaviour'])}", flush=True)

    verdicts = judge({n: r["behaviour"] for n, r in results.items()}, args.shuffles)
    summary = {"tag": args.tag, "fit_args": args.fit_args, "networks": results, "verdicts": verdicts}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"\n{'behaviour':28s} {'intact':>8s} " + " ".join(f"{'sh' + s:>8s}" for s in args.shuffles) + "  specific")
    for key, v in verdicts.items():
        vals = [results[n]["behaviour"][key] for n in ["intact", *args.shuffles]]
        print(f"{key:28s} " + " ".join(f"{x:8.2f}" for x in vals) + f"  {v['connectome_specific']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
