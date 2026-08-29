from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWER_SOURCE = (ROOT / "viewer" / "src" / "main.js").read_text()
VIEWER_HTML = (ROOT / "viewer" / "index.html").read_text()


def test_viewer_consumes_closed_loop_nodes_through_a_separate_skin():
    assert 'l1_closed_loop_v0.json' in VIEWER_SOURCE
    assert 'function sampleTrajectory' in VIEWER_SOURCE
    assert 'sample.nodes.map(physicsNodeToWorld)' in VIEWER_SOURCE
    assert 'bodyMesh.userData.continuousSurface = true' in VIEWER_SOURCE
    assert 'closedLoopTrajectory.release_validated !== false' in VIEWER_SOURCE


def test_viewer_has_no_renderer_authored_gait_controls_or_wave():
    forbidden_source = (
        'waveCenter',
        'function centerline',
        'let contraction',
        'let bend',
        'let phase',
    )
    assert all(token not in VIEWER_SOURCE for token in forbidden_source)
    assert 'id="contraction"' not in VIEWER_HTML
    assert 'id="bend"' not in VIEWER_HTML
    assert 'id="timeline"' in VIEWER_HTML
    assert 'id="speed"' in VIEWER_HTML
