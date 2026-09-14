#!/usr/bin/env python3
"""Export Stage 10 named-fiber attachment steering and lesion evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from oraclarva.axial import default_axial_locomotion_path
from oraclarva.named_fiber_steering import (
    NamedFiberSteeringLarva,
    default_named_fiber_steering_path,
    load_named_fiber_steering_config,
)
from oraclarva.steering import PlanarLinearField, default_axial_steering_path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data/trajectories/l1_named_fiber_steering_v1.json"
FROZEN_AXIAL = ROOT / "data/trajectories/l1_axial_locomotion_v1.json"
FROZEN_STEERING = ROOT / "data/trajectories/l1_axial_steering_v1.json"
ATTACHMENT_SPEC = (
    ROOT / "data/muscles/l1_a1_left_hemisegment_mechanics_v0.json"
)
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
        "attachment_active_force_samples": (
            result.attachment_active_force_samples
        ),
        "attachment_traced_force_samples": (
            result.attachment_traced_force_samples
        ),
        "attachment_force_trace_examples": (
            result.attachment_force_trace_examples
        ),
        "maximum_attachment_net_force_model_units": (
            result.maximum_attachment_net_force_model_units
        ),
        "maximum_abs_attachment_torque_model_units_m": (
            result.maximum_abs_attachment_torque_model_units_m
        ),
        "attachment_torque_impulse_model_units_m_s": (
            result.attachment_torque_impulse_model_units_m_s
        ),
        "active_curvature_constraint_executed": (
            result.active_curvature_constraint_executed
        ),
        "maximum_segment_extension_fraction": (
            result.maximum_segment_extension_fraction
        ),
        "minimum_head_tail_chord_ratio": result.minimum_head_tail_chord_ratio,
        "maximum_local_bend_deg": result.maximum_local_bend_deg,
        "integrated_local_bend_deg_s_by_joint": (
            result.integrated_local_bend_deg_s_by_joint
        ),
        "integrated_planar_bend_deg_s_by_joint": (
            result.integrated_planar_bend_deg_s_by_joint
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
                sum(
                    (left - right) ** 2
                    for left, right in zip(
                        current_node, reference_node, strict=True
                    )
                )
                ** 0.5,
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


def build_artifact() -> dict[str, Any]:
    config_path = default_named_fiber_steering_path()
    axial_config_path = default_axial_locomotion_path()
    steering_config_path = default_axial_steering_path()
    config = load_named_fiber_steering_config(config_path)
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
        larva = NamedFiberSteeringLarva(config)
        result = larva.run(
            PlanarLinearField(baseline, gradient_y_per_m=value),
            duration_s=DURATION_S,
            record_trajectory_interval_s=SAMPLE_INTERVAL_S,
        )
        larvae[name] = larva
        scenarios[name] = result_mapping(result, include_trajectory=True)

    channels = tuple((segment, "right") for segment in ("A1", "A2", "A3"))
    lesion_definitions = {
        "right_sensory": {"lesion_sensory_sides": ("right",)},
        "right_A1_A3_motor": {"lesion_motor_channels": channels},
        "right_A1_A3_attachment": {
            "lesion_attachment_channels": channels
        },
    }
    lesions = {}
    positive_field = PlanarLinearField(baseline, gradient_y_per_m=gradient)
    for name, arguments in lesion_definitions.items():
        result = NamedFiberSteeringLarva(config, **arguments).run(
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

    intact = larvae["positive_y_gradient"]
    geometry_by_id = {
        item.fiber_id: item for item in intact.coupling.geometries
    }
    attachment_pairs = [
        {
            "segment": geometry_by_id[left].segment_id,
            "muscle_number": geometry_by_id[left].muscle_number,
            "spatial_group": geometry_by_id[left].spatial_group,
            "left_fiber_id": left,
            "right_fiber_id": right,
            "coordinate_provenance": geometry_by_id[left].coordinate_provenance,
            "left_derivation": geometry_by_id[left].mirror_or_homology,
            "right_derivation": geometry_by_id[right].mirror_or_homology,
        }
        for left, right in intact.attachment_fiber_pairs
    ]
    return {
        "schema": "oraclarva.named_fiber_steering.v1",
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
            "steering_config": str(steering_config_path.relative_to(ROOT)),
            "steering_config_sha256": sha256(steering_config_path),
            "frozen_steering_trajectory": str(FROZEN_STEERING.relative_to(ROOT)),
            "frozen_steering_trajectory_sha256": sha256(FROZEN_STEERING),
            "attachment_spec": str(ATTACHMENT_SPEC.relative_to(ROOT)),
            "attachment_spec_sha256": sha256(ATTACHMENT_SPEC),
        },
        "duration_s": DURATION_S,
        "sample_interval_s": SAMPLE_INTERVAL_S,
        "action_command": False,
        "behavior_fsm": False,
        "external_policy": False,
        "target_heading_input": False,
        "yaw_input_to_body": False,
        "curvature_input_to_body": False,
        "active_curvature_constraint": False,
        "authored_translation": False,
        "duplicated_motor_neuron_nodes": False,
        "force_unit": "model_unit_not_newton",
        "attachment_coordinate_provenance": "ANATOMY_DERIVED",
        "attachment_mechanics_provenance": "MODEL_FITTED",
        "attachment_fiber_pairs": attachment_pairs,
        "attachment_pair_count": len(attachment_pairs),
        "mapped_fiber_count": len(intact.axial.projection.mappings),
        "uniform_axial_regression": uniform_regression(
            scenarios["uniform"]["trajectory_samples"]
        ),
        "anterior_pivot": config["topology"]["anterior_pivot"],
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
            print(f"generated named-fiber trajectory is stale: {args.output}")
            return 1
        print("generated named-fiber trajectory is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
