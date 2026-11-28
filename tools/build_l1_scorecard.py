#!/usr/bin/env python3
"""Build the L1 north-star scorecard from local run outputs.

One row per behaviour, with:
- the L1 reference: Greaney 2026 held-out animals (p10 / median / p90), or a
  qualitative published finding;
- the current model: the intact network of a shuffle-control run
  (tools/run_shuffle_control.py, default tag joint_v6_touch) plus the
  brain-body bridge, on held-out sign seeds 100-109;
- the block-shuffled connectomes from the same run (mean over shuffles);
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
    parser.add_argument("--control", default="joint_v6_touch", help="tag of a run_shuffle_control.py run")
    parser.add_argument("--shuffles", nargs="+", default=["1", "2", "3"])
    args = parser.parse_args(argv)
    ctl = RUNS / "control" / args.control

    ref = load(GREANEY)["held_out_validation_targets"]["cycle_metrics"]
    crawl = dict(load(ctl / "crawl_intact.json")["summary"])
    crawl.update(load(ctl / "crawl_intact_reflex.json")["summary"])  # head_touch, forward_cut
    cycles = crawl["spontaneous"]
    cond = load(ctl / "cond_intact.json")["summary"]
    fits = {n: load(ctl / f"fit_{n}.json") for n in ["intact", *args.shuffles]}
    probe = load(ctl / "probe_intact.json")["summary"]["PDM-DN"]
    nav = load(ctl / "nav_intact.json")["mirror_pairs"]
    delay = load(AXIAL)["parameters"]["intersegmental_delay_s"]

    # Learning parameters and the forward bridge current were reselected per
    # network on train seeds 0-3 by run_shuffle_control.py.
    null_crawl = [load(ctl / f"crawl_{k}.json") for k in args.shuffles]
    null_cond = [load(ctl / f"cond_{k}.json") for k in args.shuffles]
    null_probe = [d["summary"]["PDM-DN"]["seeds_increase_gt_1hz"] if d else None for d in (load(ctl / f"probe_{k}.json") for k in args.shuffles)]
    null_nav = [d["mirror_pairs"]["toward_odor_runs"] if d else None for d in (load(ctl / f"nav_{k}.json") for k in args.shuffles)]
    nc = lambda cond_, key: [d["summary"][cond_].get(key) for d in null_crawl if d and cond_ in d["summary"]]  # noqa: E731
    nl = lambda cond_: [d["summary"][cond_]["LI_mean"] for d in null_cond if d]  # noqa: E731

    def ipsilateral_seeds(fit):
        # Zimmerman 2026: KC odor responses are almost entirely ipsilateral.
        runs = fit["held_out_right_odor_new_seeds"]["runs"]
        return sum(r["kc_contra_fraction"] <= 0.2 * r["kc_ipsi_fraction"] for r in runs)

    def specific(intact_ok, values, ok):
        tested = [v for v in values if v is not None]
        if not tested:
            return "not tested"
        return "yes" if intact_ok and not any(ok(v) for v in tested) else "no"

    def rng_specific(value, key, null_values):
        ok = lambda v: in_range(v, ref[key]["p10"], ref[key]["p90"]) == "pass"  # noqa: E731
        return specific(ok(value), null_values, ok)

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
        "GVLI inhibition gates extra brain A6 spikes. The clean-body ceiling is 26.8 µm/s.",
        rng_specific(speed, "crawl_speed_um_s", nc("spontaneous", "cycle_speed_um_s_median")))
    stride = cycles["cycle_stride_um_median"]
    add("Crawling", "Stride per cycle", "µm", g("stride_um"), stride,
        in_range(stride, ref["stride_um"]["p10"], ref["stride_um"]["p90"]),
        shuffle_mean(nc("spontaneous", "cycle_stride_um_median")), "A clean body wave gives 143.7 µm.",
        rng_specific(stride, "stride_um", nc("spontaneous", "cycle_stride_um_median")))
    period = crawl["spontaneous"]["wave_period_s_median"]
    add("Crawling", "Cycle period", "s", g("cycle_period_s"), period,
        in_range(period, ref["cycle_period_s"]["p10"], ref["cycle_period_s"]["p90"]),
        shuffle_mean(nc("spontaneous", "wave_period_s_median")),
        "Set by the body's proprioceptive recovery loop. Shortening it breaks the calibration.",
        rng_specific(period, "cycle_period_s", nc("spontaneous", "wave_period_s_median")))
    wave = round(1.0 / delay, 2)
    add("Crawling", "A1-A6 wave speed", "segments/s", g("a1_a6_wave_speed_segments_s"), wave,
        in_range(wave, ref["a1_a6_wave_speed_segments_s"]["p10"], ref["a1_a6_wave_speed_segments_s"]["p90"]),
        note="Set by the body model's intersegmental delay, not by the brain.")
    add("Crawling", "Resting brain starts forward crawling", "runs of 10",
        {"text": "L1 larvae crawl spontaneously"}, crawl["spontaneous"]["runs_net_forward"],
        "pass" if crawl["spontaneous"]["runs_net_forward"] >= 8 else "fail",
        shuffle_mean(nc("spontaneous", "runs_net_forward")),
        "Shuffles crawl too once their bridge current is reselected on train seeds.",
        specific(crawl["spontaneous"]["runs_net_forward"] >= 8, nc("spontaneous", "runs_net_forward"), lambda v: v >= 8))
    add("Crawling", "Cutting the brain's forward output stops crawling", "runs forward of 10",
        {"text": "control: no brain drive, no crawl"}, crawl["forward_cut"]["runs_net_forward"],
        "pass" if crawl["forward_cut"]["runs_net_forward"] == 0 else "fail")

    add("Reflexes", "Head touch makes the larva back up", "runs of 10",
        {"text": "larvae back up on anterior touch"}, crawl["head_touch"]["backup_after_touch"],
        "pass" if crawl["head_touch"]["backup_after_touch"] >= 5 else "fail",
        note="Touch->MDN is about 2-4 Hz against 15 Hz. In larvae gentle touch acts through body-wall C3da neurons "
        "and the nerve cord (Omamiuda-Ishikawa 2020), which the brain volume barely contains.")
    stop = crawl["pdm_activation"]["waves_to_A5_in_stop_window_mean"]
    add("Reflexes", "PDM-DN activation stops crawling (5 s window)", "waves per run",
        {"text": "deterministic stop (Tastekin 2018)"}, stop, "pass" if stop == 0 else "fail",
        shuffle_mean(nc("pdm_activation", "waves_to_A5_in_stop_window_mean")),
        f"Without activation: {crawl['spontaneous']['waves_to_A5_in_stop_window_mean']} waves per run. "
        "The SEZ-DN1 relay is in the body, so this tests the bridge, not the brain wiring.",
        specific(stop == 0, nc("pdm_activation", "waves_to_A5_in_stop_window_mean"), lambda v: v == 0))

    lat = ipsilateral_seeds(fits["intact"])
    lat_null = [ipsilateral_seeds(f) if f else None for f in (fits[k] for k in args.shuffles)]
    add("Odor", "Mushroom-body odor responses stay ipsilateral", "seeds of 10",
        {"text": "almost entirely ipsilateral (Zimmerman 2026)"}, lat, "pass" if lat >= 8 else "fail",
        shuffle_mean(lat_null), "KC contralateral fraction at most 0.2 x ipsilateral, held-out fit seeds.",
        specific(lat >= 8, lat_null, lambda v: v >= 8))
    add("Odor", "Odor decrease raises PDM-DN", "seeds of 10",
        {"text": "inferred from behaviour (Tastekin 2018)"}, probe["seeds_increase_gt_1hz"],
        "pass" if probe["seeds_increase_gt_1hz"] >= 5 else "fail", shuffle_mean(null_probe),
        "Model ORNs fire only 0.36 Hz at rest, so there is no OFF signal.",
        specific(probe["seeds_increase_gt_1hz"] >= 5, null_probe, lambda v: v >= 5))
    add("Odor", "Turns toward an odor gradient", "runs of 10",
        {"text": "L1 larvae climb odor gradients"}, nav["toward_odor_runs"],
        "pass" if nav["toward_odor_runs"] >= 8 else "fail", shuffle_mean(null_nav),
        f"Mirror-pair test, Wilcoxon p = {nav['wilcoxon_p']}. Steering current reselected on train seeds for every network.",
        specific(nav["toward_odor_runs"] >= 8, null_nav, lambda v: v >= 8))
    add("Odor", "Head casts", "", {"text": "cast after a stop (Tastekin 2018)"}, None, "not built")

    add("Learning", "Odor-sugar conditioning (paired LI)", "LI",
        {"text": "positive: larvae approach the paired odor"}, cond["paired"]["LI_mean"],
        "pass" if cond["paired"]["LI_mean"] > 0.3 else "fail", shuffle_mean(nl("paired")),
        f"{cond['paired']['LI_positive']}/10 seeds positive. Unpaired control {cond['unpaired']['LI_mean']}. "
        "Learning parameters were reselected on train seeds for every network.",
        specific(cond["paired"]["LI_mean"] > 0.3, nl("paired"), lambda v: v > 0.3))
    add("Learning", "Fictive punishment memory", "LI", {"text": "negative: avoidance"},
        cond["fictive_punishment"]["LI_mean"], "pass" if cond["fictive_punishment"]["LI_mean"] < -0.3 else "fail",
        shuffle_mean(nl("fictive_punishment")),
        "A shuffle that learns attraction to punishment has a memory without valence.",
        specific(cond["fictive_punishment"]["LI_mean"] < -0.3, nl("fictive_punishment"), lambda v: v < -0.3))
    add("Learning", "Learned preference changes navigation (M4)", "", {"text": "the goal"}, None, "not built")

    report = {
        "model": f"intact network of shuffle-control run {args.control} + brain-body bridge {load(ctl / 'crawl_intact.json')['parameters']}, held-out seeds 100-109",
        "shuffles_run": [k for k, d in zip(args.shuffles, null_crawl) if d],
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
