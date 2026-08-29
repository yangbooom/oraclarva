from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from oraclarva.lif import LIFConfig, SparseLIFNetwork, Synapse


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "data" / "parity" / "lif_smoke_v0.tsv"


@dataclass
class Fixture:
    neuron_count: int
    steps: int
    config: LIFConfig
    synapses: list[Synapse]
    stimulus: dict[int, dict[int, float]]


def load_fixture() -> Fixture:
    neuron_count = 0
    steps = 0
    config: dict[str, float] = {}
    synapses: list[Synapse] = []
    stimulus: dict[int, dict[int, float]] = {}
    for raw_line in FIXTURE_PATH.read_text().splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        fields = raw_line.split("\t")
        if fields[0] == "neuron_count":
            neuron_count = int(fields[1])
        elif fields[0] == "steps":
            steps = int(fields[1])
        elif fields[0] == "config":
            config[fields[1]] = float(fields[2])
        elif fields[0] == "synapse":
            synapses.append(Synapse(
                pre=int(fields[1]),
                post=int(fields[2]),
                current_a=float(fields[3]),
                kind=fields[4],
                delay_steps=int(fields[5]),
            ))
        elif fields[0] == "stimulus":
            stimulus.setdefault(int(fields[1]), {})[int(fields[2])] = float(fields[3])
        else:
            raise AssertionError(f"unknown fixture row: {fields[0]}")
    return Fixture(neuron_count, steps, LIFConfig(**config), synapses, stimulus)


@pytest.fixture(scope="module")
def native_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    compiler = shutil.which("c++")
    if compiler is None:
        pytest.skip("C++ compiler is unavailable")
    output = tmp_path_factory.mktemp("native") / "oraclarva-native-parity"
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(ROOT / "native" / "lif_core.cpp"),
            str(ROOT / "native" / "parity_main.cpp"),
            "-o",
            str(output),
        ],
        check=True,
    )
    return output


def python_trace(fixture: Fixture, lesion: int | None) -> list[dict[str, object]]:
    network = SparseLIFNetwork(
        fixture.neuron_count,
        fixture.synapses,
        fixture.config,
    )
    if lesion is not None:
        network.lesion([lesion])
    trace = []
    for step in range(fixture.steps):
        trace.append({
            "spikes": network.step(fixture.stimulus.get(step)),
            "voltage": tuple(network.voltage_v),
            "exc": tuple(network.excitatory_current_a),
            "inh": tuple(network.inhibitory_current_a),
        })
    return trace


def native_trace(binary: Path, fixture: Fixture, lesion: int | None) -> list[dict[str, object]]:
    command = [str(binary), str(FIXTURE_PATH)]
    if lesion is not None:
        command += ["--lesion", str(lesion)]
    output = subprocess.run(command, check=True, text=True, capture_output=True).stdout
    lines = output.splitlines()
    assert lines[0] == (
        f"metadata\tsteps\t{fixture.steps}\tneurons\t{fixture.neuron_count}"
    )
    trace = []
    for expected_step, line in enumerate(lines[1:]):
        kind, step, spike_text, voltage, exc, inh = line.split("\t")
        assert kind == "frame"
        assert int(step) == expected_step
        trace.append({
            "spikes": () if spike_text == "-" else tuple(map(int, spike_text.split(","))),
            "voltage": tuple(map(float, voltage.split(","))),
            "exc": tuple(map(float, exc.split(","))),
            "inh": tuple(map(float, inh.split(","))),
        })
    assert len(trace) == fixture.steps
    return trace


@pytest.mark.parametrize("lesion", [None, 1])
def test_native_lif_matches_python_stepwise(native_binary: Path, lesion: int | None):
    fixture = load_fixture()
    expected = python_trace(fixture, lesion)
    actual = native_trace(native_binary, fixture, lesion)
    for expected_frame, actual_frame in zip(expected, actual, strict=True):
        assert actual_frame["spikes"] == expected_frame["spikes"]
        assert actual_frame["voltage"] == pytest.approx(
            expected_frame["voltage"], abs=1e-14
        )
        assert actual_frame["exc"] == pytest.approx(
            expected_frame["exc"], abs=1e-20
        )
        assert actual_frame["inh"] == pytest.approx(
            expected_frame["inh"], abs=1e-20
        )


def test_parity_fixture_is_explicitly_synthetic_and_contains_no_action_commands():
    fixture_text = FIXTURE_PATH.read_text()
    assert "status: synthetic_parity_fixture" in fixture_text
    assert "allowed_use: numerical_regression_only" in fixture_text
    lowered = fixture_text.lower()
    assert "crawl" not in lowered
    assert "turn_left" not in lowered
    assert "behavior" not in lowered
