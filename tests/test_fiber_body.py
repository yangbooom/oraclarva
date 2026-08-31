"""Tests for named-fiber force projection onto shared body nodes."""

import pytest

from oraclarva.body import load_body_spec
from oraclarva.body3d import ScientificBody3D, Vec3
from oraclarva.fiber_body import NamedFiberBodyCoupling
from oraclarva.muscles import (
    NeuralMuscleActivationModel,
    load_neural_muscle_identity_projection,
)


def coupling():
    return NamedFiberBodyCoupling(
        body=ScientificBody3D(load_body_spec()),
        projection=load_neural_muscle_identity_projection(),
        dt_s=0.001,
        active_tension_gain=15.0,
        passive_stiffness=180.0,
        damping=24.0,
        acceleration_scale_m_s2_per_model_force=0.002,
    )


def activation_model(projection):
    return NeuralMuscleActivationModel(projection, 0.001, 0.020, 0.080, 1.0)


def test_geometry_expands_only_146_mapped_a1_a6_fibers():
    model = coupling()

    assert len(model.geometries) == 146
    assert {item.segment_id for item in model.geometries} == {
        "A1", "A2", "A3", "A4", "A5", "A6"
    }
    assert not any(item.segment_id == "A7" for item in model.geometries)
    assert all(item.coordinate_provenance == "ANATOMY_DERIVED" for item in model.geometries)


def test_right_geometry_is_exact_theta_mirror_of_left_reference():
    model = coupling()
    left = next(
        item for item in model.geometries
        if item.segment_id == "A1" and item.side == "left" and item.muscle_number == "10"
    )
    right = next(
        item for item in model.geometries
        if item.segment_id == "A1" and item.side == "right" and item.muscle_number == "10"
    )

    assert right.origin.s == left.origin.s
    assert right.insertion.s == left.insertion.s
    assert right.origin.theta_rad == -left.origin.theta_rad
    assert right.insertion.theta_rad == -left.insertion.theta_rad
    assert left.mirror_or_homology == "A1_left_reference"
    assert right.mirror_or_homology == "bilateral_mirror"
    a2_left = next(
        item
        for item in model.geometries
        if item.segment_id == "A2"
        and item.side == "left"
        and item.muscle_number == "10"
    )
    a2_right = next(
        item
        for item in model.geometries
        if item.segment_id == "A2"
        and item.side == "right"
        and item.muscle_number == "10"
    )
    assert a2_left.mirror_or_homology == "A2_A6_homology"
    assert (
        a2_right.mirror_or_homology
        == "A2_A6_homology_and_bilateral_mirror"
    )


def test_zero_activation_has_zero_node_force_and_exact_trace_counts():
    model = coupling()
    projection = model.projection
    activation = activation_model(projection)
    frame = activation.step(0.0, projection.emit(()))
    force = model.step(
        frame,
        last_source_by_fiber=activation.last_applied_source,
        last_spike_time_s_by_fiber=activation.last_applied_spike_s,
    )

    assert force.active_fiber_count == 0
    assert force.traced_active_fiber_count == 0
    assert all(value == Vec3(0.0, 0.0, 0.0) for value in force.node_forces_model_units.values())
    assert force.mapped_fiber_count == 146
    assert force.unmapped_fiber_count == 212
    assert force.blocked_segments == ("A7",)
    assert not force.parallel_fitted_bridge_executed


def test_active_force_is_traced_and_equal_opposite_across_shared_nodes():
    model = coupling()
    projection = model.projection
    mapping = next(item for item in projection.mappings if item.fiber_id == "A1:left:M1:DA1")
    activation = activation_model(projection)
    first = activation.step(0.0, projection.emit((mapping.source_node_id,)))
    first_force = model.step(
        first,
        last_source_by_fiber=activation.last_applied_source,
        last_spike_time_s_by_fiber=activation.last_applied_spike_s,
    )
    assert first_force.active_fiber_count == 0
    frame = activation.step(0.001, projection.emit(()))
    force = model.step(
        frame,
        last_source_by_fiber=activation.last_applied_source,
        last_spike_time_s_by_fiber=activation.last_applied_spike_s,
    )
    target = force.fibers[mapping.fiber_id]
    total = Vec3(0.0, 0.0, 0.0)
    for value in force.node_forces_model_units.values():
        total = total + value

    assert target.activation > 0.0
    assert target.active_tension_model_units > 0.0
    assert target.source_node_id == mapping.source_node_id
    assert target.source_spike_time_s == 0.0
    assert force.active_fiber_count == force.traced_active_fiber_count == 1
    assert total.norm() == pytest.approx(0.0, abs=1e-12)


def test_body_accepts_finite_node_acceleration_and_rejects_unknown_node():
    body = ScientificBody3D(load_body_spec())
    before = body.particles[1].position
    body.step(
        0.001,
        gravity=Vec3(0.0, 0.0, 0.0),
        ground_z=None,
        external_accelerations_m_s2={1: Vec3(0.0, 1.0, 0.0)},
    )
    assert body.particles[1].position.y != before.y

    with pytest.raises(ValueError, match="unknown body node"):
        body.step(
            0.001,
            gravity=Vec3(0.0, 0.0, 0.0),
            ground_z=None,
            external_accelerations_m_s2={99: Vec3(0.0, 1.0, 0.0)},
        )
