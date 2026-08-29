import inspect
from math import cos, radians, sin

import pytest

from oraclarva.spatial import (
    SpatialClosedLoopLarva,
    SpatialSensoryState,
    SpatialStimulus,
    load_spatial_config,
)


@pytest.fixture(scope="module")
def combined_result():
    return SpatialClosedLoopLarva(ground_z_m=None).run(
        SpatialStimulus(1.0, 0.0, 1.0, 0.0),
        record_trajectory_interval_s=0.03,
    )


@pytest.fixture(scope="module")
def rotated_combined_result():
    return SpatialClosedLoopLarva(
        initial_yaw_deg=73.0,
        ground_z_m=None,
    ).run(
        SpatialStimulus(1.0, 0.0, 1.0, 0.0),
        record_trajectory_interval_s=0.03,
    )


def test_spatial_config_preserves_claim_boundary():
    config = load_spatial_config()
    assert config["status"] == "research_approximation"
    assert config["topology"]["provenance"] == "ANATOMY_DERIVED"
    assert config["parameter_provenance"]["provenance"] == "MODEL_FITTED"
    assert config["channels"] == ["left", "right", "dorsal", "ventral"]
    assert config["release_validated"] is False


def test_zero_spatial_input_is_exact_long_duration_rest():
    result = SpatialClosedLoopLarva(ground_z_m=None).run(
        SpatialStimulus(0.0, 0.0, 0.0, 0.0)
    )
    assert sum(result.spike_counts.values()) == 0
    assert result.peak_yaw_recruited_fibers == 0
    assert result.peak_pitch_recruited_fibers == 0
    assert result.displacement_x_um == pytest.approx(0.0, abs=1e-12)
    assert result.displacement_y_um == pytest.approx(0.0, abs=1e-12)
    assert result.displacement_z_um == pytest.approx(0.0, abs=1e-12)
    assert result.yaw_change_deg == pytest.approx(0.0, abs=1e-12)
    assert result.head_pitch_change_deg == pytest.approx(0.0, abs=1e-12)


def test_combined_receptor_differences_drive_one_body_in_three_dimensions(
    combined_result,
):
    assert combined_result.neuron_count == 168
    assert combined_result.synapse_count == 188
    assert abs(combined_result.displacement_y_um) > 1.0
    assert abs(combined_result.displacement_z_um) > 10.0
    assert abs(combined_result.yaw_change_deg) > 1.0
    assert abs(combined_result.head_pitch_change_deg) > 3.0
    assert combined_result.minimum_head_pitch_deg < -5.0
    assert combined_result.maximum_head_pitch_deg > 5.0
    assert combined_result.peak_yaw_recruited_fibers == 358
    assert combined_result.peak_pitch_recruited_fibers == 276
    assert len(combined_result.trajectory_samples) == 151
    for frame in combined_result.trajectory_samples:
        assert "segment_activation_left" in frame
        assert "segment_activation_right" in frame
        assert "segment_activation_dorsal" in frame
        assert "segment_activation_ventral" in frame


def test_combined_3d_trajectory_is_equivariant_under_arbitrary_screen_yaw(
    combined_result, rotated_combined_result
):
    angle = radians(73.0)
    assert rotated_combined_result.displacement_x_um == pytest.approx(
        cos(angle) * combined_result.displacement_x_um
        - sin(angle) * combined_result.displacement_y_um,
        abs=1e-9,
    )
    assert rotated_combined_result.displacement_y_um == pytest.approx(
        sin(angle) * combined_result.displacement_x_um
        + cos(angle) * combined_result.displacement_y_um,
        abs=1e-9,
    )
    assert rotated_combined_result.displacement_z_um == pytest.approx(
        combined_result.displacement_z_um, abs=1e-9
    )
    assert rotated_combined_result.yaw_change_deg == pytest.approx(
        combined_result.yaw_change_deg, abs=1e-9
    )
    assert rotated_combined_result.head_pitch_change_deg == pytest.approx(
        combined_result.head_pitch_change_deg, abs=1e-9
    )
    for base_frame, rotated_frame in zip(
        combined_result.trajectory_samples,
        rotated_combined_result.trajectory_samples,
        strict=True,
    ):
        for base_node, rotated_node in zip(
            base_frame["nodes_um"],
            rotated_frame["nodes_um"],
            strict=True,
        ):
            assert rotated_node[0] == pytest.approx(
                cos(angle) * base_node[0] - sin(angle) * base_node[1],
                abs=3e-9,
            )
            assert rotated_node[1] == pytest.approx(
                sin(angle) * base_node[0] + cos(angle) * base_node[1],
                abs=3e-9,
            )
            assert rotated_node[2] == pytest.approx(base_node[2], abs=3e-9)


def test_spatial_protocol_receives_only_four_read_only_receptor_points():
    observed = []

    def protocol(time_s, state):
        observed.append((time_s, state))
        return SpatialStimulus(0.0, 0.0, 0.0, 0.0)

    result = SpatialClosedLoopLarva(ground_z_m=None).run(
        stimulus_protocol=protocol,
        duration_s=0.003,
    )
    assert result.duration_s == pytest.approx(0.003)
    assert [time_s for time_s, _ in observed] == pytest.approx(
        [0.0, 0.001, 0.002]
    )
    assert all(isinstance(state, SpatialSensoryState) for _, state in observed)
    first = observed[0][1]
    assert first.left_head_position_m.y < first.right_head_position_m.y
    assert first.dorsal_head_position_m.z > first.ventral_head_position_m.z


def test_spatial_model_exposes_no_behavior_commands():
    source = inspect.getsource(SpatialClosedLoopLarva).lower()
    forbidden = (
        "turn_left",
        "turn_right",
        "pitch_up",
        "pitch_down",
        "crawl(",
        "move_3d",
        "behavior_tree",
        "fsm",
    )
    assert all(token not in source for token in forbidden)
    assert not hasattr(SpatialClosedLoopLarva, "turn_left")
    assert not hasattr(SpatialClosedLoopLarva, "pitch_up")
