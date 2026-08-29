from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest

from oraclarva.organism import ClosedLoopLarva, ClosedLoopResult


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "data" / "parity" / "closed_loop_native_v1.tsv"


@dataclass
class NativeFrame:
    time_s: float
    nodes_um: tuple[tuple[float, float, float], ...]
    activation: tuple[float, ...]


@dataclass
class NativeResult:
    metadata: tuple[str, ...]
    displacement_um: float
    active_motor_identities: int
    peak_recruited_fibers: int
    neurons: dict[str, tuple[int, float | None]]
    waves: dict[str, tuple[float, float]]
    frames: tuple[NativeFrame, ...]


@pytest.fixture(scope="module")
def native_organism_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    compiler = shutil.which("c++")
    if compiler is None:
        pytest.skip("C++ compiler is unavailable")
    output = tmp_path_factory.mktemp("native-organism") / "oraclarva-native-organism"
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(ROOT / "native" / "lif_core.cpp"),
            str(ROOT / "native" / "organism_core.cpp"),
            str(ROOT / "native" / "organism_main.cpp"),
            "-o",
            str(output),
        ],
        check=True,
    )
    return output


def parse_native(output: str) -> NativeResult:
    metadata: tuple[str, ...] | None = None
    displacement_um = math.nan
    frame_count = -1
    active_motor_identities = -1
    peak_recruited_fibers = -1
    neurons: dict[str, tuple[int, float | None]] = {}
    waves: dict[str, tuple[float, float]] = {}
    frames: list[NativeFrame] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if fields[0] == "metadata":
            metadata = tuple(fields[1:])
        elif fields[0] == "summary":
            displacement_um = float(fields[1])
            frame_count = int(fields[2])
            active_motor_identities = int(fields[3])
            peak_recruited_fibers = int(fields[4])
        elif fields[0] == "neuron":
            first_spike = None if fields[4] == "-" else float(fields[4])
            neurons[fields[2]] = (int(fields[3]), first_spike)
        elif fields[0] == "wave":
            waves[fields[2]] = (float(fields[3]), float(fields[4]))
        elif fields[0] == "frame":
            nodes = tuple(
                tuple(map(float, node.split(",")))
                for node in fields[3].split(";")
            )
            frames.append(NativeFrame(
                time_s=float(fields[2]),
                nodes_um=nodes,
                activation=tuple(map(float, fields[4].split(","))),
            ))
        else:
            raise AssertionError(f"unknown native output row: {fields[0]}")
    assert metadata is not None
    assert frame_count == len(frames)
    return NativeResult(
        metadata=metadata,
        displacement_um=displacement_um,
        active_motor_identities=active_motor_identities,
        peak_recruited_fibers=peak_recruited_fibers,
        neurons=neurons,
        waves=waves,
        frames=tuple(frames),
    )


CASES = {
    "normal": ((), {}, True),
    "no_stimulus": (("--no-stimulus",), {}, False),
    "premotor_a4": (
        ("--premotor-lesion", "A4"),
        {"lesion_premotor_segment": "A4"},
        True,
    ),
    "muscle_a4": (
        ("--muscle-lesion", "A4"),
        {"lesion_muscle_segment": "A4"},
        True,
    ),
    "motor_identity_a1": (
        ("--motor-identity-lesion", "A1"),
        {"lesion_motor_identity_segment": "A1"},
        True,
    ),
}


@lru_cache(maxsize=None)
def python_result(case: str) -> ClosedLoopResult:
    _, constructor_options, stimulate = CASES[case]
    return ClosedLoopLarva(**constructor_options).run(
        stimulate=stimulate,
        record_trajectory_interval_s=0.03,
    )


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
        assert actual == pytest.approx(expected, abs=1e-15)


@pytest.mark.parametrize("case", CASES)
def test_native_embodied_loop_matches_python_all_causal_conditions(
    native_organism_binary: Path,
    case: str,
):
    expected = python_result(case)
    actual = native_result(native_organism_binary, case)
    assert actual.metadata == (
        "closed_loop_native_v1",
        "dmel_l1_closed_loop_v0",
        "research_approximation",
        "release_validated=false",
    )
    assert actual.displacement_um == pytest.approx(expected.displacement_um, abs=1e-9)
    assert actual.active_motor_identities == expected.motor_identity_summary[
        "active_identities"
    ]
    assert actual.peak_recruited_fibers == expected.muscle_identity_summary[
        "peak_recruited_fibers"
    ]
    assert set(actual.neurons) == set(expected.spike_counts)
    for label, (count, first_spike) in actual.neurons.items():
        assert count == expected.spike_counts[label]
        assert_optional_time_matches(first_spike, expected.first_spike_s[label])
    assert set(actual.waves) == set(expected.peak_activation)
    for segment, (peak_activation, peak_shortening) in actual.waves.items():
        assert peak_activation == pytest.approx(
            expected.peak_activation[segment], abs=1e-13
        )
        assert peak_shortening == pytest.approx(
            expected.peak_shortening_fraction[segment], abs=1e-12
        )


@pytest.mark.parametrize("case", CASES)
def test_native_embodied_trajectory_matches_python_nodes_and_activation(
    native_organism_binary: Path,
    case: str,
):
    expected = python_result(case).trajectory_artifact()
    actual = native_result(native_organism_binary, case)
    assert len(actual.frames) == len(expected["frames"]) == 151
    for native_frame, python_frame in zip(
        actual.frames,
        expected["frames"],
        strict=True,
    ):
        assert native_frame.time_s == pytest.approx(python_frame["time_s"], abs=1e-15)
        native_nodes = tuple(value for node in native_frame.nodes_um for value in node)
        python_nodes = tuple(
            value for node in python_frame["nodes_um"] for value in node
        )
        assert native_nodes == pytest.approx(python_nodes, abs=5.1e-10)
        assert native_frame.activation == pytest.approx(
            python_frame["segment_activation"], abs=5.1e-10
        )


def test_native_fixture_preserves_research_claim_boundary_and_causal_scale():
    fixture = FIXTURE_PATH.read_text()
    assert "schema\tclosed_loop_native_v1" in fixture
    assert "status\tresearch_approximation" in fixture
    assert "release_validated\tfalse" in fixture
    assert "neuron_count\t91" in fixture
    assert fixture.count("\nsynapse\t") == 90
    assert fixture.count("\nbody_segment\t") == 12
    assert fixture.count("\nwave_segment\t") == 8
    lowered = fixture.lower()
    assert "turn_left" not in lowered
    assert "animation_command" not in lowered
    assert "\tcrawl\t" not in lowered
