from oraclarva.body import load_body_spec
from oraclarva.body3d import ScientificBody3D, Vec3
from oraclarva.surface import build_surface_mesh


def test_surface_is_one_watertight_mesh_with_anatomical_face_labels():
    body = ScientificBody3D(load_body_spec())
    mesh = build_surface_mesh(body, axial_subdivisions=3, radial_samples=12)

    assert mesh.is_watertight
    assert len(mesh.vertices) == (12 * 3 + 1) * 12 + 2
    assert set(mesh.face_segment_ids) == {segment.id for segment in body.geometry}
    assert all(count == 2 for count in mesh.edge_use_counts().values())


def test_surface_stays_watertight_after_physical_contraction_and_bending():
    body = ScientificBody3D(load_body_spec(), pinned_nodes={0})
    body.set_activations({"A4": 0.8})
    for _ in range(20):
        body.step(0.001, gravity=Vec3(0.0, 0.0, 0.0), ground_z=None)

    middle = body.particles[6]
    middle.position = Vec3(middle.position.x, middle.position.y + 15e-6, middle.position.z)
    mesh = build_surface_mesh(body, axial_subdivisions=4, radial_samples=16)

    assert mesh.is_watertight
    assert len(mesh.faces) == 12 * 4 * 16 * 2 + 16 * 2
