from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from oraclarva.repeat_crawl import (
    RepeatCrawlLarva,
    WAVE_SEGMENTS,
    load_repeat_crawl_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "organism" / "l1_repeat_crawl_v0.json"
TRAJECTORY = ROOT / "data" / "trajectories" / "l1_repeat_crawl_v0.json"
CALIBRATION = (
    ROOT / "data" / "validation" / "repeat_crawl_calibration_v0.json"
)
HELD_OUT = ROOT / "data" / "validation" / "repeat_crawl_held_out_v0.json"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_repeat_crawl_config_records_corrective_fit_without_independent_holdout_claim():
    config = load_repeat_crawl_config()
    assert config["release_validated"] is False
    assert config["topology"]["provenance"] == "ANATOMY_DERIVED"
    assert config["topology"]["periodic_stimulus"] is False
    assert config["topology"]["action_command"] is False
    assert (
        config["calibration"]["fit_status"]
        == "corrected_after_directional_mechanics_audit"
    )
    assert config["calibration"]["selection_used_held_out_values"] is False
    assert config["calibration"]["model_revision_after_prior_held_out_evaluation"] is True
    assert config["calibration"]["independent_held_out_claim_available"] is False
    assert config["body_state_transduction"]["provenance"] == "MODEL_FITTED"
    assert (
        config["named_fiber_body_coupling"]["parameter_provenance"]
        == "MODEL_FITTED"
    )


def test_checked_repeat_trajectory_has_three_physical_cycles_and_full_trace():
    artifact = load(TRAJECTORY)
    config_hash = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    assert artifact["generated_from"]["config_sha256"] == config_hash
    assert artifact["release_validated"] is False
    assert artifact["periodic_stimulus"] is False
    assert artifact["action_command"] is False
    assert artifact["node_count"] == 13
    assert tuple(
        artifact["supported_wave_segments_posterior_to_anterior"]
    ) == WAVE_SEGMENTS
    traces = artifact["causal_trace_examples"]
    assert tuple(traces) == WAVE_SEGMENTS
    for segment, trace in traces.items():
        assert trace["segment_id"] == segment
        assert trace["motor_node_id"]
        assert (
            trace["body_state_time_s"]
            <= trace["sensor_spike_time_s"]
            < trace["premotor_spike_time_s"]
            <= trace["motor_spike_time_s"]
        )
    summary = artifact["result_summary"]
    metrics = summary["cycle_metrics"]
    assert metrics["status"] == "measured"
    assert metrics["complete_cycle_count"] == 3
    assert metrics["physical_wave_cycle_count"] == 3
    assert summary["all_active_forces_sensory_traced"] is True
    assert summary["feedback_force_frames"] > 0
    assert metrics["median"]["stride_um"] > 0.0
    assert summary["forward_displacement_um"] > 0.0
    assert summary["displacement_x_um"] < 0.0
    assert all(summary["movement_gate"].values())
    assert summary["maximum_lateral_span_um"] == 0.0
    assert summary["maximum_planar_deviation_um"] == 0.0
    assert metrics["median"]["a1_a6_wave_speed_segments_s"] > 0.0
    for cycle in metrics["cycles"]:
        assert cycle["physical_onset_order_valid"] is True
        assert cycle["missing_physical_response"] == []


def test_corrected_calibration_passes_but_reused_held_out_fails_closed():
    calibration = load(CALIBRATION)
    held_out = load(HELD_OUT)
    assert calibration["status"] == "calibration_passed"
    assert calibration["passed"] is True
    assert not [row for row in calibration["comparisons"] if not row["passed"]]
    assert held_out["status"] == "diagnostic_held_out_failed"
    assert held_out["release_validated"] is False
    assert held_out["fail_closed"] is True
    protocol = held_out["evaluation_protocol"]
    assert protocol["evaluation_count"] == 2
    assert protocol["parameters_changed_after_prior_evaluation"] is True
    assert protocol["selection_used_held_out_values"] is False
    assert protocol["independent_validation_claim_available"] is False
    assert held_out["independent_validation_passed"] is False
    failed = {
        row["metric"] for row in held_out["comparisons"] if not row["passed"]
    }
    assert failed == {"A5.duty_cycle_percent", "A6.duty_cycle_percent"}


def test_zero_input_is_silent_and_does_not_translate():
    result = RepeatCrawlLarva().run(
        stimulate=False,
        duration_s=0.2,
        record_trajectory_interval_s=None,
    )
    assert sum(result.spike_counts.values()) == 0
    assert result.feedback_force_frames == 0
    assert result.displacement_x_um == pytest.approx(0.0, abs=1e-9)
    assert result.all_active_forces_sensory_traced is True


def test_each_lesion_layer_is_explicitly_registered_without_fallback():
    sensory = RepeatCrawlLarva(lesion_sensory_segment="A6")
    sensory_index = sensory.protocol.index_by_id[
        "mechanosensory:shortening:A6"
    ]
    assert sensory_index in sensory.protocol.network.lesioned

    premotor = RepeatCrawlLarva(lesion_premotor_segment="A4")
    premotor_index = premotor.protocol.index_by_id["premotor_A27h_like:A4"]
    assert premotor_index in premotor.protocol.network.lesioned

    source = sorted(sensory.projection.source_node_ids)[0]
    motor = RepeatCrawlLarva(lesion_motor_node_ids=(source,))
    assert motor.protocol.index_by_id[source] in motor.protocol.network.lesioned

    fiber = sensory.projection.mappings[0].fiber_id
    fiber_lesion = RepeatCrawlLarva(lesion_fiber_ids=(fiber,))
    assert fiber_lesion.protocol.lesion_fiber_ids == (fiber,)


def test_lesions_break_expected_downstream_stage_without_fallback_force():
    sensory = RepeatCrawlLarva(lesion_sensory_segment="A6").run(
        duration_s=0.9, record_trajectory_interval_s=None
    )
    assert sensory.premotor_spike_times_s["A6"] == (0.003,)
    assert sensory.premotor_spike_times_s["A5"] == ()

    premotor = RepeatCrawlLarva(lesion_premotor_segment="A4").run(
        duration_s=2.2, record_trajectory_interval_s=None
    )
    assert premotor.premotor_spike_times_s["A5"] == (0.6,)
    assert premotor.premotor_spike_times_s["A4"] == ()
    assert premotor.premotor_spike_times_s["A3"] == ()

    baseline = RepeatCrawlLarva()
    a6_nodes = baseline.protocol.source_nodes_by_segment["A6"]
    a6_fibers = tuple(
        item.fiber_id
        for item in baseline.projection.mappings
        if item.segment_id == "A6"
    )
    control = baseline.run(duration_s=0.08, record_trajectory_interval_s=None)
    motor = RepeatCrawlLarva(lesion_motor_node_ids=a6_nodes).run(
        duration_s=0.08, record_trajectory_interval_s=None
    )
    fiber = RepeatCrawlLarva(lesion_fiber_ids=a6_fibers).run(
        duration_s=0.08, record_trajectory_interval_s=None
    )
    assert control.feedback_force_frames > 0
    assert motor.premotor_spike_times_s["A6"] == (0.003,)
    assert motor.motor_spike_times_s["A6"] == ()
    assert motor.feedback_force_frames == 0
    assert fiber.premotor_spike_times_s["A6"] == (0.003,)
    assert fiber.motor_spike_times_s["A6"]
    assert fiber.feedback_force_frames == 0


def test_invalid_lesions_fail_closed():
    with pytest.raises(ValueError, match="sensory lesion"):
        RepeatCrawlLarva(lesion_sensory_segment="A7")
    with pytest.raises(ValueError, match="unknown motor lesion"):
        RepeatCrawlLarva(lesion_motor_node_ids=("crawl",))
    with pytest.raises(ValueError):
        RepeatCrawlLarva(lesion_fiber_ids=("unknown:fiber",))
