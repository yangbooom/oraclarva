from __future__ import annotations

import hashlib
import importlib.util
import json
from copy import deepcopy
from math import cos, pi, sin
from pathlib import Path

import pytest

from oraclarva.body3d import Vec3
from oraclarva.oriented_mechanics import (
    OrientedBodyMechanicsFixture,
    default_oriented_body_mechanics_path,
    load_oriented_body_mechanics_config,
    validate_oriented_body_mechanics_config,
)


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "data/validation/oriented_body_mechanics_v2.json"
GIF = ROOT / "docs/assets/oraclarva_oriented_body_mechanics_v2.gif"
FROZEN_V1 = ROOT / "data/trajectories/l1_named_fiber_steering_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_config_fails_closed_on_commands_and_unmeasured_claims():
    config = load_oriented_body_mechanics_config()
    topology = config["topology"]
    assert config["scope"] == "mechanics_fixture_not_yet_contact_integrated"
    assert topology["body_state_space"] == (
        "unshearable_oriented_cross_section_rod_v2"
    )
    assert topology["independent_section_degree_of_freedom"] == (
        "twist_about_centerline_tangent"
    )
    assert topology["attachment_coordinate_provenance"] == "ANATOMY_DERIVED"
    assert topology["mechanics_parameter_provenance"] == "MODEL_FITTED"
    assert topology["metric_attachment_coordinates_measured"] is False
    assert topology["csa_measured"] is False
    assert topology["fmax_measured"] is False
    assert all(
        topology[name] is False
        for name in (
            "action_command",
            "behavior_fsm",
            "external_policy",
            "heading_input",
            "curvature_input",
            "authored_translation",
        )
    )

    invalid = deepcopy(config)
    invalid["topology"]["heading_input"] = True
    with pytest.raises(ValueError, match="topology"):
        validate_oriented_body_mechanics_config(invalid)
    invalid = deepcopy(config)
    invalid["topology"]["metric_attachment_coordinates_measured"] = True
    with pytest.raises(ValueError, match="topology"):
        validate_oriented_body_mechanics_config(invalid)


def test_material_sections_are_right_handed_orthonormal_frames():
    fixture = OrientedBodyMechanicsFixture()
    assert len(fixture.body.sections) == len(fixture.body.particles) == 13
    for index in range(len(fixture.body.sections)):
        frame = fixture.body.material_frame(index)
        frame.validate(tolerance=1e-12)
        assert (
            frame.tangent.cross(frame.lateral) - frame.dorsal
        ).norm() < 1e-12


def _first_active_load(side: str):
    fixture = OrientedBodyMechanicsFixture()
    target = fixture.fiber_pair[0 if side == "left" else 1]
    source = fixture._source_for_fiber(target)
    initial = fixture.activation.step(
        0.0, fixture.projection.emit((source,))
    )
    fixture.coupling.step(
        initial,
        last_source_by_fiber=fixture.activation.last_applied_source,
        last_spike_time_s_by_fiber=fixture.activation.last_applied_spike_s,
    )
    activation = fixture.activation.step(
        fixture.dt_s, fixture.projection.emit(())
    )
    force = fixture.coupling.step(
        activation,
        last_source_by_fiber=fixture.activation.last_applied_source,
        last_spike_time_s_by_fiber=fixture.activation.last_applied_spike_s,
    )
    load = fixture.coupling.paired_generalized_active_excess_loads(
        force, (fixture.fiber_pair,), spatial_force_scale=0.3
    )
    return fixture, force, load


def test_off_axis_pair_preserves_force_and_generalized_torque():
    fixture, _, load = _first_active_load("left")
    assert load.active_fiber_count == load.traced_active_fiber_count == 1
    assert len(load.applications) == 2
    assert {item.endpoint for item in load.applications} == {
        "origin",
        "insertion",
    }
    assert load.net_force_model_units.norm() < 1e-12
    assert load.centerline_force_moment_model_units_m.norm() > 0.0
    assert load.net_generalized_torque_model_units_m.norm() < 1e-18
    assert any(
        value.norm() > 0.0
        for value in load.section_torques_model_units_m.values()
    )
    for application in load.applications:
        assert application.source_spike_time_s < load.time_s
        assert application.coordinate_provenance == "ANATOMY_DERIVED"
        assert application.mechanics_provenance == "MODEL_FITTED"
        assert application.source_node_id == fixture._source_for_fiber(
            application.fiber_id
        )


def test_equal_activation_and_attachment_lesion_do_not_create_load():
    uniform = OrientedBodyMechanicsFixture().run("uniform", duration_s=0.02)
    assert uniform.active_load_samples == 0
    assert uniform.maximum_abs_section_twist_deg == 0.0

    target = load_oriented_body_mechanics_config()["parameters"][
        "fixture_fiber_pair"
    ][0]
    lesion_fixture = OrientedBodyMechanicsFixture(
        lesioned_fiber_ids=(target,)
    )
    lesion = lesion_fixture.run("left", duration_s=0.02)
    assert lesion_fixture.activation.activations[target] > 0.0
    assert lesion.active_load_samples == 0
    assert lesion.maximum_abs_section_twist_deg == 0.0


def test_left_and_right_free_space_dynamics_are_exact_mirrors():
    left_fixture = OrientedBodyMechanicsFixture()
    right_fixture = OrientedBodyMechanicsFixture()
    left = left_fixture.run("left")
    right = right_fixture.run("right")
    assert left.active_load_samples == left.traced_load_samples > 0
    assert right.active_load_samples == right.traced_load_samples > 0
    assert left.endpoint_application_samples == 2 * left.active_load_samples
    assert right.endpoint_application_samples == 2 * right.active_load_samples
    for left_node, right_node in zip(
        left.final_nodes_m, right.final_nodes_m, strict=True
    ):
        assert left_node.x == pytest.approx(right_node.x, abs=1e-15)
        assert left_node.y == pytest.approx(-right_node.y, abs=1e-15)
        assert left_node.z == pytest.approx(right_node.z, abs=1e-15)
    for left_twist, right_twist in zip(
        left.final_twist_deg, right.final_twist_deg, strict=True
    ):
        assert left_twist == pytest.approx(-right_twist, abs=1e-12)
    assert 0.001 < left.maximum_abs_section_twist_deg < 15.0
    assert left.maximum_segment_extension_fraction < 0.05
    for fixture in (left_fixture, right_fixture):
        for index in range(len(fixture.body.sections)):
            fixture.body.material_frame(index).validate(tolerance=1e-9)


def test_generalized_load_is_covariant_under_3d_rigid_transform():
    fixture, _, baseline = _first_active_load("left")
    angle = pi / 3.0
    cosine = cos(angle)
    sine = sin(angle)
    axis = Vec3(1.0, 2.0, 3.0).normalized()
    translation = Vec3(0.002, -0.003, 0.004)

    def rotate(value: Vec3) -> Vec3:
        return (
            value * cosine
            + axis.cross(value) * sine
            + axis * (axis.dot(value) * (1.0 - cosine))
        )

    transformed = OrientedBodyMechanicsFixture()
    for particle in transformed.body.particles:
        particle.position = rotate(particle.position) + translation
        particle.previous_position = particle.position
    for state in transformed.body.sections:
        state.reference_lateral = rotate(state.reference_lateral)
        state.reference_dorsal = rotate(state.reference_dorsal)
    transformed.body._section_tangents = [
        rotate(value) for value in transformed.body._section_tangents
    ]
    target = transformed.fiber_pair[0]
    source = transformed._source_for_fiber(target)
    initial = transformed.activation.step(
        0.0, transformed.projection.emit((source,))
    )
    transformed.coupling.step(
        initial,
        last_source_by_fiber=transformed.activation.last_applied_source,
        last_spike_time_s_by_fiber=transformed.activation.last_applied_spike_s,
    )
    activation = transformed.activation.step(
        transformed.dt_s, transformed.projection.emit(())
    )
    force = transformed.coupling.step(
        activation,
        last_source_by_fiber=transformed.activation.last_applied_source,
        last_spike_time_s_by_fiber=transformed.activation.last_applied_spike_s,
    )
    moved = transformed.coupling.paired_generalized_active_excess_loads(
        force, (transformed.fiber_pair,), spatial_force_scale=0.3
    )
    for original, current in zip(
        baseline.applications, moved.applications, strict=True
    ):
        assert (
            current.point_m - (rotate(original.point_m) + translation)
        ).norm() < 1e-15
        assert (
            current.force_model_units - rotate(original.force_model_units)
        ).norm() < 1e-12
    assert moved.net_force_model_units.norm() < 1e-12
    assert moved.net_generalized_torque_model_units_m.norm() < 1e-18


def test_checked_validation_is_current_and_v1_input_is_frozen():
    report = json.loads(VALIDATION.read_text(encoding="utf-8"))
    assert report["status"] == "engineering_gates_passed"
    assert report["passed"] is True
    assert report["release_validated"] is False
    assert report["independent_biological_validation"] is False
    assert report["generated_from"]["config_sha256"] == sha256(
        default_oriented_body_mechanics_path()
    )
    assert report["generated_from"]["frozen_named_fiber_v1_sha256"] == (
        sha256(FROZEN_V1)
    )
    assert all(report["comparisons"].values())
    assert all(report["invariant_gates"].values())
    spec = importlib.util.spec_from_file_location(
        "export_oriented_body_mechanics",
        ROOT / "tools/export_oriented_body_mechanics.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert json.loads(json.dumps(module.build_artifact())) == report


def test_checked_gif_is_nonempty_51_frame_media():
    payload = GIF.read_bytes()
    assert payload[:6] in {b"GIF87a", b"GIF89a"}
    assert len(payload) > 100_000
    assert payload.count(b"\x21\xf9\x04") == 51
