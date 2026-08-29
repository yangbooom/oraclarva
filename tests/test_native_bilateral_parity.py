from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest

from oraclarva.bilateral import (
    BilateralClosedLoopLarva,
    BilateralClosedLoopResult,
    BilateralStimulus,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "data" / "parity" / "bilateral_native_v1.tsv"


@dataclass
class NativeFrame:
    time_s: float
    nodes_um: tuple[tuple[float, float, float], ...]
    left_activation: tuple[float, ...]
    right_activation: tuple[float, ...]


@dataclass
class NativeResult:
    metadata: tuple[str, ...]
    displacement_x_um: float
    displacement_y_um: float
    heading_change_deg: float
    maximum_abs_lateral_um: float
    active_motor_identities: int
    peak_recruited_fibers: int
    neurons: dict[str, tuple[int, float | None]]
    waves: dict[str, tuple[float, float, float, float]]
    frames: tuple[NativeFrame, ...]


@pytest.fixture(scope="module")
def native_bilateral_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    compiler = shutil.which("c++")
    if compiler is None:
        pytest.skip("C++ compiler is unavailable")
    output = tmp_path_factory.mktemp("native-bilateral") / "oraclarva-native-bilateral"
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(ROOT / "native" / "lif_core.cpp"),
            str(ROOT / "native" / "bilateral_core.cpp"),
            str(ROOT / "native" / "bilateral_main.cpp"),
            "-o",
            str(output),
        ],
        check=True,
    )
    return output


def parse_native(output: str) -> NativeResult:
    metadata: tuple[str, ...] | None = None
    summary: tuple[float, ...] | None = None
    frame_count = -1
    active_motor_identities = -1
    peak_recruited_fibers = -1
    neurons: dict[str, tuple[int, float | None]] = {}
    waves: dict[str, tuple[float, float, float, float]] = {}
    frames: list[NativeFrame] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if fields[0] == "metadata":
            metadata = tuple(fields[1:])
        elif fields[0] == "summary":
            summary = tuple(map(float, fields[1:5]))
            frame_count = int(fields[5])
            active_motor_identities = int(fields[6])
            peak_recruited_fibers = int(fields[7])
        elif fields[0] == "neuron":
            first_spike = None if fields[4] == "-" else float(fields[4])
            neurons[fields[2]] = (int(fields[3]), first_spike)
        elif fields[0] == "wave":
            waves[fields[2]] = tuple(map(float, fields[3:7]))
        elif fields[0] == "frame":
            nodes = tuple(
                tuple(map(float, node.split(",")))
                for node in fields[3].split(";")
            )
            frames.append(NativeFrame(
                time_s=float(fields[2]),
                nodes_um=nodes,
                left_activation=tuple(map(float, fields[4].split(","))),
                right_activation=tuple(map(float, fields[5].split(","))),
            ))
        else:
            raise AssertionError(f"unknown native bilateral row: {fields[0]}")
    assert metadata is not None
    assert summary is not None
    assert frame_count == len(frames)
    return NativeResult(
        metadata=metadata,
        displacement_x_um=summary[0],
        displacement_y_um=summary[1],
        heading_change_deg=summary[2],
        maximum_abs_lateral_um=summary[3],
        active_motor_identities=active_motor_identities,
        peak_recruited_fibers=peak_recruited_fibers,
        neurons=neurons,
        waves=waves,
        frames=tuple(frames),
    )


CASES = {
    "symmetric": ((), {}, BilateralStimulus(1.0, 1.0)),
    "left": (("--left", "1", "--right", "0"), {}, BilateralStimulus(1.0, 0.0)),
    "right": (("--left", "0", "--right", "1"), {}, BilateralStimulus(0.0, 1.0)),
    "none": (("--left", "0", "--right", "0"), {}, BilateralStimulus(0.0, 0.0)),
    "premotor_t3_left": (
        ("--left", "1", "--right", "0", "--premotor-lesion", "T3:left"),
        {"lesion_premotor_channel": ("T3", "left")},
        BilateralStimulus(1.0, 0.0),
    ),
    "motor_identity_a1_left": (
        (
            "--left", "1", "--right", "0",
            "--motor-identity-lesion", "A1:left",
        ),
        {"lesion_motor_identity_channel": ("A1", "left")},
        BilateralStimulus(1.0, 0.0),
    ),
    "muscle_a1_left": (
        ("--left", "1", "--right", "0", "--muscle-lesion", "A1:left"),
        {"lesion_muscle_channel": ("A1", "left")},
        BilateralStimulus(1.0, 0.0),
    ),
}


@lru_cache(maxsize=None)
def python_result(case: str) -> BilateralClosedLoopResult:
    _, constructor_options, stimulus = CASES[case]
    return BilateralClosedLoopLarva(**constructor_options).run(
        stimulus, record_trajectory_interval_s=0.03
    )


@lru_cache(maxsize=None)
def native_result(binary: Path, case: str) -> NativeResult:
    command_options, _, _ = CASES[case]
    completed = subprocess.run(
        [str(binary), str(FIXTURE_PATH), *command_options],
        check=True,
        text=True,
        capture_output=True,
    )
    return parse_native(completed.stdout)


def assert_optional_time_matches(
    actual: float | None,
    expected: float | None,
) -> None:
    if expected is None:
        assert actual is None
    else:
        assert actual == pytest.approx(expected, rel=0.0, abs=1e-15)


@pytest.mark.parametrize("case", CASES)
def test_native_bilateral_loop_matches_python_all_causal_conditions(
    native_bilateral_binary: Path,
    case: str,
):
    expected = python_result(case)
    actual = native_result(native_bilateral_binary, case)
    assert actual.metadata == (
        "bilateral_closed_loop_native_v1",
        "dmel_l1_bilateral_steering_v0",
        "research_approximation",
        "release_validated=false",
    )
    assert actual.displacement_x_um == pytest.approx(
        expected.displacement_x_um, rel=0.0, abs=1e-9
    )
    assert actual.displacement_y_um == pytest.approx(
        expected.displacement_y_um, rel=0.0, abs=1e-9
    )
    assert actual.heading_change_deg == pytest.approx(
        expected.heading_change_deg, rel=0.0, abs=1e-9
    )
    assert actual.maximum_abs_lateral_um == pytest.approx(
        expected.maximum_abs_lateral_um, rel=0.0, abs=1e-9
    )
    assert actual.active_motor_identities == expected.active_motor_identities
    assert actual.peak_recruited_fibers == expected.peak_recruited_fibers
    assert set(actual.neurons) == set(expected.spike_counts)
    for label, (count, first_spike) in actual.neurons.items():
        assert count == expected.spike_counts[label]
        assert_optional_time_matches(first_spike, expected.first_spike_s[label])
    assert set(actual.waves) == set(expected.peak_activation)
    for segment, native_wave in actual.waves.items():
        expected_activation = expected.peak_activation[segment]
        expected_shortening = expected.peak_shortening_fraction[segment]
        assert native_wave == pytest.approx((
            expected_activation["left"],
            expected_activation["right"],
            expected_shortening["left"],
            expected_shortening["right"],
        ), rel=0.0, abs=1e-12)


@pytest.mark.parametrize("case", CASES)
def test_native_bilateral_trajectory_matches_python_nodes_and_activation(
    native_bilateral_binary: Path,
    case: str,
):
    expected = python_result(case).trajectory_artifact()
    actual = native_result(native_bilateral_binary, case)
    assert len(actual.frames) == len(expected["frames"]) == 151
    for native_frame, python_frame in zip(
        actual.frames, expected["frames"], strict=True
    ):
        assert native_frame.time_s == pytest.approx(
            python_frame["time_s"], rel=0.0, abs=1e-15
        )
        native_nodes = tuple(value for node in native_frame.nodes_um for value in node)
        python_nodes = tuple(value for node in python_frame["nodes_um"] for value in node)
        assert native_nodes == pytest.approx(python_nodes, rel=0.0, abs=2e-9)
        assert native_frame.left_activation == pytest.approx(
            python_frame["segment_activation_left"], rel=0.0, abs=5.1e-10
        )
        assert native_frame.right_activation == pytest.approx(
            python_frame["segment_activation_right"], rel=0.0, abs=5.1e-10
        )


def test_native_bilateral_fixture_preserves_claim_boundary_and_causal_scale():
    fixture = FIXTURE_PATH.read_text()
    assert "schema\tbilateral_closed_loop_native_v1" in fixture
    assert "status\tresearch_approximation" in fixture
    assert "release_validated\tfalse" in fixture
    assert "neuron_count\t126" in fixture
    assert fixture.count("\nsynapse\t") == 130
    assert fixture.count("\nbody_segment\t") == 12
    assert fixture.count("\nwave_segment\t") == 8
    lowered = fixture.lower()
    assert "turn_left" not in lowered
    assert "turn_right" not in lowered
    assert "animation_command" not in lowered
    assert "\tcrawl\t" not in lowered
