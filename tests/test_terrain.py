import pytest

from oraclarva.body import load_body_spec
from oraclarva.body3d import ScientificBody3D, Vec3
from oraclarva.terrain import ContactWorld, PlaneCollider, SphereCollider


def test_plane_and_sphere_contact_project_without_penetration():
    plane = PlaneCollider.from_slopes(0.1, -0.05)
    point = Vec3(10e-6, 20e-6, -5e-6)
    projection = plane.query(point, 4e-6)
    assert projection is not None
    assert plane.signed_distance_m(projection.position) == pytest.approx(4e-6)

    sphere = SphereCollider(Vec3(0.0, 0.0, 0.0), 20e-6)
    projection = sphere.query(Vec3(10e-6, 0.0, 0.0), 5e-6)
    assert projection is not None
    assert (projection.position - sphere.center_m).norm() == pytest.approx(25e-6)
    assert projection.normal.x == pytest.approx(1.0)
    assert projection.normal.y == pytest.approx(0.0)
    assert projection.normal.z == pytest.approx(0.0)


def test_contact_world_samples_only_sensory_enabled_obstacles():
    world = ContactWorld((
        PlaneCollider.from_slopes(0.0, 0.0, sensory_enabled=False),
        SphereCollider(Vec3(0.0, -50e-6, 50e-6), 20e-6),
    ))
    near = world.receptor_intensity(
        Vec3(0.0, -75e-6, 50e-6),
        sensing_range_m=100e-6,
    )
    far = world.receptor_intensity(
        Vec3(0.0, 75e-6, 50e-6),
        sensing_range_m=100e-6,
    )
    assert near > far
    assert 0.0 <= far <= near <= 1.0
    with pytest.raises(ValueError, match="sensing range"):
        world.receptor_intensity(Vec3(0.0, 0.0, 0.0), sensing_range_m=0.0)


def test_xpbd_nodes_follow_tilted_plane_contact_normal():
    plane = PlaneCollider.from_slopes(0.12, 0.04)
    world = ContactWorld((plane,))
    body = ScientificBody3D(load_body_spec())
    for _ in range(30):
        body.step(
            0.001,
            gravity=Vec3(0.0, 0.0, -9.81),
            ground_z=None,
            ground_velocity_retention_x=(0.15, 0.85),
            use_local_tangent_friction=True,
            contact_surface=world,
        )
    for index, particle in enumerate(body.particles):
        assert plane.signed_distance_m(particle.position) >= (
            body._node_clearance(index) - 1e-12
        )


def test_sphere_obstacle_and_plane_resolve_simultaneous_contacts():
    body = ScientificBody3D(load_body_spec())
    head = body.particles[0].position
    sphere = SphereCollider(
        Vec3(head.x - 25e-6, head.y, head.z),
        20e-6,
    )
    plane = PlaneCollider.from_slopes(0.0, 0.0)
    world = ContactWorld((plane, sphere))
    for _ in range(10):
        body.step(
            0.001,
            gravity=Vec3(0.0, 0.0, -9.81),
            ground_z=None,
            ground_velocity_retention_x=(0.15, 0.85),
            use_local_tangent_friction=True,
            contact_surface=world,
        )
    for index, particle in enumerate(body.particles):
        assert sphere.signed_distance_m(particle.position) >= (
            body._node_clearance(index) - 1e-12
        )
        assert plane.signed_distance_m(particle.position) >= (
            body._node_clearance(index) - 1e-12
        )


def test_body_rejects_two_contact_environments_at_once():
    body = ScientificBody3D(load_body_spec())
    world = ContactWorld((PlaneCollider.from_slopes(0.0, 0.0),))
    with pytest.raises(ValueError, match="either ground_z"):
        body.step(0.001, ground_z=0.0, contact_surface=world)
