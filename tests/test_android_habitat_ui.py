from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOBILE = (
    ROOT
    / "android"
    / "app"
    / "src"
    / "main"
    / "kotlin"
    / "org"
    / "oraclarva"
    / "mobile"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_habitat_visual_assets_are_versioned_and_do_not_replace_live_mesh():
    reference = ROOT / "docs" / "assets" / "habitat-ui-reference.jpg"
    plate = (
        ROOT
        / "android"
        / "app"
        / "src"
        / "main"
        / "res"
        / "drawable-nodpi"
        / "habitat_plate.png"
    )
    capture = ROOT / "docs" / "assets" / "habitat-ui-redroid.png"
    renderer = (MOBILE / "OraclarvaRenderer.kt").read_text()

    assert sha256(reference) == (
        "4e620e5100bac6666fc0d2f07b79b835c27242d7f1cef088d60a338515d5c4ab"
    )
    assert sha256(plate) == (
        "3665d44b9adc18c6db053c649f13f47153195b9af6525e68d0c6ec66b42d60c3"
    )
    assert plate.stat().st_size > 2_000_000
    assert sha256(capture) == (
        "fe31639597dfe4127ad90079e259f59f40e0181fb9c80d459702b6be7c25f02c"
    )
    assert capture.stat().st_size > 1_000_000
    assert "R.drawable.habitat_plate" in renderer
    assert "drawBackground()" in renderer
    assert "uViewportAspect" in renderer
    assert "uTextureAspect" in renderer
    assert "GLES30.glShaderSource(shader, source.trimIndent())" in renderer
    assert "vec3 activeColor" in renderer
    assert "vec3 active =" not in renderer
    assert "BODY_AXIAL_SCALE = 0.73" in renderer
    assert "BODY_RADIAL_SCALE = 1.20" in renderer
    assert "Matrix.translateM(model, 0, -0.55f, 0f, -0.45f)" in renderer
    assert "Matrix.rotateM(model, 0, -10f, 0f, 1f, 0f)" in renderer
    assert "* BODY_AXIAL_SCALE" in renderer
    assert "GLES30.glDrawElements" in renderer
    assert "frame.vertices" in renderer


def test_habitat_controls_change_environment_inputs_not_body_commands():
    activity = (MOBILE / "MainActivity.kt").read_text()
    surface = (MOBILE / "OraclarvaSurfaceView.kt").read_text()
    combined = (activity + surface).lower()

    assert '"ORACLARVA"' in activity
    assert '"HABITAT"' in activity
    assert '"LIGHT"' in activity
    assert '"GROUND"' in activity
    assert '"OBSTACLE"' in activity
    assert '"OBSERVE"' in activity
    assert '"FIELD"' in activity
    assert '"SENSE"' in activity
    assert '"BODY"' in activity
    assert "setLightField(x, y)" in activity
    assert "setPhysicalFieldGradients(lateralGradient, verticalGradient)" in activity
    assert "lightFieldTouch(normalizedX, normalizedY)" in surface
    assert "createdSurface.pulsePosteriorContact()" in activity
    assert 'label = "GROUND"' in activity
    assert "enabled = false" in activity
    assert "setSimulationPaused" in activity
    assert "release_validated=false" in activity
    assert "R.drawable.ic_light_mode_24" in activity
    assert "R.drawable.ic_grain_24" in activity
    assert "R.drawable.ic_bubble_chart_24" in activity
    assert "seekbar" not in combined
    for forbidden in ("crawl(", "turnleft", "turnright", "behavior tree", "fsm"):
        assert forbidden not in combined


def test_habitat_core_controls_expose_accessibility_semantics():
    activity = (MOBILE / "MainActivity.kt").read_text()
    surface = (MOBILE / "OraclarvaSurfaceView.kt").read_text()

    assert 'contentDescription = "Pause simulation"' in activity
    assert 'contentDescription = "Show simulation observation details"' in activity
    assert "contentDescription = description" in activity
    assert "override fun performClick()" in surface
    assert "dp(48)" in activity
