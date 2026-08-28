"""Compile the checked-in L1 motor map from source snapshots.

This is an offline, deterministic join. It never guesses a neuron class from
an unresolved CATMAID skeleton ID.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "neuromuscular"
SNAPSHOT_PATH = SOURCE_DIR / "zarin_2019_catmaid_snapshot.json"
TABLE_PATH = SOURCE_DIR / "zarin_2019_table1.json"
OUTPUT_PATH = SOURCE_DIR / "l1_motor_map_v1.json"
SEGMENT_SIDE = re.compile(r"_a(?P<segment>[0-9]+)(?P<side>[lr])\s*$")


def compile_map() -> dict[str, object]:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    table = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    rows = {row["class_id"]: row for row in table["rows"]}
    projections: list[dict[str, object]] = []
    unresolved: list[dict[str, str]] = []

    for neuron in snapshot["neurons"]:
        neuron_id = neuron["neuron_id"]
        neuron_name = neuron["neuron_name"]
        if neuron_name is None:
            unresolved.append(
                {
                    "neuron_id": neuron_id,
                    "reason": "Supplementary skeleton ID has no name in the current public CATMAID endpoint; class and target are not inferred.",
                }
            )
            continue

        match = SEGMENT_SIDE.search(neuron_name)
        if not match:
            raise ValueError(f"cannot parse segment and side from {neuron_name!r}")
        class_id = neuron_name.strip().split()[0]
        if class_id == "MN12-III":
            class_id = "MN12"
        row = rows.get(class_id)
        if row is None:
            raise ValueError(f"no Table 1 target row for {class_id!r}")

        projections.append(
            {
                "neuron_id": neuron_id,
                "neuron_name": neuron_name,
                "dataset_id": snapshot["dataset"]["id"],
                "segment_id": f"A{match.group('segment')}",
                "side": "left" if match.group("side") == "l" else "right",
                "spatial_group": row["spatial_group"],
                "target_muscles": [
                    {"number": target[0], "synonym": target[1], "evidence": target[2]}
                    for target in row["targets"]
                ],
                "synapse_type": row["synapse_type"],
                "nerve": row["nerve"],
                "muscle_group": None,
                "weight": None,
                "gain_provenance": "unknown",
                "provenance": "observed",
                "source_id": table["source_id"],
            }
        )

    projections.sort(key=lambda item: int(item["neuron_id"]))
    unresolved.sort(key=lambda item: int(item["neuron_id"]))
    return {
        "schema_version": 2,
        "model_id": "dmel_l1_motor_map_v1",
        "organism": "Drosophila melanogaster",
        "stage": "L1",
        "status": "curated_partial_a1_a2_targets_pending_gains_and_geometry",
        "dataset": snapshot["dataset"],
        "note": (
            "Table 1 muscle targets are cross-walked to current CATMAID names for "
            "58 reconstructed motor neurons. A1 is represented bilaterally; MN25 is "
            "represented in A2 because it is absent in A1. Three supplementary IDs "
            "remain unresolved. Muscle gains and attachment geometry are unknown, so "
            "this anatomical map must not yet drive release body physics."
        ),
        "coverage": {
            "supplement_skeleton_ids": len(snapshot["neurons"]),
            "resolved_current_names": len(projections),
            "unresolved_current_names": len(unresolved),
            "mapped_segments": ["A1", "A2"],
            "full_body_segments": False,
        },
        "projections": projections,
        "unresolved_neurons": unresolved,
        "sources": [
            {
                "id": snapshot["source_id"],
                "citation": snapshot["citation"],
                "doi": snapshot["doi"],
                "url": snapshot["download_url"],
                "used_for": ["CATMAID skeleton IDs", "current CATMAID neuron names"],
            },
            {
                "id": table["source_id"],
                "citation": table["citation"],
                "doi": table["doi"],
                "url": table["url"],
                "used_for": [
                    "motor-neuron class",
                    "muscle targets",
                    "spatial muscle group",
                    "synapse type",
                ],
            },
        ],
    }


def encoded_map() -> str:
    return json.dumps(compile_map(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    compiled = encoded_map()
    if args.check:
        if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(encoding="utf-8") != compiled:
            print(f"stale generated map: run {Path(__file__).relative_to(ROOT)}")
            return 1
        print("generated motor map is current")
        return 0
    OUTPUT_PATH.write_text(compiled, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
