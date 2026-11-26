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
