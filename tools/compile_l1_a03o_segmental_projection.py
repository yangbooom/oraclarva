"""Compile an evidence-bounded A03o segmental homology projection.

Public VFB currently exposes only the bilateral A1 A03o1 instances.  The A2
ontology class exists but has no public instance, and no segment-specific A3-A7
class is returned by the audited label query.  This compiler therefore keeps
the A1 CATMAID graph untouched and builds only an ANATOMY_DERIVED A2-A6
projection.  It never invents skeleton IDs or repeats A1 contact counts as
measured segmental synapses.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    ROOT
    / "data"
    / "sources"
    / "vfb_l1em_a03o_segmental_audit"
    / "vfb-a03o-segmental-ontology-audit-2026-08-31.tar"
)
SOURCE_SHA256 = (
    "459763508bebc9969ae22b25697565e30001e341b363d27fe648ad429b486228"
)
OBSERVED_PATH = ROOT / "data" / "connectome" / "l1_a03o_motor_path_v0.json"
MUSCLE_ATLAS = (
    ROOT / "data" / "muscles" / "l1_abdominal_muscle_template_v0.json"
)
OUTPUT_PATH = (
    ROOT / "data" / "connectome" / "l1_a03o_segmental_projection_v0.json"
)

GENERIC_CLASS = "FBbt_00111250"
A1_CLASS = "FBbt_00047772"
A2_CLASS = "FBbt_00048658"
A1_INSTANCES = {"VFB_00100635", "VFB_00100686"}
DERIVED_SEGMENTS = ("A2", "A3", "A4", "A5", "A6")
SIDES = ("left", "right")


def _read_snapshot() -> dict[str, bytes]:
    digest = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError("VFB A03o segmental audit checksum differs")
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


def _short_form(iri: str) -> str:
    return iri.rsplit("/", 1)[-1]


def _audit_ontology(payloads: dict[str, bytes]) -> dict[str, Any]:
    solr = _json(payloads, "vfb-solr-a03o-label-query.json")
    docs = solr.get("response", {}).get("docs", [])
    hits = [
        {"id": _short_form(str(item["id"])), "label": str(item["label"])}
        for item in docs
    ]
    if len(hits) != 7:
        raise ValueError("VFB A03o label audit no longer has seven hits")
    hit_ids = {item["id"] for item in hits}
    if not {GENERIC_CLASS, A1_CLASS, A2_CLASS, *A1_INSTANCES} <= hit_ids:
        raise ValueError("required A03o ontology or instance record is absent")

    def instances(name: str, expected_class: str) -> set[str]:
        response = _json(payloads, name)
        if _short_form(str(response.get("@id"))) != expected_class:
            raise ValueError(f"unexpected Owlery class in {name}")
        return {
            _short_form(str(value)) for value in response.get("hasInstance", [])
        }

    generic = instances("vfb-owlery-a03o1-instances.json", GENERIC_CLASS)
    a1 = instances("vfb-owlery-a1-a03o1-instances.json", A1_CLASS)
    a2 = instances("vfb-owlery-a2-a03o1-instances.json", A2_CLASS)
    if generic != A1_INSTANCES or a1 != A1_INSTANCES or a2:
        raise ValueError("public A03o instance boundary changed")
    return {
        "label_query_hits": hits,
        "generic_a03o1_class": GENERIC_CLASS,
        "a1_a03o1_class": A1_CLASS,
        "a2_a03o1_class": A2_CLASS,
        "generic_public_instances": sorted(generic),
        "a1_public_instances": sorted(a1),
        "a2_public_instances": sorted(a2),
        "interpretation": (
            "The audited public VFB graph exposes only the bilateral A1 "
            "A03o1 instances. The A2 class is defined but has no public "
            "instance; no A3-A7 segment-specific A03o1 class is returned."
        ),
        "provenance": "MEASURED_PUBLISHED",
    }


def _target_weights(
    observed: dict[str, Any], atlas: dict[str, Any]
) -> list[dict[str, Any]]:
    neurons = {item["node_id"]: item for item in observed["neurons"]}
    contact_mass: dict[str, float] = defaultdict(float)
    for connection in observed["connections"]:
        targets = neurons[connection["post"]]["target_muscles"]
        share = float(connection["synaptic_contacts"]) / len(targets)
        for target in targets:
            contact_mass[str(target["number"])] += share
    total = sum(contact_mass.values())
    if total != 26.0 or len(contact_mass) != 13:
        raise ValueError("A1 pooled target support changed")
    template = {item["number"]: item for item in atlas["muscles"]}
    weights = []
    for number in sorted(contact_mass, key=int):
        muscle = template[number]
        weights.append(
            {
                "number": number,
                "synonym": muscle["synonym"],
                "spatial_group": muscle["spatial_group"],
                "a1_pooled_contact_mass": contact_mass[number],
                "relative_weight": contact_mass[number] / total,
            }
        )
    if abs(sum(item["relative_weight"] for item in weights) - 1.0) > 1e-12:
        raise ValueError("derived motor target weights must sum to one")
    return weights


def compile_projection() -> dict[str, Any]:
    ontology_audit = _audit_ontology(_read_snapshot())
    observed = json.loads(OBSERVED_PATH.read_text(encoding="utf-8"))
    atlas = json.loads(MUSCLE_ATLAS.read_text(encoding="utf-8"))
    if observed.get("model_id") != "dmel_l1_a03o_motor_path_v0":
        raise ValueError("unexpected observed A03o motor source")
    supported = tuple(atlas.get("scope", {}).get("homology_supported_segments", ()))
    blocked = set(atlas.get("scope", {}).get("blocked_segments", ()))
    if supported != ("A1", *DERIVED_SEGMENTS) or "A7" not in blocked:
        raise ValueError("muscle homology gate no longer supports A2-A6 only")
    weights = _target_weights(observed, atlas)

    homologs = []
    targets = []
    cpf_connections = []
    motor_connections = []
    for segment in DERIVED_SEGMENTS:
        ontology_class = A2_CLASS if segment == "A2" else GENERIC_CLASS
        for side in SIDES:
            homolog_id = f"derived:{side}:A03o_{segment}"
            homologs.append(
                {
                    "node_id": homolog_id,
                    "side": side,
                    "segment": segment,
                    "neuron_class": "A03o_homolog_proxy",
                    "path_role": "segmental_premotor_proxy",
                    "ontology_class": ontology_class,
                    "catmaid_skeleton_id": None,
                    "identity_status": "predicted_homolog_not_public_instance",
                    "provenance": "ANATOMY_DERIVED",
                }
            )
            cpf_connections.append(
                {
                    "pre": f"{side}:CPf_DN",
                    "post": homolog_id,
                    "connection_role": "cpf_to_derived_a03o",
                    "relative_weight": 1.0,
                    "synaptic_contacts": None,
                    "physiological_effect": None,
                    "provenance": "ANATOMY_DERIVED",
                }
            )
            for weight in weights:
                target_id = (
                    f"derived_motor_target:{segment}:{side}:"
                    f"M{weight['number']}:{weight['synonym']}"
                )
                targets.append(
                    {
                        "node_id": target_id,
                        "side": side,
                        "segment": segment,
                        "neuron_class": "segmental_motor_target_proxy",
                        "path_role": "motor_to_muscle_identity_proxy",
                        "target_muscle": {
                            "number": weight["number"],
                            "synonym": weight["synonym"],
                            "spatial_group": weight["spatial_group"],
                        },
                        "catmaid_skeleton_id": None,
                        "identity_status": (
                            "muscle_target_channel_not_identified_motor_neuron"
                        ),
                        "provenance": "ANATOMY_DERIVED",
                    }
                )
                motor_connections.append(
                    {
                        "pre": homolog_id,
                        "post": target_id,
                        "connection_role": "derived_a03o_to_motor_target",
                        "relative_weight": weight["relative_weight"],
                        "a1_pooled_contact_mass": weight[
                            "a1_pooled_contact_mass"
                        ],
                        "synaptic_contacts": None,
                        "physiological_effect": None,
                        "provenance": "ANATOMY_DERIVED",
                    }
                )

    return {
        "schema_version": 1,
        "model_id": "dmel_l1_a03o_segmental_projection_v0",
        "status": "anatomy_derived_a2_a6_projection_a7_blocked",
        "stage": "L1",
        "source": {
            "source_id": "vfb_l1em_a03o_segmental_audit",
            "retrieved_at": "2026-08-31",
            "vfb_solr_api": "https://solr.virtualflybrain.org/solr/ontology/",
            "vfb_owlery_api": "https://owl.virtualflybrain.org/kbs/vfb/",
            "license": "CC BY-SA 4.0",
            "local_artifact": str(SOURCE_PATH.relative_to(ROOT)),
            "sha256": SOURCE_SHA256,
            "provenance": "MEASURED_PUBLISHED",
        },
        "supporting_sources": [
            {
                "doi": "10.7554/eLife.67510",
                "used_for": "A03o1 NB7-1 lineage identity",
                "provenance": "MEASURED_PUBLISHED",
            },
            {
                "doi": "10.1038/srep30806",
                "used_for": (
                    "research-case prior that larval excitatory premotor "
                    "interneurons can be segmentally arrayed"
                ),
                "provenance": "MEASURED_PUBLISHED",
            },
            {
                "doi": "10.7554/eLife.51781",
                "used_for": "A1 versus A2-A6 body-wall muscle identity homology",
                "provenance": "MEASURED_PUBLISHED",
            },
        ],
        "ontology_audit": ontology_audit,
        "projection_scope": {
            "observed_segment": "A1",
            "derived_segments": list(DERIVED_SEGMENTS),
            "blocked_segments": ["A7"],
            "blocked_reason": (
                "No public A7 A03o instance/contact graph and the current "
                "muscle identity atlas explicitly blocks terminal A7."
            ),
            "provenance": "ANATOMY_DERIVED",
        },
        "projection_rule": {
            "source_observed_contacts": 26,
            "source_unique_target_muscles": 13,
            "target_weight_policy": (
                "Split each observed A1 A03o-to-MN contact mass equally "
                "among that MN's listed target muscles, pool both sides, "
                "then normalize to one. Relative mass is a dimensionless "
                "prior and is never represented as a segmental contact count."
            ),
            "bilateral_policy": (
                "Instantiate the pooled target distribution once per side "
                "to avoid repeating one-specimen A1 left/right asymmetry."
            ),
            "target_weights": weights,
            "provenance": "ANATOMY_DERIVED",
        },
        "summary": {
            "vfb_a03o_label_query_hits": 7,
            "public_a03o1_instances": 2,
            "public_a2_a03o1_instances": 0,
            "derived_segments": len(DERIVED_SEGMENTS),
            "derived_a03o_homologs": len(homologs),
            "derived_motor_target_channels": len(targets),
            "cpf_to_a03o_projection_edges": len(cpf_connections),
            "a03o_to_motor_projection_edges": len(motor_connections),
            "unique_projected_target_muscles": len(weights),
            "blocked_segments": 1,
        },
        "a03o_homologs": homologs,
        "motor_target_channels": targets,
        "connections": cpf_connections + motor_connections,
        "limitations": [
            "Only the A1 bilateral A03o pair and its 15 motor edges/26 contacts "
            "are public specimen observations.",
            "A2-A6 nodes have no public skeleton IDs and are explicitly "
            "ANATOMY_DERIVED proxies, not reconstructed neurons.",
            "Relative target weights preserve only pooled A1 distribution; "
            "they are not synapse counts, conductances, or release strengths.",
            "The motor-target channels name supported muscle identities but "
            "do not identify segment-specific motor neurons or NMJs.",
            "A7 remains blocked and is not silently cloned from A1-A6.",
            "No attachment coordinate, CSA, force gain, or individual muscle "
            "actuator is supplied by this projection.",
        ],
        "release_validated": False,
    }


def render_projection() -> str:
    return json.dumps(compile_projection(), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile the evidence-bounded A03o A2-A6 projection"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_projection()
    if args.check:
        if not args.output.exists() or args.output.read_text(
            encoding="utf-8"
        ) != rendered:
            print(f"generated A03o segmental projection is stale: {args.output}")
            return 1
        print("generated A03o segmental projection is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
