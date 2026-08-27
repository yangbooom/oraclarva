from oraclarva.lif import LIFConfig, SparseLIFNetwork, Synapse
from oraclarva.smoke import run_smoke


def test_resting_neuron_does_not_spike():
    assert SparseLIFNetwork(1).run(20) == [()] * 20


def test_external_current_causes_spike():
    network = SparseLIFNetwork(1)
    events = network.run(10, {step: {0: 4e-9} for step in range(10)})
    assert any(0 in spikes for spikes in events)


def test_excitatory_synapse_propagates_spikes():
    counts = run_smoke()
    assert counts["sensory"] > counts["interneuron"] > 0
    assert counts["interneuron"] >= counts["motor"] > 0


def test_inhibitory_current_suppresses_target():
    cfg = LIFConfig(v_threshold_v=-0.060)
    control = SparseLIFNetwork(1, config=cfg)
    inhibited = SparseLIFNetwork(2, [Synapse(0, 1, 4e-9, "inhibitory")], cfg)
    control_events = control.run(8, {step: {0: 1.5e-9} for step in range(8)})
    inhibited_stimulus = {0: {0: 4e-9}}
    inhibited_stimulus.update({step: {1: 1.5e-9} for step in range(1, 8)})
    inhibited_events = inhibited.run(8, inhibited_stimulus)
    assert sum(0 in event for event in control_events) > 0
    assert sum(1 in event for event in inhibited_events) == 0


def test_lesion_breaks_causal_motor_path():
    assert run_smoke()["motor"] > 0
    assert run_smoke(lesion_interneuron=True)["motor"] == 0
