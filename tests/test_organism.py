from oraclarva.organism import ClosedLoopLarva, load_closed_loop_config

SEGMENTS = ("A7", "A6", "A5", "A4", "A3", "A2", "A1", "T3")


def test_config_keeps_approximations_and_causal_contract_explicit():
    config = load_closed_loop_config()
    assert config["status"] == "research_approximation"
    assert config["topology"]["provenance"] == "ANATOMY_DERIVED"
    assert config["parameter_provenance"]["provenance"] == "MODEL_FITTED"
    assert config["parameter_provenance"]["fit_status"] == "phase_fitted_research_baseline"
    assert config["parameters"]["fitted_cycle_period_s"] == 2.5
    assert config["causal_contract"] == [
        "environment", "sensory_transduction", "neural_dynamics",
        "motor_neurons", "muscle_activation", "body_physics", "environment",
    ]


def test_touch_produces_ordered_neural_wave_contraction_and_forward_motion():
    result = ClosedLoopLarva().run()
    motor_onsets = [result.first_spike_s[f"motor_pool:{segment}"] for segment in SEGMENTS]
    assert all(onset is not None for onset in motor_onsets)
    assert motor_onsets == sorted(motor_onsets)
    assert len(set(motor_onsets)) == len(motor_onsets)
    for segment in SEGMENTS:
        premotor = result.first_spike_s[f"premotor_A27h_like:{segment}"]
        motor = result.first_spike_s[f"motor_pool:{segment}"]
        proprioceptor = result.first_spike_s[f"proprioceptor:{segment}"]
        assert premotor is not None and motor is not None and proprioceptor is not None
        assert premotor < motor < proprioceptor
        assert result.peak_activation[segment] > 0
        assert result.peak_shortening_fraction[segment] >= 0.05
    assert result.displacement_um < -1.0
    assert result.phase_fit_passed
    assert set(result.phase_fit) == set(SEGMENTS[:-1])
    assert all(
        item["inside_observed_p10_p90"] for item in result.phase_fit.values()
    )


def test_without_environmental_touch_nervous_system_and_body_remain_at_rest():
    result = ClosedLoopLarva().run(stimulate=False)
    assert sum(result.spike_counts.values()) == 0
    assert all(value == 0 for value in result.peak_activation.values())
    assert abs(result.displacement_um) < 1e-6
    assert not result.phase_fit_passed


def test_premotor_lesion_breaks_downstream_wave_instead_of_invoking_fallback_action():
    result = ClosedLoopLarva(lesion_premotor_segment="A4").run()
    for segment in ("A7", "A6", "A5"):
        assert result.spike_counts[f"motor_pool:{segment}"] > 0
    for segment in ("A4", "A3", "A2", "A1", "T3"):
        assert result.spike_counts[f"motor_pool:{segment}"] == 0
        assert result.peak_activation[segment] == 0
    assert not result.phase_fit_passed
    assert not hasattr(ClosedLoopLarva, "crawl")
    assert not hasattr(ClosedLoopLarva, "turn_left")
