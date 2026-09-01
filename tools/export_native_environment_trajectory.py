#!/usr/bin/env python3
"""Export the checked Stage 9 C++ spatial environment trajectory."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from oraclarva.artifacts import first_mismatch

from native_environment_runtime import load_library, run_scenario


ROOT = Path(__file__).resolve().parents[1]
REPEAT_FIXTURE = ROOT / "data" / "parity" / "repeat_crawl_native_v1.tsv"
SPATIAL_FIXTURE = ROOT / "data" / "parity" / "spatial_environment_native_v1.tsv"
PYTHON_ORACLE = ROOT / "data" / "trajectories" / "l1_repeat_crawl_v0.json"
DEFAULT_OUTPUT = (
    ROOT / "data" / "trajectories" / "l1_native_environment_closed_loop_v1.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_parameters() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in SPATIAL_FIXTURE.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if fields[0] == "parameter":
            result[fields[1]] = fields[2]
    return result


def movement_metrics(frames: list[dict[str, Any]]) -> dict[str, float]:
    positions = [float(frame["anatomical_forward_um"]) for frame in frames]
    peak = positions[0]
    retrace = 0.0
    backward = 0.0
    for left, right in zip(positions, positions[1:]):
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


def compact(run: dict[str, Any]) -> dict[str, Any]:
    for frame in run["frames"]:
        frame.pop("spatial_spike_counts")
        frame.pop("spatial_last_step_spikes")
        frame.pop("segment_yaw_activation")
        frame.pop("segment_pitch_activation")
        frame.pop("adapted_light_w_m2")
        frame.pop("light_drive")
    return run


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def render_artifact() -> str:
    with tempfile.TemporaryDirectory(prefix="oraclarva-stage9-export-") as temp:
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
        library = load_library(build / "liboraclarva_mobile.so")
        scenarios = {
            "uniform": compact(
                run_scenario(
                    library,
                    REPEAT_FIXTURE,
                    SPATIAL_FIXTURE,
                    gradient_w_m3=(0.0, 0.0, 0.0),
                    steps=14600,
                    sample_stride=120,
                )
            ),
            "positive_y_gradient": compact(
                run_scenario(
                    library,
                    REPEAT_FIXTURE,
                    SPATIAL_FIXTURE,
                    gradient_w_m3=(0.0, 6000.0, 0.0),
                    steps=4500,
                    sample_stride=90,
                )
            ),
            "negative_y_gradient": compact(
                run_scenario(
                    library,
                    REPEAT_FIXTURE,
                    SPATIAL_FIXTURE,
                    gradient_w_m3=(0.0, -6000.0, 0.0),
                    steps=4500,
                    sample_stride=90,
                )
            ),
            "positive_z_gradient": compact(
                run_scenario(
                    library,
                    REPEAT_FIXTURE,
                    SPATIAL_FIXTURE,
                    gradient_w_m3=(0.0, 0.0, 6000.0),
                    steps=4500,
                    sample_stride=90,
                )
            ),
            "negative_z_gradient": compact(
                run_scenario(
                    library,
                    REPEAT_FIXTURE,
                    SPATIAL_FIXTURE,
                    gradient_w_m3=(0.0, 0.0, -6000.0),
                    steps=4500,
                    sample_stride=90,
                )
            ),
            "positive_y_right_sensor_lesion": compact(
                run_scenario(
                    library,
                    REPEAT_FIXTURE,
                    SPATIAL_FIXTURE,
                    gradient_w_m3=(0.0, 6000.0, 0.0),
                    steps=4500,
                    sample_stride=90,
                    sensory_lesion_channel="right",
                )
            ),
        }

    uniform = scenarios["uniform"]
    left = scenarios["positive_y_gradient"]["result_summary"]
    right = scenarios["negative_y_gradient"]["result_summary"]
    dorsal = scenarios["positive_z_gradient"]["result_summary"]
    ventral = scenarios["negative_z_gradient"]["result_summary"]
    lesion = scenarios["positive_y_right_sensor_lesion"]["result_summary"]
    progress = movement_metrics(uniform["frames"])
    oracle = json.loads(PYTHON_ORACLE.read_text(encoding="utf-8"))["result_summary"]
    gates = {
        "uniform_preserves_stage8_forward_path": abs(
            uniform["result_summary"]["anatomical_forward_um"]
            - oracle["forward_displacement_um"]
        )
        < 1e-8,
        "uniform_heading_is_symmetric": abs(
            uniform["result_summary"]["heading_change_deg"]
        )
        < 1e-12,
        "uniform_maximum_retrace_below_25_um": progress[
            "maximum_backward_retrace_um"
        ]
        < 25.0,
        "uniform_progress_efficiency_above_0_8": progress[
            "forward_progress_efficiency"
        ]
        > 0.8,
        "lateral_gradients_turn_opposite_directions": (
            left["heading_change_deg"] < -3.0
            and right["heading_change_deg"] > 3.0
        ),
        "lateral_mirror_heading_within_0_01_deg": abs(
            left["heading_change_deg"] + right["heading_change_deg"]
        )
        < 0.01,
        "lateral_mirror_displacement_within_0_01_um": abs(
            left["displacement_um"][1] + right["displacement_um"][1]
        )
        < 0.01,
        "dorsal_gradient_lifts_head": (
            dorsal["displacement_um"][2] > 25.0
            and dorsal["head_pitch_change_deg"] > 10.0
        ),
        "ventral_gradient_is_ground_limited": (
            ventral["displacement_um"][2] < 1.0
            and abs(ventral["head_pitch_change_deg"]) < 1.0
        ),
        "right_sensor_lesion_abolishes_positive_y_gradient_turn": abs(
            lesion["heading_change_deg"]
        )
        < 0.1,
    }
    require(all(gates.values()), f"Stage 9 gate failed: {gates}")
    parameters = fixture_parameters()
    require(
        parameters.get("integrated_proprioception_enabled") == "0",
        "uncalibrated spatial proprioception must remain disabled",
    )
    artifact = {
        "schema_version": 1,
        "schema": "l1_native_environment_closed_loop_v1",
        "model_id": "oraclarva_stage9_native_environment_v1",
        "scientific_status": "research_approximation",
        "release_validated": False,
        "host_tested_only": True,
        "android_ios_device_tested": False,
        "native_language": "C++17",
        "mobile_extension_abi_version": 1,
        "fixtures": {
            "repeat": {
                "path": str(REPEAT_FIXTURE.relative_to(ROOT)),
                "sha256": sha256(REPEAT_FIXTURE),
            },
            "spatial_environment": {
                "path": str(SPATIAL_FIXTURE.relative_to(ROOT)),
                "sha256": sha256(SPATIAL_FIXTURE),
                "neuron_count": 168,
                "synapse_count": 188,
            },
        },
        "causal_contract": [
            "physical_light_field",
            "four_surface_samples",
            "adaptive_sensory_transduction",
            "sparse_lif_dynamics",
            "motor_neurons",
            "muscle_activation",
            "shared_13_node_body_physics",
            "physical_light_field",
        ],
        "direct_behavior_command": False,
        "provenance": {
            "environment_and_transducer_parameters": "MODEL_FITTED",
            "spatial_network_topology": "ANATOMY_DERIVED",
            "body_and_muscle_parameters": "MODEL_FITTED",
        },
        "scope_boundaries": {
            "native_environment_modality": "light_only",
            "integrated_spatial_proprioception_enabled": False,
            "spatial_proprioception_reason": (
                "cross-coupling to axial repeat physics is not calibrated"
            ),
            "complete_visual_connectome": False,
            "validated_phototaxis_claim": False,
        },
        "field": {
            "value_at_origin_w_m2": 4.0,
            "bounds_w_m2": [0.0, 20.0],
            "gradient_magnitude_w_m3": 6000.0,
            "synthetic_diagnostic": True,
        },
        "movement_quality": progress,
        "acceptance_gates": gates,
        "scenarios": scenarios,
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
            print(f"Stage 9 artifact is missing: {args.output}")
            return 1
        mismatch = first_mismatch(
            json.loads(args.output.read_text(encoding="utf-8")),
            json.loads(rendered),
        )
        if mismatch is not None:
            print(f"Stage 9 artifact is stale: {mismatch}")
            return 1
        print("Stage 9 native environment artifact is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
