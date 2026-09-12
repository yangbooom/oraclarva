from __future__ import annotations

import hashlib
import json
from pathlib import Path

from oraclarva.axial import default_axial_locomotion_path


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY = (
    ROOT / "data" / "trajectories" / "l1_axial_locomotion_v1.json"
)
CALIBRATION = (
    ROOT / "data" / "validation" / "axial_locomotion_calibration_v1.json"
)
HELD_OUT = (
    ROOT
    / "data"
    / "validation"
    / "axial_locomotion_diagnostic_held_out_v1.json"
)


def test_checked_axial_artifact_matches_config_and_claim_boundary():
    artifact = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    config_path = default_axial_locomotion_path()

    assert artifact["generated_from"]["config_sha256"] == hashlib.sha256(
        config_path.read_bytes()
    ).hexdigest()
    assert artifact["release_validated"] is False
    assert artifact["action_command"] is False
    assert artifact["behavior_fsm"] is False
    assert artifact["external_policy"] is False
    assert artifact["shared_mapped_fiber_count"] == 146
    assert artifact["sample_interval_s"] == 0.005
    assert (
        artifact["continuous_ground_contact"]["movement_direction_input"]
        is False
    )
    assert artifact["forward"]["anatomical_forward_displacement_um"] > 20.0
    assert artifact["backward"]["anatomical_forward_displacement_um"] < -10.0
    assert artifact["forward"]["t3_contact_proxy_peak_activation"] == 0.0
    assert artifact["backward"]["t3_contact_proxy_peak_activation"] > 0.0
    for direction in ("forward", "backward"):
        result = artifact[direction]
        assert result["all_active_forces_sensory_traced"] is True
        assert result["contact_direction_input"] is False
        assert result["t3_contact_proxy_neural_traced"] is True


def test_axial_calibration_passes_but_held_out_remains_diagnostic():
    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    held_out = json.loads(HELD_OUT.read_text(encoding="utf-8"))
    config_path = default_axial_locomotion_path()
    expected_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()

    assert calibration["frozen_config_sha256"] == expected_hash
    assert calibration["status"] == "calibration_passed"
    assert calibration["passed"] is True
    assert all(item["passed"] for item in calibration["comparisons"])
    assert all(calibration["directional_shape_gates"].values())
    assert all(calibration["causal_gates"].values())
    for direction in ("forward", "backward"):
        assert all(
            calibration["full_response_progress_gates"][direction].values()
        )

    assert held_out["frozen_config_sha256"] == expected_hash
    assert held_out["status"] == "diagnostic_held_out_failed"
    assert held_out["independent_validation_passed"] is False
    assert held_out["selection_used_held_out_values"] is False
    assert held_out["fail_closed"] is True
