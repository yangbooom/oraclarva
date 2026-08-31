#!/usr/bin/env python3
"""Extract held-out L1 kinematic targets from Greaney et al. 2026.

The source MAT file is intentionally not vendored. This script verifies the
exact upstream artifact, selects the behavior-only L1 cohort, keeps animals
intact across a predeclared 12/6 calibration/validation split, and reports
population variability separately from bootstrap uncertainty of the median.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat


SOURCE_SHA256 = "b3b7f2149d6dd247064968bbd5abaf5d94ef3b945b5a3b846d3ce9ee3287bf94"
SOURCE_URL = (
    "https://raw.githubusercontent.com/kaufmanlab/larvariability-public/"
    "main/data/combined/comboResults.mat"
)
SOURCE_COMMIT = "b9f3a82028b1223de1e5933151ad3a8ea1b10b91"
FIGSHARE_DOI = "10.6084/m9.figshare.31510339.v1"
FIGSHARE_URL = (
    "https://figshare.com/articles/dataset/"
    "Cleaned_DLC_markers_and_results/31510339"
)
SEGMENTS = ("T3", "A1", "A2", "A3", "A4", "A5", "A6", "A7")
FIELDS = {
    "rest_length_um": "baseLength",
    "contraction_amplitude_percent": "cnAmpNorm",
    "shortening_rate_um_s": "shortnRate",
    "contraction_duration_s": "contrDurn",
    "onset_phase_cycle_fraction": "sgOnPhases",
    "adjacent_onset_delay_cycle_fraction": "onPhaDelays",
}
SPLIT_SEGMENT_FIELDS = {**FIELDS, "duty_cycle_percent": "cnDurNorm"}
CALIBRATION_SOURCE_INDICES = (0, 1, 3, 4, 6, 7, 9, 10, 12, 13, 15, 16)
VALIDATION_SOURCE_INDICES = (2, 5, 8, 11, 14, 17)
CYCLE_FIELDS = {
    "crawl_speed_um_s": "cycleSpeed",
    "stride_um": "cycleStride",
    "cycle_period_s": "cyclePeriod",
    "cycle_frequency_hz": "cycleFreq",
}
BOOTSTRAP_RESAMPLES = 2000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite_mean(value: Any) -> float | None:
    values = np.asarray(value, dtype=float).reshape(-1)
    values = values[np.isfinite(values)]
    return float(np.mean(values)) if values.size else None


def summarize(values: list[float | None], label: str) -> dict[str, Any] | None:
    finite = np.asarray([value for value in values if value is not None], dtype=float)
    if not finite.size:
        return None
    p10, median, p90 = np.quantile(finite, [0.1, 0.5, 0.9])
    seed = int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    sampled = rng.choice(
        finite, size=(BOOTSTRAP_RESAMPLES, finite.size), replace=True
    )
    medians = np.median(sampled, axis=1)
    ci_low, ci_high = np.quantile(medians, [0.025, 0.975])
    return {
        "p10": round(float(p10), 6),
        "median": round(float(median), 6),
        "p90": round(float(p90), 6),
        "animal_count": int(finite.size),
        "median_bootstrap_95_ci": [
            round(float(ci_low), 6),
            round(float(ci_high), 6),
        ],
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
    }


def wave_speed_segments_s(larva: dict[str, Any]) -> float | None:
    """Return T3-to-A7 onset propagation in segment intervals per second."""
    delays = np.vstack(
        [
            np.asarray(
                larva["segments"][index]["onPhaDelays"], dtype=float
            ).reshape(-1)
            for index in range(1, len(SEGMENTS))
        ]
    )
    periods = np.asarray(
        [wave["cyclePeriod"] for wave in larva["waves"]], dtype=float
    ).reshape(-1)
    valid = np.all(np.isfinite(delays), axis=0) & np.isfinite(periods)
    phase_span = np.sum(delays[:, valid], axis=0)
    valid_span = phase_span > 0.0
    speeds = (len(SEGMENTS) - 1) / (
        phase_span[valid_span] * periods[valid][valid_span]
    )
    return float(np.mean(speeds)) if speeds.size else None


def segment_summaries(
    records: list[dict[str, Any]], fields: dict[str, str], label: str
) -> dict[str, Any]:
    return {
        segment: {
            metric: summarize(
                [record["segments"][segment][metric] for record in records],
                f"{label}:{segment}:{metric}",
            )
            for metric in fields
        }
        for segment in SEGMENTS
    }


def cycle_summaries(
    records: list[dict[str, Any]], label: str
) -> dict[str, Any]:
    return {
        metric: summarize(
            [record["cycle_metrics"][metric] for record in records],
            f"{label}:cycle:{metric}",
        )
        for metric in (*CYCLE_FIELDS, "wave_speed_segments_s")
    }


def extract(source_path: Path) -> dict[str, Any]:
    actual_hash = sha256(source_path)
    if actual_hash != SOURCE_SHA256:
        raise ValueError(
            f"unexpected source SHA-256 {actual_hash}; expected {SOURCE_SHA256}"
        )

    larvae = loadmat(source_path, simplify_cells=True)["larvae"]
    selected: list[tuple[int, dict[str, Any]]] = []
    for source_index, larva in enumerate(larvae):
        segments = larva["segments"]
        names = tuple(segment.get("segtName", "") for segment in segments)
        is_behavior_only_l1 = (
            names == SEGMENTS
            and all("fOnsets" not in segment for segment in segments)
            and len(larva["waves"]) >= 50
        )
        if is_behavior_only_l1:
            selected.append((source_index, larva))

    if len(selected) != 18:
        raise ValueError(f"expected 18 L1 behavior animals, found {len(selected)}")
    if tuple(index for index, _ in selected) != tuple(range(18)):
        raise ValueError("upstream selected-animal order changed; audit split again")

    records: list[dict[str, Any]] = []
    for source_index, larva in selected:
        segment_records = {
            segment_name: {
                output_name: finite_mean(
                    larva["segments"][segment_index][source_name]
                )
                for output_name, source_name in SPLIT_SEGMENT_FIELDS.items()
            }
            for segment_index, segment_name in enumerate(SEGMENTS)
        }
        cycle_metrics = {
            output_name: finite_mean(
                [wave[source_name] for wave in larva["waves"]]
            )
            for output_name, source_name in CYCLE_FIELDS.items()
        }
        cycle_metrics["wave_speed_segments_s"] = wave_speed_segments_s(larva)
        split = (
            "calibration"
            if source_index in CALIBRATION_SOURCE_INDICES
            else "validation"
        )
        records.append(
            {
                "animal_id": f"behavior_l1_source_index_{source_index:02d}",
                "source_larva_index": source_index,
                "split": split,
                "good_cycle_count": len(larva["waves"]),
                "segments": segment_records,
                "cycle_metrics": cycle_metrics,
            }
        )

    calibration = [
        record for record in records if record["split"] == "calibration"
    ]
    validation = [
        record for record in records if record["split"] == "validation"
    ]
    if len(calibration) != 12 or len(validation) != 6:
        raise ValueError("predeclared animal split is invalid")

    return {
        "schema_version": 2,
        "dataset_id": "greaney_2026_l1_kinematics_v0",
        "stage": "first-instar L1 (~1 mm screening size)",
        "task": "forward crawling",
        "generated_on": date.today().isoformat(),
        "source": {
            "citation": (
                "Greaney MR, Heckscher ES, Kaufman ML. J Neurosci. 2026. "
                "Multiple Scales of Coordination along the Body Axis during "
                "Drosophila Larval Locomotion."
            ),
            "doi": "10.1523/JNEUROSCI.1623-25.2026",
            "repository": "https://github.com/kaufmanlab/larvariability-public",
            "repository_commit": SOURCE_COMMIT,
            "artifact_url": SOURCE_URL,
            "artifact_sha256": SOURCE_SHA256,
            "upstream_data_repository": FIGSHARE_URL,
            "upstream_data_doi": FIGSHARE_DOI,
            "upstream_data_license": "CC BY 4.0",
            "license_boundary": (
                "The Figshare preprocessed animal data are CC BY 4.0. The "
                "checksum-pinned combined MAT is a generated consolidation in "
                "the public GitHub repository, whose code has no declared "
                "license at the audited commit; repository code is not bundled."
            ),
        },
        "cohort": {
            "animal_count": len(selected),
            "minimum_good_cycles_per_animal": 50,
            "age_context": (
                "Source methods report first-instar jGC7f larvae selected at an "
                "average size of 1 mm after 24 hours; this is not established as "
                "age-matched to the L1 connectome specimen."
            ),
            "environment": (
                "water-saturated 2% agarose channels, 200 or 250 um wide and "
                "200 um deep"
            ),
            "pooling": (
                "Arithmetic mean across cycles within each animal, then NumPy "
                "linear p10/median/p90 across animals; 95% median uncertainty "
                "uses 2,000 deterministic animal-level bootstrap resamples."
            ),
        },
        "split": {
            "unit": "animal",
            "predeclared_rule": (
                "Preserve upstream source order and hold out every third selected "
                "animal beginning with selected index 2; no cycle from one animal "
                "appears in both partitions."
            ),
            "calibration_source_indices": list(CALIBRATION_SOURCE_INDICES),
            "validation_source_indices": list(VALIDATION_SOURCE_INDICES),
            "calibration_animal_count": len(calibration),
            "validation_animal_count": len(validation),
            "selection_used_model_output": False,
            "selection_used_target_values": False,
        },
        "coverage": {
            "observed_segments": list(SEGMENTS),
            "unobserved_body_regions": ["PSC", "T1", "T2", "A8"],
            "l1_muscle_recruitment_observed": False,
            "age_matched_to_connectome": False,
            "free_surface_locomotion_observed": False,
            "note": (
                "The L1 jGCaMP7f cohort supplies segment kinematics only. Muscle "
                "recruitment in the source study was measured in L2 Gerry animals "
                "and is excluded from this L1 target bundle."
            ),
        },
        "segments": segment_summaries(records, FIELDS, "all"),
        "calibration_targets": {
            "segments": segment_summaries(
                calibration, SPLIT_SEGMENT_FIELDS, "calibration"
            ),
            "cycle_metrics": cycle_summaries(calibration, "calibration"),
        },
        "held_out_validation_targets": {
            "segments": segment_summaries(
                validation, SPLIT_SEGMENT_FIELDS, "validation"
            ),
            "cycle_metrics": cycle_summaries(validation, "validation"),
        },
        "animal_records": records,
        "derived_metric_definitions": {
            "duty_cycle_percent": (
                "Author analysis field cnDurNorm = contraction duration / cycle "
                "period * 100."
            ),
            "wave_speed_segments_s": (
                "Seven segment intervals (T3 to A7) divided by the sum of the "
                "seven adjacent onset phase delays times each cycle period, then "
                "averaged within animal. Unit is segment intervals per second, "
                "not micrometers per second."
            ),
            "stride_um": "Author analysis field cycleStride.",
            "contraction_amplitude_percent": (
                "Author analysis field cnAmpNorm; used as segment length change."
            ),
            "provenance": "PUBLIC_IMAGE_DERIVED",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="upstream comboResults.mat")
    parser.add_argument("output", type=Path, help="output JSON path")
    args = parser.parse_args(argv)
    result = extract(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
