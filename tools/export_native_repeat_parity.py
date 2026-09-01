#!/usr/bin/env python3
"""Compile and compare the C++17 repeat core with the checked Python oracle."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from oraclarva.artifacts import first_mismatch
from oraclarva.repeat_crawl import WAVE_SEGMENTS


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "parity" / "repeat_crawl_native_v1.tsv"
PYTHON_TRAJECTORY = (
    ROOT / "data" / "trajectories" / "l1_repeat_crawl_v0.json"
)
DEFAULT_OUTPUT = (
    ROOT / "data" / "parity" / "repeat_crawl_native_parity_v1.json"
)
NODE_TOLERANCE_UM = 5e-8
ACTIVATION_TOLERANCE = 5.1e-10
FORCE_TOLERANCE_MODEL_UNITS = 2e-7
SUMMARY_TOLERANCE = 1e-8
SAMPLE_TIME_TOLERANCE_S = 3e-15


def vectors(value: str) -> list[list[float]]:
    return [list(map(float, item.split(","))) for item in value.split(";")]


def native_run(binary: Path, arguments: tuple[str, ...] = ()) -> dict[str, Any]:
    completed = subprocess.run(
        [str(binary), str(FIXTURE), *arguments],
        check=True,
        text=True,
        capture_output=True,
    )
    parsed: dict[str, Any] = {
        "neurons": {},
        "premotor": {},
        "traces": {},
        "frames": [],
    }
    for line in completed.stdout.splitlines():
        fields = line.split("\t")
        if fields[0] == "metadata":
            parsed["metadata"] = fields[1:]
        elif fields[0] == "summary":
            parsed["summary"] = {
                "displacement_x_um": float(fields[1]),
                "feedback_force_frames": int(fields[2]),
                "all_active_forces_traced": fields[3] == "true",
                "complete_cycle_count": int(fields[4]),
                "physical_wave_cycle_count": int(fields[5]),
                "median_period_s": None if fields[6] == "-" else float(fields[6]),
                "median_stride_um": None if fields[7] == "-" else float(fields[7]),
                "median_wave_speed_segments_s": (
                    None if fields[8] == "-" else float(fields[8])
                ),
                "frame_count": int(fields[9]),
            }
        elif fields[0] == "neuron":
            parsed["neurons"][fields[2]] = {
                "count": int(fields[3]),
                "first_spike_s": (
                    None if fields[4] == "-" else float(fields[4])
                ),
            }
        elif fields[0] == "premotor":
            parsed["premotor"][fields[2]] = list(map(float, fields[3:]))
        elif fields[0] == "trace":
            parsed["traces"][fields[2]] = {
                "body_state_time_s": float(fields[3]),
                "sensor_index": int(fields[4]),
                "sensor_spike_time_s": float(fields[5]),
                "premotor_index": int(fields[6]),
                "premotor_spike_time_s": float(fields[7]),
                "motor_index": int(fields[8]),
                "motor_spike_time_s": float(fields[9]),
            }
        elif fields[0] == "frame":
            parsed["frames"].append(
                {
                    "time_s": float(fields[2]),
                    "nodes_um": vectors(fields[3]),
                    "segment_activation": list(
                        map(float, fields[4].split(","))
                    ),
                    "node_force_model_units": vectors(fields[5]),
                }
            )
        else:
            raise RuntimeError(f"unknown native output row {fields[0]}")
    if parsed["summary"]["frame_count"] != len(parsed["frames"]):
        raise RuntimeError("native frame count mismatch")
    return parsed


def maximum_error(left: Any, right: Any) -> float:
    if isinstance(left, list):
        return max(
            (
                maximum_error(a, b)
                for a, b in zip(left, right, strict=True)
            ),
            default=0.0,
        )
    return abs(float(left) - float(right))


def sampled_progress_metrics(frames: list[dict[str, Any]]) -> dict[str, float]:
    initial_nodes = frames[0]["nodes_um"]
    head = initial_nodes[0]
    tail = initial_nodes[-1]
    forward_x = head[0] - tail[0]
    forward_y = head[1] - tail[1]
    magnitude = math.hypot(forward_x, forward_y)
    forward_x /= magnitude
    forward_y /= magnitude
    centers = [
        (
            sum(node[0] for node in frame["nodes_um"]) / len(frame["nodes_um"]),
            sum(node[1] for node in frame["nodes_um"]) / len(frame["nodes_um"]),
        )
        for frame in frames
    ]
    origin_x, origin_y = centers[0]
    positions = [
        (x - origin_x) * forward_x + (y - origin_y) * forward_y
        for x, y in centers
    ]
    running_peak = positions[0]
    maximum_retrace = 0.0
    cumulative_backward = 0.0
    for left, right in zip(positions, positions[1:], strict=False):
        delta = right - left
        if delta < 0.0:
            cumulative_backward -= delta
        running_peak = max(running_peak, right)
        maximum_retrace = max(maximum_retrace, running_peak - right)
    net = positions[-1] - positions[0]
    denominator = net + cumulative_backward
    return {
        "net_forward_um": net,
        "maximum_backward_retrace_um": maximum_retrace,
        "cumulative_backward_travel_um": cumulative_backward,
        "forward_progress_efficiency": (
            net / denominator if denominator > 0.0 else 0.0
        ),
    }


def compile_native(output: Path) -> None:
    compiler = shutil.which("c++")
    if compiler is None:
        raise RuntimeError("C++ compiler is unavailable")
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(ROOT / "native" / "lif_core.cpp"),
            str(ROOT / "native" / "spatial_controller.cpp"),
            str(ROOT / "native" / "repeat_core.cpp"),
            str(ROOT / "native" / "repeat_main.cpp"),
            "-o",
            str(output),
        ],
        check=True,
    )


def render_report() -> str:
    python = json.loads(PYTHON_TRAJECTORY.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="oraclarva-native-repeat-") as temp:
        binary = Path(temp) / "oraclarva-native-repeat"
        compile_native(binary)
        native = native_run(binary)
        lesion_runs = {
            "zero_input": native_run(
                binary, ("--no-stimulus", "--steps", "200")
            ),
            "a6_sensory": native_run(
                binary, ("--sensory-lesion", "A6", "--steps", "900")
            ),
            "a4_premotor": native_run(
                binary, ("--premotor-lesion", "A4", "--steps", "2200")
            ),
            "a6_mapped_mn": native_run(
                binary, ("--motor-segment-lesion", "A6", "--steps", "80")
            ),
            "a6_fiber": native_run(
                binary, ("--fiber-segment-lesion", "A6", "--steps", "80")
            ),
        }

    expected_metadata = [
        "repeat_crawl_native_v1",
        python["model_id"],
        "research_approximation",
        "release_validated=false",
        python["generated_from"]["config_sha256"],
    ]
    if native["metadata"] != expected_metadata:
        raise RuntimeError("native repeat metadata/freeze mismatch")
    python_summary = python["result_summary"]
    for label, expected_count in python_summary["spike_counts"].items():
        actual = native["neurons"].get(label)
        if actual is None or actual["count"] != expected_count:
            raise RuntimeError(f"native spike-count mismatch for {label}")
        expected_first = python_summary["first_spike_s"][label]
        actual_first = actual["first_spike_s"]
        if expected_first is None:
            if actual_first is not None:
                raise RuntimeError(f"native unexpected spike for {label}")
        elif actual_first is None or abs(actual_first - expected_first) > 1e-15:
            raise RuntimeError(f"native first-spike mismatch for {label}")

    python_frames = python["frames"]
    native_frames = native["frames"]
    if len(python_frames) != len(native_frames):
        raise RuntimeError("Python/native normal frame-count mismatch")
    max_node = 0.0
    max_activation = 0.0
    max_force = 0.0
    for expected, actual in zip(python_frames, native_frames, strict=True):
        if abs(float(expected["time_s"]) - actual["time_s"]) > SAMPLE_TIME_TOLERANCE_S:
            raise RuntimeError("Python/native sample time mismatch")
        max_node = max(
            max_node,
            maximum_error(expected["nodes_um"], actual["nodes_um"]),
        )
        expected_activation = [
            expected["segment_activation"][segment]
            for segment in WAVE_SEGMENTS
        ]
        max_activation = max(
            max_activation,
            maximum_error(
                expected_activation, actual["segment_activation"]
            ),
        )
        max_force = max(
            max_force,
            maximum_error(
                expected["node_force_model_units"],
                actual["node_force_model_units"],
            ),
        )
    if max_node > NODE_TOLERANCE_UM:
        raise RuntimeError(f"native node error {max_node} exceeds tolerance")
    if max_activation > ACTIVATION_TOLERANCE:
        raise RuntimeError(
            f"native activation error {max_activation} exceeds tolerance"
        )
    if max_force > FORCE_TOLERANCE_MODEL_UNITS:
        raise RuntimeError(f"native force error {max_force} exceeds tolerance")

    cycle = python_summary["cycle_metrics"]
    model = cycle["median"]
    native_summary = native["summary"]
    summary_errors = {
        "displacement_x_um": abs(
            native_summary["displacement_x_um"]
            - python_summary["displacement_x_um"]
        ),
        "period_s": abs(
            native_summary["median_period_s"] - model["period_s"]
        ),
        "stride_um": abs(
            native_summary["median_stride_um"] - model["stride_um"]
        ),
        "wave_speed_segments_s": abs(
            native_summary["median_wave_speed_segments_s"]
            - model["a1_a6_wave_speed_segments_s"]
        ),
    }
    python_sampled_progress = sampled_progress_metrics(python_frames)
    native_sampled_progress = sampled_progress_metrics(native_frames)
    progress_errors = {
        key: abs(native_sampled_progress[key] - python_sampled_progress[key])
        for key in python_sampled_progress
    }
    if max(summary_errors.values()) > SUMMARY_TOLERANCE:
        raise RuntimeError("native repeat summary exceeds tolerance")
    if max(progress_errors.values()) > SUMMARY_TOLERANCE:
        raise RuntimeError("native repeat progress metrics exceed tolerance")
    if not all(python_summary["movement_gate"].values()):
        raise RuntimeError("Python repeat movement gate failed")
    if (
        native_summary["feedback_force_frames"]
        != python_summary["feedback_force_frames"]
        or native_summary["complete_cycle_count"]
        != cycle["complete_cycle_count"]
        or native_summary["physical_wave_cycle_count"]
        != cycle["physical_wave_cycle_count"]
        or native_summary["all_active_forces_traced"] is not True
    ):
        raise RuntimeError("native repeat causal/cycle count mismatch")

    if set(native["traces"]) != set(WAVE_SEGMENTS):
        raise RuntimeError("native repeat trace examples are incomplete")
    for trace in native["traces"].values():
        if not (
            trace["body_state_time_s"]
            <= trace["sensor_spike_time_s"]
            < trace["premotor_spike_time_s"]
            <= trace["motor_spike_time_s"]
        ):
            raise RuntimeError("native repeat trace ordering failed")

    zero = lesion_runs["zero_input"]
    sensory = lesion_runs["a6_sensory"]
    premotor = lesion_runs["a4_premotor"]
    motor = lesion_runs["a6_mapped_mn"]
    fiber = lesion_runs["a6_fiber"]
    lesion_gates = {
        "zero_input": (
            sum(item["count"] for item in zero["neurons"].values()) == 0
            and zero["summary"]["feedback_force_frames"] == 0
            and abs(zero["summary"]["displacement_x_um"]) <= 1e-12
        ),
        "a6_sensory": (
            sensory["premotor"]["A6"] == [0.003]
            and sensory["premotor"]["A5"] == []
        ),
        "a4_premotor": (
            premotor["premotor"]["A5"] == [0.6]
            and premotor["premotor"]["A4"] == []
            and premotor["premotor"]["A3"] == []
        ),
        "a6_mapped_mn": (
            motor["premotor"]["A6"] == [0.003]
            and motor["summary"]["feedback_force_frames"] == 0
        ),
        "a6_fiber": (
            fiber["premotor"]["A6"] == [0.003]
            and fiber["summary"]["feedback_force_frames"] == 0
        ),
    }
    if not all(lesion_gates.values()):
        raise RuntimeError("native repeat lesion gate failed")

    frame_indices = [
        round(index * (len(python_frames) - 1) / 50)
        for index in range(51)
    ]
    paired_frames = []
    for index in frame_indices:
        expected = python_frames[index]
        actual = native_frames[index]
        paired_frames.append(
            {
                "time_s": expected["time_s"],
                "python_nodes_um": expected["nodes_um"],
                "native_nodes_um": actual["nodes_um"],
                "segment_activation": expected["segment_activation"],
                "frame_max_node_error_um": maximum_error(
                    expected["nodes_um"], actual["nodes_um"]
                ),
                "frame_max_force_error_model_units": maximum_error(
                    expected["node_force_model_units"],
                    actual["node_force_model_units"],
                ),
            }
        )

    report = {
        "schema_version": 1,
        "schema": "repeat_crawl_native_parity_v1",
        "model_id": python["model_id"],
        "status": "numerical_parity_passed",
        "release_validated": False,
        "frozen_config_sha256": python["generated_from"]["config_sha256"],
        "python_oracle": str(PYTHON_TRAJECTORY.relative_to(ROOT)),
        "native_fixture": str(FIXTURE.relative_to(ROOT)),
        "causal_contract": python["causal_contract"],
        "tolerances": {
            "sample_time_s": SAMPLE_TIME_TOLERANCE_S,
            "sampled_node_um": NODE_TOLERANCE_UM,
            "segment_activation": ACTIVATION_TOLERANCE,
            "node_force_model_units": FORCE_TOLERANCE_MODEL_UNITS,
            "summary_absolute": SUMMARY_TOLERANCE,
            "spike_count": 0,
            "first_spike_s": 1e-15,
        },
        "observed_maximum_errors": {
            "sampled_node_um": max_node,
            "segment_activation": max_activation,
            "node_force_model_units": max_force,
            **summary_errors,
            **{
                f"sampled_{key}": value
                for key, value in progress_errors.items()
            },
        },
        "exact_counts": {
            "neurons": len(native["neurons"]),
            "synapses": 307,
            "mapped_sources": 144,
            "mapped_fibers": 146,
            "body_nodes": 13,
            "sampled_frames": len(native_frames),
            "complete_cycles": native_summary["complete_cycle_count"],
            "physical_wave_cycles": native_summary[
                "physical_wave_cycle_count"
            ],
            "feedback_force_frames": native_summary[
                "feedback_force_frames"
            ],
        },
        "lesion_gates": lesion_gates,
        "sampled_progress": {
            "python": python_sampled_progress,
            "native": native_sampled_progress,
            "full_timestep_python": {
                "maximum_backward_retrace_um": python_summary[
                    "maximum_backward_retrace_um"
                ],
                "cumulative_backward_travel_um": python_summary[
                    "cumulative_backward_travel_um"
                ],
                "forward_progress_efficiency": python_summary[
                    "forward_progress_efficiency"
                ],
            },
            "movement_gate": python_summary["movement_gate"],
        },
        "all_active_forces_traced": True,
        "held_out_behavior_status": (
            "diagnostic_passed_but_non_independent"
        ),
        "paired_frames": paired_frames,
    }
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_report()
    if args.check:
        if not args.output.exists():
            print(f"native repeat parity report is missing: {args.output}")
            return 1
        mismatch = first_mismatch(
            json.loads(args.output.read_text(encoding="utf-8")),
            json.loads(rendered),
        )
        if mismatch:
            print(f"native repeat parity report is stale: {mismatch}")
            return 1
        print("native repeat parity report is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
