import json

import pytest

from oraclarva.kinematics import KINEMATIC_METRICS, load_kinematic_targets


def test_repository_targets_preserve_l1_cohort_and_stage_boundary():
    targets = load_kinematic_targets()

    assert targets.dataset_id == "greaney_2026_l1_kinematics_v0"
    assert targets.animal_count == 18
    assert targets.observed_segments == ("T3", "A1", "A2", "A3", "A4", "A5", "A6", "A7")
    assert targets.unobserved_body_regions == ("PSC", "T1", "T2", "A8")
    assert not targets.l1_muscle_recruitment_observed
    assert not targets.age_matched_to_connectome
    assert not targets.free_surface_locomotion_observed
    assert not targets.is_full_body_validation


def test_repository_targets_match_known_derived_medians():
    targets = load_kinematic_targets()

    assert targets.targets["A4"]["contraction_amplitude_percent"].median == pytest.approx(51.646236)
    assert targets.targets["A5"]["contraction_duration_s"].median == pytest.approx(2.304459)
    assert targets.targets["T3"]["adjacent_onset_delay_cycle_fraction"] is None


def test_observed_medians_pass_screen_but_never_claim_release_validation():
    targets = load_kinematic_targets()
    simulation = {
        segment: {
            metric: band.median
            for metric, band in metrics.items()
            if band is not None
        }
        for segment, metrics in targets.targets.items()
    }

    report = targets.screen(simulation)

    assert report["screening_passed"]
    assert not report["release_validated"]
    assert report["failures"] == []


def test_screen_fails_closed_for_missing_and_out_of_band_results():
    targets = load_kinematic_targets()
    simulation = {
        segment: {
            metric: band.median
            for metric, band in metrics.items()
            if band is not None
        }
        for segment, metrics in targets.targets.items()
    }
    del simulation["A2"]
    simulation["A4"]["contraction_amplitude_percent"] = 99.0

    report = targets.screen(simulation)

    assert not report["screening_passed"]
    assert {failure["reason"] for failure in report["failures"]} == {
        "missing_segment",
        "outside_observed_p10_p90",
    }


def test_loader_rejects_stage_or_schema_drift(tmp_path):
    source = load_kinematic_targets()
    path = tmp_path / "invalid.json"
    raw = json.loads(source_path().read_text(encoding="utf-8"))
    raw["stage"] = "L2"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="developmental stage"):
        load_kinematic_targets(path)

    raw["stage"] = "first-instar L1 (~1 mm screening size)"
    del raw["segments"]["A1"][KINEMATIC_METRICS[0]]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete metric schema"):
        load_kinematic_targets(path)


def source_path():
    from oraclarva.kinematics import default_kinematic_path

    return default_kinematic_path()
