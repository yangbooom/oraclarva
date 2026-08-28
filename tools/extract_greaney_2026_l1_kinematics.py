#!/usr/bin/env python3
"""Extract compact L1 kinematic validation targets from Greaney et al. 2026.

The source MAT file is intentionally not vendored.  This script verifies the
exact upstream artifact, selects the behavior-only L1 cohort, pools cycles
within each animal, and then reports population quantiles across animals.
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
SEGMENTS = ("T3", "A1", "A2", "A3", "A4", "A5", "A6", "A7")
FIELDS = {
    "rest_length_um": "baseLength",
    "contraction_amplitude_percent": "cnAmpNorm",
    "shortening_rate_um_s": "shortnRate",
    "contraction_duration_s": "contrDurn",
    "onset_phase_cycle_fraction": "sgOnPhases",
    "adjacent_onset_delay_cycle_fraction": "onPhaDelays",
}


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


def extract(source_path: Path) -> dict[str, Any]:
    actual_hash = sha256(source_path)
    if actual_hash != SOURCE_SHA256:
        raise ValueError(
            f"unexpected source SHA-256 {actual_hash}; expected {SOURCE_SHA256}"
        )

    larvae = loadmat(source_path, simplify_cells=True)["larvae"]
    selected: list[dict[str, Any]] = []
    for larva in larvae:
        segments = larva["segments"]
        names = tuple(segment.get("segtName", "") for segment in segments)
        is_behavior_only_l1 = (
            names == SEGMENTS
            and all("fOnsets" not in segment for segment in segments)
            and len(larva["waves"]) >= 50
        )
        if is_behavior_only_l1:
            selected.append(larva)

    if len(selected) != 18:
        raise ValueError(f"expected 18 L1 behavior animals, found {len(selected)}")

    output_segments: dict[str, Any] = {}
    for segment_index, segment_name in enumerate(SEGMENTS):
        metrics: dict[str, Any] = {}
        for output_name, source_name in FIELDS.items():
            animal_means = [
                finite_mean(larva["segments"][segment_index][source_name])
                for larva in selected
            ]
            finite = np.asarray(
                [value for value in animal_means if value is not None], dtype=float
            )
            if not finite.size:
                metrics[output_name] = None
                continue
            p10, median, p90 = np.quantile(finite, [0.1, 0.5, 0.9])
            metrics[output_name] = {
                "p10": round(float(p10), 6),
                "median": round(float(median), 6),
                "p90": round(float(p90), 6),
                "animal_count": int(finite.size),
            }
        output_segments[segment_name] = metrics

    return {
        "schema_version": 1,
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
                "arithmetic mean across cycles within each animal, then NumPy "
                "linear p10/median/p90 across animals"
            ),
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
        "segments": output_segments,
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
