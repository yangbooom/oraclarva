import pytest

from oraclarva.muscles import load_muscle_atlas


def test_abdominal_atlas_has_exact_a1_to_a6_identity_counts():
    atlas = load_muscle_atlas()

    assert len(atlas.template) == 30
    assert [muscle.number for muscle in atlas.template] == [str(i) for i in range(1, 31)]
    assert len(atlas.fibers_for_segment("A1")) == 58
    for segment in ("A2", "A3", "A4", "A5", "A6"):
        assert len(atlas.fibers_for_segment(segment)) == 60
    assert len(atlas.all_supported_fibers) == 358


def test_a1_lacks_muscle_25_and_homologous_segments_include_it_bilaterally():
    atlas = load_muscle_atlas()

    assert not any(fiber.muscle.number == "25" for fiber in atlas.fibers_for_segment("A1"))
    a2_muscle_25 = [
        fiber for fiber in atlas.fibers_for_segment("A2") if fiber.muscle.number == "25"
    ]
    assert {fiber.side for fiber in a2_muscle_25} == {"left", "right"}
    assert all(fiber.provenance == "derived_homology" for fiber in a2_muscle_25)


def test_atlas_fails_closed_outside_supported_homology_and_for_physics():
    atlas = load_muscle_atlas()

    assert atlas.blocked_segments == ("PSC", "T1", "T2", "T3", "A7", "A8")
    assert not atlas.mechanically_executable
    assert not atlas.is_full_body_ready
    with pytest.raises(ValueError, match="no supported"):
        atlas.fibers_for_segment("T3")


def test_audit_reports_geometry_blockers():
    summary = load_muscle_atlas().audit_summary()

    assert summary["fibers_per_segment"] == {
        "A1": 58,
        "A2": 60,
        "A3": 60,
        "A4": 60,
        "A5": 60,
        "A6": 60,
    }
    assert summary["supported_fibers"] == 358
    assert not summary["geometry_gate"]["attachment_coordinates_complete"]
