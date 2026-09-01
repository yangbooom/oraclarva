from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest

from oraclarva.repeat_crawl import RepeatCrawlLarva, RepeatCrawlResult, WAVE_SEGMENTS


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "parity" / "repeat_crawl_native_v1.tsv"


@dataclass(frozen=True)
class NativeFrame:
    time_s: float
    nodes_um: tuple[tuple[float, float, float], ...]
    activation: tuple[float, ...]
    node_force: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class NativeTrace:
    segment: str
    body_state_time_s: float
    sensor_index: int
    sensor_spike_time_s: float
    premotor_index: int
    premotor_spike_time_s: float
    motor_index: int
    motor_spike_time_s: float


@dataclass(frozen=True)
class NativeResult:
    metadata: tuple[str, ...]
    displacement_x_um: float
    feedback_force_frames: int
    all_active_forces_traced: bool
    complete_cycle_count: int
    physical_wave_cycle_count: int
    median_period_s: float | None
    median_stride_um: float | None
    median_wave_speed_segments_s: float | None
    neurons: dict[str, tuple[int, float | None]]
    premotor: dict[str, tuple[float, ...]]
    traces: dict[str, NativeTrace]
    frames: tuple[NativeFrame, ...]


@dataclass(frozen=True)
class PythonRun:
    larva: RepeatCrawlLarva
    result: RepeatCrawlResult


def optional_float(value: str) -> float | None:
    return None if value == "-" else float(value)


def parse_vector_list(value: str) -> tuple[tuple[float, float, float], ...]:
    return tuple(
        tuple(map(float, item.split(",")))
        for item in value.split(";")
    )


def parse_native(output: str) -> NativeResult:
    metadata: tuple[str, ...] | None = None
    summary: tuple[object, ...] | None = None
    neurons: dict[str, tuple[int, float | None]] = {}
    premotor: dict[str, tuple[float, ...]] = {}
    traces: dict[str, NativeTrace] = {}
    frames: list[NativeFrame] = []
    expected_frames = -1
    for line in output.splitlines():
        fields = line.split("\t")
        kind = fields[0]
        if kind == "metadata":
            metadata = tuple(fields[1:])
        elif kind == "summary":
            summary = (
                float(fields[1]),
                int(fields[2]),
                fields[3] == "true",
                int(fields[4]),
                int(fields[5]),
                optional_float(fields[6]),
                optional_float(fields[7]),
                optional_float(fields[8]),
            )
            expected_frames = int(fields[9])
        elif kind == "neuron":
            neurons[fields[2]] = (int(fields[3]), optional_float(fields[4]))
        elif kind == "premotor":
            premotor[fields[2]] = tuple(map(float, fields[3:]))
        elif kind == "trace":
            traces[fields[2]] = NativeTrace(
                segment=fields[2],
                body_state_time_s=float(fields[3]),
                sensor_index=int(fields[4]),
                sensor_spike_time_s=float(fields[5]),
                premotor_index=int(fields[6]),
                premotor_spike_time_s=float(fields[7]),
                motor_index=int(fields[8]),
                motor_spike_time_s=float(fields[9]),
            )
        elif kind == "frame":
            frames.append(
                NativeFrame(
                    time_s=float(fields[2]),
                    nodes_um=parse_vector_list(fields[3]),
                    activation=tuple(map(float, fields[4].split(","))),
                    node_force=parse_vector_list(fields[5]),
                )
            )
        else:
            raise AssertionError(f"unknown native repeat row {kind}")
    assert metadata is not None
    assert summary is not None
    assert expected_frames == len(frames)
    return NativeResult(
        metadata=metadata,
        displacement_x_um=summary[0],
        feedback_force_frames=summary[1],
        all_active_forces_traced=summary[2],
        complete_cycle_count=summary[3],
        physical_wave_cycle_count=summary[4],
        median_period_s=summary[5],
        median_stride_um=summary[6],
        median_wave_speed_segments_s=summary[7],
        neurons=neurons,
        premotor=premotor,
        traces=traces,
        frames=tuple(frames),
    )


@pytest.fixture(scope="module")
def native_repeat_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    compiler = shutil.which("c++")
    if compiler is None:
        pytest.skip("C++ compiler is unavailable")
    output = tmp_path_factory.mktemp("native-repeat") / "oraclarva-native-repeat"
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
    return output


CASES = {
    "normal": ((), {}, True, 14.6),
    "zero": (("--no-stimulus", "--steps", "200"), {}, False, 0.2),
    "sensory_a6": (
        ("--sensory-lesion", "A6", "--steps", "900"),
        {"lesion_sensory_segment": "A6"},
        True,
        0.9,
    ),
    "premotor_a4": (
        ("--premotor-lesion", "A4", "--steps", "2200"),
        {"lesion_premotor_segment": "A4"},
        True,
        2.2,
    ),
    "motor_a6": (
        ("--motor-segment-lesion", "A6", "--steps", "80"),
        {"motor_segment_lesion": "A6"},
        True,
        0.08,
    ),
    "fiber_a6": (
        ("--fiber-segment-lesion", "A6", "--steps", "80"),
        {"fiber_segment_lesion": "A6"},
        True,
        0.08,
    ),
}


@lru_cache(maxsize=None)
def python_result(case: str) -> PythonRun:
    _, options, stimulate, duration = CASES[case]
    base = RepeatCrawlLarva()
    constructor = {}
    if "lesion_sensory_segment" in options:
        constructor["lesion_sensory_segment"] = options[
            "lesion_sensory_segment"
        ]
    if "lesion_premotor_segment" in options:
        constructor["lesion_premotor_segment"] = options[
            "lesion_premotor_segment"
        ]
    if options.get("motor_segment_lesion"):
        constructor["lesion_motor_node_ids"] = (
            base.protocol.source_nodes_by_segment[
                options["motor_segment_lesion"]
            ]
        )
    if options.get("fiber_segment_lesion"):
        constructor["lesion_fiber_ids"] = tuple(
            item.fiber_id
            for item in base.projection.mappings
            if item.segment_id == options["fiber_segment_lesion"]
        )
    larva = RepeatCrawlLarva(**constructor)
    return PythonRun(
        larva=larva,
        result=larva.run(
            stimulate=stimulate,
            duration_s=duration,
            record_trajectory_interval_s=0.03,
        ),
    )


@lru_cache(maxsize=None)
def native_result(binary: Path, case: str) -> NativeResult:
    arguments, _, _, _ = CASES[case]
    completed = subprocess.run(
        [str(binary), str(FIXTURE), *arguments],
        check=True,
        text=True,
        capture_output=True,
    )
    return parse_native(completed.stdout)


def assert_optional_matches(
    actual: float | None, expected: float | None, tolerance: float = 1e-15
) -> None:
    if expected is None:
        assert actual is None
    else:
        assert actual == pytest.approx(expected, rel=0.0, abs=tolerance)


@pytest.mark.parametrize("case", CASES)
def test_native_repeat_matches_python_neural_force_and_cycle_summary(
    native_repeat_binary: Path, case: str
):
    expected = python_result(case).result
    actual = native_result(native_repeat_binary, case)
    assert actual.metadata == (
        "repeat_crawl_native_v1",
        "dmel_l1_repeat_crawl_v0",
        "research_approximation",
        "release_validated=false",
        next(
            line.split("\t")[1]
            for line in FIXTURE.read_text(encoding="utf-8").splitlines()
            if line.startswith("config_sha256\t")
        ),
    )
    assert actual.displacement_x_um == pytest.approx(
        expected.displacement_x_um, rel=0.0, abs=1e-8
    )
    assert actual.feedback_force_frames == expected.feedback_force_frames
    assert (
        actual.all_active_forces_traced
        is expected.all_active_forces_sensory_traced
    )
    assert set(actual.neurons) == set(expected.spike_counts)
    for label, (count, first_spike) in actual.neurons.items():
        assert count == expected.spike_counts[label]
        assert_optional_matches(first_spike, expected.first_spike_s[label])
    assert set(actual.premotor) == set(WAVE_SEGMENTS)
    for segment in WAVE_SEGMENTS:
        assert actual.premotor[segment] == pytest.approx(
            expected.premotor_spike_times_s[segment],
            rel=0.0,
            abs=1e-15,
        )
    metrics = expected.cycle_metrics()
    assert actual.complete_cycle_count == metrics["complete_cycle_count"]
    assert (
        actual.physical_wave_cycle_count
        == metrics["physical_wave_cycle_count"]
    )
    if metrics["median"] is None:
        assert actual.median_period_s is None
        assert actual.median_stride_um is None
        assert actual.median_wave_speed_segments_s is None
    else:
        assert_optional_matches(
            actual.median_period_s, metrics["median"]["period_s"]
        )
        assert_optional_matches(
            actual.median_stride_um,
            metrics["median"]["stride_um"],
            tolerance=1e-8,
        )
        assert_optional_matches(
            actual.median_wave_speed_segments_s,
            metrics["median"]["a1_a6_wave_speed_segments_s"],
            tolerance=1e-12,
        )


@pytest.mark.parametrize("case", CASES)
def test_native_repeat_sampled_nodes_activation_and_force_match_python(
    native_repeat_binary: Path, case: str
):
    expected = python_result(case).result.trajectory_samples
    actual = native_result(native_repeat_binary, case).frames
    assert len(actual) == len(expected)
    for native, python in zip(actual, expected, strict=True):
        assert native.time_s == pytest.approx(
            python["time_s"], rel=0.0, abs=3e-15
        )
        native_nodes = tuple(value for node in native.nodes_um for value in node)
        python_nodes = tuple(value for node in python["nodes_um"] for value in node)
        assert native_nodes == pytest.approx(
            python_nodes, rel=0.0, abs=5e-8
        )
        python_activation = tuple(
            python["segment_activation"][segment]
            for segment in WAVE_SEGMENTS
        )
        assert native.activation == pytest.approx(
            python_activation, rel=0.0, abs=5.1e-10
        )
        native_force = tuple(
            value for node in native.node_force for value in node
        )
        python_force = tuple(
            value
            for node in python["node_force_model_units"]
            for value in node
        )
        assert native_force == pytest.approx(
            python_force, rel=0.0, abs=2e-7
        )


def test_native_repeat_normal_sampled_path_rejects_visible_backslip(
    native_repeat_binary: Path,
):
    frames = native_result(native_repeat_binary, "normal").frames
    centers = [
        -sum(node[0] for node in frame.nodes_um) / len(frame.nodes_um)
        for frame in frames
    ]
    peak = centers[0]
    maximum_retrace = 0.0
    cumulative_backward = 0.0
    for left, right in zip(centers, centers[1:], strict=False):
        delta = right - left
        cumulative_backward += max(0.0, -delta)
        peak = max(peak, right)
        maximum_retrace = max(maximum_retrace, peak - right)
    net = centers[-1] - centers[0]
    efficiency = net / (net + cumulative_backward)
    assert maximum_retrace <= 25.0
    assert efficiency >= 0.8


def test_native_repeat_normal_trace_examples_are_ordered_and_identified(
    native_repeat_binary: Path,
):
    actual = native_result(native_repeat_binary, "normal")
    assert set(actual.traces) == set(WAVE_SEGMENTS)
    labels = tuple(python_result("normal").larva.protocol.labels)
    for segment, trace in actual.traces.items():
        assert trace.segment == segment
        assert labels[trace.sensor_index].startswith(
            ("environment_touch_receptor", "mechanosensory:")
        )
        assert labels[trace.premotor_index] == f"premotor_A27h_like:{segment}"
        assert labels[trace.motor_index] in (
            python_result("normal").larva.protocol.source_nodes_by_segment[
                segment
            ]
        )
        assert (
            trace.body_state_time_s
            <= trace.sensor_spike_time_s
            < trace.premotor_spike_time_s
            <= trace.motor_spike_time_s
        )


def test_native_repeat_fixture_preserves_freeze_and_no_action_boundary():
    fixture = FIXTURE.read_text(encoding="utf-8")
    assert "schema\trepeat_crawl_native_v1" in fixture
    config_hash = next(
        line.split("\t")[1]
        for line in fixture.splitlines()
        if line.startswith("config_sha256\t")
    )
    assert len(config_hash) == 64
    assert all(character in "0123456789abcdef" for character in config_hash)
    assert "release_validated\tfalse" in fixture
    assert "neuron_count\t164" in fixture
    assert fixture.count("\nsynapse\t") == 307
    assert fixture.count("\nfiber\t") == 146
    assert fixture.count("\nbody_segment\t") == 12
    assert fixture.count("\nwave_segment\t") == 6
    lowered = fixture.lower()
    for forbidden in (
        "turn_left",
        "turn_right",
        "animation_command",
        "behavior_tree",
        "policy_network",
        "\tcrawl\t",
    ):
        assert forbidden not in lowered


def test_native_repeat_invalid_lesion_fails_closed(
    native_repeat_binary: Path,
):
    completed = subprocess.run(
        [
            str(native_repeat_binary),
            str(FIXTURE),
            "--sensory-lesion",
            "A7",
            "--steps",
            "80",
        ],
        text=True,
        capture_output=True,
    )
    assert completed.returncode != 0
    assert "unknown repeat wave segment" in completed.stderr
