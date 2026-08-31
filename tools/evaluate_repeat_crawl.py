#!/usr/bin/env python3
"""Evaluate the frozen repeat-crawl artifact against calibration then held-out L1 data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from oraclarva.artifacts import first_mismatch


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "organism" / "l1_repeat_crawl_v0.json"
TARGETS = ROOT / "data" / "validation" / "greaney_2026_l1_kinematics_v0.json"
TRAJECTORY = ROOT / "data" / "trajectories" / "l1_repeat_crawl_v0.json"
CALIBRATION_OUTPUT = (
    ROOT / "data" / "validation" / "repeat_crawl_calibration_v0.json"
)
HELD_OUT_OUTPUT = (
    ROOT / "data" / "validation" / "repeat_crawl_held_out_v0.json"
)
SEGMENTS = ("A1", "A2", "A3", "A4", "A5", "A6")


def comparison(
    metric: str,
    value: float | None,
    band: dict[str, Any],
) -> dict[str, Any]:
    passed = (
        value is not None
        and float(band["p10"]) <= value <= float(band["p90"])
    )
    return {
        "metric": metric,
        "model_value": value,
        "target_p10": band["p10"],
        "target_median": band["median"],
        "target_p90": band["p90"],
        "passed": passed,
    }


def evaluate_partition(
    model: dict[str, Any],
    target: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = [
        comparison(
            "cycle_period_s",
            model["period_s"],
            target["cycle_metrics"]["cycle_period_s"],
        ),
        comparison(
            "stride_um",
            model["stride_um"],
            target["cycle_metrics"]["stride_um"],
        ),
        comparison(
            "a1_a6_wave_speed_segments_s",
            model["a1_a6_wave_speed_segments_s"],
            target["cycle_metrics"]["a1_a6_wave_speed_segments_s"],
        ),
    ]
    for segment in SEGMENTS:
        segment_model = model["segments"].get(segment)
        rows.append(
            comparison(
                f"{segment}.contraction_amplitude_percent",
                (
                    None
                    if segment_model is None
                    else segment_model["length_change_percent"]
                ),
                target["segments"][segment][
                    "contraction_amplitude_percent"
                ],
            )
        )
        rows.append(
            comparison(
                f"{segment}.duty_cycle_percent",
                (
                    None
                    if segment_model is None
                    else segment_model["duty_cycle_percent"]
                ),
                target["segments"][segment]["duty_cycle_percent"],
            )
        )
    return rows


def reports() -> tuple[dict[str, Any], dict[str, Any]]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    targets = json.loads(TARGETS.read_text(encoding="utf-8"))
    trajectory = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    config_sha256 = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    generated = trajectory["generated_from"]
    if (
        generated["config_sha256"] != config_sha256
        or generated["parameter_fit_status"]
        != "frozen_before_single_held_out_evaluation"
        or generated["selection_used_held_out_values"] is not False
        or config["calibration"]["selection_used_held_out_values"] is not False
    ):
        raise ValueError("repeat-crawl parameters were not frozen before evaluation")
    cycle = trajectory["result_summary"]["cycle_metrics"]
    if cycle["complete_cycle_count"] < 3 or cycle["median"] is None:
        raise ValueError("at least three complete repeat-crawl cycles are required")
    model = cycle["median"]
    calibration_rows = evaluate_partition(
        model, targets["calibration_targets"]
    )
    held_out_rows = evaluate_partition(
        model, targets["held_out_validation_targets"]
    )
    calibration_passed = all(item["passed"] for item in calibration_rows)
    held_out_passed = all(item["passed"] for item in held_out_rows)
    common = {
        "schema_version": 1,
        "model_id": config["model_id"],
        "release_validated": False,
        "target_dataset": targets["dataset_id"],
        "target_schema_version": targets["schema_version"],
        "frozen_config_sha256": config_sha256,
        "trajectory": str(TRAJECTORY.relative_to(ROOT)),
        "complete_cycle_count": cycle["complete_cycle_count"],
        "physical_wave_cycle_count": cycle["physical_wave_cycle_count"],
        "model_metrics": model,
    }
    calibration_report = {
        **common,
        "partition": "calibration",
        "animal_count": targets["split"]["calibration_animal_count"],
        "status": (
            "calibration_passed" if calibration_passed else "calibration_failed"
        ),
        "comparisons": calibration_rows,
        "passed": calibration_passed,
        "interpretation": (
            "The fitted repeat path matches cycle timing/stride targets but "
            "does not reproduce L1 segment contraction amplitude or duty."
        ),
    }
    held_out_report = {
        **common,
        "partition": "held_out_validation",
        "animal_count": targets["split"]["validation_animal_count"],
        "status": (
            "held_out_passed" if held_out_passed else "held_out_failed"
        ),
        "evaluation_protocol": {
            "evaluation_count": 1,
            "evaluated_on": "2026-08-31",
            "parameters_changed_after_evaluation": False,
            "selection_used_held_out_values": False,
            "note": (
                "Held-out values were already present in the repository, but "
                "the frozen candidate selection used calibration values only."
            ),
        },
        "comparisons": held_out_rows,
        "passed": held_out_passed,
        "fail_closed": not held_out_passed,
        "interpretation": (
            "This frozen research approximation is not behaviorally validated; "
            "failed rows remain explicit and block a release claim."
        ),
    }
    return calibration_report, held_out_report


def rendered_reports() -> tuple[str, str]:
    calibration, held_out = reports()
    return (
        json.dumps(calibration, indent=2, ensure_ascii=False) + "\n",
        json.dumps(held_out, indent=2, ensure_ascii=False) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    calibration, held_out = rendered_reports()
    outputs = (
        (CALIBRATION_OUTPUT, calibration),
        (HELD_OUT_OUTPUT, held_out),
    )
    if args.check:
        for path, rendered in outputs:
            if not path.exists():
                print(f"repeat-crawl evaluation is missing: {path}")
                return 1
            mismatch = first_mismatch(
                json.loads(path.read_text(encoding="utf-8")),
                json.loads(rendered),
            )
            if mismatch:
                print(f"repeat-crawl evaluation is stale: {path}: {mismatch}")
                return 1
        print("repeat-crawl calibration and single held-out evaluation are current")
        return 0
    for path, rendered in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
