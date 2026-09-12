#!/usr/bin/env python3
"""Evaluate axial locomotion against L1 calibration and shape gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from math import sqrt
from pathlib import Path
from typing import Any

from oraclarva.artifacts import first_mismatch


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "organism" / "l1_axial_locomotion_v1.json"
TARGETS = ROOT / "data" / "validation" / "greaney_2026_l1_kinematics_v0.json"
TRAJECTORY = ROOT / "data" / "trajectories" / "l1_axial_locomotion_v1.json"
CALIBRATION_OUTPUT = (
    ROOT / "data" / "validation" / "axial_locomotion_calibration_v1.json"
)
HELD_OUT_OUTPUT = (
    ROOT
    / "data"
    / "validation"
    / "axial_locomotion_diagnostic_held_out_v1.json"
)
FORWARD_WAVE = ("A6", "A5", "A4", "A3", "A2", "A1")


def comparison(
    metric: str,
    value: float | None,
    band: dict[str, Any],
) -> dict[str, Any]:
    passed = (
        value is not None
        and float(band["p10"]) <= value <= float(band["p90"])
    )
    return {
        "metric": metric,
        "model_value": value,
        "target_p10": band["p10"],
        "target_median": band["median"],
        "target_p90": band["p90"],
        "passed": passed,
    }


def _center(frame: dict[str, Any]) -> tuple[float, float, float]:
    nodes = frame["nodes_um"]
    count = len(nodes)
    return tuple(sum(float(node[axis]) for node in nodes) / count for axis in range(3))


def _length(frame: dict[str, Any], index: int) -> float:
    left = frame["nodes_um"][index]
    right = frame["nodes_um"][index + 1]
    return sqrt(sum((float(right[axis]) - float(left[axis])) ** 2 for axis in range(3)))


def _crossing_time(
    frames: list[dict[str, Any]],
    values: list[float],
    before_index: int,
    threshold: float,
) -> float:
    before = values[before_index]
    after = values[before_index + 1]
    if before == after:
        return float(frames[before_index + 1]["time_s"])
    fraction = (threshold - before) / (after - before)
    left_time = float(frames[before_index]["time_s"])
    right_time = float(frames[before_index + 1]["time_s"])
    return left_time + fraction * (right_time - left_time)


def _nearest_frame(frames: list[dict[str, Any]], time_s: float) -> int:
    return min(
        range(len(frames)),
        key=lambda index: abs(float(frames[index]["time_s"]) - time_s),
    )


def measure_forward_cycle(artifact: dict[str, Any]) -> dict[str, Any]:
    result = artifact["forward"]
    frames = result["trajectory_samples"]
    premotor = result["premotor_spike_times_s"]["forward"]
    boundaries = [float(value) for value in premotor["A6"]]
    if len(boundaries) < 2:
        raise ValueError("axial calibration requires two forward A6 waves")
    start_s, end_s = boundaries[:2]
    period_s = end_s - start_s
    start = _nearest_frame(frames, start_s)
    end = _nearest_frame(frames, end_s)
    sample_interval_s = float(artifact["sample_interval_s"])
    segment_index = {
        segment: artifact["body_segment_ids"].index(segment)
        for segment in FORWARD_WAVE
    }

    segments: dict[str, dict[str, float]] = {}
    physical_onsets: dict[str, float] = {}
    for segment in FORWARD_WAVE:
        values = [_length(frame, segment_index[segment]) for frame in frames]
        event_s = next(
            float(value)
            for value in premotor[segment]
            if start_s <= float(value) < end_s
        )
        event_index = _nearest_frame(frames, event_s)
        peak_end = min(end, event_index + round(0.1 / sample_interval_s) + 1)
        peak_index = max(
            range(max(start, event_index - 2), peak_end),
            key=values.__getitem__,
        )
        trough_index = min(range(peak_index, end), key=values.__getitem__)
        peak = values[peak_index]
        trough = values[trough_index]
        amplitude = peak - trough
        if amplitude <= 0.0:
            raise ValueError(f"{segment} lacks a physical contraction")
        threshold = peak - 0.25 * amplitude
        onset_before = next(
            index
            for index in range(peak_index, trough_index)
            if values[index] > threshold >= values[index + 1]
        )
        offset_before = next(
            index
            for index in range(trough_index, len(values) - 1)
            if values[index] < threshold <= values[index + 1]
        )
        onset_s = _crossing_time(frames, values, onset_before, threshold)
        offset_s = _crossing_time(frames, values, offset_before, threshold)
        maximum_shortening_rate = max(
            (values[index - 1] - values[index]) / sample_interval_s
            for index in range(peak_index + 1, trough_index + 1)
        )
        physical_onsets[segment] = onset_s
        segments[segment] = {
            "contraction_amplitude_percent": 100.0 * amplitude / peak,
            "shortening_rate_um_s": maximum_shortening_rate,
            "contraction_duration_s": offset_s - onset_s,
            "duty_cycle_percent": 100.0 * (offset_s - onset_s) / period_s,
            "onset_s": onset_s,
        }

    for posterior, anterior in zip(FORWARD_WAVE, FORWARD_WAVE[1:]):
        segments[anterior]["adjacent_onset_delay_cycle_fraction"] = (
            physical_onsets[anterior] - physical_onsets[posterior]
        ) / period_s

    positions = [-_center(frame)[0] for frame in frames]
    stride_um = positions[end] - positions[start]
    cumulative_opposite = sum(
        max(0.0, positions[index] - positions[index + 1])
        for index in range(start, end)
    )
    running_peak = positions[start]
    maximum_retrace = 0.0
    for position in positions[start : end + 1]:
        running_peak = max(running_peak, position)
        maximum_retrace = max(maximum_retrace, running_peak - position)
    progress_efficiency = (
        stride_um / (stride_um + cumulative_opposite)
        if stride_um > 0.0
        else 0.0
    )

    initial = frames[start]["nodes_um"]
    dx = float(initial[-1][0]) - float(initial[0][0])
    dy = float(initial[-1][1]) - float(initial[0][1])
    norm = sqrt(dx * dx + dy * dy)
    posterior = (dx / norm, dy / norm)
    minimum_alignment = 1.0
    minimum_chord_ratio = 1.0
    maximum_lateral_span = 0.0
    maximum_planar_deviation = 0.0
    maximum_extension_fraction = 0.0
    node_order_violations = 0
    initial_lengths = [
        _length(frames[start], index)
        for index in range(len(artifact["body_segment_ids"]))
    ]
    for frame in frames[start : end + 1]:
        nodes = frame["nodes_um"]
        lateral = [
            -posterior[1] * float(node[0]) + posterior[0] * float(node[1])
            for node in nodes
        ]
        maximum_lateral_span = max(
            maximum_lateral_span, max(lateral) - min(lateral)
        )
        chord_x = float(nodes[-1][0]) - float(nodes[0][0])
        chord_y = float(nodes[-1][1]) - float(nodes[0][1])
        chord = sqrt(chord_x * chord_x + chord_y * chord_y)
        polyline = 0.0
        for index in range(len(nodes) - 1):
            segment_x = float(nodes[index + 1][0]) - float(nodes[index][0])
            segment_y = float(nodes[index + 1][1]) - float(nodes[index][1])
            segment_norm = sqrt(segment_x * segment_x + segment_y * segment_y)
            polyline += segment_norm
            if segment_norm:
                alignment = (
                    segment_x * posterior[0] + segment_y * posterior[1]
                ) / segment_norm
                minimum_alignment = min(minimum_alignment, alignment)
                node_order_violations += int(alignment <= 0.0)
            maximum_extension_fraction = max(
                maximum_extension_fraction,
                _length(frame, index) / initial_lengths[index] - 1.0,
            )
        minimum_chord_ratio = min(
            minimum_chord_ratio, chord / polyline if polyline else 0.0
        )
        if chord:
            maximum_planar_deviation = max(
                maximum_planar_deviation,
                *(
                    abs(
                        chord_x * (float(node[1]) - float(nodes[0][1]))
                        - chord_y * (float(node[0]) - float(nodes[0][0]))
                    )
                    / chord
                    for node in nodes
                ),
            )

    return {
        "start_s": start_s,
        "end_s": end_s,
        "cycle_period_s": period_s,
        "cycle_frequency_hz": 1.0 / period_s,
        "stride_um": stride_um,
        "crawl_speed_um_s": stride_um / period_s,
        "a1_a6_wave_speed_segments_s": 5.0
        / (physical_onsets["A1"] - physical_onsets["A6"]),
        "segments": segments,
        "shape": {
            "maximum_opposite_retrace_um": maximum_retrace,
            "cumulative_opposite_travel_um": cumulative_opposite,
            "progress_efficiency": progress_efficiency,
            "maximum_lateral_span_um": maximum_lateral_span,
            "maximum_planar_deviation_um": maximum_planar_deviation,
            "minimum_axial_segment_alignment": minimum_alignment,
            "minimum_head_tail_chord_ratio": minimum_chord_ratio,
            "maximum_segment_extension_fraction": maximum_extension_fraction,
            "node_order_violation_count": node_order_violations,
        },
    }


def evaluate_partition(
    model: dict[str, Any],
    target: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = [
        comparison(metric, model[metric], target["cycle_metrics"][metric])
        for metric in (
            "crawl_speed_um_s",
            "stride_um",
            "cycle_period_s",
            "cycle_frequency_hz",
            "a1_a6_wave_speed_segments_s",
        )
    ]
    for segment in reversed(FORWARD_WAVE):
        for metric in (
            "contraction_amplitude_percent",
            "shortening_rate_um_s",
            "contraction_duration_s",
            "duty_cycle_percent",
        ):
            rows.append(
                comparison(
                    f"{segment}.{metric}",
                    model["segments"][segment][metric],
                    target["segments"][segment][metric],
                )
            )
    return rows


def diagnostic_adjacent_delays(
    model: dict[str, Any],
    target: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        comparison(
            f"{segment}.adjacent_onset_delay_cycle_fraction",
            model["segments"][segment][
                "adjacent_onset_delay_cycle_fraction"
            ],
            target["segments"][segment][
                "adjacent_onset_delay_cycle_fraction"
            ],
        )
        for segment in ("A1", "A2", "A3", "A4", "A5")
    ]


def _ordered(values: dict[str, Any], order: tuple[str, ...]) -> bool:
    first = [float(values[segment][0]) for segment in order if values[segment]]
    return len(first) == len(order) and first == sorted(first)


def measure_response_progress(
    result: dict[str, Any], *, direction: str
) -> dict[str, float]:
    sign = -1.0 if direction == "forward" else 1.0
    centers = [_center(frame)[0] for frame in result["trajectory_samples"]]
    positions = [sign * (value - centers[0]) for value in centers]
    cumulative_opposite = sum(
        max(0.0, positions[index] - positions[index + 1])
        for index in range(len(positions) - 1)
    )
    running_peak = 0.0
    maximum_retrace = 0.0
    for position in positions:
        running_peak = max(running_peak, position)
        maximum_retrace = max(maximum_retrace, running_peak - position)
    displacement = positions[-1]
    return {
        "directional_displacement_um": displacement,
        "maximum_opposite_retrace_um": maximum_retrace,
        "cumulative_opposite_travel_um": cumulative_opposite,
        "progress_efficiency": (
            displacement / (displacement + cumulative_opposite)
            if displacement > 0.0
            else 0.0
        ),
    }


def reports() -> tuple[dict[str, Any], dict[str, Any]]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    targets = json.loads(TARGETS.read_text(encoding="utf-8"))
    artifact = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    config_sha256 = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    if artifact["generated_from"]["config_sha256"] != config_sha256:
        raise ValueError("axial trajectory does not match its frozen config")
    model = measure_forward_cycle(artifact)
    calibration_rows = evaluate_partition(model, targets["calibration_targets"])
    held_out_rows = evaluate_partition(
        model, targets["held_out_validation_targets"]
    )
    adjacent_rows = diagnostic_adjacent_delays(
        model, targets["calibration_targets"]
    )

    gates = config["validation"]["directional_shape_gate"]
    shape = model["shape"]
    shape_gates = {
        "maximum_opposite_retrace": shape["maximum_opposite_retrace_um"]
        <= float(gates["maximum_opposite_retrace_um"]),
        "progress_efficiency": shape["progress_efficiency"]
        >= float(gates["minimum_progress_efficiency"]),
        "lateral_span": shape["maximum_lateral_span_um"]
        <= float(gates["maximum_lateral_span_um"]),
        "planar_deviation": shape["maximum_planar_deviation_um"]
        <= float(gates["maximum_planar_deviation_um"]),
        "axial_segment_alignment": shape["minimum_axial_segment_alignment"]
        >= float(gates["minimum_axial_segment_alignment"]),
        "head_tail_chord_ratio": shape["minimum_head_tail_chord_ratio"]
        >= float(gates["minimum_head_tail_chord_ratio"]),
        "segment_extension": shape["maximum_segment_extension_fraction"]
        <= float(gates["maximum_segment_extension_fraction"]),
        "node_order": shape["node_order_violation_count"] == 0,
    }
    forward = artifact["forward"]
    backward = artifact["backward"]
    response_progress = {
        "forward": measure_response_progress(forward, direction="forward"),
        "backward": measure_response_progress(backward, direction="backward"),
    }
    response_progress_gates = {
        direction: {
            "directional_displacement": values["directional_displacement_um"]
            >= float(gates["minimum_directional_displacement_um"]),
            "maximum_opposite_retrace": values["maximum_opposite_retrace_um"]
            <= float(gates["maximum_opposite_retrace_um"]),
            "progress_efficiency": values["progress_efficiency"]
            >= float(gates["minimum_progress_efficiency"]),
        }
        for direction, values in response_progress.items()
    }
    causal_gates = {
        "forward_neural_order": _ordered(
            forward["premotor_spike_times_s"]["forward"], FORWARD_WAVE
        ),
        "backward_neural_order": _ordered(
            backward["premotor_spike_times_s"]["backward"],
            tuple(reversed(FORWARD_WAVE)),
        ),
        "forward_force_trace_complete": forward[
            "all_active_forces_sensory_traced"
        ],
        "backward_force_trace_complete": backward[
            "all_active_forces_sensory_traced"
        ],
        "contact_has_no_direction_input": (
            artifact["continuous_ground_contact"]["movement_direction_input"]
            is False
            and forward["contact_direction_input"] is False
            and backward["contact_direction_input"] is False
        ),
        "shared_mapped_fibers": artifact["shared_mapped_fiber_count"] == 146,
        "forward_does_not_activate_t3_backward_proxy": (
            float(forward["t3_contact_proxy_peak_activation"]) == 0.0
        ),
        "backward_t3_proxy_is_active_and_neural_traced": (
            float(backward["t3_contact_proxy_peak_activation"]) > 0.0
            and backward["t3_contact_proxy_neural_traced"] is True
        ),
    }
    calibration_passed = (
        all(row["passed"] for row in calibration_rows)
        and all(shape_gates.values())
        and all(
            passed
            for by_direction in response_progress_gates.values()
            for passed in by_direction.values()
        )
        and all(causal_gates.values())
    )
    common = {
        "schema_version": 1,
        "model_id": config["model_id"],
        "release_validated": False,
        "target_dataset": targets["dataset_id"],
        "frozen_config_sha256": config_sha256,
        "trajectory": str(TRAJECTORY.relative_to(ROOT)),
        "sample_interval_s": artifact["sample_interval_s"],
        "model_metrics": model,
    }
    calibration = {
        **common,
        "partition": "calibration",
        "animal_count": targets["split"]["calibration_animal_count"],
        "status": (
            "calibration_passed" if calibration_passed else "calibration_failed"
        ),
        "comparisons": calibration_rows,
        "directional_shape_gates": shape_gates,
        "full_response_progress": response_progress,
        "full_response_progress_gates": response_progress_gates,
        "causal_gates": causal_gates,
        "adjacent_delay_diagnostic_not_acceptance_gate": adjacent_rows,
        "passed": calibration_passed,
        "interpretation": (
            "Forward L1 calibration accepts speed, stride, period, frequency, "
            "A1-A6 wave speed, contraction amplitude/rate/duration/duty, causal "
            "traceability, and distortion/backslip gates together. Nonuniform "
            "adjacent delays remain diagnostic because fitting them broke the "
            "closed-loop shape gates."
        ),
    }
    held_out_passed = all(row["passed"] for row in held_out_rows)
    held_out = {
        **common,
        "partition": "diagnostic_held_out",
        "animal_count": targets["split"]["validation_animal_count"],
        "status": (
            "diagnostic_held_out_passed"
            if held_out_passed
            else "diagnostic_held_out_failed"
        ),
        "comparisons": held_out_rows,
        "passed": held_out_passed,
        "independent_validation_passed": False,
        "selection_used_held_out_values": False,
        "fail_closed": True,
        "interpretation": (
            "The six-animal values were already visible in the repository. "
            "They are reported only as a diagnostic and cannot release-validate "
            "this model. No quantitative L1 backward target is available."
        ),
    }
    return calibration, held_out


def rendered_reports() -> tuple[str, str]:
    calibration, held_out = reports()
    return (
        json.dumps(calibration, indent=2, ensure_ascii=False) + "\n",
        json.dumps(held_out, indent=2, ensure_ascii=False) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    calibration, held_out = rendered_reports()
    outputs = (
        (CALIBRATION_OUTPUT, calibration),
        (HELD_OUT_OUTPUT, held_out),
    )
    if args.check:
        for path, rendered in outputs:
            if not path.exists():
                print(f"axial evaluation is missing: {path}")
                return 1
            mismatch = first_mismatch(
                json.loads(path.read_text(encoding="utf-8")),
                json.loads(rendered),
            )
            if mismatch:
                print(f"axial evaluation is stale: {path}: {mismatch}")
                return 1
        print("axial calibration and held-out diagnostic are current")
        return 0
    for path, rendered in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
