"""Compile neural-output to named-muscle identity mappings.

This compiler joins the published A1 motor-neuron target crosswalk and the
explicitly ANATOMY_DERIVED A2-A6 motor-target proxies to the 358-fiber
abdominal identity atlas.  It creates identity events only: no NMJ position,
attachment, activation dynamics, CSA, force, or line of action is implied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OBSERVED_PATH = ROOT / "data" / "connectome" / "l1_a03o_motor_path_v0.json"
DERIVED_PATH = (
    ROOT / "data" / "connectome" / "l1_a03o_segmental_projection_v0.json"
)
ATLAS_PATH = ROOT / "data" / "muscles" / "l1_abdominal_muscle_template_v0.json"
OUTPUT_PATH = (
    ROOT / "data" / "neuromuscular" / "l1_neural_muscle_identity_v0.json"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _fiber_id(segment: str, side: str, number: str, synonym: str) -> str:
    return f"{segment}:{side}:M{number}:{synonym}"


def compile_mapping() -> dict[str, Any]:
    observed = _load(OBSERVED_PATH)
    derived = _load(DERIVED_PATH)
    atlas = _load(ATLAS_PATH)
    if observed.get("model_id") != "dmel_l1_a03o_motor_path_v0":
        raise ValueError("unexpected observed A03o motor path")
    if derived.get("model_id") != "dmel_l1_a03o_segmental_projection_v0":
        raise ValueError("unexpected derived A03o segmental projection")
    if atlas.get("model_id") != "dmel_l1_abdominal_muscle_template_v0":
        raise ValueError("unexpected abdominal muscle atlas")

    template = {str(item["number"]): item for item in atlas["muscles"]}
    if tuple(template) != tuple(str(number) for number in range(1, 31)):
        raise ValueError("muscle atlas template changed")

    mappings: list[dict[str, Any]] = []
    for neuron in observed["neurons"]:
        if neuron.get("segment") != "A1" or neuron.get("provenance") != "MEASURED_PUBLISHED":
            raise ValueError("observed motor identity boundary changed")
        for target in neuron["target_muscles"]:
            number = str(target["number"])
            muscle = template[number]
            if target["synonym"] != muscle["synonym"]:
                raise ValueError(f"muscle synonym mismatch for M{number}")
            mappings.append(
                {
                    "source_node_id": neuron["node_id"],
                    "fiber_id": _fiber_id(
                        "A1", neuron["side"], number, muscle["synonym"]
                    ),
                    "segment": "A1",
                    "side": neuron["side"],
                    "muscle": {
                        "number": number,
                        "synonym": muscle["synonym"],
                        "spatial_group": muscle["spatial_group"],
                    },
                    "mapping_role": "observed_motor_identity_to_named_muscle",
                    "mapping_provenance": "MEASURED_PUBLISHED",
                }
            )

    observed_count = len(mappings)
    for target in derived["motor_target_channels"]:
        if target.get("provenance") != "ANATOMY_DERIVED":
            raise ValueError("derived target provenance changed")
        muscle = target["target_muscle"]
        number = str(muscle["number"])
        atlas_muscle = template[number]
        if (
            muscle["synonym"] != atlas_muscle["synonym"]
            or muscle["spatial_group"] != atlas_muscle["spatial_group"]
        ):
            raise ValueError(f"derived muscle identity mismatch for M{number}")
        mappings.append(
            {
                "source_node_id": target["node_id"],
                "fiber_id": _fiber_id(
                    target["segment"], target["side"], number, muscle["synonym"]
                ),
                "segment": target["segment"],
                "side": target["side"],
                "muscle": dict(muscle),
                "mapping_role": "derived_motor_target_to_named_muscle",
                "mapping_provenance": "ANATOMY_DERIVED",
            }
        )

    fiber_ids = [item["fiber_id"] for item in mappings]
    pairs = [(item["source_node_id"], item["fiber_id"]) for item in mappings]
    if observed_count != 16 or len(mappings) != 146:
        raise ValueError("expected 16 observed and 130 derived identity mappings")
    if len(fiber_ids) != len(set(fiber_ids)) or len(pairs) != len(set(pairs)):
        raise ValueError("neural-muscle identity mapping must be one-to-one by fiber")

    return {
        "schema_version": 1,
        "model_id": "dmel_l1_neural_muscle_identity_v0",
        "status": "identity_event_mapping_only_not_activation_or_mechanics",
        "stage": "L1",
        "sources": [
            {
                "model_id": observed["model_id"],
                "local_artifact": str(OBSERVED_PATH.relative_to(ROOT)),
                "used_for": "observed A1 motor identities and published target-muscle crosswalk",
                "provenance": "MEASURED_PUBLISHED",
            },
            {
                "model_id": derived["model_id"],
                "local_artifact": str(DERIVED_PATH.relative_to(ROOT)),
                "used_for": "A2-A6 motor-target proxies",
                "provenance": "ANATOMY_DERIVED",
            },
            {
                "model_id": atlas["model_id"],
                "local_artifact": str(ATLAS_PATH.relative_to(ROOT)),
                "used_for": "358-fiber A1-A6 identity namespace",
                "provenance": "MEASURED_PUBLISHED_AND_ANATOMY_DERIVED",
            },
        ],
        "event_semantics": {
            "rule": "one source-node spike emits one event to each explicitly mapped named fiber unless that fiber is lesioned",
            "provenance": "ANATOMY_DERIVED",
            "activation_dynamics_executed": False,
            "individual_geometry_executed": False,
            "mechanical_force_executed": False,
            "nmj_location_claimed": False,
        },
        "summary": {
            "atlas_fibers": 358,
            "mapped_unique_fibers": len(set(fiber_ids)),
            "unmapped_fibers": 358 - len(set(fiber_ids)),
            "observed_a1_motor_identities": len(observed["neurons"]),
            "observed_a1_identity_mappings": observed_count,
            "derived_a2_a6_identity_mappings": len(mappings) - observed_count,
            "total_identity_mappings": len(mappings),
            "blocked_segments": ["A7"],
        },
        "mappings": mappings,
        "limitations": [
            "A1 mappings preserve published motor-to-muscle identity targets but do not locate individual NMJs.",
            "A2-A6 mappings terminate anatomy-derived target proxies and do not claim identified segmental motor neurons.",
            "The remaining 212 atlas fibers receive no event; missing neural evidence is not filled by uniform recruitment.",
            "Events are discrete causal bookkeeping only; spike-to-activation dynamics are deferred to the next model stage.",
            "No attachment, rest length, CSA, force gain, material law, or muscle actuator is introduced.",
            "A7 remains blocked.",
        ],
        "release_validated": False,
    }


def render_mapping() -> str:
    return json.dumps(compile_mapping(), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile neural-output to named-muscle identity mappings"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_mapping()
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            print(f"generated neural-muscle identity mapping is stale: {args.output}")
            return 1
        print("generated neural-muscle identity mapping is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
