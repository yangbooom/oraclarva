#!/usr/bin/env python3
"""Build the L1 north-star scorecard from local run outputs.

One row per behaviour, with:
- the L1 reference: Greaney 2026 held-out animals (p10 / median / p90), or a
  qualitative published finding;
- the current model: joint fit v4 plus the brain-body bridge, on held-out
  sign seeds 100-109;
- the block-shuffled connectome given the same protocol (mean over shuffles),
  where it was run;
- a pass / fail / not-built status.

Only aggregate numbers are written. They go to the git-ignored data/local/
by default.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "local" / "l1em_public_connectome" / "runs"
GREANEY = ROOT / "data" / "validation" / "greaney_2026_l1_kinematics_v0.json"
AXIAL = ROOT / "data" / "organism" / "l1_axial_locomotion_v1.json"


def load(path):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def in_range(value, low, high):
    return "pass" if value is not None and low <= value <= high else "fail"


def shuffle_mean(values):
    values = [v for v in values if v is not None]
    return (round(float(np.mean(values)), 2), len(values)) if values else (None, 0)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=RUNS / "scorecard_v0.json")
    parser.add_argument("--shuffles", type=int, nargs="+", default=[1, 2, 3])
    args = parser.parse_args(argv)

    ref = load(GREANEY)["held_out_validation_targets"]["cycle_metrics"]
    crawl = load(RUNS / "brain_body_crawl_v1.json")["summary"]
    cycles = load(RUNS / "brain_body_crawl_v1_cycles.json")["summary"]["spontaneous"]
    cond = load(RUNS / "conditioning_v4.json")["summary"]
    probe = load(RUNS / "odor_offset_probe_v5_transducer.json")["summary"]["PDM-DN"]
    nav = load(RUNS / "odor_navigation_v0.json")["mirror_pairs"]
    delay = load(AXIAL)["parameters"]["intersegmental_delay_s"]

    null_crawl = [load(RUNS / "null" / f"crawl_joint_v4_block_{k}.json") for k in args.shuffles]
    # Conditioning parameters were reselected per network on train seeds 0-3;
    # "_selected" holds the held-out run where the choice differed from the default.
    null_cond = [
        load(RUNS / "null" / f"cond_joint_v4_block_{k}_selected.json") or load(RUNS / "null" / f"cond_joint_v4_block_{k}.json")
        for k in args.shuffles
    ]
    nc = lambda cond_, key: [d["summary"][cond_].get(key) for d in null_crawl if d and cond_ in d["summary"]]  # noqa: E731
    nl = lambda cond_: [d["summary"][cond_]["LI_mean"] for d in null_cond if d]  # noqa: E731

    rows = []

    def add(category, metric, unit, l1, model, status, shuffle=(None, 0), note="", specific="not tested"):
        rows.append(
            {
                "category": category,
                "metric": metric,
                "unit": unit,
                "l1_p10": l1.get("p10"),
                "l1_median": l1.get("median"),
                "l1_p90": l1.get("p90"),
                "l1_text": l1.get("text"),
                "model": model,
                "shuffle_mean": shuffle[0],
                "shuffle_n": shuffle[1],
                "status": status,
                "connectome_specific": specific,
                "note": note,
            }
        )

    g = lambda k: {a: round(ref[k][a], 2) for a in ("p10", "median", "p90")}  # noqa: E731
    speed = cycles["cycle_speed_um_s_median"]
    add("Crawling", "Crawl speed per cycle", "µm/s", g("crawl_speed_um_s"), speed,
        in_range(speed, ref["crawl_speed_um_s"]["p10"], ref["crawl_speed_um_s"]["p90"]),
        shuffle_mean(nc("spontaneous", "cycle_speed_um_s_median")),
        "The clean-body ceiling is 26.8 µm/s. Extra brain A6 spikes shorten strides.", "no")
    stride = cycles["cycle_stride_um_median"]
    add("Crawling", "Stride per cycle", "µm", g("stride_um"), stride,
        in_range(stride, ref["stride_um"]["p10"], ref["stride_um"]["p90"]),
        shuffle_mean(nc("spontaneous", "cycle_stride_um_median")), "A clean body wave gives 143.7 µm.", "no")
    period = crawl["spontaneous"]["wave_period_s_median"]
    add("Crawling", "Cycle period", "s", g("cycle_period_s"), period,
        in_range(period, ref["cycle_period_s"]["p10"], ref["cycle_period_s"]["p90"]),
        shuffle_mean(nc("spontaneous", "wave_period_s_median")),
        "Mostly set by the body's proprioceptive recovery loop.", "no")
    wave = round(1.0 / delay, 2)
    add("Crawling", "A1-A6 wave speed", "segments/s", g("a1_a6_wave_speed_segments_s"), wave,
        in_range(wave, ref["a1_a6_wave_speed_segments_s"]["p10"], ref["a1_a6_wave_speed_segments_s"]["p90"]),
        note="Set by the body model's intersegmental delay, not by the brain.")
    add("Crawling", "Resting brain starts forward crawling", "runs of 10",
        {"text": "L1 larvae crawl spontaneously"}, crawl["spontaneous"]["runs_net_forward"],
        "pass" if crawl["spontaneous"]["runs_net_forward"] >= 8 else "fail",
        shuffle_mean(nc("spontaneous", "runs_net_forward")),
        "Shuffles crawl too once their bridge current is reselected on train seeds (6, 10 and 10 of 10).", "no")
    add("Crawling", "Cutting the brain's forward output stops crawling", "runs forward of 10",
        {"text": "control: no brain drive, no crawl"}, crawl["forward_cut"]["runs_net_forward"],
        "pass" if crawl["forward_cut"]["runs_net_forward"] == 0 else "fail")

    add("Reflexes", "Head touch makes the larva back up", "runs of 10",
        {"text": "larvae back up on anterior touch"}, crawl["head_touch"]["backup_after_touch"],
        "pass" if crawl["head_touch"]["backup_after_touch"] >= 5 else "fail",
        note="The v4 MDN response to touch is too weak.")
    stop = crawl["pdm_activation"]["waves_to_A5_in_stop_window_mean"]
    add("Reflexes", "PDM-DN activation stops crawling (5 s window)", "waves per run",
        {"text": "deterministic stop (Tastekin 2018)"}, stop, "pass" if stop == 0 else "fail",
        shuffle_mean(nc("pdm_activation", "waves_to_A5_in_stop_window_mean")),
        f"Without activation: {crawl['spontaneous']['waves_to_A5_in_stop_window_mean']} waves per run. "
        "The SEZ-DN1 relay is in the body, so this tests the bridge, not the brain wiring.", "no")

    add("Odor", "Odor decrease raises PDM-DN", "seeds of 10",
        {"text": "inferred from behaviour (Tastekin 2018)"}, probe["seeds_increase_gt_1hz"],
        "pass" if probe["seeds_increase_gt_1hz"] >= 5 else "fail",
        note="Model ORNs fire only 0.36 Hz at rest, so there is no OFF signal.")
    add("Odor", "Turns toward an odor gradient", "runs of 10",
        {"text": "L1 larvae climb odor gradients"}, nav["toward_odor_runs"],
        "pass" if nav["toward_odor_runs"] >= 8 else "fail", note="v3b brain, not yet rerun with v4.")
    add("Odor", "Head casts", "", {"text": "cast after a stop (Tastekin 2018)"}, None, "not built")

    add("Learning", "Odor-sugar conditioning (paired LI)", "LI",
        {"text": "positive: larvae approach the paired odor"}, cond["paired"]["LI_mean"],
        "pass" if cond["paired"]["LI_mean"] > 0.3 else "fail", shuffle_mean(nl("paired")),
        f"{cond['paired']['LI_positive']}/10 seeds positive. Unpaired control {cond['unpaired']['LI_mean']}. "
        "Learning parameters were reselected on train seeds for every network.", "yes")
    add("Learning", "Fictive punishment memory", "LI", {"text": "negative: avoidance"},
        cond["fictive_punishment"]["LI_mean"], "pass" if cond["fictive_punishment"]["LI_mean"] < -0.3 else "fail",
        shuffle_mean(nl("fictive_punishment")),
        "One shuffle learns attraction to punishment (+0.80), so its memory has no valence.", "yes")
    add("Learning", "Learned preference changes navigation (M4)", "", {"text": "the goal"}, None, "not built")

    report = {
        "model": "joint fit v4 + brain-body bridge (forward 1e-10, MDN 1.5e-10, SEZ-DN1 9e-10), held-out seeds 100-109",
        "l1_reference": "Greaney 2026 held-out animals (p10/median/p90); qualitative rows cite the paper",
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for r in rows:
        print(f"{r['status']:9s} {r['connectome_specific']:10s} {r['metric']:52s} model={r['model']} shuffle={r['shuffle_mean']}({r['shuffle_n']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
