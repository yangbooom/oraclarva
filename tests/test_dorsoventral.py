import inspect
import json

import pytest

from oraclarva.dorsoventral import (
    DorsoventralClosedLoopLarva,
    DorsoventralSensoryState,
    DorsoventralStimulus,
    load_dorsoventral_config,
)


@pytest.fixture(scope="module")
def dorsal_free_result():
    return DorsoventralClosedLoopLarva(ground_z_m=None).run(
        DorsoventralStimulus(1.0, 0.0),
        record_trajectory_interval_s=0.03,
    )


@pytest.fixture(scope="module")
def ventral_free_result():
    return DorsoventralClosedLoopLarva(ground_z_m=None).run(
        DorsoventralStimulus(0.0, 1.0),
        record_trajectory_interval_s=0.03,
    )


@pytest.fixture(scope="module")
def ventral_ground_result():
    return DorsoventralClosedLoopLarva().run(
        DorsoventralStimulus(0.0, 1.0)
    )


def test_dorsoventral_config_preserves_evidence_and_claim_boundary():
    config = load_dorsoventral_config()
    assert config["status"] == "research_approximation"
    assert config["topology"]["provenance"] == "ANATOMY_DERIVED"
    assert config["parameter_provenance"]["provenance"] == "MODEL_FITTED"
    assert config["parameters"]["asymmetric_anterior_segments"] == [
        "T1", "T2", "T3", "A1", "A2"
    ]
    assert config["parameters"]["active_pitch_curvature_gain"] == 0.2
    assert config["muscle_identity_projection"]["dorsal_groups"] == ["DL", "DO"]
    assert config["muscle_identity_projection"]["ventral_groups"] == [
        "VL", "VA", "VO"
    ]
    assert config["release_validated"] is False


def test_dorsoventral_config_fails_closed_on_unbounded_pitch_gain(tmp_path):
    config = load_dorsoventral_config()
    config["parameters"]["active_pitch_curvature_gain"] = 0.0
    path = tmp_path / "invalid_pitch.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="pitch curvature gain"):
        load_dorsoventral_config(path)


def test_opposed_inputs_create_both_free_3d_head_pitch_directions(
    dorsal_free_result, ventral_free_result
):
    assert dorsal_free_result.neuron_count == 84
    assert ventral_free_result.neuron_count == 84
    assert dorsal_free_result.head_pitch_change_deg < -3.0
    assert ventral_free_result.head_pitch_change_deg > 3.0
    assert dorsal_free_result.head_pitch_change_deg == pytest.approx(
        -ventral_free_result.head_pitch_change_deg, abs=0.6
    )
    assert dorsal_free_result.displacement_y_um == pytest.approx(0.0, abs=1e-12)
    assert ventral_free_result.displacement_y_um == pytest.approx(0.0, abs=1e-12)
    assert dorsal_free_result.minimum_head_pitch_deg < -5.0
    assert dorsal_free_result.maximum_head_pitch_deg > 5.0
    assert ventral_free_result.minimum_head_pitch_deg < -5.0
    assert ventral_free_result.maximum_head_pitch_deg > 5.0
    assert dorsal_free_result.peak_recruited_fibers == 276
    assert ventral_free_result.peak_recruited_fibers == 276
    for frame in dorsal_free_result.trajectory_samples:
        assert "segment_activation_dorsal" in frame
        assert "segment_activation_ventral" in frame
        assert "segment_activation_left" not in frame


def test_ground_contact_blocks_downward_head_penetration_but_allows_lift(
    ventral_ground_result,
):
    assert ventral_ground_result.minimum_head_height_um == 0.0
    assert ventral_ground_result.maximum_head_height_um > 50.0
    assert ventral_ground_result.maximum_head_pitch_deg > 3.0


def test_zero_dorsoventral_input_leaves_neurons_muscles_and_body_at_rest():
    result = DorsoventralClosedLoopLarva(ground_z_m=None).run(
        DorsoventralStimulus(0.0, 0.0)
    )
    assert sum(result.spike_counts.values()) == 0
    assert result.peak_recruited_fibers == 0
    assert result.displacement_x_um == pytest.approx(0.0, abs=1e-12)
    assert result.displacement_y_um == pytest.approx(0.0, abs=1e-12)
    assert result.displacement_z_um == pytest.approx(0.0, abs=1e-12)
    assert result.minimum_head_pitch_deg == 0.0
    assert result.maximum_head_pitch_deg == 0.0


def test_dorsoventral_protocol_receives_only_read_only_head_sensor_state():
    observed = []

    def protocol(time_s, state):
        observed.append((time_s, state))
        return DorsoventralStimulus(0.0, 0.0)

    result = DorsoventralClosedLoopLarva(ground_z_m=None).run(
        stimulus_protocol=protocol,
        duration_s=0.003,
    )
    assert result.duration_s == pytest.approx(0.003)
    assert [time_s for time_s, _ in observed] == pytest.approx(
        [0.0, 0.001, 0.002]
    )
    assert all(
        isinstance(state, DorsoventralSensoryState) for _, state in observed
    )
    first = observed[0][1]
    assert first.dorsal_head_position_m.z > first.ventral_head_position_m.z


def test_dorsoventral_model_exposes_no_behavior_commands():
    source = inspect.getsource(DorsoventralClosedLoopLarva).lower()
    forbidden = (
        "pitch_up",
        "pitch_down",
        "crawl(",
        "behavior_tree",
        "fsm",
        "move_head",
    )
    assert all(token not in source for token in forbidden)
    assert not hasattr(DorsoventralClosedLoopLarva, "pitch_up")
    assert not hasattr(DorsoventralClosedLoopLarva, "pitch_down")
