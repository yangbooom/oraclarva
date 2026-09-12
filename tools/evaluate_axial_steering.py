"""Evaluate axial-steering symmetry, causality, lesion, and shape gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from oraclarva.steering import (
    default_axial_steering_path,
    load_axial_steering_config,
)


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY = ROOT / "data/trajectories/l1_axial_steering_v1.json"
DEFAULT_OUTPUT = ROOT / "data/validation/axial_steering_v1.json"


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
    config_path = default_axial_steering_path()
    config = load_axial_steering_config(config_path)
    artifact = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    generated = artifact["generated_from"]
    if generated["config_sha256"] != sha256(config_path):
        raise RuntimeError("steering artifact config hash is stale")
    axial_config = ROOT / generated["axial_config"]
    frozen_axial = ROOT / generated["frozen_axial_trajectory"]
    if (
        generated["axial_config_sha256"] != sha256(axial_config)
        or generated["frozen_axial_trajectory_sha256"] != sha256(frozen_axial)
    ):
        raise RuntimeError("steering artifact axial baseline hash is stale")

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
        "positive_gradient_yaw": (
            positive["heading_change_deg"]
            < -gates["minimum_abs_heading_change_deg"]
        ),
        "negative_gradient_yaw": (
            negative["heading_change_deg"]
            > gates["minimum_abs_heading_change_deg"]
        ),
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
    for name, scenario in (
        ("positive", positive), ("negative", negative)
    ):
        traces = scenario["steering_causal_trace_examples"]
        causal_gates[f"{name}_active_forces_exist"] = (
            scenario["steering_active_force_samples"] > 0
        )
        causal_gates[f"{name}_all_steering_forces_traced"] = (
            scenario["steering_active_force_samples"]
            == scenario["steering_traced_force_samples"]
            and scenario["all_active_forces_sensory_traced"] is True
        )
        causal_gates[f"{name}_ordered_trace"] = (
            len(traces) == 2 and all(ordered_trace(trace) for trace in traces.values())
        )

    shape_gates = {}
    for name, scenario in (
        ("positive", positive), ("negative", negative)
    ):
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

    intact_heading = abs(positive["heading_change_deg"])
    sensory = lesions["right_sensory"]
    motor = lesions["right_A1_A2_motor"]
    muscle = lesions["right_A1_A2_muscle"]
    intact_steering_motor_ids = {
        node_id
        for node_id, count in positive["steering_spike_counts"].items()
        if node_id in positive["axial_spike_counts"] and count > 0
    }
    if not intact_steering_motor_ids:
        raise RuntimeError("intact steering artifact lacks shared MN spikes")
    lesion_gates = {
        "sensory_lesion_removes_yaw": abs(sensory["heading_change_deg"])
        <= gates["straight_heading_tolerance_deg"],
        "sensory_lesion_preserves_axial": abs(
            sensory["displacement_x_um"] - uniform["displacement_x_um"]
        ) <= gates["straight_trajectory_tolerance_um"],
        "motor_lesion_preserves_sensory_spikes": (
            motor["steering_spike_counts"]["field_sensory:right"] > 0
        ),
        "motor_lesion_preserves_premotor_spikes": (
            motor["steering_spike_counts"]["premotor:steering:A1:right"] > 0
        ),
        "motor_lesion_removes_shared_MN_spikes": all(
            motor["steering_spike_counts"][node_id] == 0
            and motor["axial_spike_counts"][node_id] == 0
            for node_id in intact_steering_motor_ids
        ),
        "motor_lesion_removes_steering_force": (
            motor["steering_active_force_samples"] == 0
        ),
        "motor_lesion_attenuates_yaw": (
            abs(motor["heading_change_deg"]) < intact_heading
        ),
        "muscle_lesion_preserves_sensory_spikes": (
            muscle["steering_spike_counts"]["field_sensory:right"] > 0
        ),
        "muscle_lesion_preserves_premotor_spikes": (
            muscle["steering_spike_counts"][
                "premotor:steering:A1:right"
            ] > 0
        ),
        "muscle_lesion_preserves_shared_MN_spikes": all(
            muscle["steering_spike_counts"][node_id] > 0
            and muscle["axial_spike_counts"][node_id] > 0
            for node_id in intact_steering_motor_ids
        ),
        "muscle_lesion_removes_steering_force": (
            muscle["steering_active_force_samples"] == 0
        ),
        "muscle_lesion_attenuates_yaw": abs(muscle["heading_change_deg"])
        < intact_heading,
    }
    invariant_gates = {
        "no_action_command": artifact["action_command"] is False,
        "no_behavior_fsm": artifact["behavior_fsm"] is False,
        "no_external_policy": artifact["external_policy"] is False,
        "no_target_heading_input": artifact["target_heading_input"] is False,
        "no_yaw_input_to_body": artifact["yaw_input_to_body"] is False,
        "shared_MN_nodes_not_duplicated": (
            artifact["duplicated_motor_neuron_nodes"] is False
        ),
        "release_not_validated": artifact["release_validated"] is False,
        "shared_axial_config_is_frozen": (
            generated["axial_config_sha256"] == sha256(axial_config)
        ),
        "shared_axial_trajectory_is_frozen": (
            generated["frozen_axial_trajectory_sha256"] == sha256(frozen_axial)
        ),
    }
    passed = all(
        all(group.values())
        for group in (
            comparisons,
            causal_gates,
            shape_gates,
            lesion_gates,
            invariant_gates,
        )
    )
    return {
        "schema": "oraclarva.axial_steering_validation.v1",
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
            "mirror_x_error_um": abs(
                positive["displacement_x_um"] - negative["displacement_x_um"]
            ),
            "mirror_y_error_um": abs(
                positive["displacement_y_um"] + negative["displacement_y_um"]
            ),
            "uniform_axial_regression": regression,
        },
        "comparisons": comparisons,
        "causal_gates": causal_gates,
        "shape_gates": shape_gates,
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
            print(f"generated axial-steering evaluation is stale: {args.output}")
            return 1
        print("generated axial-steering evaluation is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0 if json.loads(rendered)["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
