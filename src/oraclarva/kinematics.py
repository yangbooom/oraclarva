"""Stage-specific, source-backed kinematic screening targets."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


KINEMATIC_METRICS = (
    "rest_length_um",
    "contraction_amplitude_percent",
    "shortening_rate_um_s",
    "contraction_duration_s",
    "onset_phase_cycle_fraction",
    "adjacent_onset_delay_cycle_fraction",
)
HELD_OUT_SEGMENT_METRICS = KINEMATIC_METRICS + ("duty_cycle_percent",)
HELD_OUT_CYCLE_METRICS = (
    "crawl_speed_um_s",
    "stride_um",
    "cycle_period_s",
    "cycle_frequency_hz",
    "wave_speed_segments_s",
)


@dataclass(frozen=True, slots=True)
class ObservedBand:
    p10: float
    median: float
    p90: float
    animal_count: int

    def validate(self) -> None:
        if not self.p10 <= self.median <= self.p90:
            raise ValueError("kinematic quantiles must be ordered")
        if self.animal_count <= 0:
            raise ValueError("kinematic band requires at least one animal")

    def contains(self, value: float) -> bool:
        return self.p10 <= value <= self.p90


@dataclass(frozen=True, slots=True)
class KinematicTargetSet:
    dataset_id: str
    stage: str
    task: str
    observed_segments: tuple[str, ...]
    unobserved_body_regions: tuple[str, ...]
    animal_count: int
    l1_muscle_recruitment_observed: bool
    age_matched_to_connectome: bool
    free_surface_locomotion_observed: bool
    targets: Mapping[str, Mapping[str, ObservedBand | None]]

    def validate(self) -> None:
        if not self.stage.startswith("first-instar L1"):
            raise ValueError("L1 validator cannot load a different developmental stage")
        if tuple(self.targets) != self.observed_segments:
            raise ValueError("target segment order must match declared coverage")
        for segment, metrics in self.targets.items():
            if set(metrics) != set(KINEMATIC_METRICS):
                raise ValueError(f"incomplete metric schema for {segment}")
            for band in metrics.values():
                if band is not None:
                    band.validate()
                    if band.animal_count > self.animal_count:
                        raise ValueError("metric animal count exceeds cohort size")

    @property
    def is_full_body_validation(self) -> bool:
        return (
            not self.unobserved_body_regions
            and self.l1_muscle_recruitment_observed
            and self.age_matched_to_connectome
            and self.free_surface_locomotion_observed
        )

    def screening_summary(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "stage": self.stage,
            "task": self.task,
            "animal_count": self.animal_count,
            "observed_segments": list(self.observed_segments),
            "unobserved_body_regions": list(self.unobserved_body_regions),
            "l1_muscle_recruitment_observed": self.l1_muscle_recruitment_observed,
            "age_matched_to_connectome": self.age_matched_to_connectome,
            "free_surface_locomotion_observed": self.free_surface_locomotion_observed,
            "full_body_validation": self.is_full_body_validation,
        }

    def screen(
        self, simulated_medians: Mapping[str, Mapping[str, float]]
    ) -> dict[str, Any]:
        failures: list[dict[str, Any]] = []
        for segment in self.observed_segments:
            supplied = simulated_medians.get(segment)
            if supplied is None:
                failures.append({"segment": segment, "reason": "missing_segment"})
                continue
            for metric, band in self.targets[segment].items():
                if band is None:
                    continue
                if metric not in supplied:
                    failures.append(
                        {"segment": segment, "metric": metric, "reason": "missing_metric"}
                    )
                    continue
                value = float(supplied[metric])
                if not band.contains(value):
                    failures.append(
                        {
                            "segment": segment,
                            "metric": metric,
                            "reason": "outside_observed_p10_p90",
                            "value": value,
                            "p10": band.p10,
                            "p90": band.p90,
                        }
                    )
        return {
            "screening_passed": not failures,
            "release_validated": False,
            "failures": failures,
            "note": (
                "Passing is an in-cohort plausibility screen, not independent "
                "whole-body biological validation."
            ),
        }


@dataclass(frozen=True, slots=True)
class HeldOutKinematicTargetSet:
    calibration_animal_count: int
    validation_animal_count: int
    calibration_source_indices: tuple[int, ...]
    validation_source_indices: tuple[int, ...]
    calibration_segments: Mapping[str, Mapping[str, ObservedBand | None]]
    validation_segments: Mapping[str, Mapping[str, ObservedBand | None]]
    calibration_cycle_metrics: Mapping[str, ObservedBand | None]
    validation_cycle_metrics: Mapping[str, ObservedBand | None]

    def validate(self) -> None:
        if self.calibration_animal_count != 12 or self.validation_animal_count != 6:
            raise ValueError("Greaney split must remain 12 calibration / 6 validation")
        calibration = set(self.calibration_source_indices)
        validation = set(self.validation_source_indices)
        if calibration & validation:
            raise ValueError("an animal appears in both kinematic partitions")
        if calibration | validation != set(range(18)):
            raise ValueError("kinematic split does not cover the 18-animal cohort")
        expected_segments = ("T3", "A1", "A2", "A3", "A4", "A5", "A6", "A7")
        for partition in (self.calibration_segments, self.validation_segments):
            if tuple(partition) != expected_segments:
                raise ValueError("held-out segment coverage changed")
            for metrics in partition.values():
                if set(metrics) != set(HELD_OUT_SEGMENT_METRICS):
                    raise ValueError("held-out segment metric schema is incomplete")
                for band in metrics.values():
                    if band is not None:
                        band.validate()
        for partition in (
            self.calibration_cycle_metrics,
            self.validation_cycle_metrics,
        ):
            if set(partition) != set(HELD_OUT_CYCLE_METRICS):
                raise ValueError("held-out cycle metric schema is incomplete")
            for band in partition.values():
                if band is not None:
                    band.validate()


def default_kinematic_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "validation"
        / "greaney_2026_l1_kinematics_v0.json"
    )


def load_kinematic_targets(path: str | Path | None = None) -> KinematicTargetSet:
    source_path = Path(path) if path else default_kinematic_path()
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    coverage = raw["coverage"]
    targets: dict[str, dict[str, ObservedBand | None]] = {}
    for segment, metrics in raw["segments"].items():
        targets[segment] = {}
        for metric, value in metrics.items():
            targets[segment][metric] = (
                None
                if value is None
                else ObservedBand(
                    p10=float(value["p10"]),
                    median=float(value["median"]),
                    p90=float(value["p90"]),
                    animal_count=int(value["animal_count"]),
                )
            )
    result = KinematicTargetSet(
        dataset_id=str(raw["dataset_id"]),
        stage=str(raw["stage"]),
        task=str(raw["task"]),
        observed_segments=tuple(coverage["observed_segments"]),
        unobserved_body_regions=tuple(coverage["unobserved_body_regions"]),
        animal_count=int(raw["cohort"]["animal_count"]),
        l1_muscle_recruitment_observed=bool(
            coverage["l1_muscle_recruitment_observed"]
        ),
        age_matched_to_connectome=bool(coverage["age_matched_to_connectome"]),
        free_surface_locomotion_observed=bool(
            coverage["free_surface_locomotion_observed"]
        ),
        targets=targets,
    )
    result.validate()
    return result


def load_held_out_kinematic_targets(
    path: str | Path | None = None,
) -> HeldOutKinematicTargetSet:
    source_path = Path(path) if path else default_kinematic_path()
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    if int(raw.get("schema_version", 0)) != 2:
        raise ValueError("held-out kinematic targets require schema version 2")
    split = raw["split"]
    if (
        split.get("unit") != "animal"
        or split.get("selection_used_model_output") is not False
        or split.get("selection_used_target_values") is not False
    ):
        raise ValueError("held-out split provenance is invalid")

    def bands(source: Mapping[str, Any]) -> dict[str, ObservedBand | None]:
        result: dict[str, ObservedBand | None] = {}
        for metric, value in source.items():
            if value is None:
                result[metric] = None
                continue
            ci = value.get("median_bootstrap_95_ci")
            if (
                value.get("bootstrap_resamples") != 2000
                or not isinstance(ci, list)
                or len(ci) != 2
                or not float(ci[0]) <= float(value["median"]) <= float(ci[1])
            ):
                raise ValueError(f"invalid bootstrap uncertainty for {metric}")
            result[metric] = ObservedBand(
                p10=float(value["p10"]),
                median=float(value["median"]),
                p90=float(value["p90"]),
                animal_count=int(value["animal_count"]),
            )
        return result

    calibration = raw["calibration_targets"]
    validation = raw["held_out_validation_targets"]
    result = HeldOutKinematicTargetSet(
        calibration_animal_count=int(split["calibration_animal_count"]),
        validation_animal_count=int(split["validation_animal_count"]),
        calibration_source_indices=tuple(split["calibration_source_indices"]),
        validation_source_indices=tuple(split["validation_source_indices"]),
        calibration_segments={
            segment: bands(metrics)
            for segment, metrics in calibration["segments"].items()
        },
        validation_segments={
            segment: bands(metrics)
            for segment, metrics in validation["segments"].items()
        },
        calibration_cycle_metrics=bands(calibration["cycle_metrics"]),
        validation_cycle_metrics=bands(validation["cycle_metrics"]),
    )
    result.validate()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect L1 kinematic targets")
    parser.add_argument("path", nargs="?", default=None)
    args = parser.parse_args(argv)
    print(json.dumps(load_kinematic_targets(args.path).screening_summary(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
