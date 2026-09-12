from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from oraclarva.axial import default_axial_locomotion_path
from oraclarva.steering import default_axial_steering_path


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY = ROOT / "data/trajectories/l1_axial_steering_v1.json"
VALIDATION = ROOT / "data/validation/axial_steering_v1.json"
FROZEN_AXIAL = ROOT / "data/trajectories/l1_axial_locomotion_v1.json"
GIF = ROOT / "docs/assets/oraclarva_axial_steering_v1.gif"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_checked_trajectory_hashes_sources_and_preserves_claim_boundary():
    artifact = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    generated = artifact["generated_from"]
    assert artifact["model_id"] == "dmel_l1_axial_steering_v1"
    assert artifact["release_validated"] is False
    assert artifact["action_command"] is False
    assert artifact["behavior_fsm"] is False
    assert artifact["external_policy"] is False
    assert artifact["target_heading_input"] is False
    assert artifact["yaw_input_to_body"] is False
    assert artifact["duplicated_motor_neuron_nodes"] is False
    assert generated["config_sha256"] == sha256(default_axial_steering_path())
    assert generated["axial_config_sha256"] == sha256(
        default_axial_locomotion_path()
    )
    assert generated["frozen_axial_trajectory_sha256"] == sha256(FROZEN_AXIAL)
    assert artifact["mapped_fiber_count"] == 146
    assert artifact["paired_muscle_numbers_by_segment"]["A1"] == [
        "1", "10", "20"
    ]
    assert set(artifact["steering_motor_source_count_by_channel"].values()) == {
        3, 13
    }


def test_checked_trajectory_contains_closed_loop_and_lesion_evidence():
    artifact = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    scenarios = artifact["scenarios"]
    assert set(scenarios) == {
        "uniform", "positive_y_gradient", "negative_y_gradient"
    }
    assert set(artifact["lesions"]) == {
        "right_sensory", "right_A1_A2_motor", "right_A1_A2_muscle"
    }
    assert artifact["uniform_axial_regression"][
        "maximum_node_position_error_um"
    ] < 1e-6
    assert artifact["uniform_axial_regression"][
        "maximum_contact_retention_error"
    ] == 0.0
    assert artifact["uniform_axial_regression"][
        "maximum_segment_activation_error"
    ] == 0.0
    assert scenarios["uniform"]["heading_change_deg"] == 0.0
    assert scenarios["positive_y_gradient"]["heading_change_deg"] < 0.0
    assert scenarios["negative_y_gradient"]["heading_change_deg"] > 0.0
    for name in ("positive_y_gradient", "negative_y_gradient"):
        scenario = scenarios[name]
        assert scenario["steering_active_force_samples"] > 0
        assert scenario["steering_active_force_samples"] == scenario[
            "steering_traced_force_samples"
        ]
        assert scenario["all_active_forces_sensory_traced"] is True
        assert len(scenario["trajectory_samples"]) == 401


def test_checked_validation_is_current_and_every_engineering_gate_passes():
    report = json.loads(VALIDATION.read_text(encoding="utf-8"))
    assert report["generated_from"]["trajectory_sha256"] == sha256(TRAJECTORY)
    assert report["generated_from"]["config_sha256"] == sha256(
        default_axial_steering_path()
    )
    assert report["status"] == "engineering_gates_passed"
    assert report["passed"] is True
    assert report["release_validated"] is False
    assert report["independent_biological_validation"] is False
    for group in (
        "comparisons", "causal_gates", "shape_gates",
        "lesion_gates", "invariant_gates",
    ):
        assert all(report[group].values()), group

    spec = importlib.util.spec_from_file_location(
        "evaluate_axial_steering", ROOT / "tools/evaluate_axial_steering.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build_evaluation() == report


def test_checked_gif_is_nonempty_multiframe_media():
    payload = GIF.read_bytes()
    assert payload[:6] in {b"GIF87a", b"GIF89a"}
    assert len(payload) > 100_000
    assert payload.count(b"\x21\xf9\x04") == 61
