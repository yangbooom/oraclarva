from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android"


@pytest.fixture(scope="module")
def android_host_output(tmp_path_factory: pytest.TempPathFactory) -> str:
    output = tmp_path_factory.mktemp("android-jni")
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_android_host_bridge.py"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def test_android_jni_boundary_is_deterministic_and_preserves_claim_boundary(
    android_host_output: str,
):
    rows = {
        fields[0]: fields[1:]
        for line in android_host_output.splitlines()
        if (fields := line.split("\t"))
    }
    assert tuple(map(float, rows["uniform"][:3])) == pytest.approx(
        (14.6, 467.539285129721, 0.0), rel=0.0, abs=1e-10
    )
    assert int(rows["uniform"][3]) == 53_524
    assert tuple(map(float, rows["lateral"])) == pytest.approx(
        (-3.831016030048, -1.956735327396), rel=0.0, abs=2e-12
    )
    assert tuple(map(int, rows["render"])) == (302, 600)
    assert rows["replay"] == ["exact"]
    assert rows["release_validated"] == ["false"]


def test_android_runtime_keeps_native_physics_and_render_projection_separate():
    bridge = (
        ANDROID / "app" / "src" / "main" / "cpp" / "android_bridge.cpp"
    ).read_text()
    renderer = (
        ANDROID
        / "app"
        / "src"
        / "main"
        / "kotlin"
        / "org"
        / "oraclarva"
        / "mobile"
        / "OraclarvaRenderer.kt"
    ).read_text()
    organism = (
        ANDROID
        / "app"
        / "src"
        / "main"
        / "kotlin"
        / "org"
        / "oraclarva"
        / "mobile"
        / "NativeOrganism.kt"
    ).read_text()

    assert "oraclarva_mobile_advance_environment" in bridge
    assert "oraclarva_mobile_read_environment_snapshot" in bridge
    assert "oraclarva_mobile_read_render_mesh" in bridge
    assert "jdoubleArray state_values" in bridge
    assert "jfloatArray render_vertices" in bridge
    assert "jintArray render_indices" in bridge
    assert "constexpr std::size_t kVertexStride = 7" in bridge
    assert "private const val FIXED_DT_S = 0.001" in renderer
    assert "private const val MAX_STEPS_PER_FRAME = 50" in renderer
    assert "native.advance(field" in renderer
    assert "val frame = native.readFrame()" in renderer
    assert "GLES30.glDrawElements" in renderer
    assert "frame.vertices" in renderer
    assert "frame.state[30 + node * 3]" in renderer
    assert "native organism must stay on its owning GL thread" in organism
    assert "Thread.currentThread() === ownerThread" in organism
    assert "require(!frame.releaseValidated)" in organism

    exposed = (bridge + renderer + organism).lower()
    for forbidden in ("crawl(", "turnleft", "turnright", "behavior tree", "fsm"):
        assert forbidden not in exposed


def test_android_package_targets_mobile_native_runtime_without_automatic_ci():
    application = (ANDROID / "app" / "build.gradle.kts").read_text()
    manifest = (ANDROID / "app" / "src" / "main" / "AndroidManifest.xml").read_text()
    wrapper_properties = (
        ANDROID / "gradle" / "wrapper" / "gradle-wrapper.properties"
    ).read_text()
    wrapper_jar = ANDROID / "gradle" / "wrapper" / "gradle-wrapper.jar"
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    documentation = (ROOT / "docs" / "ANDROID_NATIVE_RUNTIME_V1.md").read_text()
    media = ROOT / "docs" / "assets" / "oraclarva_android_mobile_runtime.gif"

    assert 'compileSdk = 36' in application
    assert 'abiFilters += listOf("arm64-v8a", "x86_64")' in application
    assert 'path = file("src/main/cpp/CMakeLists.txt")' in application
    assert 'android:glEsVersion="0x00030000"' in manifest
    assert "<uses-permission" not in manifest
    assert (
        "distributionSha256Sum="
        "553c78f50dafcd54d65b9a444649057857469edf836431389695608536d6b746"
    ) in wrapper_properties
    assert hashlib.sha256(wrapper_jar.read_bytes()).hexdigest() == (
        "497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7"
    )
    assert media.stat().st_size > 1_000_000
    assert "host JVM" in documentation
    assert "not Android device or emulator footage" in documentation
    assert "release_validated=false" in documentation
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "32fd9a750c9edebbbd9faa8426305e1a9936625c3cef466126c86af6ce04fe82" in documentation
    assert "device_performance_claim=false" in documentation


def test_android_ndk_parity_gate_covers_both_abis_without_device_claim():
    runner = (ROOT / "tools" / "build_android_ndk_parity.py").read_text()
    native_gate = (ROOT / "tools" / "android_ndk_parity_main.cpp").read_text()

    assert '"arm64-v8a": "aarch64-linux-android26-clang++"' in runner
    assert '"x86_64": "x86_64-linux-android26-clang++"' in runner
    assert '"-static"' in runner
    assert "tolerance = 1e-8" in runner
    assert 'print("device_performance_claim\\tfalse")' in runner
    assert "oraclarva_mobile_create_spatial" in native_gate
    assert "oraclarva_mobile_advance_environment" in native_gate
    assert "oraclarva_mobile_read_render_mesh" in native_gate
    assert "reset replay drifted" in native_gate
    assert 'release_validated\\tfalse' in native_gate
