from __future__ import annotations

import ctypes
import json
import math
import subprocess
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "parity" / "repeat_crawl_native_v1.tsv"
PYTHON_ORACLE = ROOT / "data" / "trajectories" / "l1_repeat_crawl_v0.json"


@dataclass(frozen=True)
class Frame:
    time_s: float
    nodes: tuple[tuple[float, float, float], ...]
    activation: tuple[float, ...]
    force: tuple[tuple[float, float, float], ...]
    mesh: tuple[tuple[float, float, float, float], ...] = ()


@dataclass(frozen=True)
class Summary:
    steps: int
    digest: str | None
    displacement_um: float
    feedback_force_frames: int
    all_traced: bool
    complete_cycles: int
    physical_cycles: int
    period_s: float | None
    stride_um: float | None
    wave_speed: float | None
    spike_counts: tuple[int, ...]
    first_spike_s: tuple[float | None, ...]
    trace_valid: tuple[int, ...]


@dataclass(frozen=True)
class MobileOutput:
    metadata: tuple[str, ...]
    frames: tuple[Frame, ...]
    summary: Summary
    replay: tuple[str, str, str]


def optional(value: str) -> float | None:
    return None if value == "-" else float(value)


def vectors(value: str) -> tuple[tuple[float, float, float], ...]:
    if not value:
        return ()
    return tuple(tuple(map(float, item.split(","))) for item in value.split(";"))


def parse_mobile(output: str) -> MobileOutput:
    metadata: tuple[str, ...] | None = None
    frames: list[Frame] = []
    summary: Summary | None = None
    replay: tuple[str, str, str] | None = None
    for line in output.splitlines():
        fields = line.split("\t")
        if fields[0] == "metadata":
            metadata = tuple(fields[1:])
        elif fields[0] == "frame":
            frames.append(
                Frame(
                    time_s=float(fields[2]),
                    nodes=vectors(fields[3]),
                    activation=tuple(map(float, fields[4].split(","))),
                    force=vectors(fields[5]),
                    mesh=tuple(
                        tuple(map(float, item.split(",")))
                        for item in fields[6].split(";")
                        if item
                    ),
                )
            )
        elif fields[0] == "summary":
            summary = Summary(
                steps=int(fields[1]),
                digest=fields[2],
                displacement_um=float(fields[3]),
                feedback_force_frames=int(fields[4]),
                all_traced=fields[5] == "true",
                complete_cycles=int(fields[6]),
                physical_cycles=int(fields[7]),
                period_s=optional(fields[8]),
                stride_um=optional(fields[9]),
                wave_speed=optional(fields[10]),
                spike_counts=tuple(map(int, fields[11].split(","))),
                first_spike_s=tuple(optional(item) for item in fields[12].split(",")),
                trace_valid=tuple(map(int, fields[13].split(","))),
            )
        elif fields[0] == "replay":
            replay = (fields[1], fields[2], fields[3])
        elif fields[0] == "benchmark":
            continue
        else:
            raise AssertionError(f"unknown mobile output row {fields[0]}")
    assert metadata is not None
    assert summary is not None
    assert replay is not None
    return MobileOutput(metadata, tuple(frames), summary, replay)


def parse_native(output: str) -> tuple[Summary, tuple[Frame, ...]]:
    summary_fields: list[str] | None = None
    neurons: dict[int, tuple[int, float | None]] = {}
    frames: list[Frame] = []
    trace_count = 0
    for line in output.splitlines():
        fields = line.split("\t")
        if fields[0] == "summary":
            summary_fields = fields
        elif fields[0] == "neuron":
            neurons[int(fields[1])] = (int(fields[3]), optional(fields[4]))
        elif fields[0] == "trace":
            trace_count += 1
        elif fields[0] == "frame":
            frames.append(
                Frame(
                    time_s=float(fields[2]),
                    nodes=vectors(fields[3]),
                    activation=tuple(map(float, fields[4].split(","))),
                    force=vectors(fields[5]),
                )
            )
    assert summary_fields is not None
    ordered = tuple(neurons[index] for index in range(164))
    return (
        Summary(
            steps=-1,
            digest=None,
            displacement_um=float(summary_fields[1]),
            feedback_force_frames=int(summary_fields[2]),
            all_traced=summary_fields[3] == "true",
            complete_cycles=int(summary_fields[4]),
            physical_cycles=int(summary_fields[5]),
            period_s=optional(summary_fields[6]),
            stride_um=optional(summary_fields[7]),
            wave_speed=optional(summary_fields[8]),
            spike_counts=tuple(item[0] for item in ordered),
            first_spike_s=tuple(item[1] for item in ordered),
            trace_valid=tuple(1 for _ in range(trace_count)),
        ),
        tuple(frames),
    )


@pytest.fixture(scope="module")
def mobile_build(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    output = tmp_path_factory.mktemp("mobile-core")
    subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "tools" / "build_mobile_core.py"),
            "--output",
            str(output),
        ],
        check=True,
    )
    native = output / "oraclarva-native-repeat"
    subprocess.run(
        [
            "c++",
            "-std=c++17",
            "-O3",
            "-DNDEBUG",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(ROOT / "native" / "lif_core.cpp"),
            str(ROOT / "native" / "repeat_core.cpp"),
            str(ROOT / "native" / "repeat_main.cpp"),
            "-o",
            str(native),
        ],
        check=True,
    )
    return {
        "directory": output,
        "host": output / "oraclarva-mobile-host",
        "shared": output / "liboraclarva_mobile.so",
        "static": output / "liboraclarva_mobile.a",
        "native": native,
    }


def run_mobile(
    build: dict[str, Path], *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(build["host"]), str(FIXTURE), *arguments],
        text=True,
        capture_output=True,
        check=check,
    )


def run_native(
    build: dict[str, Path], *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(build["native"]), str(FIXTURE), *arguments],
        text=True,
        capture_output=True,
        check=True,
    )


@lru_cache(maxsize=1)
def oracle() -> dict[str, object]:
    return json.loads(PYTHON_ORACLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def full_mobile(mobile_build: dict[str, Path]) -> MobileOutput:
    completed = run_mobile(
        mobile_build,
        "--sample-stride",
        "30",
        "--omit-mesh-output",
    )
    return parse_mobile(completed.stdout)


@pytest.fixture(scope="module")
def full_native(mobile_build: dict[str, Path]) -> tuple[Summary, tuple[Frame, ...]]:
    return parse_native(run_native(mobile_build).stdout)


def flatten(values: tuple[tuple[float, ...], ...]) -> tuple[float, ...]:
    return tuple(item for vector in values for item in vector)


def test_mobile_full_stepped_run_matches_frozen_python_oracle(
    full_mobile: MobileOutput,
):
    expected = oracle()
    frames = expected["frames"]
    assert len(full_mobile.frames) == len(frames) == 488
    for actual, reference in zip(full_mobile.frames, frames, strict=True):
        assert actual.time_s == pytest.approx(reference["time_s"], abs=3e-15)
        assert flatten(actual.nodes) == pytest.approx(
            flatten(tuple(tuple(item) for item in reference["nodes_um"])),
            rel=0.0,
            abs=5e-8,
        )
        expected_activation = tuple(
            reference["segment_activation"][segment]
            for segment in ("A6", "A5", "A4", "A3", "A2", "A1")
        )
        assert actual.activation == pytest.approx(
            expected_activation, rel=0.0, abs=5.1e-10
        )
        assert flatten(actual.force) == pytest.approx(
            flatten(
                tuple(
                    tuple(item)
                    for item in reference["node_force_model_units"]
                )
            ),
            rel=0.0,
            abs=2e-7,
        )
    result = expected["result_summary"]
    assert full_mobile.summary.displacement_um == pytest.approx(
        result["displacement_x_um"], rel=0.0, abs=1e-8
    )
    assert all(result["movement_gate"].values())
    assert result["maximum_backward_retrace_um"] <= 25.0
    assert result["forward_progress_efficiency"] >= 0.8
    assert full_mobile.summary.feedback_force_frames == result["feedback_force_frames"]
    assert full_mobile.summary.complete_cycles == 3
    assert full_mobile.summary.physical_cycles == 3
    assert full_mobile.summary.all_traced is True
    assert full_mobile.summary.trace_valid == (1, 1, 1, 1, 1, 1)


def test_mobile_full_stepped_run_matches_native_one_shot_exactly(
    full_mobile: MobileOutput,
    full_native: tuple[Summary, tuple[Frame, ...]],
):
    native_summary, native_frames = full_native
    assert len(full_mobile.frames) == len(native_frames)
    for actual, reference in zip(full_mobile.frames, native_frames, strict=True):
        assert actual.time_s == reference.time_s
        assert actual.nodes == reference.nodes
        assert actual.activation == reference.activation
        assert actual.force == reference.force
    mobile = full_mobile.summary
    assert mobile.displacement_um == native_summary.displacement_um
    assert mobile.feedback_force_frames == native_summary.feedback_force_frames
    assert mobile.all_traced is native_summary.all_traced
    assert mobile.complete_cycles == native_summary.complete_cycles
    assert mobile.physical_cycles == native_summary.physical_cycles
    assert mobile.period_s == native_summary.period_s
    assert mobile.stride_um == native_summary.stride_um
    assert mobile.wave_speed == native_summary.wave_speed
    assert mobile.spike_counts == native_summary.spike_counts
    assert mobile.first_spike_s == native_summary.first_spike_s


def test_mobile_reset_replay_digest_is_exact(full_mobile: MobileOutput):
    first, replay, status = full_mobile.replay
    assert status == "exact"
    assert first == replay == full_mobile.summary.digest
    assert len(first) == 16


@pytest.mark.parametrize(
    ("mobile_arguments", "native_arguments"),
    (
        (("--touch-steps", "0", "--steps", "200"), ("--no-stimulus", "--steps", "200")),
        (("--sensory-lesion", "A6", "--steps", "900"), ("--sensory-lesion", "A6", "--steps", "900")),
        (("--premotor-lesion", "A4", "--steps", "2200"), ("--premotor-lesion", "A4", "--steps", "2200")),
        (("--motor-lesion", "A6", "--steps", "80"), ("--motor-segment-lesion", "A6", "--steps", "80")),
        (("--fiber-lesion", "A6", "--steps", "80"), ("--fiber-segment-lesion", "A6", "--steps", "80")),
    ),
)
def test_mobile_intervention_boundary_matches_one_shot(
    mobile_build: dict[str, Path],
    mobile_arguments: tuple[str, ...],
    native_arguments: tuple[str, ...],
):
    mobile = parse_mobile(
        run_mobile(mobile_build, *mobile_arguments, "--no-frame-output").stdout
    ).summary
    native, _ = parse_native(run_native(mobile_build, *native_arguments).stdout)
    assert mobile.displacement_um == native.displacement_um
    assert mobile.feedback_force_frames == native.feedback_force_frames
    assert mobile.all_traced is native.all_traced
    assert mobile.spike_counts == native.spike_counts
    assert mobile.first_spike_s == native.first_spike_s


def test_mobile_metadata_preserves_claim_boundary(full_mobile: MobileOutput):
    assert full_mobile.metadata == (
        "1",
        "repeat_crawl_native_v1",
        "dmel_l1_repeat_crawl_v0",
        "research_approximation",
        "release_validated=false",
        oracle()["generated_from"]["config_sha256"],
        "0.001",
        "164",
        "13",
        "6",
        "302",
        "600",
    )
    held_out = json.loads(
        (ROOT / "data" / "validation" / "repeat_crawl_held_out_v0.json").read_text()
    )
    assert held_out["release_validated"] is False
    assert held_out["status"] == "diagnostic_held_out_passed"
    assert held_out["passed"] is True
    assert held_out["fail_closed"] is True
    assert held_out["evaluation_protocol"][
        "independent_validation_claim_available"
    ] is False


def test_mobile_c_header_and_shared_exports_are_c_only(mobile_build: dict[str, Path]):
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
            str(ROOT / "native" / "mobile_core.h"),
            "/dev/null",
        ],
        check=True,
    )
    symbols = subprocess.run(
        ["nm", "-D", "--defined-only", str(mobile_build["shared"])],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    assert {line.split()[-1] for line in symbols} == {
        "oraclarva_mobile_create",
        "oraclarva_mobile_destroy",
        "oraclarva_mobile_reset",
        "oraclarva_mobile_advance",
        "oraclarva_mobile_read_metadata",
        "oraclarva_mobile_read_snapshot",
        "oraclarva_mobile_render_counts",
        "oraclarva_mobile_read_render_mesh",
    }


class RenderVertex(ctypes.Structure):
    _fields_ = [
        ("position_um", ctypes.c_float * 3),
        ("normal", ctypes.c_float * 3),
        ("activation", ctypes.c_float),
    ]


class Triangle(ctypes.Structure):
    _fields_ = [("vertex", ctypes.c_uint32 * 3)]


def test_mobile_render_mesh_is_finite_watertight_and_read_only(
    mobile_build: dict[str, Path],
):
    library = ctypes.CDLL(str(mobile_build["shared"]))
    library.oraclarva_mobile_create.restype = ctypes.c_int
    library.oraclarva_mobile_create.argtypes = [
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    library.oraclarva_mobile_render_counts.restype = ctypes.c_int
    library.oraclarva_mobile_render_counts.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    library.oraclarva_mobile_read_render_mesh.restype = ctypes.c_int
    library.oraclarva_mobile_read_render_mesh.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(RenderVertex),
        ctypes.c_size_t,
        ctypes.POINTER(Triangle),
        ctypes.c_size_t,
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    library.oraclarva_mobile_destroy.argtypes = [ctypes.c_void_p]
    error = ctypes.create_string_buffer(256)
    core = ctypes.c_void_p()
    assert library.oraclarva_mobile_create(
        str(FIXTURE).encode(), None, ctypes.byref(core), error, len(error)
    ) == 0
    try:
        vertex_count = ctypes.c_size_t()
        triangle_count = ctypes.c_size_t()
        assert library.oraclarva_mobile_render_counts(
            core,
            2,
            12,
            ctypes.byref(vertex_count),
            ctypes.byref(triangle_count),
            error,
            len(error),
        ) == 0
        assert vertex_count.value == 302 > 13
        assert triangle_count.value == 600
        vertices = (RenderVertex * vertex_count.value)()
        triangles = (Triangle * triangle_count.value)()
        assert library.oraclarva_mobile_read_render_mesh(
            core,
            2,
            12,
            vertices,
            len(vertices),
            triangles,
            len(triangles),
            error,
            len(error),
        ) == 0
        for vertex in vertices:
            assert all(math.isfinite(value) for value in vertex.position_um)
            norm = math.sqrt(sum(value * value for value in vertex.normal))
            assert norm == pytest.approx(1.0, abs=2e-6)
            assert 0.0 <= vertex.activation <= 1.0
        edges: Counter[tuple[int, int]] = Counter()
        for triangle in triangles:
            a, b, c = triangle.vertex
            assert len({a, b, c}) == 3
            for left, right in ((a, b), (b, c), (c, a)):
                edges[tuple(sorted((left, right)))] += 1
        assert edges and set(edges.values()) == {2}
        assert library.oraclarva_mobile_read_render_mesh(
            core,
            2,
            12,
            vertices,
            len(vertices) - 1,
            triangles,
            len(triangles),
            error,
            len(error),
        ) == 4
    finally:
        library.oraclarva_mobile_destroy(core)


@pytest.mark.parametrize(
    ("arguments", "message"),
    (
        (("--steps", "1", "--touch-steps", "1", "--touch-intensity", "1.1"), "intensity"),
        (("--steps", "80", "--sensory-lesion", "A7"), "unknown repeat wave"),
        (("--steps", "16001"), "outside fixture"),
    ),
)
def test_mobile_invalid_inputs_fail_closed(
    mobile_build: dict[str, Path], arguments: tuple[str, ...], message: str
):
    completed = run_mobile(mobile_build, *arguments, check=False)
    assert completed.returncode != 0
    assert message in completed.stderr


def test_mobile_public_api_contains_no_behavior_commands():
    header = (ROOT / "native" / "mobile_core.h").read_text().lower()
    for forbidden in (
        "crawl(",
        "turn_left",
        "turn_right",
        "seek_food",
        "behavior_tree",
        "policy_network",
        "animation_command",
    ):
        assert forbidden not in header
    assert "posterior_touch_intensity" in header
    assert "physics_nodes_um" in header
    assert "read_render_mesh" in header



def test_mobile_checked_artifacts_preserve_host_and_scientific_boundaries():
    integration = json.loads(
        (ROOT / "data" / "mobile" / "mobile_core_integration_v1.json").read_text()
    )
    benchmark = json.loads(
        (ROOT / "data" / "benchmarks" / "mobile_core_host_v1.json").read_text()
    )
    assert integration["release_validated"] is False
    assert integration["android_ios_device_tested"] is False
    assert integration["reset_replay"]["status"] == "exact"
    assert len(integration["frames"]) == 47
    assert integration["fixed_step"] == {"dt_s": 0.001, "steps": 14600}
    assert integration["render_projection"] == {
        "read_only": True,
        "internal_physics_nodes_exposed_as_render_vertices": False,
        "axial_samples_per_segment": 2,
        "radial_samples": 12,
        "vertex_count": 302,
        "triangle_count": 600,
        "watertight_manifold_tested": True,
    }
    assert benchmark["host_tested_only"] is True
    assert benchmark["android_ios_device_tested"] is False
    assert benchmark["device_performance_claim_allowed"] is False
    assert benchmark["all_gates_pass"] is True
    assert all(benchmark["gates"].values())
    assert (
        benchmark["canonical_workload_fnv1a64"]
        == integration["result_summary"]["canonical_fnv1a64"]
    )


def test_ci_remains_manual_only():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
