from math import isclose, pi

import pytest
from math import atan2, degrees, hypot, pi

from oraclarva.body import load_body_spec
from oraclarva.body3d import ScientificBody3D, Vec3


def test_l1_body_spec_is_valid_and_bounded_by_cited_cohort():
    spec = load_body_spec()
    assert len(spec.segments) == 12
    assert isclose(sum(segment.length_fraction for segment in spec.segments), 1.0)
    assert spec.total_length.upper <= 1e-3


def test_segment_geometry_sums_to_nominal_length():
    spec = load_body_spec()
    geometry = spec.segment_geometry()
    assert isclose(sum(segment.rest_length_m for segment in geometry), 0.0009)
    assert geometry[6].width_m > geometry[0].width_m
    assert geometry[6].width_m > geometry[-1].width_m


def test_l3_mechanics_are_scaled_with_declared_similarity_laws():
    mechanics = load_body_spec().scaled_mechanics()
    assert isclose(mechanics.linear_scale, 0.9 / 3.5)
    assert isclose(mechanics.segment_k1_n_per_m, 40.7 * 0.9 / 3.5)
    assert isclose(mechanics.segment_c_n_s_per_m, 2640 * 0.9 / 3.5)
    assert isclose(mechanics.maximum_muscle_force_n, 0.0067 * (0.9 / 3.5) ** 2)


def test_unmeasured_l1_geometry_is_not_mislabeled_observed():
    spec = load_body_spec()
    assert spec.total_length.provenance == "hypothesis"
    assert spec.maximum_width.provenance == "constraint"
    assert spec.raw["segment_geometry_provenance"]["provenance"] == "hypothesis"


def test_only_continuous_segment_activation_is_accepted():
    body = ScientificBody3D(load_body_spec())
    body.set_activations({"A4": 0.6})
    with pytest.raises(ValueError):
        body.set_activations({"A4": 1.1})
    with pytest.raises(KeyError):
        body.set_activations({"turn_left": 1.0})


def test_active_segment_shortens_and_whole_cavity_preserves_volume():
    spec = load_body_spec()
    body = ScientificBody3D(spec, pinned_nodes={0})
    segment_index = next(i for i, segment in enumerate(spec.segments) if segment.id == "PSC")
    rest_length = body.segment_length_m(segment_index)
    rest_width = body.current_width_m(segment_index)
    distant_width = body.current_width_m(len(body.geometry) - 1)
    body.set_activations({"PSC": 1.0})
    for _ in range(25):
        body.step(0.001, gravity=Vec3(0.0, 0.0, 0.0), ground_z=None)
    assert body.segment_length_m(segment_index) < rest_length
    assert body.current_width_m(segment_index) > rest_width
    assert body.current_width_m(len(body.geometry) - 1) > distant_width
    assert body.cross_section_scale(0) == pytest.approx(body.cross_section_scale(8))

    current_volume = sum(
        pi
        * (body.current_width_m(index) / 2)
        * (body.current_height_m(index) / 2)
        * body.segment_length_m(index)
        for index in range(len(body.geometry))
    )
    rest_volume = sum(segment.volume_m3 for segment in body.geometry)
    assert current_volume == pytest.approx(rest_volume, rel=1e-12)


def test_unstimulated_body_preserves_rest_lengths_without_gravity():
    body = ScientificBody3D(load_body_spec(), pinned_nodes={0})
    before = [body.segment_length_m(i) for i in range(len(body.geometry))]
    for _ in range(10):
        body.step(0.001, gravity=Vec3(0.0, 0.0, 0.0), ground_z=None)
    after = [body.segment_length_m(i) for i in range(len(body.geometry))]
    assert after == pytest.approx(before, rel=1e-9, abs=1e-12)


def test_ground_tangential_retention_is_a_bounded_physical_parameter():
    body = ScientificBody3D(load_body_spec())
    with pytest.raises(ValueError, match="tangential retention"):
        body.step(0.001, ground_velocity_retention_x=(1.1, 0.1))
    body.step(0.001, ground_velocity_retention_x=(0.9, 0.1))


def test_directional_ground_retention_can_include_current_external_force():
    def shifted(include_acceleration: bool) -> float:
        body = ScientificBody3D(load_body_spec())
        before = sum(item.position.x for item in body.particles) / len(
            body.particles
        )
        body.step(
            0.001,
            gravity=Vec3(0.0, 0.0, 0.0),
            ground_z=0.0,
            external_accelerations_m_s2={
                index: Vec3(1.0, 0.0, 0.0)
                for index in range(len(body.particles))
            },
            velocity_retention=0.0,
            ground_velocity_retention_x=(0.9, 0.1),
            use_local_tangent_friction=True,
            directional_retention_includes_acceleration=include_acceleration,
        )
        after = sum(item.position.x for item in body.particles) / len(
            body.particles
        )
        return after - before

    legacy = shifted(False)
    corrected = shifted(True)
    assert legacy == pytest.approx(1e-6, rel=1e-9)
    assert corrected == pytest.approx(legacy * 0.1, rel=1e-9)


def test_segment_specific_shortening_capacity_is_bounded_and_changes_target():
    spec = load_body_spec()
    body = ScientificBody3D(
        spec, maximum_shortening_by_segment={"A4": 0.5}
    )
    index = next(i for i, segment in enumerate(body.geometry) if segment.id == "A4")
    body.set_activations({"A4": 1.0})
    assert body.target_length_m(index) == pytest.approx(
        body.geometry[index].rest_length_m * 0.5
    )
    with pytest.raises(ValueError, match="shortening capacity"):
        ScientificBody3D(
            spec,
            maximum_shortening_by_segment={
                "A4": spec.maximum_shortening_fraction.upper + 0.01
            },
        )
    with pytest.raises(KeyError, match="unknown segment"):
        ScientificBody3D(
            spec, maximum_shortening_by_segment={"crawl": 0.5}
        )


def test_bilateral_activation_creates_mirrored_active_curvature():
    def simulate(pair):
        body = ScientificBody3D(load_body_spec())
        body.set_bilateral_activations({
            segment: pair for segment in ("A2", "A3", "A4", "A5", "A6")
        })
        for _ in range(50):
            body.step(
                0.001,
                gravity=Vec3(0.0, 0.0, 0.0),
                ground_z=None,
                active_curvature_gain=0.05,
            )
        return body

    left = simulate((1.0, 0.0))
    right = simulate((0.0, 1.0))
    symmetric = simulate((1.0, 1.0))
    left_y = [particle.position.y for particle in left.particles]
    right_y = [particle.position.y for particle in right.particles]
    assert max(abs(value) for value in left_y) > 50e-6
    # Body coordinates run anterior-to-posterior in +x and left-to-right in +y.
    assert min(left_y) < 0.0
    assert max(right_y) > 0.0
    assert right_y == pytest.approx([-value for value in left_y], abs=1e-15)
    assert [particle.position.y for particle in symmetric.particles] == pytest.approx(
        [0.0] * len(symmetric.particles), abs=1e-15
    )


def test_dorsoventral_activation_creates_opposed_local_binormal_pitch():
    def simulate(pair):
        body = ScientificBody3D(load_body_spec())
        initial_axis = body.particles[-1].position - body.particles[0].position
        initial_pitch = degrees(atan2(
            initial_axis.z, hypot(initial_axis.x, initial_axis.y)
        ))
        body.set_dorsoventral_activations({
            segment: pair for segment in ("A2", "A3", "A4", "A5", "A6")
        })
        for _ in range(50):
            body.step(
                0.001,
                gravity=Vec3(0.0, 0.0, 0.0),
                ground_z=None,
                active_pitch_curvature_gain=0.05,
            )
        axis = body.particles[-1].position - body.particles[0].position
        pitch_change = degrees(atan2(axis.z, hypot(axis.x, axis.y))) - initial_pitch
        return body, pitch_change

    dorsal, dorsal_pitch = simulate((1.0, 0.0))
    ventral, ventral_pitch = simulate((0.0, 1.0))
    symmetric, symmetric_pitch = simulate((0.5, 0.5))

    assert ventral_pitch < symmetric_pitch < dorsal_pitch
    assert dorsal_pitch == pytest.approx(-ventral_pitch, abs=0.3)
    assert abs(symmetric_pitch) < 1.0
    for body in (dorsal, ventral, symmetric):
        assert [particle.position.y for particle in body.particles] == pytest.approx(
            [0.0] * len(body.particles), abs=1e-15
        )


def test_spatial_activation_combines_yaw_and_pitch_without_double_counting():
    body = ScientificBody3D(load_body_spec())
    driven = ("A2", "A3", "A4", "A5", "A6")
    body.set_spatial_activations(
        {segment: (1.0, 0.0) for segment in driven},
        {segment: (1.0, 0.0) for segment in driven},
    )
    for segment in driven:
        index = next(
            i for i, geometry in enumerate(body.geometry) if geometry.id == segment
        )
        assert body.activations[index] == pytest.approx(0.5)
    for _ in range(50):
        body.step(
            0.001,
            gravity=Vec3(0.0, 0.0, 0.0),
            ground_z=None,
            active_curvature_gain=0.05,
            active_pitch_curvature_gain=0.05,
        )
    assert max(abs(particle.position.y) for particle in body.particles) > 20e-6
    initial = ScientificBody3D(load_body_spec())
    assert max(
        abs(particle.position.z - reference.position.z)
        for particle, reference in zip(body.particles, initial.particles, strict=True)
    ) > 20e-6

    with pytest.raises(ValueError, match="two opposed pairs"):
        body.set_spatial_activations({"A4": (1.0,)}, {})
    with pytest.raises(ValueError, match="spatial muscle activation"):
        body.set_spatial_activations({"A4": (1.1, 0.0)}, {})
    with pytest.raises(KeyError, match="unknown spatial activation"):
        body.set_spatial_activations({"move_3d": (1.0, 0.0)}, {})


def test_dorsoventral_activation_validation_and_ground_contact():
    body = ScientificBody3D(load_body_spec())
    with pytest.raises(ValueError, match="dorsal/ventral pair"):
        body.set_dorsoventral_activations({"A4": (1.0,)})
    with pytest.raises(ValueError, match="dorsoventral muscle activation"):
        body.set_dorsoventral_activations({"A4": (1.1, 0.0)})
    with pytest.raises(KeyError, match="unknown segment"):
        body.set_dorsoventral_activations({"pitch_up": (1.0, 0.0)})

    body.set_dorsoventral_activations({
        segment: (0.0, 1.0) for segment in ("A2", "A3", "A4")
    })
    for _ in range(20):
        body.step(0.001, active_pitch_curvature_gain=0.05, ground_z=0.0)
    assert all(
        particle.position.z >= body._node_clearance(index)
        for index, particle in enumerate(body.particles)
    )


def test_virtual_bilateral_rails_report_side_specific_shortening():
    body = ScientificBody3D(load_body_spec())
    body.set_bilateral_activations({"A4": (1.0, 0.0), "A5": (1.0, 0.0)})
    for _ in range(50):
        body.step(
            0.001,
            gravity=Vec3(0.0, 0.0, 0.0),
            ground_z=None,
            active_curvature_gain=0.05,
        )
    a4_index = next(
        index for index, segment in enumerate(body.geometry) if segment.id == "A4"
    )
    assert body.bilateral_segment_length_m(
        a4_index, "left"
    ) < body.bilateral_segment_length_m(a4_index, "right")
    with pytest.raises(ValueError, match="side"):
        body.bilateral_segment_length_m(a4_index, "dorsal")


def test_initial_yaw_rotates_body_pose_without_changing_geometry():
    base = ScientificBody3D(load_body_spec())
    rotated = ScientificBody3D(load_body_spec(), initial_yaw_rad=pi / 2)

    for base_particle, rotated_particle in zip(
        base.particles, rotated.particles, strict=True
    ):
        assert rotated_particle.position.x == pytest.approx(-base_particle.position.y)
        assert rotated_particle.position.y == pytest.approx(base_particle.position.x)
        assert rotated_particle.position.z == pytest.approx(base_particle.position.z)
    with pytest.raises(ValueError, match="initial yaw"):
        ScientificBody3D(load_body_spec(), initial_yaw_rad=float("nan"))


def test_bilateral_surface_positions_are_mirrored_read_only_sensor_points():
    body = ScientificBody3D(load_body_spec())
    left = body.bilateral_surface_position_m(0, "left")
    right = body.bilateral_surface_position_m(0, "right")
    center = body.particles[0].position

    assert left.x == pytest.approx(right.x)
    assert left.y - center.y == pytest.approx(-(right.y - center.y))
    assert left.z == pytest.approx(right.z)
    with pytest.raises(IndexError, match="node index"):
        body.bilateral_surface_position_m(-1, "left")
    with pytest.raises(ValueError, match="left or right"):
        body.bilateral_surface_position_m(0, "dorsal")


def test_bilateral_activation_rejects_commands_and_invalid_pairs():
    body = ScientificBody3D(load_body_spec())
    with pytest.raises(KeyError):
        body.set_bilateral_activations({"turn_left": (1.0, 0.0)})
    with pytest.raises(ValueError, match="left/right pair"):
        body.set_bilateral_activations({"A4": (1.0,)})
    with pytest.raises(ValueError, match="bilateral muscle activation"):
        body.set_bilateral_activations({"A4": (1.1, 0.0)})
