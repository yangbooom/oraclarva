from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
from copy import deepcopy
from pathlib import Path

import pytest

from oraclarva.named_fiber_steering import (
    NamedFiberSteeringLarva,
    default_named_fiber_steering_path,
    load_named_fiber_steering_config,
    validate_named_fiber_steering_config,
)


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY = ROOT / "data/trajectories/l1_named_fiber_steering_v1.json"
VALIDATION = ROOT / "data/validation/named_fiber_steering_v1.json"
GIF = ROOT / "docs/assets/oraclarva_named_fiber_steering_v1.gif"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_config_fails_closed_on_curvature_commands_and_unmeasured_claims():
    config = load_named_fiber_steering_config()
    topology = config["topology"]
    attachment = topology["attachment_scope"]
    mechanics = config["mechanics"]
    assert config["base_model_id"] == "dmel_l1_axial_steering_v1"
    assert config["release_validated"] is False
    assert topology["action_command"] is False
    assert topology["behavior_fsm"] is False
    assert topology["external_policy"] is False
    assert topology["yaw_input_to_body"] is False
    assert attachment["mirrored_non_transverse_pair_count"] == 17
    assert attachment["coordinate_provenance"] == "ANATOMY_DERIVED"
    assert attachment["metric_coordinates_measured"] is False
    assert attachment["csa_measured"] is False
    assert attachment["fmax_measured"] is False
    assert mechanics["active_curvature_constraint"] is False
    assert mechanics["active_curvature_gain"] == 0.0
    assert mechanics["curvature_input_to_body"] is False
    assert mechanics["force_unit"] == "model_unit_not_newton"

    invalid = deepcopy(config)
    invalid["parameters"]["active_curvature_gain"] = 0.01
    with pytest.raises(ValueError, match="mechanics parameters"):
        validate_named_fiber_steering_config(invalid)
    invalid = deepcopy(config)
    invalid["topology"]["attachment_scope"]["metric_coordinates_measured"] = True
    with pytest.raises(ValueError, match="topology"):
        validate_named_fiber_steering_config(invalid)


def test_runtime_uses_17_pairs_and_exposes_no_behavior_method():
    larva = NamedFiberSteeringLarva()
    assert len(larva.attachment_fiber_pairs) == 17
    assert larva.active_curvature_gain == 0.0
    assert larva.force_projection_mode == "paired_activation_excess_attachment_3d"
    assert not hasattr(larva, "turn_left")
    assert not hasattr(larva, "turn_right")
    source = inspect.getsource(NamedFiberSteeringLarva).lower()
    assert all(
        token not in source
        for token in (
            "turn_left",
            "turn_right",
            "crawl(",
            "target_heading",
            "requested_yaw",
            "direction_command",
        )
    )


def test_checked_trajectory_hashes_every_source_and_preserves_boundary():
    artifact = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    generated = artifact["generated_from"]
    assert artifact["model_id"] == "dmel_l1_named_fiber_steering_v1"
    assert artifact["release_validated"] is False
    assert artifact["action_command"] is False
    assert artifact["behavior_fsm"] is False
    assert artifact["external_policy"] is False
    assert artifact["target_heading_input"] is False
    assert artifact["yaw_input_to_body"] is False
    assert artifact["curvature_input_to_body"] is False
    assert artifact["active_curvature_constraint"] is False
    assert artifact["attachment_pair_count"] == 17
    assert artifact["mapped_fiber_count"] == 146
    assert generated["config_sha256"] == sha256(
        default_named_fiber_steering_path()
    )
    for name in (
        "axial_config",
        "frozen_axial_trajectory",
        "steering_config",
        "frozen_steering_trajectory",
        "attachment_spec",
    ):
        assert generated[f"{name}_sha256"] == sha256(ROOT / generated[name])
    assert all(
        pair["coordinate_provenance"] == "ANATOMY_DERIVED"
        for pair in artifact["attachment_fiber_pairs"]
    )


def test_checked_scenarios_contain_regression_mirror_and_causal_evidence():
    artifact = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    scenarios = artifact["scenarios"]
    uniform = scenarios["uniform"]
    positive = scenarios["positive_y_gradient"]
    negative = scenarios["negative_y_gradient"]
    assert artifact["uniform_axial_regression"][
        "maximum_node_position_error_um"
    ] < 1e-6
    assert uniform["heading_change_deg"] == 0.0
    assert uniform["attachment_active_force_samples"] == 0
    assert positive["heading_change_deg"] > 0.5
    assert negative["heading_change_deg"] < -0.5
    assert positive["attachment_torque_impulse_model_units_m_s"] > 0.0
    assert negative["attachment_torque_impulse_model_units_m_s"] < 0.0
    for scenario in (positive, negative):
        assert scenario["active_curvature_constraint_executed"] is False
        assert scenario["attachment_active_force_samples"] > 0
        assert scenario["attachment_active_force_samples"] == scenario[
            "attachment_traced_force_samples"
        ]
        assert len(scenario["attachment_force_trace_examples"]) == 17
        assert len(scenario["trajectory_samples"]) == 401


def test_checked_validation_is_current_and_every_engineering_gate_passes():
    report = json.loads(VALIDATION.read_text(encoding="utf-8"))
    assert report["generated_from"]["trajectory_sha256"] == sha256(TRAJECTORY)
    assert report["status"] == "engineering_gates_passed"
    assert report["passed"] is True
    assert report["release_validated"] is False
    assert report["independent_biological_validation"] is False
    for group in (
        "comparisons",
        "causal_gates",
        "force_gates",
        "shape_gates",
        "bend_distribution_gates",
        "lesion_gates",
        "invariant_gates",
    ):
        assert all(report[group].values()), group
    spec = importlib.util.spec_from_file_location(
        "evaluate_named_fiber_steering",
        ROOT / "tools/evaluate_named_fiber_steering.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build_evaluation() == report


def test_checked_gif_is_nonempty_61_frame_media():
    payload = GIF.read_bytes()
    assert payload[:6] in {b"GIF87a", b"GIF89a"}
    assert len(payload) > 100_000
    assert payload.count(b"\x21\xf9\x04") == 61
