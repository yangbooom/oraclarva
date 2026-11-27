import pytest

from oraclarva.axial import AxialLocomotionLarva, load_axial_locomotion_config


def _run(source, duration_s=2.5):
    config = load_axial_locomotion_config()
    config["parameters"]["brain_bridge_current_a"] = 2e-10
    return AxialLocomotionLarva(config).run(
        duration_s=duration_s, record_trajectory_interval_s=None, descending_spike_source=source
    )


def test_brain_mdn_burst_drives_traced_backward_crawl_without_touch():
    burst = lambda t, dt: {"descending:MDN": 4} if 0.1 <= t < 0.2 else {}  # noqa: E731
    result = _run(burst)
    assert result.spike_counts["environment_touch:anterior"] == 0
    assert result.spike_counts["descending:MDN"] > 0
    assert result.anatomical_forward_displacement_um < -5.0


def test_sparse_brain_mdn_spikes_below_bridge_threshold_do_not_move_body():
    sparse = lambda t, dt: {"descending:MDN": 1} if round(t * 1000) % 250 == 0 else {}  # noqa: E731
    result = _run(sparse)
    assert result.spike_counts["descending:MDN"] == 0
    assert abs(result.anatomical_forward_displacement_um) < 1.0


def test_only_identified_bridge_nodes_accept_brain_spikes():
    with pytest.raises(ValueError, match="brain-bridge"):
        _run(lambda t, dt: {"premotor:A18b:A1": 1}, duration_s=0.01)


def test_forward_bridge_burst_starts_traced_forward_wave_without_touch():
    config = load_axial_locomotion_config()
    config["parameters"]["brain_bridge_current_a_by_node"] = {"premotor:A27h:A6": 3e-10}
    # Six coincident brain spikes in one step (1.8 nA total) -> one A27h:A6 spike.
    burst = lambda t, dt: {"premotor:A27h:A6": 6} if 0.1 <= t < 0.101 else {}  # noqa: E731
    result = AxialLocomotionLarva(config).run(
        duration_s=4.0, record_trajectory_interval_s=None, descending_spike_source=burst
    )
    assert result.spike_counts["environment_touch:posterior"] == 0
    assert result.spike_counts["premotor:A27h:A6"] > 0
    assert result.premotor_spike_times_s["forward"]["A1"]  # the wave reached A1
    assert result.anatomical_forward_displacement_um > 20.0
    assert result.untraced_active_force_frames == 0


def test_brain_steering_counts_drive_only_the_named_side_relay():
    from oraclarva.steering import AxialSteeringLarva, PlanarLinearField

    larva = AxialSteeringLarva()
    larva.config["parameters"]["brain_steering_current_a"] = 4e-9
    result = larva.run(
        PlanarLinearField(baseline=0.5, gradient_y_per_m=5000.0),  # field ignored by the relay
        posterior_touch=True,
        duration_s=0.3,
        record_trajectory_interval_s=None,
        steering_spike_source=lambda: {"left": 1, "right": 0},
    )
    assert result.steering_spike_counts["field_sensory:left"] > 0
    assert result.steering_spike_counts["field_sensory:right"] == 0
