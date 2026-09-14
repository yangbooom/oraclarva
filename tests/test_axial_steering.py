from __future__ import annotations

import inspect
import json
from functools import lru_cache
from pathlib import Path

import pytest

from oraclarva.steering import (
    AxialSteeringLarva,
    BilateralSteeringCircuit,
    PlanarLinearField,
    load_axial_steering_config,
)


ROOT = Path(__file__).resolve().parents[1]
DURATION_S = 4.0
SAMPLE_INTERVAL_S = 0.02
GRADIENT = 5000.0


def field(gradient: float) -> PlanarLinearField:
    return PlanarLinearField(0.5, gradient_y_per_m=gradient)


@lru_cache(maxsize=1)
def uniform_result():
    return AxialSteeringLarva().run(
        field(0.0),
        duration_s=DURATION_S,
        record_trajectory_interval_s=SAMPLE_INTERVAL_S,
    )


@lru_cache(maxsize=1)
def positive_result():
    return AxialSteeringLarva().run(
        field(GRADIENT),
        duration_s=DURATION_S,
        record_trajectory_interval_s=SAMPLE_INTERVAL_S,
    )


@lru_cache(maxsize=1)
def negative_result():
    return AxialSteeringLarva().run(
        field(-GRADIENT),
        duration_s=DURATION_S,
        record_trajectory_interval_s=SAMPLE_INTERVAL_S,
    )


@lru_cache(maxsize=1)
def sensory_lesion_result():
    return AxialSteeringLarva(lesion_sensory_sides=("right",)).run(
        field(GRADIENT), duration_s=DURATION_S, record_trajectory_interval_s=None
    )


@lru_cache(maxsize=1)
def motor_lesion_result():
    return AxialSteeringLarva(
        lesion_motor_channels=(
            ("A1", "right"),
            ("A2", "right"),
            ("A3", "right"),
        )
    ).run(field(GRADIENT), duration_s=DURATION_S, record_trajectory_interval_s=None)


@lru_cache(maxsize=1)
def muscle_lesion_result():
    return AxialSteeringLarva(
        lesion_muscle_channels=(
            ("A1", "right"),
            ("A2", "right"),
            ("A3", "right"),
        )
    ).run(field(GRADIENT), duration_s=DURATION_S, record_trajectory_interval_s=None)


def test_config_fails_closed_on_behavior_and_claim_boundary():
    config = load_axial_steering_config()
    topology = config["topology"]
    mechanics = config["mechanics"]
    assert config["base_model_id"] == "dmel_l1_axial_locomotion_v1"
    assert config["release_validated"] is False
    assert topology["action_command"] is False
    assert topology["behavior_fsm"] is False
    assert topology["external_policy"] is False
    assert topology["target_heading_input"] is False
    assert topology["yaw_input_to_body"] is False
    assert topology["shared_axial_protocol"] is True
    assert topology["duplicated_motor_neuron_nodes"] is False
    assert topology["anterior_pivot"] == {
        "published_stage": "L2",
        "published_segment_support": ["T3", "A1", "A2", "A3"],
        "published_peak_segment": "A1",
        "published_support_provenance": "MEASURED_PUBLISHED",
        "modeled_motor_segments": ["A1", "A2", "A3"],
        "mechanical_joint_support": ["T3-A1", "A1-A2", "A2-A3", "A3-A4"],
        "allowed_dominant_joints": ["T3-A1", "A1-A2"],
        "numeric_profile_provenance": "MODEL_FITTED",
    }
    assert mechanics["yaw_angle_input"] is False
    assert mechanics["authored_translation"] is False


def test_field_is_bounded_and_rejects_invalid_parameters():
    gradient = PlanarLinearField(0.5, 1000.0, -2000.0)
    from oraclarva.body3d import Vec3

    assert gradient.sample(Vec3(1.0, 1.0, 0.0), 0.0) == 0.0
    assert gradient.sample(Vec3(1.0, -1.0, 0.0), 0.0) == 1.0
    with pytest.raises(ValueError, match="baseline"):
        PlanarLinearField(1.1)
    with pytest.raises(ValueError, match="finite"):
        PlanarLinearField(0.5, float("nan"), 0.0)


def test_circuit_uses_only_mirror_paired_named_muscle_outputs():
    larva = AxialSteeringLarva()
    circuit: BilateralSteeringCircuit = larva.circuit
    assert circuit.paired_muscle_numbers_by_segment == {
        "A1": ("1", "10", "20"),
        "A2": (
            "1", "5", "8", "9", "10", "11", "18",
            "19", "20", "21", "22", "23", "24",
        ),
        "A3": (
            "1", "5", "8", "9", "10", "11", "18",
            "19", "20", "21", "22", "23", "24",
        ),
    }
    for segment in ("A1", "A2", "A3"):
        assert len(circuit.motor_sources_by_channel[(segment, "left")]) == len(
            circuit.motor_sources_by_channel[(segment, "right")]
        )
    assert circuit.motor_source_ids.isdisjoint(circuit.labels)
    for source in circuit.motor_source_ids:
        assert larva.protocol.labels.count(source) == 1
        assert source in larva.axial.projection.source_node_ids


def test_uniform_field_preserves_frozen_axial_v1_trajectory():
    result = uniform_result()
    artifact = json.loads(
        (ROOT / "data/trajectories/l1_axial_locomotion_v1.json").read_text()
    )
    axial_by_time = {
        frame["time_s"]: frame
        for frame in artifact["forward"]["trajectory_samples"]
        if frame["time_s"] <= DURATION_S
    }
    assert result.heading_change_deg == pytest.approx(0.0, abs=1e-12)
    assert result.displacement_y_um == pytest.approx(0.0, abs=1e-12)
    assert result.steering_active_force_samples == 0
    for frame in result.trajectory_samples:
        frozen = axial_by_time[frame["time_s"]]
        for current_node, frozen_node in zip(
            frame["nodes_um"], frozen["nodes_um"], strict=True
        ):
            assert current_node == pytest.approx(frozen_node, abs=1e-6)
        assert frame["contact_retention_by_node"] == pytest.approx(
            frozen["contact_retention_by_node"], abs=1e-9
        )
        for segment in result.side_peak_activation:
            assert frame["segment_activation_left"][segment] == pytest.approx(
                frozen["segment_activation"][segment], abs=1e-9
            )
            assert frame["segment_activation_right"][segment] == pytest.approx(
                frozen["segment_activation"][segment], abs=1e-9
            )


def test_reversed_field_gradients_generate_mirrored_yaw_and_path():
    positive = positive_result()
    negative = negative_result()
    gates = load_axial_steering_config()["validation"]["gates"]
    assert positive.heading_change_deg < -gates["minimum_abs_heading_change_deg"]
    assert negative.heading_change_deg > gates["minimum_abs_heading_change_deg"]
    assert abs(positive.heading_change_deg + negative.heading_change_deg) <= gates[
        "mirror_heading_tolerance_deg"
    ]
    assert abs(positive.displacement_x_um - negative.displacement_x_um) <= gates[
        "mirror_position_tolerance_um"
    ]
    assert abs(positive.displacement_y_um + negative.displacement_y_um) <= gates[
        "mirror_position_tolerance_um"
    ]
    assert positive.anatomical_forward_displacement_um > gates[
        "minimum_anatomical_forward_displacement_um"
    ]
    assert negative.anatomical_forward_displacement_um > gates[
        "minimum_anatomical_forward_displacement_um"
    ]
    assert positive.maximum_abs_field_contrast > 0.1
    assert negative.maximum_abs_field_contrast > 0.1
    assert (
        positive.trajectory_samples[0]["field_right"]
        != positive.trajectory_samples[-1]["field_right"]
    )


@pytest.mark.parametrize("result", [positive_result, negative_result])
def test_all_steering_forces_have_ordered_field_to_muscle_trace(result):
    value = result()
    assert value.all_active_forces_sensory_traced is True
    assert value.steering_active_force_samples > 0
    assert value.steering_traced_force_samples == value.steering_active_force_samples
    expected_side = "right" if value.heading_change_deg < 0.0 else "left"
    assert set(value.steering_causal_trace_examples) == {
        f"{expected_side}:A1", f"{expected_side}:A2",
        f"{expected_side}:A3",
    }
    for trace in value.steering_causal_trace_examples.values():
        assert (
            trace["body_state_time_s"]
            <= trace["sensor_spike_time_s"]
            < trace["premotor_spike_time_s"]
            < trace["motor_spike_time_s"]
        )
        assert trace["sensor_node_id"].startswith("field_sensory:")
        assert trace["motor_node_id"] in value.steering_spike_counts


@pytest.mark.parametrize("result", [positive_result, negative_result])
def test_steering_passes_distortion_and_slip_rejection_gates(result):
    value = result()
    gates = load_axial_steering_config()["validation"]["gates"]
    assert value.maximum_segment_extension_fraction <= gates[
        "maximum_segment_extension_fraction"
    ]
    assert value.minimum_head_tail_chord_ratio >= gates[
        "minimum_head_tail_chord_ratio"
    ]
    assert value.maximum_local_bend_deg <= gates["maximum_local_bend_deg"]
    assert value.integrated_lateral_slip_um <= gates[
        "maximum_integrated_lateral_slip_um"
    ]


def test_steering_bend_is_distributed_across_the_anterior_pivot():
    config = load_axial_steering_config()
    gates = config["validation"]["gates"]
    pivot = config["topology"]["anterior_pivot"]
    values = {
        "uniform": uniform_result().integrated_local_bend_deg_s_by_joint,
        "positive": positive_result().integrated_local_bend_deg_s_by_joint,
        "negative": negative_result().integrated_local_bend_deg_s_by_joint,
    }
    assert len({frozenset(item) for item in values.values()}) == 1
    excess = {
        joint: max(
            0.0,
            0.5 * (values["positive"][joint] + values["negative"][joint])
            - values["uniform"][joint],
        )
        for joint in values["uniform"]
    }
    total = sum(excess.values())
    peak = max(excess.values())
    dominant = max(excess, key=excess.__getitem__)
    joints = pivot["mechanical_joint_support"]
    active = [
        joint
        for joint in joints
        if excess[joint] >= gates["bend_activity_relative_threshold"] * peak
    ]
    outside = sum(
        value for joint, value in excess.items() if joint not in joints
    ) / total
    adjacent_jump = max(
        abs(excess[left] - excess[right])
        for left, right in zip(joints[:-1], joints[1:], strict=True)
    ) / peak
    mirror_error = max(
        abs(values["positive"][joint] - values["negative"][joint])
        for joint in values["uniform"]
    )
    assert len(active) >= gates["minimum_active_pivot_joint_count"]
    assert dominant in pivot["allowed_dominant_joints"]
    assert peak / total <= gates["maximum_single_joint_bend_fraction"]
    assert outside <= gates["maximum_outside_pivot_bend_fraction"]
    assert adjacent_jump <= gates["maximum_adjacent_pivot_bend_jump_fraction"]
    assert mirror_error <= gates["maximum_mirror_integrated_bend_error_deg_s"]


def test_sensory_lesion_removes_field_steering_only():
    uniform = uniform_result()
    for lesioned in (sensory_lesion_result(),):
        assert lesioned.heading_change_deg == pytest.approx(0.0, abs=1e-12)
        assert lesioned.displacement_y_um == pytest.approx(0.0, abs=1e-12)
        assert lesioned.displacement_x_um == pytest.approx(
            uniform.displacement_x_um, abs=1e-9
        )
        assert lesioned.steering_active_force_samples == 0


def test_shared_mn_lesion_preserves_upstream_but_removes_mn_and_force():
    intact = positive_result()
    lesioned = motor_lesion_result()
    motor_ids = {
        node_id for node_id, count in intact.steering_spike_counts.items()
        if node_id in intact.axial_spike_counts and count > 0
    }
    assert motor_ids
    assert lesioned.steering_spike_counts["field_sensory:right"] > 0
    assert lesioned.steering_spike_counts["premotor:steering:A1:right"] > 0
    assert all(
        lesioned.steering_spike_counts[node_id] == 0 for node_id in motor_ids
    )
    assert all(lesioned.axial_spike_counts[node_id] == 0 for node_id in motor_ids)
    assert lesioned.steering_active_force_samples == 0
    assert abs(lesioned.heading_change_deg) < abs(intact.heading_change_deg)


def test_muscle_lesion_preserves_neural_spikes_but_attenuates_yaw():
    intact = positive_result()
    lesioned = muscle_lesion_result()
    assert lesioned.steering_spike_counts["field_sensory:right"] > 0
    assert lesioned.steering_spike_counts["premotor:steering:A1:right"] > 0
    motor_ids = {
        node_id for node_id, count in intact.steering_spike_counts.items()
        if node_id in intact.axial_spike_counts and count > 0
    }
    assert all(lesioned.steering_spike_counts[node_id] > 0 for node_id in motor_ids)
    assert all(lesioned.axial_spike_counts[node_id] > 0 for node_id in motor_ids)
    assert abs(lesioned.heading_change_deg) < abs(intact.heading_change_deg)
    assert lesioned.steering_active_force_samples == 0
    assert lesioned.all_active_forces_sensory_traced is True


def test_model_exposes_no_behavior_direction_or_yaw_command():
    source = inspect.getsource(AxialSteeringLarva).lower()
    forbidden = (
        "turn_left", "turn_right", "crawl(", "behavior_tree",
        "target_heading", "requested_yaw", "direction_command",
    )
    assert all(token not in source for token in forbidden)
    assert not hasattr(AxialSteeringLarva, "turn_left")
    assert not hasattr(AxialSteeringLarva, "turn_right")
