#!/usr/bin/env python3
"""Evaluate Stage 10 mechanics, causality, symmetry, and lesion gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from oraclarva.named_fiber_steering import (
    default_named_fiber_steering_path,
    load_named_fiber_steering_config,
)


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY = ROOT / "data/trajectories/l1_named_fiber_steering_v1.json"
DEFAULT_OUTPUT = ROOT / "data/validation/named_fiber_steering_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordered_trace(trace: dict[str, Any]) -> bool:
    return bool(
        trace["body_state_time_s"]
        <= trace["sensor_spike_time_s"]
        < trace["premotor_spike_time_s"]
        < trace["motor_spike_time_s"]
    )


def build_evaluation() -> dict[str, Any]:
    config_path = default_named_fiber_steering_path()
    config = load_named_fiber_steering_config(config_path)
    artifact = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    generated = artifact["generated_from"]
    source_hash_gates = {
        "config": generated["config_sha256"] == sha256(config_path),
    }
    for name in (
        "axial_config",
        "frozen_axial_trajectory",
        "steering_config",
        "frozen_steering_trajectory",
        "attachment_spec",
    ):
        path = ROOT / generated[name]
        source_hash_gates[name] = generated[f"{name}_sha256"] == sha256(path)
    if not all(source_hash_gates.values()):
        raise RuntimeError("named-fiber steering source hash is stale")

    scenarios = artifact["scenarios"]
    uniform = scenarios["uniform"]
    positive = scenarios["positive_y_gradient"]
    negative = scenarios["negative_y_gradient"]
    lesions = {
        name: item["result"] for name, item in artifact["lesions"].items()
    }
    gates = config["validation"]["gates"]
    regression = artifact["uniform_axial_regression"]

    comparisons = {
        "positive_gradient_heading": positive["heading_change_deg"]
        >= gates["minimum_abs_heading_change_deg"],
        "negative_gradient_heading": negative["heading_change_deg"]
        <= -gates["minimum_abs_heading_change_deg"],
        "mirror_heading": abs(
            positive["heading_change_deg"] + negative["heading_change_deg"]
        ) <= gates["mirror_heading_tolerance_deg"],
        "mirror_axial_position": abs(
            positive["displacement_x_um"] - negative["displacement_x_um"]
        ) <= gates["mirror_position_tolerance_um"],
        "mirror_lateral_position": abs(
            positive["displacement_y_um"] + negative["displacement_y_um"]
        ) <= gates["mirror_position_tolerance_um"],
        "uniform_heading": abs(uniform["heading_change_deg"])
        <= gates["straight_heading_tolerance_deg"],
        "uniform_node_trajectory": regression["maximum_node_position_error_um"]
        <= gates["straight_trajectory_tolerance_um"],
        "uniform_contact_trajectory": regression[
            "maximum_contact_retention_error"
        ] <= 1e-9,
        "uniform_activation_trajectory": regression[
            "maximum_segment_activation_error"
        ] <= 1e-9,
        "positive_forward_progress": positive[
            "anatomical_forward_displacement_um"
        ] >= gates["minimum_anatomical_forward_displacement_um"],
        "negative_forward_progress": negative[
            "anatomical_forward_displacement_um"
        ] >= gates["minimum_anatomical_forward_displacement_um"],
    }

    causal_gates = {}
    force_gates = {}
    for name, scenario in (("positive", positive), ("negative", negative)):
        traces = scenario["attachment_force_trace_examples"]
        causal_gates[f"{name}_attachment_forces_exist"] = (
            scenario["attachment_active_force_samples"] > 0
        )
        causal_gates[f"{name}_all_attachment_forces_traced"] = (
            scenario["attachment_active_force_samples"]
            == scenario["attachment_traced_force_samples"]
            and scenario["all_active_forces_sensory_traced"] is True
        )
        causal_gates[f"{name}_all_17_fiber_pairs_witnessed"] = (
            len(traces) == artifact["attachment_pair_count"]
            and all(ordered_trace(trace) for trace in traces.values())
        )
        force_gates[f"{name}_equal_opposite_net_force"] = scenario[
            "maximum_attachment_net_force_model_units"
        ] <= gates["maximum_attachment_net_force_model_units"]
        force_gates[f"{name}_attachment_moment_exists"] = abs(
            scenario["attachment_torque_impulse_model_units_m_s"]
        ) >= gates["minimum_abs_attachment_torque_impulse_model_units_m_s"]
    force_gates["mirrored_attachment_moment"] = abs(
        positive["attachment_torque_impulse_model_units_m_s"]
        + negative["attachment_torque_impulse_model_units_m_s"]
    ) <= gates[
        "mirror_attachment_torque_impulse_tolerance_model_units_m_s"
    ]
    force_gates["uniform_has_no_attachment_excess"] = (
        uniform["attachment_active_force_samples"] == 0
        and uniform["maximum_attachment_net_force_model_units"] == 0.0
        and uniform["attachment_torque_impulse_model_units_m_s"] == 0.0
    )

    shape_gates = {}
    for name, scenario in (("positive", positive), ("negative", negative)):
        shape_gates[f"{name}_segment_extension"] = scenario[
            "maximum_segment_extension_fraction"
        ] <= gates["maximum_segment_extension_fraction"]
        shape_gates[f"{name}_head_tail_chord"] = scenario[
            "minimum_head_tail_chord_ratio"
        ] >= gates["minimum_head_tail_chord_ratio"]
        shape_gates[f"{name}_local_bend"] = scenario[
            "maximum_local_bend_deg"
        ] <= gates["maximum_local_bend_deg"]
        shape_gates[f"{name}_integrated_lateral_slip"] = scenario[
            "integrated_lateral_slip_um"
        ] <= gates["maximum_integrated_lateral_slip_um"]

    pivot = artifact["anterior_pivot"]
    maps = {
        name: scenario["integrated_planar_bend_deg_s_by_joint"]
        for name, scenario in (
            ("uniform", uniform),
            ("positive", positive),
            ("negative", negative),
        )
    }
    if len({frozenset(values) for values in maps.values()}) != 1:
        raise RuntimeError("named-fiber planar-bend labels differ by scenario")
    excess = {
        joint: max(
            0.0,
            0.5 * (maps["positive"][joint] + maps["negative"][joint])
            - maps["uniform"][joint],
        )
        for joint in maps["uniform"]
    }
    total = sum(excess.values())
    if total <= 0.0:
        raise RuntimeError("named-fiber artifact lacks planar deformation")
    pivot_joints = tuple(pivot["mechanical_joint_support"])
    pivot_total = sum(excess[joint] for joint in pivot_joints)
    peak = max(excess[joint] for joint in pivot_joints)
    active = [
        joint
        for joint in pivot_joints
        if excess[joint] >= gates["bend_activity_relative_threshold"] * peak
    ]
    dominant = max(pivot_joints, key=excess.__getitem__)
    outside_fraction = (total - pivot_total) / total
    adjacent_jump = max(
        abs(excess[left] - excess[right])
        for left, right in zip(pivot_joints[:-1], pivot_joints[1:], strict=True)
    ) / peak
    mirror_error = max(
        abs(maps["positive"][joint] - maps["negative"][joint])
        for joint in maps["uniform"]
    )
    bend_distribution_gates = {
        "all_four_pivot_joints_active": len(active)
        >= gates["minimum_active_pivot_joint_count"],
        "dominant_joint_is_T3_A1": dominant == "T3-A1",
        "no_single_joint_hinge": peak / pivot_total
        <= gates["maximum_single_joint_bend_fraction"],
        "passive_propagation_is_bounded": outside_fraction
        <= gates["maximum_outside_pivot_bend_fraction"],
        "adjacent_pivot_bend_is_bounded": adjacent_jump
        <= gates["maximum_adjacent_pivot_bend_jump_fraction"],
        "mirrored_planar_bend_distribution": mirror_error
        <= gates["maximum_mirror_integrated_planar_bend_error_deg_s"],
    }

    sensory = lesions["right_sensory"]
    motor = lesions["right_A1_A3_motor"]
    attachment = lesions["right_A1_A3_attachment"]
    intact_motor_ids = {
        node_id
        for node_id, count in positive["steering_spike_counts"].items()
        if node_id in positive["axial_spike_counts"] and count > 0
    }
    if not intact_motor_ids:
        raise RuntimeError("named-fiber artifact lacks shared steering MN spikes")
    lesion_gates = {
        "sensory_lesion_removes_spatial_force": (
            sensory["attachment_active_force_samples"] == 0
        ),
        "sensory_lesion_restores_uniform_heading": abs(
            sensory["heading_change_deg"]
        ) <= gates["straight_heading_tolerance_deg"],
        "sensory_lesion_restores_uniform_axial_path": abs(
            sensory["displacement_x_um"] - uniform["displacement_x_um"]
        ) <= gates["straight_trajectory_tolerance_um"],
        "motor_lesion_preserves_sensory_spikes": (
            motor["steering_spike_counts"]["field_sensory:right"] > 0
        ),
        "motor_lesion_preserves_premotor_spikes": (
            motor["steering_spike_counts"]["premotor:steering:A1:right"] > 0
        ),
        "motor_lesion_removes_target_MN_spikes": all(
            motor["steering_spike_counts"][node_id] == 0
            and motor["axial_spike_counts"][node_id] == 0
            for node_id in intact_motor_ids
        ),
        "motor_lesion_removes_field_driven_muscle_force": (
            motor["steering_active_force_samples"] == 0
        ),
        "motor_lesion_changes_mechanical_response": abs(
            motor["heading_change_deg"] - positive["heading_change_deg"]
        ) >= gates["minimum_abs_heading_change_deg"],
        "attachment_lesion_preserves_field_driven_muscle_force": (
            attachment["steering_active_force_samples"]
            == positive["steering_active_force_samples"]
        ),
        "attachment_lesion_removes_spatial_force": (
            attachment["attachment_active_force_samples"] == 0
        ),
        "attachment_lesion_removes_heading_change": abs(
            attachment["heading_change_deg"]
        ) <= gates["straight_heading_tolerance_deg"],
    }

    invariant_gates = {
        "source_hashes_current": all(source_hash_gates.values()),
        "no_action_command": artifact["action_command"] is False,
        "no_behavior_fsm": artifact["behavior_fsm"] is False,
        "no_external_policy": artifact["external_policy"] is False,
        "no_target_heading_input": artifact["target_heading_input"] is False,
        "no_yaw_input_to_body": artifact["yaw_input_to_body"] is False,
        "no_curvature_input_to_body": artifact["curvature_input_to_body"] is False,
        "no_active_curvature_constraint": (
            artifact["active_curvature_constraint"] is False
            and all(
                scenario["active_curvature_constraint_executed"] is False
                for scenario in scenarios.values()
            )
        ),
        "no_authored_translation": artifact["authored_translation"] is False,
        "shared_MN_nodes_not_duplicated": (
            artifact["duplicated_motor_neuron_nodes"] is False
        ),
        "all_17_attachment_pairs_present": artifact["attachment_pair_count"] == 17,
        "attachment_coordinates_are_not_measured": (
            artifact["attachment_coordinate_provenance"] == "ANATOMY_DERIVED"
        ),
        "attachment_force_is_not_newtons": artifact["force_unit"]
        == "model_unit_not_newton",
        "release_not_validated": artifact["release_validated"] is False,
    }
    groups = (
        comparisons,
        causal_gates,
        force_gates,
        shape_gates,
        bend_distribution_gates,
        lesion_gates,
        invariant_gates,
    )
    passed = all(all(group.values()) for group in groups)
    return {
        "schema": "oraclarva.named_fiber_steering_validation.v1",
        "model_id": artifact["model_id"],
        "status": "engineering_gates_passed" if passed else "engineering_gates_failed",
        "passed": passed,
        "release_validated": False,
        "independent_biological_validation": False,
        "generated_from": {
            "trajectory": str(TRAJECTORY.relative_to(ROOT)),
            "trajectory_sha256": sha256(TRAJECTORY),
            "config_sha256": sha256(config_path),
        },
        "observed": {
            "positive_heading_change_deg": positive["heading_change_deg"],
            "negative_heading_change_deg": negative["heading_change_deg"],
            "mirror_heading_error_deg": abs(
                positive["heading_change_deg"] + negative["heading_change_deg"]
            ),
            "positive_attachment_torque_impulse_model_units_m_s": positive[
                "attachment_torque_impulse_model_units_m_s"
            ],
            "negative_attachment_torque_impulse_model_units_m_s": negative[
                "attachment_torque_impulse_model_units_m_s"
            ],
            "maximum_attachment_net_force_model_units": max(
                positive["maximum_attachment_net_force_model_units"],
                negative["maximum_attachment_net_force_model_units"],
            ),
            "uniform_axial_regression": regression,
            "steering_excess_planar_bend_deg_s_by_joint": excess,
            "active_pivot_joints": active,
            "dominant_pivot_joint": dominant,
            "single_joint_bend_fraction": peak / pivot_total,
            "outside_pivot_bend_fraction": outside_fraction,
            "maximum_adjacent_pivot_bend_jump_fraction": adjacent_jump,
            "maximum_mirror_planar_bend_error_deg_s": mirror_error,
        },
        "comparisons": comparisons,
        "causal_gates": causal_gates,
        "force_gates": force_gates,
        "shape_gates": shape_gates,
        "bend_distribution_gates": bend_distribution_gates,
        "lesion_gates": lesion_gates,
        "invariant_gates": invariant_gates,
        "claim_limit": config["validation"]["claim_limit"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = json.dumps(
        build_evaluation(), indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            print(f"generated named-fiber evaluation is stale: {args.output}")
            return 1
        print("generated named-fiber evaluation is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0 if json.loads(rendered)["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
