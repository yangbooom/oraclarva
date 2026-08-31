"""Compile observed A03o(A1)-to-motor contacts from public L1EM data.

The source snapshot contains the unmodified VFB/CATMAID connectivity,
annotation, and term-info responses retrieved on 2026-08-31.  Motor targets
are cross-checked against the existing Zarin 2019 motor map.  The compiler
does not infer missing contralateral edges, repeat A1 contacts in A2-A7, or
assign physiological signs and gains to structural contacts.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    ROOT
    / "data"
    / "sources"
    / "vfb_l1em_a03o_motor_path"
    / "vfb-l1em-a03o-motor-api-snapshot-2026-08-31.tar"
)
OUTPUT_PATH = ROOT / "data" / "connectome" / "l1_a03o_motor_path_v0.json"
MOTOR_MAP_PATH = ROOT / "data" / "neuromuscular" / "l1_motor_map_v1.json"
SOURCE_SHA256 = (
    "07dcc865c82ebeff4e8051a7a8f6994c3f8400cdf7c6fa722f65d88a5a2e571e"
)

A03O_NODES = {
    "4302562": {
        "node_id": "left:A03o_A1",
        "side": "left",
        "vfb_id": "VFB_00100635",
    },
    "3180525": {
        "node_id": "right:A03o_A1",
        "side": "right",
        "vfb_id": "VFB_00100686",
    },
}


def _read_snapshot() -> dict[str, bytes]:
    digest = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError("VFB A03o motor snapshot checksum differs")
    payloads: dict[str, bytes] = {}
    with tarfile.open(SOURCE_PATH) as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"cannot read snapshot member {member.name}")
            payloads[member.name] = extracted.read()
    return payloads


def _json(payloads: dict[str, bytes], name: str) -> dict[str, Any]:
    try:
        value = json.load(io.BytesIO(payloads[name]))
    except (KeyError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid snapshot member {name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"snapshot member {name} must contain an object")
    return value


def _motor_annotations(
    payloads: dict[str, bytes], selected_ids: set[str]
) -> None:
    response = _json(payloads, "oraclarva-a03o-motor-annotations.json")
    if (
        response.get("instance") != "l1em"
        or response.get("project_id") != 1
        or response.get("command") != "annotations_for_skeletons"
    ):
        raise ValueError("unexpected motor annotation response")
    result = response.get("result", {})
    annotation_names = {
        str(key): value for key, value in result.get("annotations", {}).items()
    }
    for skeleton_id in selected_ids:
        names = {
            annotation_names.get(str(item.get("id")))
            for item in result.get("skeletons", {}).get(skeleton_id, [])
        }
        if not {"A1 motorneurons", "mw A1 MN", "MNs (A1)"} <= names:
            raise ValueError(
                f"A1 motor annotations changed for skeleton {skeleton_id}"
            )


def _term(
    payloads: dict[str, bytes], vfb_id: str, skeleton_id: str
) -> dict[str, Any]:
    term = _json(
        payloads,
        f"oraclarva-a03o-motor-terms/{vfb_id}.json",
    )
    if term.get("Id") != vfb_id:
        raise ValueError(f"VFB identity changed for {skeleton_id}")
    if not any(
        str(item.get("accession")) == skeleton_id
        for item in term.get("Xrefs", [])
    ):
        raise ValueError(f"CATMAID accession absent for {skeleton_id}")
    licenses = {item.get("label") for item in term.get("Licenses", {}).values()}
    if "CC-BY-SA_4.0" not in licenses:
        raise ValueError(f"CC BY-SA 4.0 absent for {skeleton_id}")
    return term


def _contact_count(
    outgoing: dict[str, Any], pre_id: str, post_id: str
) -> int:
    values = outgoing.get(post_id, {}).get("skids", {}).get(pre_id)
    if not isinstance(values, list) or len(values) != 5:
        raise ValueError(f"invalid CATMAID edge {pre_id}->{post_id}")
    if any(values[index] != 0 for index in range(4)) or values[4] <= 0:
        raise ValueError(
            f"selected edge {pre_id}->{post_id} must be confidence 5"
        )
    return int(values[4])


def compile_path() -> dict[str, Any]:
    payloads = _read_snapshot()
    connectivity = _json(payloads, "oraclarva-a03o-connectivity.json")
    if (
        connectivity.get("instance") != "l1em"
        or connectivity.get("project_id") != 1
        or connectivity.get("command") != "connectivity"
    ):
        raise ValueError("unexpected VFB CATMAID connectivity response")
    if connectivity.get("unmatched"):
        raise ValueError("A03o connectivity query contains unmatched ids")

    motor_map = json.loads(MOTOR_MAP_PATH.read_text(encoding="utf-8"))
    projections = {
        str(item["neuron_id"]): item
        for item in motor_map["projections"]
        if item["segment_id"] == "A1"
    }
    outgoing = connectivity.get("result", {}).get("outgoing", {})
    selected_ids = set(outgoing) & set(projections)
    if len(selected_ids) != 14:
        raise ValueError("expected exactly 14 observed A1 motor partners")
    _motor_annotations(payloads, selected_ids)

    reverse_map = {
        str(key): str(value)
        for key, value in connectivity.get("reverse_map", {}).items()
    }
    neurons = []
    for skeleton_id in sorted(selected_ids, key=int):
        projection = projections[skeleton_id]
        vfb_id = reverse_map.get(skeleton_id)
        if not vfb_id:
            raise ValueError(f"VFB reverse map absent for {skeleton_id}")
        term = _term(payloads, vfb_id, skeleton_id)
        neurons.append(
            {
                "node_id": (
                    f"motor_identity:{skeleton_id}:{projection['side']}"
                ),
                "side": projection["side"],
                "neuron_class": "A1_motor_identity",
                "path_role": "A1_motor_neuron",
                "catmaid_skeleton_id": int(skeleton_id),
                "vfb_id": vfb_id,
                "vfb_name": term.get("Name"),
                "flybase_type": str(
                    term.get("Meta", {}).get("Types", "")
                ),
                "segment": "A1",
                "spatial_group": projection["spatial_group"],
                "target_muscles": projection["target_muscles"],
                "motor_map_source_id": projection["source_id"],
                "synaptic_effect": None,
                "synaptic_effect_provenance": "unknown",
                "provenance": "MEASURED_PUBLISHED",
            }
        )

    node_by_skeleton = {
        str(item["catmaid_skeleton_id"]): item["node_id"] for item in neurons
    }
    connections = []
    for pre_id, upstream in A03O_NODES.items():
        for post_id in sorted(selected_ids, key=int):
            values = outgoing.get(post_id, {}).get("skids", {}).get(pre_id)
            if values is None:
                continue
            count = _contact_count(outgoing, pre_id, post_id)
            connections.append(
                {
                    "pre": upstream["node_id"],
                    "post": node_by_skeleton[post_id],
                    "synaptic_contacts": count,
                    "connection_compartment": "axon_to_dendrite",
                    "confidence": 5,
                    "physiological_effect": None,
                    "physiological_effect_provenance": "unknown",
                    "provenance": "MEASURED_PUBLISHED",
                }
            )
    if len(connections) != 15 or sum(
        item["synaptic_contacts"] for item in connections
    ) != 26:
        raise ValueError("A03o-to-motor edge audit changed")

    target_numbers = {
        target["number"]
        for neuron in neurons
        for target in neuron["target_muscles"]
    }
    groups = Counter(item["spatial_group"] for item in neurons)
    sides = Counter(item["side"] for item in neurons)
    return {
        "schema_version": 1,
        "model_id": "dmel_l1_a03o_motor_path_v0",
        "status": "published_structural_a1_motor_branch_with_unresolved_effect_signs",
        "stage": "L1",
        "source": {
            "source_id": "vfb_l1em_a03o_motor_path",
            "article_doi": "10.1126/science.add9330",
            "motor_map_doi": "10.7554/eLife.51781",
            "vfb_query_api": "https://v3-cached.virtualflybrain.org/",
            "catmaid_instance": "l1em",
            "catmaid_project_id": 1,
            "retrieved_at": "2026-08-31",
            "license": "CC BY-SA 4.0",
            "local_artifact": str(SOURCE_PATH.relative_to(ROOT)),
            "sha256": SOURCE_SHA256,
            "provenance": "MEASURED_PUBLISHED",
        },
        "upstream_nodes": [
            {
                **item,
                "catmaid_skeleton_id": int(skeleton_id),
                "segment": "A1",
                "provenance": "MEASURED_PUBLISHED",
            }
            for skeleton_id, item in A03O_NODES.items()
        ],
        "summary": {
            "queried_a03o_neurons": 2,
            "identified_a1_motor_neurons": len(neurons),
            "a1_motor_map_denominator": len(projections),
            "axon_to_dendrite_connection_pairs": len(connections),
            "axon_to_dendrite_synaptic_contacts": sum(
                item["synaptic_contacts"] for item in connections
            ),
            "unique_target_muscle_numbers": len(target_numbers),
            "motor_neurons_by_side": dict(sorted(sides.items())),
            "motor_neurons_by_spatial_group": dict(sorted(groups.items())),
        },
        "neurons": neurons,
        "connections": connections,
        "limitations": [
            "This is one L1EM specimen: 14 of the 56 mapped A1 motor "
            "identities receive at least one observed A03o contact.",
            "The observed 15 edges and 26 contacts are sparse and asymmetric; "
            "missing left/right homolog edges are not synthesized.",
            "Structural contacts do not establish physiological effect sign, "
            "current, delay, release probability, or recruitment strength.",
            "A1 topology is not copied to A2-A7, and this motor branch alone "
            "cannot produce or validate a full-body locomotor wave.",
            "Published motor-to-muscle identities do not provide individual "
            "3D attachment coordinates, CSA, line of action, or force gain.",
        ],
        "release_validated": False,
    }


def render() -> str:
    return json.dumps(compile_path(), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile observed L1 A03o-to-A1-motor contacts"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render()
    if args.check:
        if not args.output.exists() or args.output.read_text(
            encoding="utf-8"
        ) != rendered:
            print(f"compiled A03o motor path is stale: {args.output}")
            return 1
        print("compiled A03o motor path is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
