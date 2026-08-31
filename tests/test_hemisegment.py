"""Tests for the isolated A1-left mechanics fixture."""

import json
import pytest

from oraclarva.hemisegment import (
    IsolatedA1HemisegmentMechanics,
    load_a1_hemisegment_spec,
)


def fixture():
    return IsolatedA1HemisegmentMechanics(load_a1_hemisegment_spec())


def run(model, steps, activations=None, lesions=()):
    frame = None
    for step in range(steps):
        frame = model.step(
            step * model.spec.dt_s,
            activations or {},
            lesioned_fiber_ids=lesions,
        )
    assert frame is not None
    return frame


def test_a1_left_geometry_has_29_explicit_bounded_attachments():
    model = fixture()

    assert len(model.geometries) == 29
    assert len(set(model.fiber_ids)) == 29
    assert "A1:left:M25:VT1" not in model.fiber_ids
    assert {item.spatial_group for item in model.geometries} == {
        "DL", "DO", "VL", "VO", "VA", "T"
    }
    for item in model.geometries:
        item.origin.validate()
        item.insertion.validate()
        assert item.rest_length_body_units > 0.0
        assert sum(value * value for value in item.line_of_action) == pytest.approx(1.0)
        assert item.coordinate_provenance == "ANATOMY_DERIVED"
        assert not item.quantitative_image_coordinates_used
        assert not item.individual_layer_claimed


def test_spec_fails_closed_on_absolute_or_full_body_claims(tmp_path):
    raw = load_a1_hemisegment_spec().raw
    for key in ("absolute_scale_claimed", "full_body_motion_enabled"):
        altered = json.loads(json.dumps(raw))
        altered["claim_boundary"][key] = True
        path = tmp_path / f"{key}.json"
        path.write_text(json.dumps(altered))
        with pytest.raises(ValueError, match="cannot claim scale or drive"):
            load_a1_hemisegment_spec(path)


def test_zero_input_is_exactly_stable():
    model = fixture()
    frame = run(model, 1000)

    assert frame.deformed_fiber_count == 0
    assert frame.maximum_shortening_fraction == 0.0
    assert all(item.active_tension_model_units == 0.0 for item in frame.fibers.values())
    assert not frame.full_body_motion_executed
    assert frame.absolute_force_unit == "model_unit_not_newton"


def test_single_fiber_activation_is_bounded_and_local():
    model = fixture()
    target = "A1:left:M1:DA1"
    frame = run(model, 500, {target: 1.0})

    assert frame.fibers[target].shortening_fraction > 0.05
    assert frame.fibers[target].shortening_fraction <= model.spec.maximum_shortening_fraction
    assert frame.fibers[target].active_tension_model_units > 0.0
    assert frame.fibers[target].passive_elastic_force_model_units > 0.0
    assert frame.deformed_fiber_count == 1
    assert all(
        item.shortening_body_units == 0.0
        for fiber_id, item in frame.fibers.items()
        if fiber_id != target
    )


def test_individual_fiber_lesion_blocks_only_that_fiber():
    target = "A1:left:M1:DA1"
    sibling = "A1:left:M10:DO2"
    control = run(fixture(), 500, {target: 1.0, sibling: 0.7})
    lesioned = run(
        fixture(),
        500,
        {target: 1.0, sibling: 0.7},
        lesions=(target,),
    )

    assert lesioned.fibers[target].shortening_body_units == 0.0
    assert lesioned.fibers[target].activation == 1.0
    assert not lesioned.fibers[target].mechanics_enabled
    assert lesioned.fibers[target].active_tension_model_units == 0.0
    assert lesioned.fibers[sibling].shortening_body_units == pytest.approx(
        control.fibers[sibling].shortening_body_units
    )
    assert lesioned.deformed_fiber_count == 1


def test_step_order_and_fixture_boundary_are_strict():
    model = fixture()
    with pytest.raises(ValueError, match="stepped once"):
        model.step(0.001, {})
    with pytest.raises(ValueError, match="outside"):
        model.step(0.0, {"A2:left:M1:DA1": 1.0})


def test_stage2_activation_drives_mechanics_and_lesion_preserves_upstream():
    from oraclarva.muscles import (
        NeuralMuscleActivationModel,
        load_neural_muscle_identity_projection,
    )

    spec = load_a1_hemisegment_spec()
    projection = load_neural_muscle_identity_projection()
    mapping = next(
        item for item in projection.mappings if item.fiber_id == "A1:left:M1:DA1"
    )
    activation = NeuralMuscleActivationModel(
        projection, spec.dt_s, 0.020, 0.080, 1.0
    )
    mechanics = IsolatedA1HemisegmentMechanics(spec)
    lesioned_mechanics = IsolatedA1HemisegmentMechanics(spec)
    final_activation = final_control = final_lesion = None
    for step in range(300):
        time_s = step * spec.dt_s
        spikes = (mapping.source_node_id,) if step < 100 and step % 5 == 0 else ()
        events = projection.emit(spikes)
        final_activation = activation.step(time_s, events)
        trace_source = {mapping.fiber_id: mapping.source_node_id}
        trace_provenance = {mapping.fiber_id: mapping.mapping_provenance}
        final_control = mechanics.step_activation_frame(
            final_activation,
            source_by_fiber=trace_source,
            mapping_provenance_by_fiber=trace_provenance,
        )
        final_lesion = lesioned_mechanics.step_activation_frame(
            final_activation,
            lesioned_fiber_ids=(mapping.fiber_id,),
            source_by_fiber=trace_source,
            mapping_provenance_by_fiber=trace_provenance,
        )
    assert final_activation is not None
    assert final_control is not None
    assert final_lesion is not None
    assert final_activation.activations[mapping.fiber_id] > 0.0
    assert final_control.fibers[mapping.fiber_id].shortening_body_units > 0.0
    assert final_control.fibers[mapping.fiber_id].source_node_id == mapping.source_node_id
    assert final_control.fibers[mapping.fiber_id].mapping_provenance == "MEASURED_PUBLISHED"
    assert final_lesion.fibers[mapping.fiber_id].shortening_body_units == 0.0
    assert final_lesion.fibers[mapping.fiber_id].activation > 0.0


def test_checked_a1_artifact_preserves_claim_and_causal_boundaries():
    from pathlib import Path

    artifact = json.loads(
        (
            Path(__file__).parents[1]
            / "data"
            / "trajectories"
            / "l1_a1_left_hemisegment_mechanics_v0.json"
        ).read_text()
    )
    assert artifact["fiber_count"] == 29
    assert artifact["zero_input"]["exact_equilibrium"]
    assert artifact["claim_boundary"]["force_unit"] == "model_unit_not_newton"
    assert not artifact["claim_boundary"]["full_body_motion_executed"]
    control, lesion = artifact["scenarios"]
    target = "A1:left:M1:DA1"
    assert control["first_spike_s"][target] < control["first_activation_s"][target]
    assert control["first_activation_s"][target] <= control["first_shortening_s"][target]
    assert lesion["peak_activation"][target] == control["peak_activation"][target]
    assert lesion["peak_shortening_body_units"][target] == 0.0
