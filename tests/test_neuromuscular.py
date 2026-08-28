import pytest

from oraclarva.body import load_body_spec
from oraclarva.body3d import ScientificBody3D
from oraclarva.neuromuscular import (
    MuscleChannel,
    MotorProjection,
    NeuromuscularMap,
    UnvalidatedMappingError,
    load_neuromuscular_map,
)


def test_repository_map_fails_closed_until_identifiers_are_curated():
    spec = load_body_spec()
    mapping = load_neuromuscular_map(spec)

    assert mapping.status == "blocked_pending_identifier_crosswalk"
    assert not mapping.projections
    assert not mapping.is_scientifically_ready
    with pytest.raises(UnvalidatedMappingError):
        mapping.project({})


def test_explicit_synthetic_fixture_can_exercise_projection_but_is_not_release_ready():
    spec = load_body_spec()
    projection = MotorProjection(
        neuron_id="fixture-mn-a4-left",
        channel=MuscleChannel("A4", "left", "longitudinal"),
        weight=1.0,
        provenance="synthetic",
        source_id=None,
    )
    mapping = NeuromuscularMap(
        model_id="fixture",
        status="fixture",
        projections=(projection,),
        body_segment_ids=tuple(segment.id for segment in spec.segments),
    )
    mapping.validate()

    with pytest.raises(UnvalidatedMappingError):
        mapping.project({"fixture-mn-a4-left": 0.75})
    frame = mapping.project(
        {"fixture-mn-a4-left": 0.75},
        allow_unvalidated=True,
    )
    body = ScientificBody3D(spec)
    mapping.apply_axial_activation(body, frame)

    a4_index = next(index for index, segment in enumerate(body.geometry) if segment.id == "A4")
    assert body.activations[a4_index] == pytest.approx(0.75)
    assert sum(body.activations) == pytest.approx(0.75)


def test_neuromuscular_schema_rejects_behavior_commands_and_invalid_activity():
    spec = load_body_spec()
    invalid = NeuromuscularMap(
        model_id="invalid",
        status="fixture",
        projections=(
            MotorProjection(
                neuron_id="mn",
                channel=MuscleChannel("turn_left", "left", "longitudinal"),
                weight=1.0,
                provenance="synthetic",
            ),
        ),
        body_segment_ids=tuple(segment.id for segment in spec.segments),
    )
    with pytest.raises(ValueError):
        invalid.validate()

    valid = NeuromuscularMap(
        model_id="fixture",
        status="fixture",
        projections=(
            MotorProjection(
                neuron_id="mn",
                channel=MuscleChannel("A1", "bilateral", "longitudinal"),
                weight=1.0,
                provenance="synthetic",
            ),
        ),
        body_segment_ids=tuple(segment.id for segment in spec.segments),
    )
    valid.validate()
    with pytest.raises(ValueError):
        valid.project({"mn": 1.2}, allow_unvalidated=True)
