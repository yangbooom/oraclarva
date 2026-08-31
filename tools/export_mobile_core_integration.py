#!/usr/bin/env python3
"""Export deterministic stepped mobile-ABI snapshots and render projection."""

from __future__ import annotations

import argparse
import json
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


def vectors(value: str, size: int) -> list[list[float]]:
    result = [list(map(float, item.split(","))) for item in value.split(";")]
    if len(result) != size:
        raise RuntimeError(f"expected {size} vectors, got {len(result)}")
    return result


def optional(value: str) -> float | None:
    return None if value == "-" else float(value)


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
                "320",
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

    expected_metadata = [
        "1",
        "repeat_crawl_native_v1",
        "dmel_l1_repeat_crawl_v0",
        "research_approximation",
        "release_validated=false",
        "5cbaec6a716cf2b8dd2d8e053b00469f5e9f09389fa74645c17a148143b936e3",
        "0.001",
        "164",
        "13",
        "6",
        "302",
        "600",
    ]
    if metadata != expected_metadata:
        raise RuntimeError("mobile metadata/freeze boundary mismatch")
    if summary is None or replay is None:
        raise RuntimeError("mobile summary or replay row is missing")
    if len(frames) != 51 or frames[0]["time_s"] != 0.0 or frames[-1]["time_s"] != 16.0:
        raise RuntimeError("mobile artifact must contain 51 complete frames")
    if any(len(frame["render_vertices_um_activation"]) != 302 for frame in frames):
        raise RuntimeError("mobile render projection vertex count drifted")
    if (
        summary["steps"] != 16000
        or summary["complete_cycle_count"] != 3
        or summary["physical_wave_cycle_count"] != 3
        or summary["feedback_force_frames"] != 15993
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
    if held_out["release_validated"] is not False:
        raise RuntimeError("mobile artifact lost held-out failure boundary")

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
        "fixed_step": {"dt_s": float(metadata[6]), "steps": 16000},
        "snapshot": {
            "neuron_count": int(metadata[7]),
            "physics_node_count": int(metadata[8]),
            "wave_segment_count": int(metadata[9]),
            "sample_stride_steps": 320,
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
        "reset_replay": replay,
        "held_out_behavior_status": "held_out_failed_amplitude_and_duty",
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
