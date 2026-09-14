"""Export axial-v1-integrated bilateral steering trajectories and lesions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from oraclarva.axial import default_axial_locomotion_path
from oraclarva.steering import (
    AxialSteeringLarva,
    PlanarLinearField,
    default_axial_steering_path,
    load_axial_steering_config,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data/trajectories/l1_axial_steering_v1.json"
FROZEN_AXIAL = ROOT / "data/trajectories/l1_axial_locomotion_v1.json"
DURATION_S = 4.0
SAMPLE_INTERVAL_S = 0.01


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def result_mapping(result, *, include_trajectory: bool) -> dict[str, Any]:
    mapped = {
        "duration_s": result.duration_s,
        "field": dict(result.field),
        "displacement_x_um": result.displacement_x_um,
        "displacement_y_um": result.displacement_y_um,
        "anatomical_forward_displacement_um": (
            result.anatomical_forward_displacement_um
        ),
        "heading_change_deg": result.heading_change_deg,
        "maximum_abs_lateral_um": result.maximum_abs_lateral_um,
        "maximum_abs_field_contrast": result.maximum_abs_field_contrast,
        "field_sample_range": result.field_sample_range,
        "side_peak_activation": result.side_peak_activation,
        "steering_spike_counts": result.steering_spike_counts,
        "steering_first_spike_s": result.steering_first_spike_s,
        "axial_spike_counts": result.axial_spike_counts,
        "contact_retention_range": result.contact_retention_range,
        "all_active_forces_sensory_traced": (
            result.all_active_forces_sensory_traced
        ),
        "steering_active_force_samples": result.steering_active_force_samples,
        "steering_traced_force_samples": result.steering_traced_force_samples,
        "steering_causal_trace_examples": (
            result.steering_causal_trace_examples
        ),
        "maximum_segment_extension_fraction": (
            result.maximum_segment_extension_fraction
        ),
        "minimum_head_tail_chord_ratio": result.minimum_head_tail_chord_ratio,
        "maximum_local_bend_deg": result.maximum_local_bend_deg,
        "integrated_local_bend_deg_s_by_joint": (
            result.integrated_local_bend_deg_s_by_joint
        ),
        "integrated_lateral_slip_um": result.integrated_lateral_slip_um,
        "release_validated": result.release_validated,
    }
    if include_trajectory:
        mapped["trajectory_samples"] = result.trajectory_samples
    return mapped


def uniform_regression(trajectory: tuple[dict[str, Any], ...]) -> dict[str, float]:
    frozen = json.loads(FROZEN_AXIAL.read_text(encoding="utf-8"))
    by_time = {
        frame["time_s"]: frame
        for frame in frozen["forward"]["trajectory_samples"]
        if frame["time_s"] <= DURATION_S
    }
    maximum_node = 0.0
    maximum_contact = 0.0
    maximum_activation = 0.0
    for frame in trajectory:
        reference = by_time[frame["time_s"]]
        for current_node, reference_node in zip(
            frame["nodes_um"], reference["nodes_um"], strict=True
        ):
            maximum_node = max(
                maximum_node,
                sqrt_sum_square(current_node, reference_node),
            )
        maximum_contact = max(
            maximum_contact,
            *(
                abs(float(current) - float(expected))
                for current, expected in zip(
                    frame["contact_retention_by_node"],
                    reference["contact_retention_by_node"],
                    strict=True,
                )
            ),
        )
        for segment, expected in reference["segment_activation"].items():
            maximum_activation = max(
                maximum_activation,
                abs(frame["segment_activation_left"][segment] - expected),
                abs(frame["segment_activation_right"][segment] - expected),
            )
    return {
        "maximum_node_position_error_um": maximum_node,
        "maximum_contact_retention_error": maximum_contact,
        "maximum_segment_activation_error": maximum_activation,
    }


def sqrt_sum_square(left: list[float], right: list[float]) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right, strict=True)) ** 0.5


def build_artifact() -> dict[str, Any]:
    config_path = default_axial_steering_path()
    axial_config_path = default_axial_locomotion_path()
    config = load_axial_steering_config(config_path)
    parameters = config["parameters"]
    baseline = float(parameters["default_field_baseline"])
    gradient = float(parameters["default_lateral_gradient_per_m"])

    scenarios = {}
    larvae = {}
    for name, value in (
        ("uniform", 0.0),
        ("positive_y_gradient", gradient),
        ("negative_y_gradient", -gradient),
    ):
        larva = AxialSteeringLarva(config)
        result = larva.run(
            PlanarLinearField(baseline, gradient_y_per_m=value),
            duration_s=DURATION_S,
            record_trajectory_interval_s=SAMPLE_INTERVAL_S,
        )
        larvae[name] = larva
        scenarios[name] = result_mapping(result, include_trajectory=True)

    lesion_definitions = {
        "right_sensory": {
            "lesion_sensory_sides": ("right",),
        },
        "right_A1_A3_motor": {
            "lesion_motor_channels": (
                ("A1", "right"),
                ("A2", "right"),
                ("A3", "right"),
            ),
        },
        "right_A1_A3_muscle": {
            "lesion_muscle_channels": (
                ("A1", "right"),
                ("A2", "right"),
                ("A3", "right"),
            ),
        },
    }
    lesions = {}
    positive_field = PlanarLinearField(baseline, gradient_y_per_m=gradient)
    for name, arguments in lesion_definitions.items():
        result = AxialSteeringLarva(config, **arguments).run(
            positive_field,
            duration_s=DURATION_S,
            record_trajectory_interval_s=None,
        )
        lesions[name] = {
            "intervention": {
                key: [list(item) if isinstance(item, tuple) else item for item in value]
                for key, value in arguments.items()
            },
            "result": result_mapping(result, include_trajectory=False),
        }

    circuit = larvae["positive_y_gradient"].circuit
    return {
        "schema": "oraclarva.axial_steering.v1",
        "model_id": config["model_id"],
        "status": config["status"],
        "stage": config["stage"],
        "release_validated": False,
        "causal_contract": config["causal_contract"],
        "generated_from": {
            "config": str(config_path.relative_to(ROOT)),
            "config_sha256": sha256(config_path),
            "axial_config": str(axial_config_path.relative_to(ROOT)),
            "axial_config_sha256": sha256(axial_config_path),
            "frozen_axial_trajectory": str(FROZEN_AXIAL.relative_to(ROOT)),
            "frozen_axial_trajectory_sha256": sha256(FROZEN_AXIAL),
        },
        "duration_s": DURATION_S,
        "sample_interval_s": SAMPLE_INTERVAL_S,
        "action_command": False,
        "behavior_fsm": False,
        "external_policy": False,
        "target_heading_input": False,
        "yaw_input_to_body": False,
        "duplicated_motor_neuron_nodes": False,
        "anterior_pivot": config["topology"]["anterior_pivot"],
        "body_segment_ids": [
            item.id for item in larvae["uniform"].body.geometry
        ],
        "mapped_fiber_count": len(larvae["uniform"].axial.projection.mappings),
        "paired_muscle_numbers_by_segment": (
            circuit.paired_muscle_numbers_by_segment
        ),
        "steering_motor_source_count_by_channel": {
            f"{segment}:{side}": len(values)
            for (segment, side), values in circuit.motor_sources_by_channel.items()
        },
        "uniform_axial_regression": uniform_regression(
            scenarios["uniform"]["trajectory_samples"]
        ),
        "scenarios": scenarios,
        "lesions": lesions,
        "limitations": config["topology"]["limitations"],
        "claim_limit": config["validation"]["claim_limit"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = json.dumps(
        build_artifact(), indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            print(f"generated axial-steering trajectory is stale: {args.output}")
            return 1
        print("generated axial-steering trajectory is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
