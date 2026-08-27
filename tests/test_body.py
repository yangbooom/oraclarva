from math import isclose

import pytest

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


def test_active_segment_shortens_and_thickens_with_volume_preservation():
    spec = load_body_spec()
    body = ScientificBody3D(spec, pinned_nodes={0})
    segment_index = next(i for i, segment in enumerate(spec.segments) if segment.id == "PSC")
    rest_length = body.segment_length_m(segment_index)
    rest_width = body.current_width_m(segment_index)
    body.set_activations({"PSC": 1.0})
    for _ in range(25):
        body.step(0.001, gravity=Vec3(0.0, 0.0, 0.0), ground_z=None)
    assert body.segment_length_m(segment_index) < rest_length
    assert body.current_width_m(segment_index) > rest_width


def test_unstimulated_body_preserves_rest_lengths_without_gravity():
    body = ScientificBody3D(load_body_spec(), pinned_nodes={0})
    before = [body.segment_length_m(i) for i in range(len(body.geometry))]
    for _ in range(10):
        body.step(0.001, gravity=Vec3(0.0, 0.0, 0.0), ground_z=None)
    after = [body.segment_length_m(i) for i in range(len(body.geometry))]
    assert after == pytest.approx(before, rel=1e-9, abs=1e-12)
