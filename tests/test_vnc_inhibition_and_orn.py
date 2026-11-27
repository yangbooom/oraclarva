"""GVLI wave-lagged inhibition, the SEZ-DN1 stop relay and the ORN transducer."""

import numpy as np
import pytest

from oraclarva.axial import AxialLocomotionLarva, gvli_inputs, load_axial_locomotion_config
from oraclarva.brain_body import OrnTransducer


def _config(**params):
    config = load_axial_locomotion_config()
    config["parameters"].update(params)
    return config


def test_gvli_and_sez_dn1_are_absent_by_default():
    labels = AxialLocomotionLarva(_config()).protocol.labels
    assert not any(":GVLI:" in label for label in labels)
    assert "descending:SEZ-DN1" not in labels


def test_gvli_inputs_are_two_and_three_segments_anterior():
    assert gvli_inputs() == {"A6": ("A4", "A3"), "A5": ("A3", "A2"), "A4": ("A2", "A1"), "A3": ("A1",)}


def test_gvli_fires_only_after_the_wave_front_is_two_segments_ahead():
    larva = AxialLocomotionLarva(_config(gvli_inhibitory_current_a=2e-10, gvli_gate_tau_s=1.0))
    result = larva.run(posterior_touch=True, duration_s=1.5, record_trajectory_interval_s=None)
    a4 = result.premotor_spike_times_s["forward"]["A4"]
    assert a4, "the wave should reach A4 within 1.5 s"
    assert larva.protocol.spike_counts["inhibitory:GVLI:A6"] >= 1
    assert larva.protocol.first_spike_s["inhibitory:GVLI:A6"] >= a4[0]
    assert larva.protocol.gvli_gate["A6"] > 0.0
    assert larva.protocol.spike_counts["inhibitory:GVLI:A3"] == 0  # its input A1 not reached yet


def test_sez_dn1_relay_blocks_posterior_wave_initiation():
    def source(t, dt):
        return {"descending:SEZ-DN1": 5} if t < 0.05 else {}

    params = {"sez_dn1_inhibitory_current_a": 8e-9}
    blocked = AxialLocomotionLarva(_config(**params)).run(
        posterior_touch=True, duration_s=0.3, record_trajectory_interval_s=None, descending_spike_source=source
    )
    control = AxialLocomotionLarva(_config(**params)).run(
        posterior_touch=True, duration_s=0.3, record_trajectory_interval_s=None
    )
    assert blocked.spike_counts["descending:SEZ-DN1"] > 0
    assert blocked.spike_counts["premotor:A27h:A6"] == 0
    assert control.spike_counts["premotor:A27h:A6"] == 1


def test_sez_dn1_bridge_requires_the_relay_to_be_enabled():
    with pytest.raises(ValueError, match="not enabled"):
        AxialLocomotionLarva(_config()).run(
            duration_s=0.01, record_trajectory_interval_s=None,
            descending_spike_source=lambda t, dt: {"descending:SEZ-DN1": 1},
        )


class _FakeBrain:
    def __init__(self, n):
        self.bg_prob = np.full(n, 0.01)
        self.step = 0
        self.state = (None, None, None, None, np.zeros(n, dtype=np.int64))


def test_orn_transducer_adapts_and_inhibits_after_a_decrease():
    brain = _FakeBrain(4)
    orn = OrnTransducer(brain, np.array([0, 1]), gain_hz=100.0, beta=0.7, tau_s=1.0, inhibition_scale=0.2)
    onset = orn(1.0, 1e-3)
    assert onset[0] == pytest.approx(100.0 * (1.0 - 0.7 * 1e-3), rel=1e-6)
    for _ in range(5000):
        sustained = orn(1.0, 1e-3)
    assert 0.0 < sustained[0] < 0.5 * onset[0]  # adapted but still above zero
    assert brain.bg_prob[0] == pytest.approx(0.01)
    after = orn(0.0, 1e-3)  # step decrease
    assert after == {}
    assert brain.bg_prob[0] == 0.0 and brain.bg_prob[1] == 0.0  # offset inhibition
    assert brain.bg_prob[2] == pytest.approx(0.01)  # other neurons untouched
    assert brain.state[4][0] == np.iinfo(np.int64).max
    for _ in range(10000):
        orn(0.0, 1e-3)
    assert brain.bg_prob[0] == pytest.approx(0.01)  # recovered to spontaneous input
    assert brain.state[4][0] < np.iinfo(np.int64).max
