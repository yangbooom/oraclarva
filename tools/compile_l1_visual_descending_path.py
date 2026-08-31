"""Compile an audited L1 visual-to-A1 structural path from VFB/CATMAID.

The bundled input is a 2026-08-31 snapshot of public VFB term-info and L1EM
CATMAID connectivity responses.  This compiler selects eight axon-to-dendrite
edges; it does not infer physiological signs, gains, delays, or segmental
replication from the observed structural contacts.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    ROOT
    / "data"
    / "sources"
    / "vfb_l1em_visual_descending_path"
    / "vfb-l1em-api-snapshot-2026-08-31.tar"
)
OUTPUT_PATH = (
    ROOT / "data" / "connectome" / "l1_visual_descending_path_v0.json"
)
SOURCE_SHA256 = (
    "0f558cf16f30b58b760ac7053abb7cd5ccb64243de36492c937760c5642e465b"
)


NEURONS = (
    {
        "node_id": "left:pOLP",
        "side": "left",
        "neuron_class": "pOLP",
        "path_role": "visual_projection_neuron",
        "catmaid_skeleton_id": 9940382,
        "vfb_id": "VFB_00100587",
        "vfb_name": "pOLP;left (L1EM:9940382)",
        "flybase_type": "optic lobe pioneer neuron 3",
        "flybase_type_id": "FBbt_00003706",
        "segment": "brain",
    },
    {
        "node_id": "right:pOLP",
        "side": "right",
        "neuron_class": "pOLP",
        "path_role": "visual_projection_neuron",
        "catmaid_skeleton_id": 8124177,
        "vfb_id": "VFB_00100527",
        "vfb_name": "pOLP;right (L1EM:8124177)",
        "flybase_type": "optic lobe pioneer neuron 3",
        "flybase_type_id": "FBbt_00003706",
        "segment": "brain",
    },
    {
        "node_id": "left:PVL09",
        "side": "left",
        "neuron_class": "PVL09",
        "path_role": "visual_projection_neuron",
        "catmaid_skeleton_id": 9567051,
        "vfb_id": "VFB_00100585",
        "vfb_name": "MB2ON-186 (L1EM:9567051)",
        "flybase_type": "larval visual projection neuron PVL09",
        "flybase_type_id": "FBbt_00047739",
        "segment": "brain",
    },
    {
        "node_id": "right:PVL09",
        "side": "right",
        "neuron_class": "PVL09",
        "path_role": "visual_projection_neuron",
        "catmaid_skeleton_id": 9539868,
        "vfb_id": "VFB_00100584",
        "vfb_name": "MB2ON-186 (L1EM:9539868)",
        "flybase_type": "larval visual projection neuron PVL09",
        "flybase_type_id": "FBbt_00047739",
        "segment": "brain",
    },
    {
        "node_id": "left:down_PVL09_PN-OLP",
        "side": "left",
        "neuron_class": "down_PVL09_PN-OLP",
        "path_role": "lateral_horn_neuron",
        "catmaid_skeleton_id": 11037238,
        "vfb_id": "VFB_00102exl",
        "vfb_name": "down_PVL09_PN-OLP_left (L1EM:11037238)",
        "flybase_type": "larval lateral horn neuron",
        "flybase_type_id": "FBbt_00051206",
        "segment": "brain",
    },
    {
        "node_id": "right:down_PVL09_PN-OLP",
        "side": "right",
        "neuron_class": "down_PVL09_PN-OLP",
        "path_role": "lateral_horn_neuron",
        "catmaid_skeleton_id": 7719118,
        "vfb_id": "VFB_00102epj",
        "vfb_name": "down_PVL09_PN-OLP_right (L1EM:7719118)",
        "flybase_type": "larval lateral horn neuron",
        "flybase_type_id": "FBbt_00051206",
        "segment": "brain",
    },
    {
        "node_id": "left:CPf_DN",
        "side": "left",
        "neuron_class": "CPf_DN",
        "path_role": "descending_neuron",
        "catmaid_skeleton_id": 5690425,
        "vfb_id": "VFB_00102emh",
        "vfb_name": "CPf descending ipsilateral left (L1EM:5690425)",
        "flybase_type": "larval descending neuron to VNC",
        "flybase_type_id": "FBbt_00049517",
        "segment": "brain_to_A1",
    },
    {
        "node_id": "right:CPf_DN",
        "side": "right",
        "neuron_class": "CPf_DN",
        "path_role": "descending_neuron",
        "catmaid_skeleton_id": 19010160,
        "vfb_id": "VFB_00102fkm",
        "vfb_name": "CPf descending ipsilateral right (L1EM:19010160)",
        "flybase_type": "larval descending neuron to VNC",
        "flybase_type_id": "FBbt_00049517",
        "segment": "brain_to_A1",
    },
    {
        "node_id": "left:A03o_A1",
        "side": "left",
        "neuron_class": "A03o_A1",
        "path_role": "A1_premotor_neuron",
        "catmaid_skeleton_id": 4302562,
        "vfb_id": "VFB_00100635",
        "vfb_name": "A03o_a1l (L1EM:4302562)",
        "flybase_type": "larval abdominal 1 A03o1 neuron",
        "flybase_type_id": "FBbt_00047772",
        "segment": "A1",
    },
    {
        "node_id": "right:A03o_A1",
        "side": "right",
        "neuron_class": "A03o_A1",
        "path_role": "A1_premotor_neuron",
        "catmaid_skeleton_id": 3180525,
        "vfb_id": "VFB_00100686",
        "vfb_name": "A03o_a1r (L1EM:3180525)",
        "flybase_type": "larval abdominal 1 A03o1 neuron",
        "flybase_type_id": "FBbt_00047772",
        "segment": "A1",
    },
)


EDGES = (
    ("left:pOLP", "left:down_PVL09_PN-OLP", 33),
    ("right:pOLP", "right:down_PVL09_PN-OLP", 25),
    ("left:PVL09", "left:down_PVL09_PN-OLP", 12),
    ("right:PVL09", "right:down_PVL09_PN-OLP", 8),
    ("left:down_PVL09_PN-OLP", "left:CPf_DN", 4),
    ("right:down_PVL09_PN-OLP", "right:CPf_DN", 3),
    ("left:CPf_DN", "left:A03o_A1", 2),
    ("right:CPf_DN", "right:A03o_A1", 11),
)


def _read_snapshot() -> dict[str, bytes]:
    digest = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError("VFB L1EM snapshot checksum differs from audited artifact")
    with tarfile.open(SOURCE_PATH) as archive:
        payloads: dict[str, bytes] = {}
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


def _validate_neuron_terms(payloads: dict[str, bytes]) -> None:
    for neuron in NEURONS:
        term = _json(payloads, f"{neuron['vfb_id']}.json")
        if term.get("Id") != neuron["vfb_id"] or term.get("Name") != neuron["vfb_name"]:
            raise ValueError(f"VFB identity changed for {neuron['node_id']}")
        expected_accession = str(neuron["catmaid_skeleton_id"])
        if not any(
            item.get("accession") == expected_accession
            for item in term.get("Xrefs", [])
        ):
            raise ValueError(f"CATMAID accession absent for {neuron['node_id']}")
        types = str(term.get("Meta", {}).get("Types", ""))
        if str(neuron["flybase_type_id"]) not in types:
            raise ValueError(f"FlyBase type changed for {neuron['node_id']}")
        licenses = {
            item.get("label") for item in term.get("Licenses", {}).values()
        }
        required = (
            "CC-BY-SA_4.0"
            if neuron["neuron_class"] == "A03o_A1"
            else "CC-BY_4.0"
        )
        if required not in licenses:
            raise ValueError(f"expected license absent for {neuron['node_id']}")


def _validate_a03o_premotor_annotations(payloads: dict[str, bytes]) -> None:
    response = _json(payloads, "cpf_premotor_annotations.json")
    if response.get("command") != "annotations_for_skeletons":
        raise ValueError("unexpected CATMAID annotation response")
    result = response.get("result", {})
    annotation_names = {
        str(key): value for key, value in result.get("annotations", {}).items()
    }
    expected = {"4302562": "A1L", "3180525": "A1R"}
    for skeleton_id, side_annotation in expected.items():
        names = {
            annotation_names.get(str(item.get("id")))
            for item in result.get("skeletons", {}).get(skeleton_id, [])
        }
        required = {
            side_annotation,
            "mw A1 premotorneuron plot",
            "mw A1 interneuron pre-MN 2nd_order",
        }
        if not required <= names:
            raise ValueError(
                f"A03o premotor annotations changed for {skeleton_id}"
            )


def _contact_count(
    connectivity: dict[str, Any], pre_skid: int, post_skid: int
) -> int:
    # CATMAID's response is partner-major: the outgoing partner is the outer
    # key and the selected presynaptic skeleton is inside ``skids``.
    values = (
        connectivity.get("result", {})
        .get("outgoing", {})
        .get(str(post_skid), {})
        .get("skids", {})
        .get(str(pre_skid))
    )
    if not isinstance(values, list) or len(values) != 5:
        raise ValueError(f"missing outgoing CATMAID edge {pre_skid}->{post_skid}")
    if any(values[index] != 0 for index in range(4)):
        raise ValueError(
            f"selected CATMAID edge {pre_skid}->{post_skid} has "
            "non-confidence-5 contacts"
        )
    return int(values[4])


def compile_path() -> dict[str, Any]:
    payloads = _read_snapshot()
    _validate_neuron_terms(payloads)
    _validate_a03o_premotor_annotations(payloads)
    connectivity = _json(payloads, "visual_a1_connectivity.json")
    if (
        connectivity.get("instance") != "l1em"
        or connectivity.get("project_id") != 1
        or connectivity.get("command") != "connectivity"
    ):
        raise ValueError("unexpected VFB CATMAID connectivity response")

    by_id = {str(item["node_id"]): item for item in NEURONS}
    connections = []
    for pre, post, expected_count in EDGES:
        count = _contact_count(
            connectivity,
            int(by_id[pre]["catmaid_skeleton_id"]),
            int(by_id[post]["catmaid_skeleton_id"]),
        )
        if count != expected_count:
            raise ValueError(
                f"audited contact count changed for {pre}->{post}: {count}"
            )
        connections.append(
            {
                "pre": pre,
                "post": post,
                "synaptic_contacts": count,
                "connection_compartment": "axon_to_dendrite",
                "confidence": 5,
                "physiological_effect": None,
                "physiological_effect_provenance": "unknown",
                "provenance": "MEASURED_PUBLISHED",
            }
        )

    neurons = []
    for item in NEURONS:
        neuron = dict(item)
        neuron.update(
            {
                "synaptic_effect": None,
                "synaptic_effect_provenance": "unknown",
                "provenance": "MEASURED_PUBLISHED",
            }
        )
        neurons.append(neuron)

    return {
        "schema_version": 1,
        "model_id": "dmel_l1_visual_descending_path_v0",
        "status": "published_structural_path_with_unresolved_effect_signs",
        "stage": "L1",
        "source": {
            "source_id": "vfb_l1em_visual_descending_path",
            "article_doi": "10.1126/science.add9330",
            "vfb_query_api": "https://v3-cached.virtualflybrain.org/",
            "catmaid_instance": "l1em",
            "catmaid_project_id": 1,
            "retrieved_at": "2026-08-31",
            "license": "CC BY 4.0 and CC BY-SA 4.0",
            "local_artifact": str(SOURCE_PATH.relative_to(ROOT)),
            "sha256": SOURCE_SHA256,
            "provenance": "MEASURED_PUBLISHED",
        },
        "summary": {
            "bilateral_pairs": 5,
            "identified_neurons": len(neurons),
            "new_runtime_compartments": 6,
            "axon_to_dendrite_connection_pairs": len(connections),
            "axon_to_dendrite_synaptic_contacts": sum(
                item["synaptic_contacts"] for item in connections
            ),
        },
        "neurons": neurons,
        "connections": connections,
        "limitations": [
            "This is one observed L1EM specimen path and not a "
            "population-average pathway.",
            "The 2-versus-11 CPf-to-A03o contact asymmetry is preserved "
            "and must not be generalized as a hemispheric constant.",
            "Structural axon-to-dendrite contacts do not establish "
            "physiological sign, current, delay, release probability, or "
            "behavioral role.",
            "The selected A03o neurons are in A1 only; this file does not "
            "justify replication into A2-A7 or a complete motor path.",
            "The Winding brain matrix is not a complete whole-body or "
            "all-segment VNC motor connectome; A1 links here come from the "
            "public L1EM CATMAID graph.",
        ],
        "release_validated": False,
    }


def encoded_path() -> str:
    return json.dumps(compile_path(), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile the audited L1 visual descending structural path"
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = encoded_path()
    if args.check:
        if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(
            encoding="utf-8"
        ) != rendered:
            print(
                "stale generated visual descending path: run "
                f"{Path(__file__).relative_to(ROOT)}"
            )
            return 1
        print("generated visual descending path is current")
        return 0
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
