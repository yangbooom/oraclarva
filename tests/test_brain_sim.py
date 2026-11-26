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


def test_reweighted_matches_fresh_build_and_scales_rows():
    compiled = _compiled(sign_b=-1, contacts=10)
    net = build_network(compiled, SignPolicy(mode="silent"))
    same = net.reweighted()
    assert np.allclose(same.weights.toarray(), net.weights.toarray())
    scaled = net.reweighted(row_scale=np.array([2.0, 1.0, 1.0]))
    assert scaled.weights[0, 1] == pytest.approx(2 * 10 * 0.275)
    flipped = net.reweighted(signs=np.array([1, 1, 0]))
    assert flipped.weights[1, 2] == pytest.approx(10 * 0.275)


def test_late_counts_only_after_cutoff():
    net = build_network(_compiled(contacts=160), SignPolicy(mode="silent"))
    run = simulate(net, 300.0, poisson_inputs={0: 150.0}, stim_window_ms=(0.0, 100.0), seed=1, late_from_ms=200.0)
    assert run.late_counts is not None and run.late_counts.sum() == 0
    assert run.spike_counts[0] > 0


def _mb_compiled():
    # 0 = odor input -> 1 = KC -> 2 = MBON ; 3 = sugar input -> 4 = DAN
    neurons = [{"skid": str(i), "fast_sign": 1} for i in range(5)]
    edges = [
        {"pre": "0", "post": "1", "contacts_by_confidence": [0, 0, 0, 0, 160]},
        {"pre": "1", "post": "2", "contacts_by_confidence": [0, 0, 0, 0, 160]},
        {"pre": "3", "post": "4", "contacts_by_confidence": [0, 0, 0, 0, 160]},
    ]
    return {"neurons": neurons, "edges": edges}


def _plastic(net):
    from oraclarva.brain_sim import Plasticity

    p = Plasticity(
        kc_idx=np.array([1]), mbon_idx=np.array([2]), dan_idx=np.array([4]), modulation=np.array([[1.0]]), eta=2e-5
    )
    return p, p.attach(net)


def test_kc_mbon_weights_move_out_of_sparse_matrix_and_still_drive_mbon():
    net = build_network(_mb_compiled(), SignPolicy(mode="silent"))
    p, stripped = _plastic(net)
    assert stripped.weights[1, 2] == 0 and p.km[0, 0] == pytest.approx(160 * 0.275)
    p.learn = False
    run = simulate(stripped, 300.0, {0: 150.0}, seed=1, plasticity=p)
    assert run.spike_counts[2] > 0


def test_pairing_kc_with_dan_depresses_but_either_alone_does_not():
    net = build_network(_mb_compiled(), SignPolicy(mode="silent"))
    p, stripped = _plastic(net)
    simulate(stripped, 500.0, {0: 150.0}, seed=1, plasticity=p)  # odor only
    assert p.km[0, 0] == pytest.approx(p.km_initial[0, 0])
    simulate(stripped, 500.0, {3: 150.0}, seed=1, plasticity=p)  # sugar only
    assert p.km[0, 0] == pytest.approx(p.km_initial[0, 0])
    simulate(stripped, 500.0, {0: 150.0, 3: 150.0}, seed=1, plasticity=p)  # paired
    assert p.km[0, 0] < 0.9 * p.km_initial[0, 0]


def test_background_noise_creates_baseline_activity():
    net = build_network(_compiled(), SignPolicy(mode="silent"))
    quiet = simulate(net, 500.0, seed=2)
    noisy = simulate(net, 500.0, seed=2, background_hz=200.0, background_weight_mv=6.0)
    assert quiet.spike_counts.sum() == 0 and noisy.spike_counts.sum() > 0


def test_dopamine_threshold_blocks_weak_dan_activity():
    net = build_network(_mb_compiled(), SignPolicy(mode="silent"))
    p, stripped = _plastic(net)
    p.da_threshold = 1e9
    simulate(stripped, 500.0, {0: 150.0, 3: 150.0}, seed=1, plasticity=p)
    assert p.km[0, 0] == pytest.approx(p.km_initial[0, 0])
