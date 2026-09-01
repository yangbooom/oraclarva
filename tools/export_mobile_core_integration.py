#!/usr/bin/env python3
"""Export deterministic stepped mobile-ABI snapshots and render projection."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from oraclarva.artifacts import first_mismatch


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "parity" / "repeat_crawl_native_v1.tsv"
DEFAULT_OUTPUT = ROOT / "data" / "mobile" / "mobile_core_integration_v1.json"
SEGMENTS = ("A6", "A5", "A4", "A3", "A2", "A1")
PYTHON_TRAJECTORY = ROOT / "data" / "trajectories" / "l1_repeat_crawl_v0.json"
SAMPLE_STRIDE = 320


def vectors(value: str, size: int) -> list[list[float]]:
    result = [list(map(float, item.split(","))) for item in value.split(";")]
    if len(result) != size:
        raise RuntimeError(f"expected {size} vectors, got {len(result)}")
    return result


def optional(value: str) -> float | None:
    return None if value == "-" else float(value)


def sampled_progress(frames: list[dict[str, Any]]) -> dict[str, float]:
    initial = frames[0]["physics_nodes_um"]
    forward_x = initial[0][0] - initial[-1][0]
    forward_y = initial[0][1] - initial[-1][1]
    magnitude = math.hypot(forward_x, forward_y)
    forward_x /= magnitude
    forward_y /= magnitude
    centers = [
        (
            sum(node[0] for node in frame["physics_nodes_um"]) / 13,
            sum(node[1] for node in frame["physics_nodes_um"]) / 13,
        )
        for frame in frames
    ]
    origin_x, origin_y = centers[0]
    positions = [
        (x - origin_x) * forward_x + (y - origin_y) * forward_y
        for x, y in centers
    ]
    peak = positions[0]
    retrace = 0.0
    backward = 0.0
    for left, right in zip(positions, positions[1:], strict=False):
        delta = right - left
        backward += max(0.0, -delta)
        peak = max(peak, right)
        retrace = max(retrace, peak - right)
    net = positions[-1] - positions[0]
    denominator = net + backward
    return {
        "net_forward_um": net,
        "maximum_backward_retrace_um": retrace,
        "cumulative_backward_travel_um": backward,
        "forward_progress_efficiency": (
            net / denominator if denominator > 0.0 else 0.0
        ),
    }


def render_artifact() -> str:
    with tempfile.TemporaryDirectory(prefix="oraclarva-mobile-export-") as temp:
        build = Path(temp)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build_mobile_core.py"),
                "--output",
                str(build),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        completed = subprocess.run(
            [
                str(build / "oraclarva-mobile-host"),
                str(FIXTURE),
                "--sample-stride",
                str(SAMPLE_STRIDE),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    metadata: list[str] | None = None
    frames: list[dict[str, Any]] = []
    summary: dict[str, Any] | None = None
    replay: dict[str, Any] | None = None
    for line in completed.stdout.splitlines():
        fields = line.split("\t")
        if fields[0] == "metadata":
            metadata = fields[1:]
        elif fields[0] == "frame":
            mesh = [
                list(map(float, item.split(",")))
                for item in fields[6].split(";")
            ]
            if any(len(item) != 4 for item in mesh):
                raise RuntimeError("mobile render vertex row is malformed")
            frames.append(
                {
                    "time_s": float(fields[2]),
                    "physics_nodes_um": vectors(fields[3], 13),
                    "segment_activation": dict(
                        zip(
                            SEGMENTS,
                            map(float, fields[4].split(",")),
                            strict=True,
                        )
                    ),
                    "node_force_model_units": vectors(fields[5], 13),
                    "render_vertices_um_activation": mesh,
                }
            )
        elif fields[0] == "summary":
            summary = {
                "steps": int(fields[1]),
                "canonical_fnv1a64": fields[2],
                "displacement_x_um": float(fields[3]),
                "feedback_force_frames": int(fields[4]),
                "all_active_forces_traced": fields[5] == "true",
                "complete_cycle_count": int(fields[6]),
                "physical_wave_cycle_count": int(fields[7]),
                "median_period_s": optional(fields[8]),
                "median_stride_um": optional(fields[9]),
                "median_wave_speed_segments_s": optional(fields[10]),
                "spike_counts": list(map(int, fields[11].split(","))),
                "first_spike_s": [
                    optional(item) for item in fields[12].split(",")
                ],
                "trace_valid": list(map(int, fields[13].split(","))),
            }
        elif fields[0] == "replay":
            replay = {
                "first_fnv1a64": fields[1],
                "reset_fnv1a64": fields[2],
                "status": fields[3],
            }
        else:
            raise RuntimeError(f"unknown mobile host row: {fields[0]}")

    fixture_rows = [
        line.split("\t")
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    fixture_values = {
        row[0]: row[1] for row in fixture_rows if len(row) == 2
    }
    dt_s = next(
        float(row[2])
        for row in fixture_rows
        if row[:2] == ["config", "dt_s"]
    )
    expected_steps = int(fixture_values["steps"])
    expected_duration_s = expected_steps * dt_s
    expected_frame_count = 1 + expected_steps // SAMPLE_STRIDE + (
        expected_steps % SAMPLE_STRIDE != 0
    )
    python = json.loads(PYTHON_TRAJECTORY.read_text(encoding="utf-8"))
    expected_metadata = [
        "1",
        fixture_values["schema"],
        fixture_values["model_id"],
        fixture_values["status"],
        "release_validated=false",
        fixture_values["config_sha256"],
        format(dt_s, ".17g"),
        fixture_values["neuron_count"],
        "13",
        "6",
        "302",
        "600",
    ]
    if metadata != expected_metadata:
        raise RuntimeError("mobile metadata/freeze boundary mismatch")
    if summary is None or replay is None:
        raise RuntimeError("mobile summary or replay row is missing")
    if (
        len(frames) != expected_frame_count
        or frames[0]["time_s"] != 0.0
        or frames[-1]["time_s"] != expected_duration_s
    ):
        raise RuntimeError("mobile artifact frame schedule is incomplete")
    if any(len(frame["render_vertices_um_activation"]) != 302 for frame in frames):
        raise RuntimeError("mobile render projection vertex count drifted")
    if (
        summary["steps"] != expected_steps
        or summary["complete_cycle_count"] != 3
        or summary["physical_wave_cycle_count"] != 3
        or summary["feedback_force_frames"]
        != python["result_summary"]["feedback_force_frames"]
        or summary["all_active_forces_traced"] is not True
        or summary["trace_valid"] != [1, 1, 1, 1, 1, 1]
        or len(summary["spike_counts"]) != 164
        or len(summary["first_spike_s"]) != 164
    ):
        raise RuntimeError("mobile causal/cycle summary gate failed")
    if (
        replay["status"] != "exact"
        or replay["first_fnv1a64"] != replay["reset_fnv1a64"]
        or replay["first_fnv1a64"] != summary["canonical_fnv1a64"]
    ):
        raise RuntimeError("mobile reset replay is not byte-stable")
    held_out = json.loads(
        (ROOT / "data" / "validation" / "repeat_crawl_held_out_v0.json").read_text()
    )
    if (
        held_out["release_validated"] is not False
        or held_out["status"] != "diagnostic_held_out_passed"
        or held_out["fail_closed"] is not True
        or held_out["evaluation_protocol"][
            "independent_validation_claim_available"
        ] is not False
    ):
        raise RuntimeError("mobile artifact lost non-independent held-out boundary")
    progress = sampled_progress(frames)
    python_summary = python["result_summary"]
    if (
        not all(python_summary["movement_gate"].values())
        or abs(progress["net_forward_um"] + summary["displacement_x_um"])
        > 1e-8
    ):
        raise RuntimeError("mobile artifact lost forward-progress boundary")

    artifact = {
        "schema_version": 1,
        "schema": "mobile_core_integration_v1",
        "model_id": metadata[2],
        "scientific_status": metadata[3],
        "release_validated": False,
        "host_tested_only": True,
        "android_ios_device_tested": False,
        "mobile_abi_version": int(metadata[0]),
        "frozen_config_sha256": metadata[5],
        "native_fixture": "data/parity/repeat_crawl_native_v1.tsv",
        "causal_contract": [
            "environment",
            "sensory_transduction",
            "neural_dynamics",
            "motor_neurons",
            "muscle_activation",
            "body_physics",
            "environment",
        ],
        "input_schedule": {
            "kind": "posterior_touch_environment_intensity",
            "intensity": 1.0,
            "start_step": 0,
            "exclusive_end_step": 2,
            "direct_behavior_command": False,
        },
        "fixed_step": {
            "dt_s": float(metadata[6]),
            "steps": expected_steps,
        },
        "snapshot": {
            "neuron_count": int(metadata[7]),
            "physics_node_count": int(metadata[8]),
            "wave_segment_count": int(metadata[9]),
            "sample_stride_steps": SAMPLE_STRIDE,
            "digest_algorithm": "canonical_little_endian_fnv1a64",
        },
        "render_projection": {
            "read_only": True,
            "internal_physics_nodes_exposed_as_render_vertices": False,
            "axial_samples_per_segment": 2,
            "radial_samples": 12,
            "vertex_count": int(metadata[10]),
            "triangle_count": int(metadata[11]),
            "watertight_manifold_tested": True,
        },
        "result_summary": summary,
        "movement_quality": {
            "retained_mobile_frames": progress,
            "full_timestep_python_oracle": {
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
        "reset_replay": replay,
        "held_out_behavior_status": (
            "diagnostic_held_out_passed_non_independent"
        ),
        "frames": frames,
    }
    return json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_artifact()
    if args.check:
        if not args.output.exists():
            print(f"mobile integration artifact is missing: {args.output}")
            return 1
        expected = json.loads(args.output.read_text(encoding="utf-8"))
        actual = json.loads(rendered)
        mismatch = first_mismatch(expected, actual)
        if mismatch is not None:
            print(f"mobile integration artifact is stale: {mismatch}")
            return 1
        print("mobile integration artifact is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
