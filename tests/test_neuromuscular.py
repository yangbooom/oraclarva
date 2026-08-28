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


def test_repository_map_has_curated_a1_targets_but_still_fails_closed():
    spec = load_body_spec()
    mapping = load_neuromuscular_map(spec)

    assert mapping.status == "curated_partial_a1_a2_targets_pending_gains_and_geometry"
    assert len(mapping.projections) == 58
    assert mapping.is_identity_curated
    assert not mapping.is_scientifically_ready
    assert set(mapping.unresolved_neuron_ids) == {"4461322", "14086623", "14197913"}
    with pytest.raises(UnvalidatedMappingError):
        mapping.project({})
    with pytest.raises(UnvalidatedMappingError, match="gains"):
        mapping.project({}, allow_unvalidated=True)


def test_repository_map_preserves_exact_catmaid_ids_and_table1_targets():
    mapping = load_neuromuscular_map(load_body_spec())
    by_id = {projection.neuron_id: projection for projection in mapping.projections}

    acc_left = by_id["10649843"]
    assert acc_left.neuron_name == "MN1 aCC_a1l"
    assert acc_left.channel.segment_id == "A1"
    assert acc_left.channel.side == "left"
    assert acc_left.channel.spatial_group == "DL"
    assert acc_left.channel.synapse_type == "Ib"
    assert [(target.number, target.synonym) for target in acc_left.channel.target_muscles] == [
        ("1", "DA1")
    ]

    mn25_left = by_id["4717729"]
    assert mn25_left.neuron_name == "MN25 (TN)_a2l"
    assert mn25_left.channel.segment_id == "A2"
    assert mn25_left.channel.target_muscles[0].number == "25"

    rp2_left = by_id["13058240"]
    assert rp2_left.channel.spatial_group == "Broad"
    target_18 = next(
        target for target in rp2_left.channel.target_muscles if target.number == "18"
    )
    assert target_18.evidence == "bracketed_in_source"


def test_repository_map_audit_reports_source_coverage_and_physics_blockers():
    summary = load_neuromuscular_map(load_body_spec()).audit_summary()

    assert summary["identity_curated"] is True
    assert summary["release_ready"] is False
    assert summary["resolved_neurons"] == 58
    assert summary["segments"] == {"A1": 56, "A2": 2}
    assert summary["sides"] == {"left": 29, "right": 29}
    assert summary["missing_gain"] == 58
    assert summary["missing_mechanical_action"] == 58


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
