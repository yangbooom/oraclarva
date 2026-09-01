from __future__ import annotations

import json
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from native_environment_runtime import load_library, run_scenario  # noqa: E402
from oraclarva.body import load_body_spec  # noqa: E402
from oraclarva.spatial import SpatialClosedLoopLarva  # noqa: E402


REPEAT_FIXTURE = ROOT / "data" / "parity" / "repeat_crawl_native_v1.tsv"
SPATIAL_FIXTURE = ROOT / "data" / "parity" / "spatial_environment_native_v1.tsv"
TRAJECTORY = (
    ROOT / "data" / "trajectories" / "l1_native_environment_closed_loop_v1.json"
)


@pytest.fixture(scope="module")
def stage9_build(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    output = tmp_path_factory.mktemp("native-environment")
    subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "tools" / "build_mobile_core.py"),
            "--output",
            str(output),
        ],
        check=True,
    )
    shared = output / "liboraclarva_mobile.so"
    return {"shared": shared, "library": load_library(shared)}


@lru_cache(maxsize=None)
def _scenario(
    shared: str,
    gradient: tuple[float, float, float],
    steps: int,
    sample_stride: int,
    sensory_lesion: str | None = None,
) -> dict[str, object]:
    return run_scenario(
        load_library(Path(shared)),
        REPEAT_FIXTURE,
        SPATIAL_FIXTURE,
        gradient_w_m3=gradient,
        steps=steps,
        sample_stride=sample_stride,
        sensory_lesion_channel=sensory_lesion,
    )


def test_stage9_fixture_is_generated_from_python_spatial_network():
    subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "tools" / "export_native_spatial_fixture.py"),
            "--check",
        ],
        check=True,
    )
    text = SPATIAL_FIXTURE.read_text()
    assert "neuron_count\t168" in text
    assert "synapse_count\t188" in text
    assert "parameter\tintegrated_proprioception_enabled\t0" in text
    assert "release_validated\tfalse" in text


def _movement_metrics(frames: list[dict[str, object]]) -> tuple[float, float]:
    positions = [float(frame["anatomical_forward_um"]) for frame in frames]
    peak = positions[0]
    maximum_retrace = 0.0
    cumulative_forward = 0.0
    cumulative_backward = 0.0
    for before, after in zip(positions, positions[1:]):
        delta = after - before
        if delta >= 0.0:
            cumulative_forward += delta
        else:
            cumulative_backward -= delta
        peak = max(peak, after)
        maximum_retrace = max(maximum_retrace, peak - after)
    efficiency = cumulative_forward / (cumulative_forward + cumulative_backward)
    return maximum_retrace, efficiency


def test_uniform_light_preserves_corrected_three_cycle_forward_path(
    stage9_build: dict[str, object],
):
    result = _scenario(
        str(stage9_build["shared"]), (0.0, 0.0, 0.0), 14600, 30
    )
    summary = result["result_summary"]
    oracle = json.loads(
        (ROOT / "data" / "trajectories" / "l1_repeat_crawl_v0.json").read_text()
    )["result_summary"]
    assert summary["anatomical_forward_um"] == pytest.approx(
        oracle["forward_displacement_um"], abs=1e-8
    )
    assert summary["heading_change_deg"] == pytest.approx(0.0, abs=1e-12)
    assert summary["receptor_current"] == pytest.approx([0.5] * 4, abs=1e-12)
    retrace, efficiency = _movement_metrics(result["frames"])
    assert retrace <= 25.0
    assert efficiency >= 0.8


def test_mirrored_lateral_fields_mirror_native_body_response(
    stage9_build: dict[str, object],
):
    positive = _scenario(
        str(stage9_build["shared"]), (0.0, 6000.0, 0.0), 4500, 60
    )["result_summary"]
    negative = _scenario(
        str(stage9_build["shared"]), (0.0, -6000.0, 0.0), 4500, 60
    )["result_summary"]
    assert positive["anatomical_forward_um"] > 100.0
    assert negative["anatomical_forward_um"] > 100.0
    assert positive["displacement_um"][1] == pytest.approx(
        -negative["displacement_um"][1], abs=0.01
    )
    assert positive["heading_change_deg"] == pytest.approx(
        -negative["heading_change_deg"], abs=0.002
    )
    assert abs(positive["heading_change_deg"]) > 3.0
    assert positive["receptor_current"][0] == pytest.approx(
        negative["receptor_current"][1], abs=2e-6
    )
    assert positive["receptor_current"][1] == pytest.approx(
        negative["receptor_current"][0], abs=2e-6
    )


def test_dorsal_field_lifts_head_and_ventral_field_is_ground_limited(
    stage9_build: dict[str, object],
):
    dorsal = _scenario(
        str(stage9_build["shared"]), (0.0, 0.0, 6000.0), 4500, 60
    )["result_summary"]
    ventral = _scenario(
        str(stage9_build["shared"]), (0.0, 0.0, -6000.0), 4500, 60
    )["result_summary"]
    assert dorsal["head_pitch_change_deg"] > 10.0
    assert dorsal["displacement_um"][2] > 30.0
    assert abs(ventral["head_pitch_change_deg"]) < 0.1
    assert ventral["displacement_um"][2] < 1.0
    assert dorsal["anatomical_forward_um"] > 0.0
    assert ventral["anatomical_forward_um"] > 0.0


def test_environment_sensory_lesion_breaks_turn_before_motor_physics(
    stage9_build: dict[str, object],
):
    intact = _scenario(
        str(stage9_build["shared"]), (0.0, 6000.0, 0.0), 4500, 60
    )["result_summary"]
    lesioned = _scenario(
        str(stage9_build["shared"]),
        (0.0, 6000.0, 0.0),
        4500,
        60,
        "right",
    )["result_summary"]
    assert abs(intact["heading_change_deg"]) > 3.0
    assert lesioned["heading_change_deg"] == pytest.approx(0.0, abs=1e-12)
    assert lesioned["spatial_spike_total"] < intact["spatial_spike_total"]
    assert lesioned["anatomical_forward_um"] > intact["anatomical_forward_um"]


def _surface_positions(
    nodes_um: list[list[float]],
) -> tuple[tuple[float, float, float], ...]:
    head = tuple(value * 1e-6 for value in nodes_um[0])
    next_node = tuple(value * 1e-6 for value in nodes_um[1])
    tangent = tuple(next_node[index] - head[index] for index in range(3))
    magnitude = math.sqrt(sum(value * value for value in tangent))
    tangent = tuple(value / magnitude for value in tangent)
    lateral = (-tangent[1], tangent[0], 0.0)
    lateral_magnitude = math.hypot(lateral[0], lateral[1])
    lateral = tuple(value / lateral_magnitude for value in lateral)
    dorsal = (
        tangent[1] * lateral[2] - tangent[2] * lateral[1],
        tangent[2] * lateral[0] - tangent[0] * lateral[2],
        tangent[0] * lateral[1] - tangent[1] * lateral[0],
    )
    dorsal_magnitude = math.sqrt(sum(value * value for value in dorsal))
    dorsal = tuple(value / dorsal_magnitude for value in dorsal)
    geometry = load_body_spec().segment_geometry()[0]
    return (
        tuple(head[index] - lateral[index] * geometry.width_m / 2 for index in range(3)),
        tuple(head[index] + lateral[index] * geometry.width_m / 2 for index in range(3)),
        tuple(head[index] + dorsal[index] * geometry.height_m / 2 for index in range(3)),
        tuple(head[index] - dorsal[index] * geometry.height_m / 2 for index in range(3)),
    )


def test_python_native_light_transduction_and_168_lif_spikes_match(
    stage9_build: dict[str, object],
):
    result = _scenario(
        str(stage9_build["shared"]), (0.0, 6000.0, 0.0), 200, 1
    )
    frames = result["frames"]
    python = SpatialClosedLoopLarva()
    network = python.network
    counts = [0] * network.neuron_count
    adapted: list[float] | None = None
    coupling = 1.0 - math.exp(-0.001 / 0.5)
    for step, frame in enumerate(frames[1:]):
        previous = frames[step]
        positions = _surface_positions(previous["physics_nodes_um"])
        expected_raw = [
            min(20.0, max(0.0, 4.0 + 6000.0 * position[1]))
            for position in positions
        ]
        assert frame["raw_light_w_m2"] == pytest.approx(expected_raw, abs=1e-12)
        if adapted is None:
            adapted = expected_raw.copy()
        mean = sum(expected_raw) / 4.0
        drive = [
            0.4 * (value - mean) / 4.0
            + 0.6 * (value - adapted[index]) / 4.0
            for index, value in enumerate(expected_raw)
        ]
        current = [min(1.0, max(0.0, 0.5 + value)) for value in drive]
        assert frame["adapted_light_w_m2"] == pytest.approx(adapted, abs=1e-12)
        assert frame["light_drive"] == pytest.approx(drive, abs=1e-12)
        assert frame["receptor_current"] == pytest.approx(current, abs=1e-12)
        adapted = [
            value + (expected_raw[index] - value) * coupling
            for index, value in enumerate(adapted)
        ]

        external = {
            python.touch_offset + index: value * 4e-9
            for index, value in enumerate(current)
            if value
        }
        for first, second in ((0, 1), (2, 3)):
            difference = current[first] - current[second]
            if difference:
                channel = first if difference > 0 else second
                external[python.asymmetry_offset + channel] = abs(difference) * 3e-9
        spikes = network.step(external)
        assert list(spikes) == frame["spatial_last_step_spikes"]
        for neuron in spikes:
            counts[neuron] += 1
    assert counts == frames[-1]["spatial_spike_counts"]


def test_stage9_header_is_c11_and_contains_no_behavior_commands(
    stage9_build: dict[str, object],
):
    subprocess.run(
        [
            "cc",
            "-x",
            "c",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsyntax-only",
            "-include",
            str(ROOT / "native" / "mobile_environment.h"),
            "/dev/null",
        ],
        check=True,
    )
    header = (ROOT / "native" / "mobile_environment.h").read_text().lower()
    for forbidden in (
        "crawl(",
        "turn_left",
        "turn_right",
        "target_heading",
        "behavior_tree",
        "policy_network",
        "animation_command",
    ):
        assert forbidden not in header
    assert "gradient_w_m3" in header
    assert "physics_nodes_um" in header


def test_checked_stage9_artifact_preserves_claim_boundaries():
    artifact = json.loads(TRAJECTORY.read_text())
    assert artifact["schema"] == "l1_native_environment_closed_loop_v1"
    assert artifact["release_validated"] is False
    assert artifact["direct_behavior_command"] is False
    assert artifact["scope_boundaries"][
        "integrated_spatial_proprioception_enabled"
    ] is False
    assert all(artifact["acceptance_gates"].values())
    assert set(artifact["scenarios"]) == {
        "uniform", "positive_y_gradient", "negative_y_gradient",
        "positive_z_gradient", "negative_z_gradient",
        "positive_y_right_sensor_lesion",
    }



def test_ci_remains_manual_only():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
