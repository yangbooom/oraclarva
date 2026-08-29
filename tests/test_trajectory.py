import json
from pathlib import Path

import pytest


TRAJECTORY_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "trajectories"
    / "l1_closed_loop_v0.json"
)


def test_checked_trajectory_has_complete_body_frames_and_real_translation():
    artifact = json.loads(TRAJECTORY_PATH.read_text())
    assert artifact["schema_version"] == 1
    assert artifact["status"] == "research_approximation"
    assert artifact["release_validated"] is False
    assert artifact["node_count"] == 13
    assert artifact["sample_interval_s"] == pytest.approx(0.03)
    assert len(artifact["frames"]) == 151
    assert artifact["frames"][0]["time_s"] == 0.0
    assert artifact["frames"][-1]["time_s"] == 4.5
    assert all(
        len(frame["nodes_um"]) == 13
        and len(frame["segment_activation"]) == 12
        for frame in artifact["frames"]
    )
    initial_center = sum(
        node[0] for node in artifact["frames"][0]["nodes_um"]
    ) / 13
    final_center = sum(
        node[0] for node in artifact["frames"][-1]["nodes_um"]
    ) / 13
    assert final_center - initial_center == pytest.approx(-15.800161128, abs=1e-6)


def test_trajectory_preserves_causal_contract_without_action_fields():
    artifact = json.loads(TRAJECTORY_PATH.read_text())
    assert artifact["causal_contract"] == [
        "environment",
        "sensory_transduction",
        "neural_dynamics",
        "motor_neurons",
        "muscle_activation",
        "body_physics",
        "environment",
    ]
    serialized = json.dumps(artifact).lower()
    assert "turn_left" not in serialized
    assert '"crawl"' not in serialized
    assert "animation_command" not in serialized
