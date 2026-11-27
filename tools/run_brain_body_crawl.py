#!/usr/bin/env python3
"""Brain-driven crawling: fitted L1EM brain -> descending groups -> axial VNC/body.

Bridges (``oraclarva.brain_body``):
- L1EM MDNs -> ``descending:MDN`` (backward);
- L1EM neurons descending to A8/A9 -> ``premotor:A27h:A6`` (forward start).

Conditions per sign seed:
- spontaneous: brain with spontaneous input only, no touch;
- head_touch: Poisson input to the head-touch sensory set (class II/III
  pathway) for ``--touch-s`` seconds at t = ``--touch-at``; the axial model's
  own anterior-touch path is not used, so backing up must come through the
  brain;
- forward_cut: spontaneous, with the forward bridge removed;
- all_cut: spontaneous, both bridges removed;
- odor_constant / odor_drop: appetitive ORNs on both sides driven through
  ``OrnTransducer`` at concentration 1 from t = 0; in odor_drop it falls to 0
  at ``--drop-at``. With ``--sez-current-a`` > 0, brain PDM-DN spikes drive the
  reduced SEZ-DN1 relay, which inhibits posterior A27h (Tastekin 2018). The
  stop readout is the number of forward waves reaching A5 (propagated starts)
  in the ``--stop-window-s`` after the drop;
- pdm_activation: Poisson input to the two brain PDM-DNs at ``--pdm-hz`` for
  ``--pdm-s`` from ``--drop-at`` (the analogue of CsChrimson activation in
  Tastekin 2018, which "induces deterministic stops"); same stop readout.

Readout: displacement, forward/backward wave counts, crawl speed and wave
period, compared with Greaney 2026 L1 kinematics. Outputs go to git-ignored
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

from oraclarva.axial import AxialLocomotionLarva, load_axial_locomotion_config  # noqa: E402
from oraclarva.brain_body import BrainContext, BrainSpikeSource, OrnTransducer, Stimulus  # noqa: E402

LOCAL = ROOT / "data" / "local" / "l1em_public_connectome"
GREANEY = ROOT / "data" / "validation" / "greaney_2026_l1_kinematics_v0.json"
_C: dict = {}


def _setup(fit_path, bg_hz, bg_mv):
    _C["ctx"] = BrainContext.load(fit_path, bg_hz, bg_mv)


def cycle_metrics(result):
    """Per-cycle kinematics comparable to Greaney 2026, which averages over
    crawl cycles rather than over a fixed time window. Progress of the body
    centroid along the initial head direction between successive forward-wave
    arrivals at A1 (one crawl cycle each)."""
    ends = np.array(result.premotor_spike_times_s.get("forward", {}).get("A1", []))
    samples = result.trajectory_samples
    if ends.size < 2 or len(samples) < 2:
        return {"cycle_stride_um": None, "cycle_speed_um_s": None, "cycles": 0}
    t = np.array([x["time_s"] for x in samples])
    nodes0 = np.array(samples[0]["nodes_um"])
    head = nodes0[0] - nodes0[-1]
    head /= np.linalg.norm(head)
    c0 = nodes0.mean(axis=0)
    progress = np.array([(np.array(x["nodes_um"]).mean(axis=0) - c0) @ head for x in samples])
    at = lambda time: float(np.interp(time, t, progress))  # noqa: E731
    strides = np.array([at(b) - at(a) for a, b in zip(ends[:-1], ends[1:])])
    periods = np.diff(ends)
    return {
        "cycle_stride_um": round(float(np.median(strides)), 1),
        "cycle_speed_um_s": round(float(np.median(strides / periods)), 2),
        "cycles": int(strides.size),
    }


def wave_metrics(result, duration_s):
    starts = np.array(result.premotor_spike_times_s.get("forward", {}).get("A6", []))
    ends = np.array(result.premotor_spike_times_s.get("forward", {}).get("A1", []))
    back = np.array(result.premotor_spike_times_s.get("backward", {}).get("A1", []))
    period = float(np.median(np.diff(ends))) if ends.size >= 2 else None
    return {
        "forward_wave_starts": int(starts.size),
        "forward_waves_completed": int(ends.size),
        "backward_waves": int(back.size),
        "wave_period_s": None if period is None else round(period, 3),
        "crawl_speed_um_s": round(result.anatomical_forward_displacement_um / duration_s, 2),
    }


def run_one(job):
    seed, condition, args = job
    ctx = _C["ctx"]
    bridges = {"descending:MDN": "MDN", "premotor:A27h:A6": "dVNC_to_A8_A9"}
    if condition in ("forward_cut",):
        bridges.pop("premotor:A27h:A6")
    if condition == "all_cut":
        bridges = {}
    if args.get("sez_current_a", 0.0) > 0.0:
        bridges["descending:SEZ-DN1"] = "PDM-DN"
    schedule = []
    brain = ctx.stepper(seed)
    dynamic = None
    if condition in ("odor_constant", "odor_drop"):
        orns = np.concatenate([ctx.state["odor_left"], ctx.state["odor_right"]])
        orn = OrnTransducer(brain, orns, gain_hz=args["odor_hz"], seed=seed)
        orn.reset(1.0)  # already adapted to the odor at t = 0
        drop = args["drop_at"] if condition == "odor_drop" else float("inf")
        dynamic = lambda t: orn(1.0 if t < drop else 0.0, 1e-3)  # noqa: E731
    if condition == "pdm_activation":
        schedule.append(Stimulus(ctx.groups["PDM-DN"], args["pdm_hz"], args["drop_at"], args["drop_at"] + args["pdm_s"]))
    if condition == "head_touch":
        schedule.append(
            Stimulus(ctx.groups["touch_II_III"], args["touch_hz"], args["touch_at"], args["touch_at"] + args["touch_s"])
        )
    source = BrainSpikeSource(
        brain, ctx.groups, bridges, schedule, dynamic_rates=dynamic, record=("MDN", "dVNC_to_A8_A9", "PDM-DN")
    )
    config = load_axial_locomotion_config()
    config["parameters"]["brain_bridge_current_a_by_node"] = {
        "descending:MDN": args["mdn_current_a"],
        "premotor:A27h:A6": args["forward_current_a"],
    }
    if args.get("gvli_current_a", 0.0) > 0.0:
        config["parameters"]["gvli_inhibitory_current_a"] = args["gvli_current_a"]
        config["parameters"]["gvli_gate_tau_s"] = args["gvli_tau_s"]
    if args.get("sez_current_a", 0.0) > 0.0:
        config["parameters"]["sez_dn1_inhibitory_current_a"] = args["sez_inhibition_a"]
        config["parameters"]["brain_bridge_current_a_by_node"]["descending:SEZ-DN1"] = args["sez_current_a"]
    larva = AxialLocomotionLarva(config)
    result = larva.run(duration_s=args["duration_s"], record_trajectory_interval_s=0.05, descending_spike_source=source)
    row = {
        "seed": seed,
        "condition": condition,
        "forward_displacement_um": round(result.anatomical_forward_displacement_um, 2),
        "brain_mdn_spikes": source.counts["MDN"],
        "brain_forward_dn_spikes": source.counts["dVNC_to_A8_A9"],
        "axial_mdn_spikes": int(result.spike_counts.get("descending:MDN", 0)),
        "untraced_active_force_frames": int(result.untraced_active_force_frames),
        **wave_metrics(result, args["duration_s"]),
        **cycle_metrics(result),
    }
    if condition in ("odor_constant", "odor_drop", "pdm_activation", "spontaneous"):
        t0, t1 = args["drop_at"], args["drop_at"] + args["stop_window_s"]
        a5 = np.array(result.premotor_spike_times_s.get("forward", {}).get("A5", []))
        per_ms = np.asarray(source.per_ms["PDM-DN"], dtype=float)
        n_pdm = len(ctx.groups["PDM-DN"])
        row["waves_to_A5_in_stop_window"] = int(((a5 >= t0) & (a5 < t1)).sum())
        row["pdm_rate_before_hz"] = round(float(per_ms[int((t0 - 2) * 1000) : int(t0 * 1000)].sum() / 2 / n_pdm), 2)
        row["pdm_rate_after_hz"] = round(float(per_ms[int(t0 * 1000) : int((t0 + 2) * 1000)].sum() / 2 / n_pdm), 2)
        row["axial_sez_dn1_spikes"] = int(result.spike_counts.get("descending:SEZ-DN1", 0))
    if condition == "head_touch":
        t0, t1 = args["touch_at"], args["touch_at"] + 3.0
        back = np.array(result.premotor_spike_times_s.get("backward", {}).get("A1", []))
        row["backward_wave_within_3s_of_touch"] = bool(((back >= t0) & (back < t1)).any())
    return row


def summarize(rows, conditions):
    out = {}
    for c in conditions:
        sel = [r for r in rows if r["condition"] == c]
        if not sel:
            continue
        get = lambda k: np.array([r[k] for r in sel if r.get(k) is not None], dtype=float)  # noqa: E731
        out[c] = {
            "n": len(sel),
            "displacement_um_mean": round(float(get("forward_displacement_um").mean()), 1),
            "crawl_speed_um_s_median": round(float(np.median(get("crawl_speed_um_s"))), 2),
            "cycle_speed_um_s_median": round(float(np.median(get("cycle_speed_um_s"))), 2) if get("cycle_speed_um_s").size else None,
            "cycle_stride_um_median": round(float(np.median(get("cycle_stride_um"))), 1) if get("cycle_stride_um").size else None,
            "wave_period_s_median": round(float(np.median(get("wave_period_s"))), 2) if get("wave_period_s").size else None,
            "forward_waves_mean": round(float(get("forward_waves_completed").mean()), 1),
            "backward_waves_mean": round(float(get("backward_waves").mean()), 1),
            "runs_net_forward": int((get("forward_displacement_um") > 20).sum()),
            "runs_net_backward": int((get("forward_displacement_um") < -20).sum()),
            "untraced_frames_max": int(get("untraced_active_force_frames").max()),
        }
        if c in ("odor_constant", "odor_drop", "pdm_activation", "spontaneous"):
            out[c]["waves_to_A5_in_stop_window_mean"] = round(float(get("waves_to_A5_in_stop_window").mean()), 2)
            out[c]["pdm_after_minus_before_hz_median"] = round(
                float(np.median(get("pdm_rate_after_hz") - get("pdm_rate_before_hz"))), 2
            )
        if c == "head_touch":
            out[c]["backup_after_touch"] = int(sum(r["backward_wave_within_3s_of_touch"] for r in sel))
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fit", default=str(LOCAL / "runs" / "celltype_motor_fit_v3.json"))
    parser.add_argument("--seeds", type=int, nargs="+", default=[100, 101, 102, 103, 104])
    parser.add_argument("--conditions", nargs="+", default=["spontaneous", "head_touch", "forward_cut", "all_cut"])
    parser.add_argument("--duration-s", type=float, default=30.0)
    parser.add_argument("--forward-current-a", type=float, default=6e-10)
    parser.add_argument("--mdn-current-a", type=float, default=2e-10)
    parser.add_argument("--gvli-current-a", type=float, default=0.0, help="GVLI -> MN inhibition (0 = no GVLI)")
    parser.add_argument("--gvli-tau-s", type=float, default=3.0, help="GVLI gate decay (fitted, not measured)")
    parser.add_argument("--sez-current-a", type=float, default=0.0, help="PDM-DN spike -> SEZ-DN1 relay current (0 = no relay)")
    parser.add_argument("--sez-inhibition-a", type=float, default=4e-9, help="SEZ-DN1 -> posterior A27h inhibition")
    parser.add_argument("--pdm-hz", type=float, default=100.0)
    parser.add_argument("--pdm-s", type=float, default=5.0)
    parser.add_argument("--odor-hz", type=float, default=150.0)
    parser.add_argument("--drop-at", type=float, default=15.0)
    parser.add_argument("--stop-window-s", type=float, default=5.0)
    parser.add_argument("--touch-at", type=float, default=15.0)
    parser.add_argument("--touch-s", type=float, default=0.5)
    parser.add_argument("--touch-hz", type=float, default=150.0)
    parser.add_argument("--bg-hz", type=float, default=100.0)
    parser.add_argument("--bg-mv", type=float, default=6.0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", type=Path, default=LOCAL / "runs" / "brain_body_crawl_v0.json")
    args = parser.parse_args(argv)
    params = {
        "duration_s": args.duration_s,
        "forward_current_a": args.forward_current_a,
        "mdn_current_a": args.mdn_current_a,
        "touch_at": args.touch_at,
        "touch_s": args.touch_s,
        "touch_hz": args.touch_hz,
        "gvli_current_a": args.gvli_current_a,
        "gvli_tau_s": args.gvli_tau_s,
        "sez_current_a": args.sez_current_a,
        "sez_inhibition_a": args.sez_inhibition_a,
        "odor_hz": args.odor_hz,
        "pdm_hz": args.pdm_hz,
        "pdm_s": args.pdm_s,
        "drop_at": args.drop_at,
        "stop_window_s": args.stop_window_s,
    }
    jobs = [(seed, c, params) for c in args.conditions for seed in args.seeds]
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_setup, initargs=(args.fit, args.bg_hz, args.bg_mv)) as pool:
        rows = list(pool.map(run_one, jobs))
    greaney = json.loads(GREANEY.read_text(encoding="utf-8"))["held_out_validation_targets"]["cycle_metrics"]
    report = {
        "fit": args.fit,
        "parameters": params,
        "l1_reference_held_out": {k: greaney[k] for k in ("crawl_speed_um_s", "cycle_period_s")},
        "summary": summarize(rows, args.conditions),
        "runs": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
