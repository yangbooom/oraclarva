from __future__ import annotations

from functools import lru_cache

import pytest

from oraclarva.axial import (
    AXIAL_SEGMENTS,
    BACKWARD_WAVE,
    FORWARD_WAVE,
    AxialLocomotionLarva,
    load_axial_locomotion_config,
)


@lru_cache(maxsize=1)
def forward_result():
    return AxialLocomotionLarva().run(
        posterior_touch=True,
        duration_s=4.0,
        record_trajectory_interval_s=None,
    )


@lru_cache(maxsize=1)
def backward_result():
    return AxialLocomotionLarva().run(
        anterior_touch=True,
        duration_s=4.0,
        record_trajectory_interval_s=None,
    )


def first_wave_times(result, direction: str, order: tuple[str, ...]):
    return tuple(
        result.premotor_spike_times_s[direction][segment][0]
        for segment in order
    )


def test_axial_config_fails_closed_on_claims_and_directional_contact():
    config = load_axial_locomotion_config()
    topology = config["topology"]
    contact = config["continuous_ground_contact"]
    coupling = config["named_fiber_body_coupling"]

    assert config["release_validated"] is False
    assert topology["action_command"] is False
    assert topology["behavior_fsm"] is False
    assert topology["external_policy"] is False
    assert topology["shared_motor_and_muscle_atlas"] is True
    assert contact["movement_direction_input"] is False
    assert contact["finite_state_machine"] is False
    assert "ground_negative_x_retention" not in coupling
    assert "ground_positive_x_retention" not in coupling


def test_zero_input_is_silent_and_stationary():
    result = AxialLocomotionLarva().run(
        duration_s=0.2,
        record_trajectory_interval_s=None,
    )
    assert sum(result.spike_counts.values()) == 0
    assert result.feedback_force_frames == 0
    assert result.displacement_x_um == pytest.approx(0.0, abs=1e-9)
    assert result.contact_direction_input is False


def test_posterior_touch_generates_forward_wave_and_motion():
    result = forward_result()
    times = first_wave_times(result, "forward", FORWARD_WAVE)

    assert times == tuple(sorted(times))
    assert all(
        not result.premotor_spike_times_s["backward"][segment]
        for segment in AXIAL_SEGMENTS
    )
    assert result.anatomical_forward_displacement_um > 20.0
    assert result.displacement_x_um < 0.0
    assert result.contact_retention_range[0] < result.contact_retention_range[1]
    assert result.all_active_forces_sensory_traced is True
    assert result.t3_contact_proxy_peak_activation == 0.0
    assert result.t3_contact_proxy_neural_traced is True
    assert set(result.causal_trace_examples) == {
        f"forward:{segment}" for segment in AXIAL_SEGMENTS
    }


def test_anterior_touch_generates_mdn_backward_wave_and_motion():
    result = backward_result()
    times = first_wave_times(result, "backward", BACKWARD_WAVE)

    assert result.first_spike_s["environment_touch:anterior"] is not None
    assert (
        result.first_spike_s["environment_touch:anterior"]
        < result.first_spike_s["descending:MDN"]
        < result.first_spike_s["descending:Pair1"]
        <= times[0]
    )
    assert times == tuple(sorted(times))
    assert all(
        not result.premotor_spike_times_s["forward"][segment]
        for segment in AXIAL_SEGMENTS
    )
    assert result.anatomical_forward_displacement_um < -10.0
    assert result.displacement_x_um > 0.0
    assert result.contact_retention_range[0] < result.contact_retention_range[1]
    assert result.all_active_forces_sensory_traced is True
    assert result.t3_contact_proxy_peak_activation > 0.0
    assert result.t3_contact_proxy_neural_traced is True
    assert set(result.causal_trace_examples) == {
        f"backward:{segment}" for segment in AXIAL_SEGMENTS
    }


def test_forward_and_backward_paths_share_every_motor_identity_and_fiber():
    larva = AxialLocomotionLarva()
    outgoing = larva.protocol.network.outgoing
    index = larva.protocol.index_by_id
    for segment, motor_ids in larva.protocol.source_nodes_by_segment.items():
        forward_targets = {
            synapse.post
            for synapse in outgoing[index[f"premotor:A27h:{segment}"]]
        }
        backward_targets = {
            synapse.post
            for synapse in outgoing[index[f"premotor:A18b:{segment}"]]
        }
        expected = {index[motor_id] for motor_id in motor_ids}
        assert expected <= forward_targets
        assert expected <= backward_targets
    assert len(larva.projection.mappings) == 146


def test_mdn_and_a27h_lesions_break_only_the_expected_path():
    mdn = AxialLocomotionLarva(
        lesion_node_ids=("descending:MDN",)
    ).run(
        anterior_touch=True,
        duration_s=0.2,
        record_trajectory_interval_s=None,
    )
    assert mdn.first_spike_s["environment_touch:anterior"] is not None
    assert mdn.first_spike_s["descending:MDN"] is None
    assert not mdn.premotor_spike_times_s["backward"]["A1"]
    assert mdn.feedback_force_frames == 0

    a27h = AxialLocomotionLarva(
        lesion_node_ids=("premotor:A27h:A4",)
    ).run(
        posterior_touch=True,
        duration_s=2.2,
        record_trajectory_interval_s=None,
    )
    assert a27h.premotor_spike_times_s["forward"]["A5"]
    assert not a27h.premotor_spike_times_s["forward"]["A4"]
    assert not a27h.premotor_spike_times_s["forward"]["A3"]


def test_invalid_axial_lesions_fail_closed():
    with pytest.raises(ValueError, match="unknown axial neural lesion"):
        AxialLocomotionLarva(lesion_node_ids=("crawl_backward",))
    with pytest.raises(ValueError):
        AxialLocomotionLarva(lesion_fiber_ids=("unknown:fiber",))


def test_t3_contact_proxy_is_a_lesionable_neural_effector_without_axial_force():
    result = AxialLocomotionLarva(
        lesion_node_ids=("motor_proxy:T3_transverse_backward",)
    ).run(
        anterior_touch=True,
        duration_s=1.0,
        record_trajectory_interval_s=None,
    )
    assert result.first_spike_s["premotor:A18b:A1"] is not None
    assert result.first_spike_s["motor_proxy:T3_transverse_backward"] is None
    assert result.t3_contact_proxy_peak_activation == 0.0
