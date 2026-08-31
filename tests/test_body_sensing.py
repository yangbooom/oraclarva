from __future__ import annotations

from oraclarva.body import load_body_spec
from oraclarva.body3d import ScientificBody3D, Vec3
from oraclarva.body_sensing import (
    BodyStateSensoryTransducer,
    SENSED_SEGMENTS,
)
from oraclarva.environment_inputs import LinearScalarField
from oraclarva.visual import (
    L1VisualClosedLoopLarva,
    load_l1_dbd_motor_feedback,
    load_visual_config,
)


def _parameters():
    return load_visual_config()["body_state_sensory_feedback"]


def _a1_index(body: ScientificBody3D) -> int:
    return next(i for i, segment in enumerate(body.geometry) if segment.id == "A1")


def _move_a1_boundary(body: ScientificBody3D, dx_m: float) -> None:
    particle = body.particles[_a1_index(body) + 1]
    particle.position = Vec3(
        particle.position.x + dx_m,
        particle.position.y,
        particle.position.z,
    )
    particle.previous_position = particle.position


def _zero_light() -> LinearScalarField:
    return LinearScalarField(
        modality_id="light",
        unit="W_m-2",
        origin_m=Vec3(0.0, 0.0, 0.0),
        value_at_origin=0.0,
        gradient_per_m=Vec3(0.0, 0.0, 0.0),
        lower_bound=0.0,
        upper_bound=0.0,
    )


def _perturbed_larva(*, lesions=(), fiber_lesions=()):
    larva = L1VisualClosedLoopLarva(
        field=_zero_light(),
        lesion_node_ids=lesions,
        lesion_muscle_fiber_ids=fiber_lesions,
        record_visual_frames=True,
    )
    _move_a1_boundary(larva.spatial.body, 10e-6)
    return larva


def test_published_dbd_motor_table_preserves_all_and_executable_counts():
    source = load_l1_dbd_motor_feedback()
    assert source["summary"] == {
        "identified_dbd_neurons": 2,
        "motor_targets": 7,
        "connection_pairs": 7,
        "synaptic_contacts": 11,
        "executable_overlap_pairs": 3,
        "executable_overlap_contacts": 3,
        "unexecuted_pairs": 4,
        "unexecuted_contacts": 8,
    }
    assert sum(
        item["synaptic_contacts"]
        for item in source["connections"]
        if item["executable"]
    ) == 3


def test_body_state_transduction_covers_a1_a6_and_preserves_provenance():
    body = ScientificBody3D(load_body_spec())
    frame = BodyStateSensoryTransducer(body, _parameters()).sample(0.0)
    assert tuple(frame.segments) == SENSED_SEGMENTS
    assert len(frame.dbd_channels) == 12
    assert len(frame.contraction_channels) == 12
    assert frame.dbd_channels["A1:left"].identity_provenance == "MEASURED_PUBLISHED"
    assert frame.dbd_channels["A2:left"].identity_provenance == "ANATOMY_DERIVED"
    assert all(item.transduction_provenance == "MODEL_FITTED" for item in frame.dbd_channels.values())
    assert not frame.contact_neural_path_executed


def test_stretch_and_shortening_have_opposite_directional_channels():
    stretched = ScientificBody3D(load_body_spec())
    stretch_transducer = BodyStateSensoryTransducer(stretched, _parameters())
    _move_a1_boundary(stretched, 5e-6)
    stretch_frame = stretch_transducer.sample(0.0)
    assert stretch_frame.segments["A1"].strain > 0.0
    assert stretch_frame.dbd_channels["A1:left"].drive_0_1 > 0.0
    assert stretch_frame.contraction_channels["A1:left"].drive_0_1 == 0.0

    shortened = ScientificBody3D(load_body_spec())
    transducer = BodyStateSensoryTransducer(shortened, _parameters())
    _move_a1_boundary(shortened, -5e-6)
    shortening_frame = transducer.sample(0.0)
    assert shortening_frame.segments["A1"].shortening_fraction > 0.0
    assert shortening_frame.dbd_channels["A1:left"].drive_0_1 == 0.0
    assert shortening_frame.contraction_channels["A1:left"].drive_0_1 > 0.0
    assert shortening_frame.contraction_channels["A1:left"].external_current_a == 0.0


def test_contact_depth_is_directional_but_has_no_invented_neural_edge():
    body = ScientificBody3D(load_body_spec())
    transducer = BodyStateSensoryTransducer(body, _parameters(), ground_z_m=0.0)
    index = _a1_index(body)
    for node in (index, index + 1):
        particle = body.particles[node]
        particle.position = Vec3(particle.position.x, particle.position.y, particle.position.z - 1e-6)
        particle.previous_position = particle.position
    frame = transducer.sample(0.0)
    assert frame.segments["A1"].contact
    assert frame.segments["A1"].contact_depth_m >= 1e-6 - 1e-12
    assert 0.0 < frame.contact_drive_by_segment["A1"] < 1.0
    assert not frame.contact_neural_path_executed


def test_exact_surface_touch_has_nonzero_diagnostic_drive_without_neural_edge():
    body = ScientificBody3D(load_body_spec())
    index = _a1_index(body)
    ground_z_m = min(
        body.particles[node].position.z - body.node_clearance_m(node)
        for node in (index, index + 1)
    )
    frame = BodyStateSensoryTransducer(
        body, _parameters(), ground_z_m=ground_z_m
    ).sample(0.0)
    assert frame.segments["A1"].contact
    assert frame.segments["A1"].contact_depth_m == 0.0
    assert frame.contact_drive_by_segment["A1"] == 0.25
    assert not frame.contact_neural_path_executed


def test_zero_input_is_silent_and_body_stable():
    result = L1VisualClosedLoopLarva(field=_zero_light()).run(duration_s=0.05)
    assert max(frame.maximum_dbd_drive for frame in result.body_sensory_frames) == 0.0
    assert sum(result.visual_spike_counts.values()) == 0
    assert max(frame.active_fiber_count for frame in result.body_force_frames) == 0
    assert result.spatial_result.displacement_x_um == 0.0
    assert result.spatial_result.displacement_y_um == 0.0
    assert result.spatial_result.displacement_z_um == 0.0


def test_stretch_closes_body_dbd_mn_fiber_force_loop_with_complete_trace():
    larva = _perturbed_larva()
    result = larva.run(duration_s=0.08)
    summary = result.to_dict()
    assert result.visual_spike_counts["proprioceptor:dbd:A1:left"] > 0
    assert result.visual_spike_counts["proprioceptor:dbd:A1:right"] > 0
    assert max(frame.feedback_driven_fiber_count for frame in result.body_force_frames) == 4
    assert summary["feedback_driven_force_frames"] > 0
    assert summary["all_feedback_forces_traced"]
    for frame in result.body_force_frames:
        for force in frame.fibers.values():
            if force.feedback_sensor_node_id is None:
                continue
            assert force.feedback_body_state_time_s <= force.feedback_sensor_spike_time_s
            assert force.feedback_sensor_spike_time_s < force.source_spike_time_s < frame.time_s
            assert force.feedback_path_provenance == "MEASURED_PUBLISHED"


def test_sensory_mn_and_fiber_lesions_preserve_causal_boundaries():
    intact = _perturbed_larva().run(duration_s=0.08)
    sensory = _perturbed_larva(
        lesions=("proprioceptor:dbd:A1:left", "proprioceptor:dbd:A1:right")
    ).run(duration_s=0.08)
    motor = _perturbed_larva(
        lesions=(
            "motor_identity:10649843:left",
            "motor_identity:14199031:left",
            "motor_identity:16713121:right",
        )
    ).run(duration_s=0.08)
    fiber = _perturbed_larva(fiber_lesions=("A1:left:M1:DA1",)).run(duration_s=0.08)

    assert max(frame.feedback_driven_fiber_count for frame in intact.body_force_frames) == 4
    assert sum(sensory.visual_spike_counts.values()) == 0
    assert max(frame.active_fiber_count for frame in sensory.body_force_frames) == 0
    assert sensory.body_sensory_frames[0].maximum_dbd_drive > 0.0
    assert motor.visual_spike_counts["proprioceptor:dbd:A1:left"] > 0
    assert max(frame.active_fiber_count for frame in motor.body_force_frames) == 0
    assert max(frame.feedback_driven_fiber_count for frame in fiber.body_force_frames) == 3
    assert intact.spatial_result.displacement_x_um != sensory.spatial_result.displacement_x_um
