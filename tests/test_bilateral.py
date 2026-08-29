import inspect

import pytest

from oraclarva.bilateral import (
    BilateralClosedLoopLarva,
    BilateralStimulus,
    load_bilateral_config,
)


@pytest.fixture(scope="module")
def symmetric_result():
    return BilateralClosedLoopLarva().run(
        BilateralStimulus(1.0, 1.0), record_trajectory_interval_s=0.03
    )


@pytest.fixture(scope="module")
def left_result():
    return BilateralClosedLoopLarva().run(
        BilateralStimulus(1.0, 0.0), record_trajectory_interval_s=0.03
    )


@pytest.fixture(scope="module")
def right_result():
    return BilateralClosedLoopLarva().run(
        BilateralStimulus(0.0, 1.0), record_trajectory_interval_s=0.03
    )


def test_bilateral_config_keeps_approximation_claim_boundary():
    config = load_bilateral_config()
    assert config["status"] == "research_approximation"
    assert config["topology"]["provenance"] == "ANATOMY_DERIVED"
    assert config["parameter_provenance"]["provenance"] == "MODEL_FITTED"
    assert config["parameters"]["asymmetric_anterior_segments"] == [
        "T3", "A1", "A2"
    ]
    assert config["release_validated"] is False


def test_bilateral_config_fails_closed_on_unbounded_asymmetric_current(tmp_path):
    import json

    config = load_bilateral_config()
    config["parameters"]["asymmetric_sensory_current_a"] = 0.0
    path = tmp_path / "invalid_bilateral.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="asymmetric sensory current"):
        load_bilateral_config(path)


def test_symmetric_sensory_input_preserves_straight_bilateral_wave(
    symmetric_result,
):
    assert symmetric_result.displacement_x_um < 0.0
    assert symmetric_result.displacement_y_um == pytest.approx(0.0, abs=1e-12)
    assert symmetric_result.heading_change_deg == pytest.approx(0.0, abs=1e-12)
    assert symmetric_result.maximum_abs_lateral_um == pytest.approx(0.0, abs=1e-12)
    assert symmetric_result.active_motor_identities == 58
    assert symmetric_result.neuron_count == 126
    assert symmetric_result.peak_recruited_fibers == 358
    for segment, peak in symmetric_result.peak_activation.items():
        assert peak["left"] == pytest.approx(peak["right"], abs=1e-12), segment


def test_left_and_right_sensory_differences_create_exact_mirrored_steering(
    left_result,
    right_result,
):
    assert left_result.heading_change_deg > 0.5
    assert right_result.heading_change_deg == pytest.approx(
        -left_result.heading_change_deg, abs=1e-9
    )
    assert left_result.displacement_x_um == pytest.approx(
        right_result.displacement_x_um, abs=1e-9
    )
    assert left_result.displacement_y_um == pytest.approx(
        -right_result.displacement_y_um, abs=1e-9
    )
    assert len(left_result.trajectory_samples) == len(right_result.trajectory_samples)
    for left_frame, right_frame in zip(
        left_result.trajectory_samples, right_result.trajectory_samples, strict=True
    ):
        assert left_frame["time_s"] == right_frame["time_s"]
        assert left_frame["segment_activation_left"] == pytest.approx(
            right_frame["segment_activation_right"], abs=1e-9
        )
        assert left_frame["segment_activation_right"] == pytest.approx(
            right_frame["segment_activation_left"], abs=1e-9
        )
        for left_node, right_node in zip(
            left_frame["nodes_um"], right_frame["nodes_um"], strict=True
        ):
            # Artifact coordinates are rounded to 1e-9 micrometres.
            assert left_node[0] == pytest.approx(right_node[0], abs=2e-9)
            assert left_node[1] == pytest.approx(-right_node[1], abs=2e-9)
            assert left_node[2] == pytest.approx(right_node[2], abs=2e-9)


def test_zero_sensory_input_leaves_network_muscles_and_body_at_rest():
    result = BilateralClosedLoopLarva().run(BilateralStimulus(0.0, 0.0))
    assert sum(result.spike_counts.values()) == 0
    assert result.active_motor_identities == 0
    assert result.peak_recruited_fibers == 0
    assert result.displacement_x_um == pytest.approx(0.0, abs=1e-12)
    assert result.displacement_y_um == pytest.approx(0.0, abs=1e-12)
    assert result.heading_change_deg == pytest.approx(0.0, abs=1e-12)


def test_left_t3_premotor_lesion_blocks_only_that_neural_channel(left_result):
    lesioned = BilateralClosedLoopLarva(
        lesion_premotor_channel=("T3", "left")
    ).run(BilateralStimulus(1.0, 0.0))
    assert lesioned.spike_counts["motor_pool:T3:left"] == 0
    assert lesioned.spike_counts["motor_pool:T3:right"] > 0
    assert lesioned.peak_activation["T3"]["left"] == 0.0
    assert lesioned.peak_activation["T3"]["right"] > 0.0
    assert abs(lesioned.heading_change_deg) < abs(left_result.heading_change_deg)


def test_left_a1_motor_identity_lesion_preserves_pool_spike_but_blocks_output():
    lesioned = BilateralClosedLoopLarva(
        lesion_motor_identity_channel=("A1", "left")
    ).run(BilateralStimulus(1.0, 0.0))
    assert lesioned.spike_counts["motor_pool:A1:left"] > 0
    assert lesioned.spike_counts["motor_pool:A1:right"] > 0
    assert lesioned.peak_activation["A1"]["left"] == 0.0
    assert lesioned.peak_activation["A1"]["right"] > 0.0
    assert lesioned.active_motor_identities == 30
    assert lesioned.peak_recruited_fibers == 329


def test_left_a1_muscle_lesion_preserves_neural_output_but_removes_fibers():
    lesioned = BilateralClosedLoopLarva(
        lesion_muscle_channel=("A1", "left")
    ).run(BilateralStimulus(1.0, 0.0))
    assert lesioned.spike_counts["motor_pool:A1:left"] > 0
    assert lesioned.peak_activation["A1"]["left"] > 0.0
    assert lesioned.active_motor_identities == 58
    assert lesioned.peak_recruited_fibers == 329


def test_bilateral_model_exposes_no_behavior_commands():
    source = inspect.getsource(BilateralClosedLoopLarva).lower()
    forbidden = ("turn_left", "turn_right", "crawl(", "behavior_tree", "fsm")
    assert all(token not in source for token in forbidden)
    assert not hasattr(BilateralClosedLoopLarva, "turn_left")
    assert not hasattr(BilateralClosedLoopLarva, "turn_right")
