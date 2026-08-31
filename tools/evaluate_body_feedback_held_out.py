#!/usr/bin/env python3
"""Fail-closed held-out status for the Stage 5 body-feedback fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from oraclarva.artifacts import first_mismatch


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "data" / "validation" / "greaney_2026_l1_kinematics_v0.json"
TRAJECTORY = ROOT / "data" / "trajectories" / "l1_visual_closed_loop_v0.json"
DEFAULT_OUTPUT = ROOT / "data" / "validation" / "body_feedback_held_out_status_v0.json"


def render_report() -> str:
    targets = json.loads(TARGETS.read_text(encoding="utf-8"))
    trajectory = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    validation = targets["held_out_validation_targets"]
    period = validation["cycle_metrics"]["cycle_period_s"]
    feedback = next(
        item
        for item in trajectory["scenarios"]
        if item["id"] == "zero_light_a1_stretch_feedback"
    )
    minimum_complete_cycles = 3
    minimum_duration_s = minimum_complete_cycles * float(period["p10"])
    available_duration_s = float(trajectory["duration_s"])
    eligible = available_duration_s >= minimum_duration_s
    if eligible:
        raise ValueError(
            "trajectory duration now permits cycle evaluation; implement metric "
            "extraction before changing held-out status"
        )
    report = {
        "schema_version": 1,
        "model_id": "dmel_l1_body_state_sensory_feedback_v0",
        "status": "not_evaluable_no_repeat_crawl_cycles",
        "release_validated": False,
        "target_dataset": targets["dataset_id"],
        "target_schema_version": targets["schema_version"],
        "split": targets["split"],
        "parameter_selection": {
            "used_calibration_animal_values": False,
            "used_held_out_animal_values": False,
            "objective": (
                "zero-input silence, bounded A1 stretch response, complete "
                "body-state/dbd/MN/fiber-force trace, and lesion directionality"
            ),
            "note": (
                "The split is frozen before future fitting. Stage 5 parameters "
                "were not optimized against Greaney kinematics."
            ),
        },
        "eligibility_gate": {
            "minimum_complete_cycles": minimum_complete_cycles,
            "held_out_cycle_period_p10_s": period["p10"],
            "minimum_required_duration_s": round(minimum_duration_s, 6),
            "available_checked_duration_s": available_duration_s,
            "duration_eligible": eligible,
            "natural_repeat_cycles_detected": 0,
            "perturbation_fixture_excluded_from_behavior_score": True,
        },
        "held_out_targets": {
            "segment_length_change": {
                segment: metrics["contraction_amplitude_percent"]
                for segment, metrics in validation["segments"].items()
            },
            "duty_cycle": {
                segment: metrics["duty_cycle_percent"]
                for segment, metrics in validation["segments"].items()
            },
            "stride_um": validation["cycle_metrics"]["stride_um"],
            "wave_speed_segments_s": validation["cycle_metrics"][
                "wave_speed_segments_s"
            ],
        },
        "model_metrics": {
            "segment_length_change": None,
            "duty_cycle": None,
            "stride_um": None,
            "wave_speed_segments_s": None,
        },
        "comparison": {
            "evaluated": False,
            "passed": False,
            "fail_closed_reason": (
                "The 1.5 s diagnostic trajectory is shorter than one held-out "
                "p10 cycle period and contains no eligible natural repeat cycles."
            ),
        },
        "causal_fixture": {
            "scenario_id": feedback["id"],
            "peak_dbd_drive": feedback["summary"]["peak_dbd_drive"],
            "feedback_driven_force_frames": feedback["summary"][
                "feedback_driven_force_frames"
            ],
            "all_feedback_forces_traced": feedback["summary"][
                "all_feedback_forces_traced"
            ],
            "claim": "software causal validation only; not behavioral validation",
        },
    }
    return json.dumps(report, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_report()
    if args.check:
        if not args.output.exists():
            print(f"held-out status is missing: {args.output}")
            return 1
        expected = json.loads(args.output.read_text(encoding="utf-8"))
        actual = json.loads(rendered)
        mismatch = first_mismatch(expected, actual)
        if mismatch:
            print(f"held-out status is stale: {mismatch}")
            return 1
        print("held-out status is current and fail-closed")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
