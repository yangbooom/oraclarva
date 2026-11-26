import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from oraclarva.brain_sim import BrainParams, SignPolicy, build_network, resolve_signs, simulate


def _compiled(sign_b=1, contacts=160):
    neurons = [
        {"skid": "1", "fast_sign": 1},
        {"skid": "2", "fast_sign": sign_b},
        {"skid": "3", "fast_sign": None},
    ]
    edges = [
        {"pre": "1", "post": "2", "contacts_by_confidence": [0, 0, 0, 0, contacts]},
        {"pre": "2", "post": "3", "contacts_by_confidence": [0, 0, 0, 0, contacts]},
    ]
    return {"neurons": neurons, "edges": edges}


def test_sign_policies():
    neurons = [{"fast_sign": 1}, {"fast_sign": -1}, {"fast_sign": None}, {"fast_sign": None, "modulatory": True}]
    assert list(resolve_signs(neurons, SignPolicy(mode="excitatory"))) == [1, -1, 1, 0]
    assert list(resolve_signs(neurons, SignPolicy(mode="silent"))) == [1, -1, 0, 0]
    sampled = resolve_signs([{"fast_sign": None}] * 2000, SignPolicy(mode="sample", p_excitatory=0.7, seed=3))
    assert 0.65 < (sampled == 1).mean() < 0.75
    with pytest.raises(ValueError):
        SignPolicy(mode="nope")


def test_weights_follow_contacts_sign_and_wsyn():
    net = build_network(_compiled(sign_b=-1, contacts=4), SignPolicy(mode="silent"))
    w = net.weights.toarray()
    assert w[0, 1] == pytest.approx(4 * 0.275)
    assert w[1, 2] == pytest.approx(-4 * 0.275)


def test_excitatory_chain_propagates_and_inhibition_blocks():
    net = build_network(_compiled(sign_b=1, contacts=160), SignPolicy(mode="silent"))
    run = simulate(net, 300.0, poisson_inputs={0: 150.0}, seed=1)
    assert run.spike_counts[0] > 10 and run.spike_counts[1] > 0 and run.spike_counts[2] > 0
    net_inh = build_network(_compiled(sign_b=-1, contacts=160), SignPolicy(mode="silent"))
    run_inh = simulate(net_inh, 300.0, poisson_inputs={0: 150.0}, seed=1)
    assert run_inh.spike_counts[1] > 0 and run_inh.spike_counts[2] == 0


def test_no_input_no_activity_and_deterministic_seed():
    net = build_network(_compiled(), SignPolicy(mode="silent"))
    assert simulate(net, 50.0).spike_counts.sum() == 0
    a = simulate(net, 200.0, poisson_inputs={0: 100.0}, seed=7).spike_counts
    b = simulate(net, 200.0, poisson_inputs={0: 100.0}, seed=7).spike_counts
    assert (a == b).all()


def test_spike_delay_is_t_dly():
    params = BrainParams()
    net = build_network(_compiled(contacts=200), SignPolicy(mode="silent"))
    # one strong kick: neuron 0 fires at the first step it crosses threshold; neuron 1 must lag >= t_dly
    run0 = simulate(net, 1.5, poisson_inputs={0: 1e7}, seed=0)
    assert run0.spike_counts[1] == 0  # 1.5 ms < 1.8 ms delay
