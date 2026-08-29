import pytest

from oraclarva.muscles import AggregateMuscleIdentityProjection, load_muscle_atlas


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


def test_aggregate_identity_projection_names_all_fibers_without_claiming_geometry():
    projection = AggregateMuscleIdentityProjection(load_muscle_atlas())
    segment_activation = {
        "A1": 0.2, "A2": 0.3, "A3": 0.4,
        "A4": 0.5, "A5": 0.6, "A6": 0.7,
        "A7": 0.8, "T3": 0.9,
    }
    frame = projection.project(segment_activation)
    assert len(frame.activations) == 358
    assert frame.active_fiber_count == 358
    assert frame.provenance == "MODEL_FITTED"
    assert not frame.individual_geometry_executed
    assert "A1:left:M1:DA1" in frame.activations
    axial = projection.axial_proxy(frame, segment_activation)
    assert axial == pytest.approx(segment_activation)


def test_identity_segment_lesion_zeroes_named_fibers_before_axial_aggregation():
    projection = AggregateMuscleIdentityProjection(load_muscle_atlas())
    segment_activation = {
        segment: 0.5 for segment in ("A1", "A2", "A3", "A4", "A5", "A6")
    }
    frame = projection.project(
        segment_activation, lesioned_segments=("A4",)
    )
    a4_values = [
        value
        for identity, value in frame.activations.items()
        if frame.segment_by_fiber[identity] == "A4"
    ]
    assert len(a4_values) == 60
    assert set(a4_values) == {0.0}
    assert projection.axial_proxy(frame, segment_activation)["A4"] == 0.0


def test_bilateral_identity_projection_preserves_side_before_aggregation():
    projection = AggregateMuscleIdentityProjection(load_muscle_atlas())
    activation = {
        "A1": (0.2, 0.8),
        "A2": (0.3, 0.7),
        "A3": (0.4, 0.6),
        "A4": (0.5, 0.5),
        "A5": (0.6, 0.4),
        "A6": (0.7, 0.3),
        "A7": (0.8, 0.2),
        "T3": (0.9, 0.1),
    }
    frame = projection.project_bilateral(activation)
    assert len(frame.activations) == 358
    assert frame.active_fiber_count == 358
    assert frame.activations["A1:left:M1:DA1"] == pytest.approx(0.2)
    assert frame.activations["A1:right:M1:DA1"] == pytest.approx(0.8)
    axial = projection.bilateral_axial_proxy(frame, activation)
    assert set(axial) == set(activation)
    for segment, pair in activation.items():
        assert axial[segment] == pytest.approx(pair)


def test_dorsoventral_projection_uses_published_spatial_groups_only():
    projection = AggregateMuscleIdentityProjection(load_muscle_atlas())
    activation = {
        segment: (0.2, 0.8)
        for segment in ("A1", "A2", "A3", "A4", "A5", "A6")
    }
    frame = projection.project_dorsoventral(activation)

    assert len(frame.activations) == 358
    assert frame.active_fiber_count == 276
    assert frame.activations["A1:left:M1:DA1"] == pytest.approx(0.2)
    assert frame.axis_by_fiber["A1:left:M1:DA1"] == "dorsal"
    assert frame.activations["A1:right:M26:VA1"] == pytest.approx(0.8)
    assert frame.axis_by_fiber["A1:right:M26:VA1"] == "ventral"
    assert frame.activations["A1:left:M8:SBM"] == 0.0
    assert frame.axis_by_fiber["A1:left:M8:SBM"] is None
    axial = projection.dorsoventral_axial_proxy(frame, activation)
    for segment, pair in activation.items():
        assert axial[segment] == pytest.approx(pair)


def test_dorsoventral_lesion_removes_only_one_spatial_group_channel():
    projection = AggregateMuscleIdentityProjection(load_muscle_atlas())
    activation = {
        segment: (0.5, 0.5)
        for segment in ("A1", "A2", "A3", "A4", "A5", "A6")
    }
    frame = projection.project_dorsoventral(
        activation, lesioned_channels=(("A4", "dorsal"),)
    )
    axial = projection.dorsoventral_axial_proxy(frame, activation)
    assert axial["A4"] == pytest.approx((0.0, 0.5))
    assert axial["A3"] == pytest.approx((0.5, 0.5))
    with pytest.raises(ValueError, match="outside A1-A6"):
        projection.project_dorsoventral(
            activation, lesioned_channels=(("T3", "dorsal"),)
        )


def test_unilateral_muscle_lesion_zeroes_only_named_side_fibers():
    projection = AggregateMuscleIdentityProjection(load_muscle_atlas())
    activation = {
        segment: (0.5, 0.5)
        for segment in ("A1", "A2", "A3", "A4", "A5", "A6")
    }
    frame = projection.project_bilateral(
        activation, lesioned_channels=(("A4", "left"),)
    )
    a4_left = [
        value
        for identity, value in frame.activations.items()
        if frame.segment_by_fiber[identity] == "A4"
        and frame.side_by_fiber[identity] == "left"
    ]
    a4_right = [
        value
        for identity, value in frame.activations.items()
        if frame.segment_by_fiber[identity] == "A4"
        and frame.side_by_fiber[identity] == "right"
    ]
    assert len(a4_left) == len(a4_right) == 30
    assert set(a4_left) == {0.0}
    assert set(a4_right) == {0.5}
    assert projection.bilateral_axial_proxy(frame, activation)["A4"] == pytest.approx(
        (0.0, 0.5)
    )
    with pytest.raises(ValueError, match="outside A1-A6"):
        projection.project_bilateral(
            activation, lesioned_channels=(("T3", "left"),)
        )
