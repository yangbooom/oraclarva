"""Published L1 larval-optic-neuropil topology in an embodied light loop."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from math import exp, isfinite
from pathlib import Path
from typing import Any, Iterable

from .body3d import Vec3
from .environment_inputs import LinearScalarField, ScalarField
from .lif import SparseLIFNetwork, Synapse
from .muscles import (
    NeuralMuscleIdentityEventFrame,
    NeuralMuscleIdentityProjection,
    load_neural_muscle_identity_projection,
)
from .spatial import (
    SpatialClosedLoopLarva,
    SpatialClosedLoopResult,
    SpatialSensoryState,
    SpatialStimulus,
)


LON_SIDES = ("left", "right")
PHOTORECEPTOR_CLASSES = ("Rh5-PR", "Rh6-PR")
BRIDGE_INPUT_LABELS = (
    "fitted_a03o_to_segmental_core:left",
    "fitted_a03o_to_segmental_core:right",
    "fitted_a03o_to_segmental_core:dorsal_shared",
    "fitted_a03o_to_segmental_core:ventral_shared",
)
BRIDGE_DIFFERENCE_LABELS = (
    "fitted_a03o_lateral_difference:left",
    "fitted_a03o_lateral_difference:right",
    "fitted_a03o_dorsoventral_difference:dorsal_shared",
    "fitted_a03o_dorsoventral_difference:ventral_shared",
)


def default_visual_config_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "organism"
        / "l1_visual_closed_loop_v0.json"
    )


def default_visual_connectome_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "connectome"
        / "l1_visual_connectome_v0.json"
    )


def default_visual_descending_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "connectome"
        / "l1_visual_descending_path_v0.json"
    )


def default_a03o_motor_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "connectome"
        / "l1_a03o_motor_path_v0.json"
    )


def default_a03o_segmental_projection_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "connectome"
        / "l1_a03o_segmental_projection_v0.json"
    )


def load_visual_config(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else default_visual_config_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("status") != "research_approximation":
        raise ValueError("visual closed loop must remain a research approximation")
    if raw.get("stage") != "L1":
        raise ValueError("visual closed loop target stage must remain L1")
    if tuple(raw.get("causal_contract", ())) != (
        "analytic_light_field",
        "bilateral_bolwig_organ_samples",
        "fitted_rh5_rh6_phototransduction",
        "published_l1_lon_synaptic_contacts",
        "fitted_effects_for_published_contacts",
        "published_polp_to_lhn_to_cpf_to_a03o_a1_contacts",
        "published_a03o_a1_to_motor_identity_contacts",
        "anatomy_derived_cpf_to_a03o_a2_a6_topology",
        "anatomy_derived_a03o_a2_a6_to_motor_target_topology",
        "fitted_effects_for_anatomy_derived_projection",
        "motor_output_spikes_to_named_muscle_identity_events",
        "fitted_a03o_a1_to_segmental_core_bridge",
        "spatial_neural_dynamics",
        "motor_pools",
        "muscle_activation",
        "3d_body_physics",
        "analytic_light_field",
    ):
        raise ValueError("visual causal contract is invalid")

    connectome = raw.get("connectome", {})
    if connectome.get("provenance") != "MEASURED_PUBLISHED":
        raise ValueError("visual connectome topology must remain measured-published")
    if (
        int(connectome.get("expected_side_scoped_matrix_entries", 0)) != 60
        or int(connectome.get("expected_nonzero_connection_pairs", 0)) != 422
        or int(connectome.get("expected_within_lon_synaptic_contacts", 0))
        != 3297
    ):
        raise ValueError("visual connectome count contract is invalid")

    descending = raw.get("descending_connectome", {})
    if descending.get("provenance") != "MEASURED_PUBLISHED":
        raise ValueError("visual descending topology must remain measured-published")
    if (
        descending.get("model_id") != "dmel_l1_visual_descending_path_v0"
        or int(descending.get("expected_identified_neurons", 0)) != 10
        or int(descending.get("expected_new_runtime_compartments", 0)) != 6
        or int(descending.get("expected_axon_to_dendrite_connection_pairs", 0))
        != 8
        or int(descending.get("expected_axon_to_dendrite_synaptic_contacts", 0))
        != 98
    ):
        raise ValueError("visual descending count contract is invalid")

    motor_path = raw.get("a03o_motor_connectome", {})
    if motor_path.get("provenance") != "MEASURED_PUBLISHED":
        raise ValueError("A03o motor topology must remain measured-published")
    if (
        motor_path.get("model_id") != "dmel_l1_a03o_motor_path_v0"
        or int(motor_path.get("expected_identified_a1_motor_neurons", 0)) != 14
        or int(motor_path.get("expected_axon_to_dendrite_connection_pairs", 0))
        != 15
        or int(motor_path.get("expected_axon_to_dendrite_synaptic_contacts", 0))
        != 26
    ):
        raise ValueError("A03o motor count contract is invalid")

    segmental_projection = raw.get("a03o_segmental_projection", {})
    if segmental_projection.get("provenance") != "ANATOMY_DERIVED":
        raise ValueError("A03o segmental projection must remain anatomy-derived")
    if (
        segmental_projection.get("model_id")
        != "dmel_l1_a03o_segmental_projection_v0"
        or int(segmental_projection.get("expected_derived_segments", 0)) != 5
        or int(segmental_projection.get("expected_derived_a03o_homologs", 0))
        != 10
        or int(
            segmental_projection.get(
                "expected_derived_motor_target_channels", 0
            )
        )
        != 130
        or int(segmental_projection.get("expected_projection_edges", 0))
        != 140
        or segmental_projection.get("blocked_segments") != ["A7"]
    ):
        raise ValueError("A03o segmental projection count contract is invalid")

    identity_projection = raw.get("neural_muscle_identity_projection", {})
    if (
        identity_projection.get("model_id")
        != "dmel_l1_neural_muscle_identity_v0"
        or identity_projection.get("event_rule_provenance")
        != "ANATOMY_DERIVED"
        or int(identity_projection.get("expected_atlas_fibers", 0)) != 358
        or int(identity_projection.get("expected_mapped_unique_fibers", 0))
        != 146
        or int(identity_projection.get("expected_observed_a1_mappings", 0))
        != 16
        or int(identity_projection.get("expected_derived_a2_a6_mappings", 0))
        != 130
        or identity_projection.get("activation_dynamics_executed") is not False
        or identity_projection.get("individual_geometry_executed") is not False
    ):
        raise ValueError("neural-muscle identity projection contract is invalid")

    transduction = raw.get("phototransduction", {})
    if transduction.get("field_unit") != "W_m-2":
        raise ValueError("visual field unit must be W_m-2")
    if transduction.get("provenance") != "MODEL_FITTED":
        raise ValueError("visual phototransduction must remain model-fitted")
    for key in (
        "ambient_half_saturation",
        "spatial_contrast_scale",
        "temporal_contrast_scale",
        "adaptation_tau_s",
    ):
        value = float(transduction.get(key, 0.0))
        if not isfinite(value) or value <= 0.0:
            raise ValueError(f"visual phototransduction {key} must be positive")
    classes = transduction.get("classes", {})
    if tuple(classes) != PHOTORECEPTOR_CLASSES:
        raise ValueError("visual photoreceptor classes are invalid")
    for neuron_class, parameters in classes.items():
        for key in (
            "ambient_gain",
            "spatial_contrast_gain",
            "temporal_contrast_gain",
            "maximum_external_current_a",
        ):
            value = float(parameters.get(key, -1.0))
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{neuron_class} {key} cannot be negative")
        if float(parameters["maximum_external_current_a"]) <= 0.0:
            raise ValueError(
                f"{neuron_class} maximum external current must be positive"
            )

    dynamics = raw.get("lon_dynamics", {})
    unit_current = float(dynamics.get("unit_current_per_synaptic_contact_a", 0.0))
    if not isfinite(unit_current) or unit_current <= 0.0:
        raise ValueError("visual contact current must be positive")
    if dynamics.get("effect_provenance") != "MODEL_FITTED":
        raise ValueError("visual synaptic effects must remain model-fitted")
    effects = dynamics.get("effect_by_presynaptic_class", {})
    if any(value not in {"excitatory", "inhibitory"} for value in effects.values()):
        raise ValueError("visual synaptic effect is invalid")
    unexecuted = tuple(dynamics.get("unexecuted_presynaptic_classes", ()))
    if unexecuted != ("SP2-1", "sVUM2", "Pdf-LaN"):
        raise ValueError("visual structural-only classes are invalid")
    if set(effects) & set(unexecuted):
        raise ValueError("visual classes cannot be both executable and structural-only")

    path_dynamics = raw.get("descending_path_dynamics", {})
    path_currents = path_dynamics.get(
        "current_per_synaptic_contact_a_by_presynaptic_class", {}
    )
    if any(
        not isfinite(float(value)) or float(value) <= 0.0
        for value in path_currents.values()
    ):
        raise ValueError("visual descending contact currents must be positive")
    if path_dynamics.get("effect_provenance") != "MODEL_FITTED":
        raise ValueError("visual descending effects must remain model-fitted")
    path_effects = path_dynamics.get("effect_by_presynaptic_class", {})
    expected_path_classes = (
        "pOLP", "PVL09", "down_PVL09_PN-OLP", "CPf_DN"
    )
    if (
        tuple(path_effects) != expected_path_classes
        or tuple(path_currents) != expected_path_classes
    ):
        raise ValueError("visual descending dynamics classes are invalid")
    if any(
        value not in {"excitatory", "inhibitory"}
        for value in path_effects.values()
    ):
        raise ValueError("visual descending effect is invalid")

    motor_dynamics = raw.get("a03o_motor_path_dynamics", {})
    if motor_dynamics.get("effect_provenance") != "MODEL_FITTED":
        raise ValueError("A03o motor effects must remain model-fitted")
    if motor_dynamics.get("effect_by_presynaptic_class") != {
        "A03o_A1": "excitatory"
    }:
        raise ValueError("A03o motor effect classes are invalid")
    motor_current = float(
        motor_dynamics.get("current_per_synaptic_contact_a", 0.0)
    )
    if not isfinite(motor_current) or motor_current <= 0.0:
        raise ValueError("A03o motor contact current must be positive")

    projection_dynamics = raw.get("a03o_segmental_projection_dynamics", {})
    if projection_dynamics.get("provenance") != "MODEL_FITTED":
        raise ValueError("A03o segmental projection effects must remain fitted")
    if projection_dynamics.get("effect_by_connection_role") != {
        "cpf_to_derived_a03o": "excitatory",
        "derived_a03o_to_motor_target": "excitatory",
    }:
        raise ValueError("A03o segmental projection effect roles are invalid")
    for key in (
        "cpf_to_a03o_current_a",
        "a03o_to_motor_total_current_a",
    ):
        value = float(projection_dynamics.get(key, 0.0))
        if not isfinite(value) or value <= 0.0:
            raise ValueError(f"A03o segmental projection {key} must be positive")

    bridge = raw.get("a03o_segmental_bridge", {})
    if bridge.get("provenance") != "MODEL_FITTED":
        raise ValueError("A03o segmental bridge must remain model-fitted")
    if (
        bridge.get("readout_class") != "A03o_A1"
        or bridge.get("readout_segment") != "A1"
    ):
        raise ValueError("A03o segmental readout identity is invalid")
    for key in (
        "activity_tau_s",
        "spike_increment",
        "common_output_gain",
        "lateral_difference_gain",
    ):
        value = float(bridge.get(key, 0.0))
        if not isfinite(value) or value <= 0.0:
            raise ValueError(f"A03o segmental bridge {key} must be positive")
    side_gains = bridge.get("side_activity_gain", {})
    if tuple(side_gains) != LON_SIDES or any(
        not isfinite(float(value)) or float(value) <= 0.0
        for value in side_gains.values()
    ):
        raise ValueError("A03o bridge side activity gains are invalid")
    if float(bridge.get("direct_dorsoventral_difference_gain", -1.0)) != 0.0:
        raise ValueError("visual bridge cannot invent direct dorsoventral sensing")
    mapping_evidence = bridge.get("lateral_mapping_evidence", {})
    if (
        bridge.get("lateral_mapping") != "crossed_light_avoidance_prior"
        or mapping_evidence.get("doi") != "10.1073/pnas.1215295110"
        or mapping_evidence.get("stage") != "L2"
    ):
        raise ValueError("visual bridge lateral mapping boundary is invalid")
    if raw.get("parameter_provenance", {}).get("provenance") != "MODEL_FITTED":
        raise ValueError("visual numerical parameters must remain model-fitted")
    if raw.get("release_validated") is not False:
        raise ValueError("visual research approximation cannot be release-validated")
    return raw


def load_visual_connectome(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else default_visual_connectome_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("model_id") != "dmel_l1_visual_connectome_v0":
        raise ValueError("unexpected visual connectome model")
    if raw.get("stage") != "L1":
        raise ValueError("visual connectome must remain L1")
    source_record = raw.get("source", {})
    if (
        source_record.get("source_data_doi") != "10.7554/eLife.28387.009"
        or source_record.get("license") != "CC BY 4.0"
        or source_record.get("provenance") != "MEASURED_PUBLISHED"
    ):
        raise ValueError("visual connectome source contract is invalid")
    summary = raw.get("summary", {})
    if (
        int(summary.get("side_scoped_matrix_entries", 0)) != 60
        or int(summary.get("nonzero_connection_pairs", 0)) != 422
        or int(summary.get("within_lon_synaptic_contacts", 0)) != 3297
    ):
        raise ValueError("visual connectome summary is invalid")
    neurons = raw.get("neurons", [])
    node_ids = [item.get("node_id") for item in neurons]
    if len(neurons) != 60 or len(node_ids) != len(set(node_ids)):
        raise ValueError("visual connectome node identities are invalid")
    if any(
        item.get("synaptic_effect") is not None
        or item.get("synaptic_effect_provenance") != "unknown"
        for item in neurons
    ):
        raise ValueError("source connectome cannot claim physiological effects")
    connections = raw.get("connections", [])
    if len(connections) != 422:
        raise ValueError("visual connectome connection count is invalid")
    known = set(node_ids)
    if any(
        item.get("pre") not in known
        or item.get("post") not in known
        or not isinstance(item.get("synaptic_contacts"), int)
        or item["synaptic_contacts"] <= 0
        or item.get("provenance") != "MEASURED_PUBLISHED"
        for item in connections
    ):
        raise ValueError("visual connectome connection is invalid")
    if sum(item["synaptic_contacts"] for item in connections) != 3297:
        raise ValueError("visual connectome contact total is invalid")
    if raw.get("release_validated") is not False:
        raise ValueError("visual connectome cannot be release-validated")
    return raw


def load_visual_descending_connectome(
    path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(path) if path else default_visual_descending_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("model_id") != "dmel_l1_visual_descending_path_v0":
        raise ValueError("unexpected visual descending connectome model")
    if raw.get("stage") != "L1":
        raise ValueError("visual descending connectome must remain L1")
    source_record = raw.get("source", {})
    if (
        source_record.get("article_doi") != "10.1126/science.add9330"
        or source_record.get("license") != "CC BY 4.0 and CC BY-SA 4.0"
        or source_record.get("provenance") != "MEASURED_PUBLISHED"
    ):
        raise ValueError("visual descending source contract is invalid")
    summary = raw.get("summary", {})
    if (
        int(summary.get("identified_neurons", 0)) != 10
        or int(summary.get("new_runtime_compartments", 0)) != 6
        or int(summary.get("axon_to_dendrite_connection_pairs", 0)) != 8
        or int(summary.get("axon_to_dendrite_synaptic_contacts", 0)) != 98
    ):
        raise ValueError("visual descending summary is invalid")
    neurons = raw.get("neurons", [])
    node_ids = [item.get("node_id") for item in neurons]
    if len(neurons) != 10 or len(node_ids) != len(set(node_ids)):
        raise ValueError("visual descending identities are invalid")
    if {item.get("side") for item in neurons} != set(LON_SIDES):
        raise ValueError("visual descending path must remain bilateral")
    if any(
        item.get("synaptic_effect") is not None
        or item.get("synaptic_effect_provenance") != "unknown"
        or item.get("provenance") != "MEASURED_PUBLISHED"
        for item in neurons
    ):
        raise ValueError("visual descending source cannot claim effects")
    connections = raw.get("connections", [])
    known = set(node_ids)
    if len(connections) != 8 or any(
        item.get("pre") not in known
        or item.get("post") not in known
        or not isinstance(item.get("synaptic_contacts"), int)
        or item["synaptic_contacts"] <= 0
        or item.get("connection_compartment") != "axon_to_dendrite"
        or item.get("confidence") != 5
        or item.get("physiological_effect") is not None
        or item.get("physiological_effect_provenance") != "unknown"
        or item.get("provenance") != "MEASURED_PUBLISHED"
        for item in connections
    ):
        raise ValueError("visual descending connection is invalid")
    if sum(item["synaptic_contacts"] for item in connections) != 98:
        raise ValueError("visual descending contact total is invalid")
    if raw.get("release_validated") is not False:
        raise ValueError("visual descending path cannot be release-validated")
    return raw


def load_a03o_motor_connectome(
    path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(path) if path else default_a03o_motor_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("model_id") != "dmel_l1_a03o_motor_path_v0":
        raise ValueError("unexpected A03o motor connectome model")
    if raw.get("stage") != "L1":
        raise ValueError("A03o motor connectome must remain L1")
    source_record = raw.get("source", {})
    if (
        source_record.get("article_doi") != "10.1126/science.add9330"
        or source_record.get("motor_map_doi") != "10.7554/eLife.51781"
        or source_record.get("license") != "CC BY-SA 4.0"
        or source_record.get("provenance") != "MEASURED_PUBLISHED"
    ):
        raise ValueError("A03o motor source contract is invalid")
    summary = raw.get("summary", {})
    if (
        int(summary.get("queried_a03o_neurons", 0)) != 2
        or int(summary.get("identified_a1_motor_neurons", 0)) != 14
        or int(summary.get("a1_motor_map_denominator", 0)) != 56
        or int(summary.get("axon_to_dendrite_connection_pairs", 0)) != 15
        or int(summary.get("axon_to_dendrite_synaptic_contacts", 0)) != 26
        or int(summary.get("unique_target_muscle_numbers", 0)) != 13
    ):
        raise ValueError("A03o motor summary is invalid")
    upstream_ids = {
        item.get("node_id") for item in raw.get("upstream_nodes", [])
    }
    if upstream_ids != {"left:A03o_A1", "right:A03o_A1"}:
        raise ValueError("A03o motor upstream identities are invalid")
    neurons = raw.get("neurons", [])
    node_ids = [item.get("node_id") for item in neurons]
    if (
        len(neurons) != 14
        or len(node_ids) != len(set(node_ids))
        or any(
            item.get("neuron_class") != "A1_motor_identity"
            or item.get("segment") != "A1"
            or item.get("side") not in LON_SIDES
            or item.get("synaptic_effect") is not None
            or item.get("synaptic_effect_provenance") != "unknown"
            or item.get("provenance") != "MEASURED_PUBLISHED"
            or not item.get("target_muscles")
            for item in neurons
        )
    ):
        raise ValueError("A03o motor identities are invalid")
    known = upstream_ids | set(node_ids)
    connections = raw.get("connections", [])
    if len(connections) != 15 or any(
        item.get("pre") not in upstream_ids
        or item.get("post") not in known
        or not isinstance(item.get("synaptic_contacts"), int)
        or item["synaptic_contacts"] <= 0
        or item.get("connection_compartment") != "axon_to_dendrite"
        or item.get("confidence") != 5
        or item.get("physiological_effect") is not None
        or item.get("physiological_effect_provenance") != "unknown"
        or item.get("provenance") != "MEASURED_PUBLISHED"
        for item in connections
    ):
        raise ValueError("A03o motor connection is invalid")
    if sum(item["synaptic_contacts"] for item in connections) != 26:
        raise ValueError("A03o motor contact total is invalid")
    if raw.get("release_validated") is not False:
        raise ValueError("A03o motor path cannot be release-validated")
    return raw


def load_a03o_segmental_projection(
    path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(path) if path else default_a03o_segmental_projection_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("model_id") != "dmel_l1_a03o_segmental_projection_v0":
        raise ValueError("unexpected A03o segmental projection model")
    if raw.get("stage") != "L1":
        raise ValueError("A03o segmental projection must remain L1")
    source_record = raw.get("source", {})
    if (
        source_record.get("source_id")
        != "vfb_l1em_a03o_segmental_audit"
        or source_record.get("license") != "CC BY-SA 4.0"
        or source_record.get("provenance") != "MEASURED_PUBLISHED"
    ):
        raise ValueError("A03o segmental audit source contract is invalid")
    summary = raw.get("summary", {})
    expected = {
        "vfb_a03o_label_query_hits": 7,
        "public_a03o1_instances": 2,
        "public_a2_a03o1_instances": 0,
        "derived_segments": 5,
        "derived_a03o_homologs": 10,
        "derived_motor_target_channels": 130,
        "cpf_to_a03o_projection_edges": 10,
        "a03o_to_motor_projection_edges": 130,
        "unique_projected_target_muscles": 13,
        "blocked_segments": 1,
    }
    if summary != expected:
        raise ValueError("A03o segmental projection summary is invalid")
    audit = raw.get("ontology_audit", {})
    if (
        set(audit.get("generic_public_instances", ()))
        != {"VFB_00100635", "VFB_00100686"}
        or set(audit.get("a1_public_instances", ()))
        != {"VFB_00100635", "VFB_00100686"}
        or audit.get("a2_public_instances") != []
    ):
        raise ValueError("A03o public instance boundary is invalid")
    scope = raw.get("projection_scope", {})
    segments = ("A2", "A3", "A4", "A5", "A6")
    if (
        tuple(scope.get("derived_segments", ())) != segments
        or scope.get("blocked_segments") != ["A7"]
        or scope.get("provenance") != "ANATOMY_DERIVED"
    ):
        raise ValueError("A03o segmental projection scope is invalid")
    homologs = raw.get("a03o_homologs", [])
    homolog_ids = {item.get("node_id") for item in homologs}
    if len(homologs) != 10 or len(homolog_ids) != 10 or any(
        item.get("segment") not in segments
        or item.get("side") not in LON_SIDES
        or item.get("neuron_class") != "A03o_homolog_proxy"
        or item.get("catmaid_skeleton_id") is not None
        or item.get("provenance") != "ANATOMY_DERIVED"
        for item in homologs
    ):
        raise ValueError("derived A03o homolog identities are invalid")
    targets = raw.get("motor_target_channels", [])
    target_ids = {item.get("node_id") for item in targets}
    if len(targets) != 130 or len(target_ids) != 130 or any(
        item.get("segment") not in segments
        or item.get("side") not in LON_SIDES
        or item.get("neuron_class") != "segmental_motor_target_proxy"
        or item.get("catmaid_skeleton_id") is not None
        or item.get("provenance") != "ANATOMY_DERIVED"
        for item in targets
    ):
        raise ValueError("derived motor target channels are invalid")
    connections = raw.get("connections", [])
    if len(connections) != 140 or any(
        item.get("synaptic_contacts") is not None
        or item.get("physiological_effect") is not None
        or item.get("provenance") != "ANATOMY_DERIVED"
        or not isfinite(float(item.get("relative_weight", 0.0)))
        or float(item.get("relative_weight", 0.0)) <= 0.0
        for item in connections
    ):
        raise ValueError("derived A03o segmental connections are invalid")
    cpf_edges = [
        item
        for item in connections
        if item.get("connection_role") == "cpf_to_derived_a03o"
    ]
    motor_edges = [
        item
        for item in connections
        if item.get("connection_role") == "derived_a03o_to_motor_target"
    ]
    if (
        len(cpf_edges) != 10
        or any(
            item.get("pre") not in {"left:CPf_DN", "right:CPf_DN"}
            or item.get("post") not in homolog_ids
            or float(item["relative_weight"]) != 1.0
            for item in cpf_edges
        )
        or len(motor_edges) != 130
        or any(
            item.get("pre") not in homolog_ids
            or item.get("post") not in target_ids
            for item in motor_edges
        )
    ):
        raise ValueError("derived A03o segmental edge roles are invalid")
    for homolog_id in homolog_ids:
        total = sum(
            float(item["relative_weight"])
            for item in motor_edges
            if item["pre"] == homolog_id
        )
        if abs(total - 1.0) > 1e-12:
            raise ValueError("derived motor weights must sum to one per homolog")
    if raw.get("release_validated") is not False:
        raise ValueError("A03o segmental projection cannot be release-validated")
    return raw


def visual_node_ids_for_class(
    connectome: dict[str, Any],
    neuron_class: str,
    *,
    lon_side: str | None = None,
) -> tuple[str, ...]:
    if lon_side is not None and lon_side not in LON_SIDES:
        raise ValueError("visual LON side must be left or right")
    result = tuple(
        item["node_id"]
        for item in connectome["neurons"]
        if item["neuron_class"] == neuron_class
        and (
            lon_side is None
            or item.get("lon_side", item.get("side")) == lon_side
        )
    )
    if not result:
        raise ValueError(f"visual neuron class {neuron_class!r} is absent")
    return result


@dataclass(frozen=True, slots=True)
class BolwigTransductionFrame:
    time_s: float
    sample_positions_m: dict[str, Vec3]
    irradiance_w_m2: dict[str, float]
    adapted_irradiance_w_m2: dict[str, float]
    receptor_drive: dict[str, dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_s": self.time_s,
            "sample_positions_m": {
                side: [position.x, position.y, position.z]
                for side, position in self.sample_positions_m.items()
            },
            "irradiance_w_m2": self.irradiance_w_m2,
            "adapted_irradiance_w_m2": self.adapted_irradiance_w_m2,
            "receptor_drive": self.receptor_drive,
        }


class BolwigLightTransduction:
    """Turn two local irradiance samples into fitted Rh5/Rh6 currents."""

    def __init__(self, field: ScalarField, config: dict[str, Any]) -> None:
        if field.modality_id != "light" or field.unit != "W_m-2":
            raise ValueError("Bolwig transduction requires a W_m-2 light field")
        self.field = field
        self.parameters = config["phototransduction"]
        self._adapted: dict[str, float] = {}
        self._last_time_s: float | None = None

    def sample(
        self, time_s: float, state: SpatialSensoryState
    ) -> BolwigTransductionFrame:
        if not isfinite(time_s) or time_s < 0.0:
            raise ValueError("visual sample time must be finite and non-negative")
        if self._last_time_s is not None and time_s < self._last_time_s:
            raise ValueError("visual sample time cannot move backwards")
        elapsed = (
            0.0 if self._last_time_s is None else time_s - self._last_time_s
        )
        positions = {
            "left": state.left_head_position_m,
            "right": state.right_head_position_m,
        }
        raw = {
            side: self.field.sample(position, time_s)
            for side, position in positions.items()
        }
        if any(not isfinite(value) or value < 0.0 for value in raw.values()):
            raise ValueError("Bolwig irradiance must be finite and non-negative")
        adapted = {
            side: self._adapted.get(side, value) for side, value in raw.items()
        }
        mean = sum(raw.values()) / len(raw)
        half_saturation = float(self.parameters["ambient_half_saturation"])
        spatial_scale = float(self.parameters["spatial_contrast_scale"])
        temporal_scale = float(self.parameters["temporal_contrast_scale"])
        receptor_drive: dict[str, dict[str, float]] = {}
        for neuron_class in PHOTORECEPTOR_CLASSES:
            class_parameters = self.parameters["classes"][neuron_class]
            drive_by_side = {}
            for side in LON_SIDES:
                ambient = raw[side] / (raw[side] + half_saturation)
                drive = (
                    float(class_parameters["ambient_gain"]) * ambient
                    + float(class_parameters["spatial_contrast_gain"])
                    * (raw[side] - mean)
                    / spatial_scale
                    + float(class_parameters["temporal_contrast_gain"])
                    * (raw[side] - adapted[side])
                    / temporal_scale
                )
                drive_by_side[side] = min(1.0, max(0.0, drive))
            receptor_drive[neuron_class] = drive_by_side

        coupling = (
            0.0
            if elapsed == 0.0
            else 1.0
            - exp(-elapsed / float(self.parameters["adaptation_tau_s"]))
        )
        self._adapted = {
            side: adapted[side] + (raw[side] - adapted[side]) * coupling
            for side in LON_SIDES
        }
        self._last_time_s = time_s
        return BolwigTransductionFrame(
            time_s=time_s,
            sample_positions_m=positions,
            irradiance_w_m2=raw,
            adapted_irradiance_w_m2=adapted,
            receptor_drive=receptor_drive,
        )


@dataclass(frozen=True, slots=True)
class VisualCircuitFrame:
    transduction: BolwigTransductionFrame
    spiked_neurons: tuple[str, ...]
    a03o_spikes: dict[str, tuple[str, ...]]
    a1_motor_spikes: dict[str, tuple[str, ...]]
    derived_a03o_spikes: dict[str, tuple[str, ...]]
    derived_motor_spikes: dict[str, tuple[str, ...]]
    muscle_identity_events: NeuralMuscleIdentityEventFrame
    bridge_activity: dict[str, float]
    bridge_stimulus: SpatialStimulus

    def to_dict(self) -> dict[str, Any]:
        return {
            "transduction": self.transduction.to_dict(),
            "spiked_neurons": list(self.spiked_neurons),
            "a03o_spikes": {
                side: list(values) for side, values in self.a03o_spikes.items()
            },
            "a1_motor_spikes": {
                side: list(values)
                for side, values in self.a1_motor_spikes.items()
            },
            "derived_a03o_spikes": {
                channel: list(values)
                for channel, values in self.derived_a03o_spikes.items()
            },
            "derived_motor_spikes": {
                channel: list(values)
                for channel, values in self.derived_motor_spikes.items()
            },
            "muscle_identity_events": {
                "source_spikes": list(self.muscle_identity_events.source_spikes),
                "fiber_events": list(self.muscle_identity_events.fiber_events),
                "source_by_fiber": dict(
                    self.muscle_identity_events.source_by_fiber
                ),
                "mapping_provenance_by_fiber": dict(
                    self.muscle_identity_events.mapping_provenance_by_fiber
                ),
                "event_rule_provenance": (
                    self.muscle_identity_events.event_rule_provenance
                ),
                "activation_dynamics_executed": False,
                "individual_geometry_executed": False,
            },
            "bridge_activity": self.bridge_activity,
            "bridge_stimulus": list(self.bridge_stimulus.values()),
        }


class L1VisualCircuitProtocol:
    """Step observed and explicitly derived visual-to-motor branches."""

    def __init__(
        self,
        field: ScalarField,
        *,
        config: dict[str, Any] | None = None,
        connectome: dict[str, Any] | None = None,
        descending_connectome: dict[str, Any] | None = None,
        motor_connectome: dict[str, Any] | None = None,
        segmental_projection: dict[str, Any] | None = None,
        muscle_identity_projection: NeuralMuscleIdentityProjection | None = None,
        lesion_node_ids: Iterable[str] = (),
        lesion_muscle_fiber_ids: Iterable[str] = (),
        record_frames: bool = False,
    ) -> None:
        self.config = config or load_visual_config()
        self.connectome = connectome or load_visual_connectome()
        self.descending_connectome = (
            descending_connectome or load_visual_descending_connectome()
        )
        self.motor_connectome = motor_connectome or load_a03o_motor_connectome()
        self.segmental_projection = (
            segmental_projection or load_a03o_segmental_projection()
        )
        self.muscle_identity_projection = (
            muscle_identity_projection
            or load_neural_muscle_identity_projection()
        )
        self.transduction = BolwigLightTransduction(field, self.config)
        self.record_frames = record_frames
        self.frames: list[VisualCircuitFrame] = []

        merged_neurons = [dict(item) for item in self.connectome["neurons"]]
        merged_index = {
            item["node_id"]: index for index, item in enumerate(merged_neurons)
        }
        for path_neuron in self.descending_connectome["neurons"]:
            node_id = path_neuron["node_id"]
            if node_id in merged_index:
                existing = merged_neurons[merged_index[node_id]]
                if (
                    existing["neuron_class"] != path_neuron["neuron_class"]
                    or existing["lon_side"] != path_neuron["side"]
                ):
                    raise ValueError(f"visual identity conflict for {node_id}")
                existing.update(path_neuron)
                continue
            neuron = dict(path_neuron)
            neuron["lon_side"] = neuron["side"]
            neuron["identity"] = neuron["vfb_name"]
            neuron["transmitter"] = "unknown"
            neuron["transmitter_provenance"] = "unknown"
            merged_index[node_id] = len(merged_neurons)
            merged_neurons.append(neuron)

        for motor_neuron in self.motor_connectome["neurons"]:
            node_id = motor_neuron["node_id"]
            if node_id in merged_index:
                raise ValueError(f"duplicate A03o motor identity {node_id}")
            neuron = dict(motor_neuron)
            neuron["lon_side"] = neuron["side"]
            neuron["identity"] = neuron["vfb_name"]
            neuron["transmitter"] = "unknown"
            neuron["transmitter_provenance"] = "unknown"
            merged_index[node_id] = len(merged_neurons)
            merged_neurons.append(neuron)

        for derived_neuron in (
            self.segmental_projection["a03o_homologs"]
            + self.segmental_projection["motor_target_channels"]
        ):
            node_id = derived_neuron["node_id"]
            if node_id in merged_index:
                raise ValueError(f"duplicate derived segmental identity {node_id}")
            neuron = dict(derived_neuron)
            neuron["lon_side"] = neuron["side"]
            neuron["identity"] = node_id
            neuron["transmitter"] = "unknown"
            neuron["transmitter_provenance"] = "unknown"
            merged_index[node_id] = len(merged_neurons)
            merged_neurons.append(neuron)

        self.neurons = tuple(merged_neurons)
        self.labels = tuple(item["node_id"] for item in self.neurons)
        self.index_by_id = {
            node_id: index for index, node_id in enumerate(self.labels)
        }
        self.metadata_by_id = {
            item["node_id"]: item for item in self.neurons
        }
        if len(self.neurons) != 220 or len(self.labels) != len(set(self.labels)):
            raise ValueError("visual runtime must contain 220 unique compartments")
        missing_muscle_sources = (
            self.muscle_identity_projection.source_node_ids - set(self.labels)
        )
        if missing_muscle_sources:
            raise ValueError(
                "neural-muscle mapping sources absent from visual runtime: "
                f"{sorted(missing_muscle_sources)}"
            )

        dynamics = self.config["lon_dynamics"]
        effects = dynamics["effect_by_presynaptic_class"]
        structural_only = set(dynamics["unexecuted_presynaptic_classes"])
        unit_current = float(dynamics["unit_current_per_synaptic_contact_a"])
        synapses: list[Synapse] = []
        executed_lon_contacts = 0
        for item in self.connectome["connections"]:
            pre_class = self.metadata_by_id[item["pre"]]["neuron_class"]
            if pre_class in structural_only:
                continue
            if pre_class not in effects:
                raise ValueError(f"visual effect absent for {pre_class}")
            count = int(item["synaptic_contacts"])
            synapses.append(
                Synapse(
                    self.index_by_id[item["pre"]],
                    self.index_by_id[item["post"]],
                    unit_current * count,
                    kind=effects[pre_class],
                )
            )
            executed_lon_contacts += count
        self.executed_lon_connection_pairs = len(synapses)
        self.executed_lon_synaptic_contacts = executed_lon_contacts

        path_dynamics = self.config["descending_path_dynamics"]
        path_effects = path_dynamics["effect_by_presynaptic_class"]
        path_currents = path_dynamics[
            "current_per_synaptic_contact_a_by_presynaptic_class"
        ]
        for item in self.descending_connectome["connections"]:
            pre_class = self.metadata_by_id[item["pre"]]["neuron_class"]
            if pre_class not in path_effects:
                raise ValueError(f"descending visual effect absent for {pre_class}")
            synapses.append(
                Synapse(
                    self.index_by_id[item["pre"]],
                    self.index_by_id[item["post"]],
                    float(path_currents[pre_class])
                    * int(item["synaptic_contacts"]),
                    kind=path_effects[pre_class],
                )
            )
        self.executed_descending_connection_pairs = len(
            self.descending_connectome["connections"]
        )
        self.executed_descending_synaptic_contacts = sum(
            item["synaptic_contacts"]
            for item in self.descending_connectome["connections"]
        )

        motor_dynamics = self.config["a03o_motor_path_dynamics"]
        motor_effects = motor_dynamics["effect_by_presynaptic_class"]
        motor_current = float(
            motor_dynamics["current_per_synaptic_contact_a"]
        )
        for item in self.motor_connectome["connections"]:
            pre_class = self.metadata_by_id[item["pre"]]["neuron_class"]
            if pre_class not in motor_effects:
                raise ValueError(f"A03o motor effect absent for {pre_class}")
            synapses.append(
                Synapse(
                    self.index_by_id[item["pre"]],
                    self.index_by_id[item["post"]],
                    motor_current * int(item["synaptic_contacts"]),
                    kind=motor_effects[pre_class],
                )
            )
        self.executed_motor_connection_pairs = len(
            self.motor_connectome["connections"]
        )
        self.executed_motor_synaptic_contacts = sum(
            item["synaptic_contacts"]
            for item in self.motor_connectome["connections"]
        )
        projection_dynamics = self.config[
            "a03o_segmental_projection_dynamics"
        ]
        projection_effects = projection_dynamics["effect_by_connection_role"]
        for item in self.segmental_projection["connections"]:
            role = item["connection_role"]
            if role == "cpf_to_derived_a03o":
                current = float(projection_dynamics["cpf_to_a03o_current_a"])
            elif role == "derived_a03o_to_motor_target":
                current = float(
                    projection_dynamics["a03o_to_motor_total_current_a"]
                ) * float(item["relative_weight"])
            else:
                raise ValueError(f"unknown segmental projection role {role}")
            synapses.append(
                Synapse(
                    self.index_by_id[item["pre"]],
                    self.index_by_id[item["post"]],
                    current,
                    kind=projection_effects[role],
                )
            )
        self.executed_segmental_projection_edges = len(
            self.segmental_projection["connections"]
        )

        self.network = SparseLIFNetwork(len(self.neurons), synapses)
        self.executed_connection_pairs = len(synapses)
        self.executed_synaptic_contacts = (
            self.executed_lon_synaptic_contacts
            + self.executed_descending_synaptic_contacts
            + self.executed_motor_synaptic_contacts
        )

        lesions = tuple(lesion_node_ids)
        if len(lesions) != len(set(lesions)):
            raise ValueError("visual lesion node ids must be unique")
        unknown = set(lesions) - set(self.labels)
        if unknown:
            raise ValueError(f"unknown visual lesion node ids: {sorted(unknown)}")
        self.lesion_node_ids = lesions
        self.network.lesion(self.index_by_id[item] for item in lesions)
        muscle_lesions = tuple(lesion_muscle_fiber_ids)
        self.muscle_identity_projection.emit(
            (), lesioned_fiber_ids=muscle_lesions
        )
        self.lesion_muscle_fiber_ids = muscle_lesions

        bridge = self.config["a03o_segmental_bridge"]
        self.a03o_indices = {
            side: tuple(
                index
                for index, item in enumerate(self.neurons)
                if item["lon_side"] == side
                and item["neuron_class"] == bridge["readout_class"]
                and item.get("segment") == bridge["readout_segment"]
            )
            for side in LON_SIDES
        }
        if any(len(values) != 1 for values in self.a03o_indices.values()):
            raise ValueError("visual bridge requires one A1 A03o neuron per side")
        self.a1_motor_indices = {
            side: tuple(
                index
                for index, item in enumerate(self.neurons)
                if item["lon_side"] == side
                and item["neuron_class"] == "A1_motor_identity"
            )
            for side in LON_SIDES
        }
        if tuple(
            len(self.a1_motor_indices[side]) for side in LON_SIDES
        ) != (6, 8):
            raise ValueError(
                "visual motor branch must preserve 6 left and 8 right MNs"
            )
        derived_segments = tuple(
            self.segmental_projection["projection_scope"]["derived_segments"]
        )
        self.derived_a03o_indices = {
            f"{segment}:{side}": tuple(
                index
                for index, item in enumerate(self.neurons)
                if item.get("segment") == segment
                and item["lon_side"] == side
                and item["neuron_class"] == "A03o_homolog_proxy"
            )
            for segment in derived_segments
            for side in LON_SIDES
        }
        self.derived_motor_indices = {
            f"{segment}:{side}": tuple(
                index
                for index, item in enumerate(self.neurons)
                if item.get("segment") == segment
                and item["lon_side"] == side
                and item["neuron_class"]
                == "segmental_motor_target_proxy"
            )
            for segment in derived_segments
            for side in LON_SIDES
        }
        if any(
            len(values) != 1 for values in self.derived_a03o_indices.values()
        ) or any(
            len(values) != 13 for values in self.derived_motor_indices.values()
        ):
            raise ValueError("derived A03o segmental runtime indices are invalid")

        self.bridge_activity = {side: 0.0 for side in LON_SIDES}
        self.spike_counts = {label: 0 for label in self.labels}
        self.first_spike_s: dict[str, float | None] = {
            label: None for label in self.labels
        }
        self.muscle_identity_event_counts = {
            fiber_id: 0
            for fiber_id in self.muscle_identity_projection.mapped_fiber_ids
        }
        self.muscle_identity_first_event_s: dict[str, float | None] = {
            fiber_id: None
            for fiber_id in self.muscle_identity_projection.mapped_fiber_ids
        }

    def __call__(
        self, time_s: float, state: SpatialSensoryState
    ) -> SpatialStimulus:
        expected_time = self.network.step_index * self.network.config.dt_s
        if not isfinite(time_s) or abs(time_s - expected_time) > 1e-9:
            raise ValueError(
                "visual circuit must be stepped once per LIF dt in time order"
            )
        transduction = self.transduction.sample(time_s, state)
        external: dict[int, float] = {}
        class_parameters = self.config["phototransduction"]["classes"]
        for index, item in enumerate(self.neurons):
            neuron_class = item["neuron_class"]
            if neuron_class not in PHOTORECEPTOR_CLASSES:
                continue
            external[index] = (
                transduction.receptor_drive[neuron_class][item["lon_side"]]
                * float(
                    class_parameters[neuron_class][
                        "maximum_external_current_a"
                    ]
                )
            )
        spikes = self.network.step(external)
        spiked_labels = tuple(self.labels[index] for index in spikes)
        for label in spiked_labels:
            self.spike_counts[label] += 1
            if self.first_spike_s[label] is None:
                self.first_spike_s[label] = time_s

        bridge = self.config["a03o_segmental_bridge"]
        decay = exp(-self.network.config.dt_s / float(bridge["activity_tau_s"]))
        a03o_spikes: dict[str, tuple[str, ...]] = {}
        spiked = set(spikes)
        for side in LON_SIDES:
            self.bridge_activity[side] *= decay
            side_spikes = tuple(
                self.labels[index]
                for index in self.a03o_indices[side]
                if index in spiked
            )
            a03o_spikes[side] = side_spikes
            self.bridge_activity[side] += (
                len(side_spikes)
                * float(bridge["spike_increment"])
                * float(bridge["side_activity_gain"][side])
            )
        a1_motor_spikes = {
            side: tuple(
                self.labels[index]
                for index in self.a1_motor_indices[side]
                if index in spiked
            )
            for side in LON_SIDES
        }

        derived_a03o_spikes = {
            channel: tuple(
                self.labels[index] for index in indices if index in spiked
            )
            for channel, indices in self.derived_a03o_indices.items()
        }
        derived_motor_spikes = {
            channel: tuple(
                self.labels[index] for index in indices if index in spiked
            )
            for channel, indices in self.derived_motor_indices.items()
        }
        muscle_source_spikes = tuple(
            node_id
            for node_id in spiked_labels
            if node_id in self.muscle_identity_projection.source_node_ids
        )
        muscle_identity_events = self.muscle_identity_projection.emit(
            muscle_source_spikes,
            lesioned_fiber_ids=self.lesion_muscle_fiber_ids,
        )
        for fiber_id in muscle_identity_events.fiber_events:
            self.muscle_identity_event_counts[fiber_id] += 1
            if self.muscle_identity_first_event_s[fiber_id] is None:
                self.muscle_identity_first_event_s[fiber_id] = time_s

        left_activity = self.bridge_activity["left"]
        right_activity = self.bridge_activity["right"]
        common = (
            float(bridge["common_output_gain"])
            * (left_activity + right_activity)
            / 2.0
        )
        lateral = (
            float(bridge["lateral_difference_gain"])
            * (right_activity - left_activity)
            / 2.0
        )

        def bounded(value: float) -> float:
            return min(1.0, max(0.0, value))

        stimulus = SpatialStimulus(
            bounded(common + lateral),
            bounded(common - lateral),
            bounded(common),
            bounded(common),
        )
        if self.record_frames:
            self.frames.append(
                VisualCircuitFrame(
                    transduction=transduction,
                    spiked_neurons=spiked_labels,
                    a03o_spikes=a03o_spikes,
                    a1_motor_spikes=a1_motor_spikes,
                    derived_a03o_spikes=derived_a03o_spikes,
                    derived_motor_spikes=derived_motor_spikes,
                    muscle_identity_events=muscle_identity_events,
                    bridge_activity=dict(self.bridge_activity),
                    bridge_stimulus=stimulus,
                )
            )
        return stimulus


@dataclass(frozen=True, slots=True)
class VisualClosedLoopResult:
    model_id: str
    status: str
    spatial_result: SpatialClosedLoopResult
    visual_neuron_compartments: int
    identified_descending_neurons: int
    identified_a1_motor_neurons: int
    derived_a03o_homologs: int
    derived_motor_target_channels: int
    anatomy_derived_projection_edges: int
    muscle_atlas_fibers: int
    mapped_muscle_fibers: int
    observed_a1_identity_mappings: int
    derived_a2_a6_identity_mappings: int
    published_connection_pairs: int
    published_synaptic_contacts: int
    published_descending_connection_pairs: int
    published_descending_synaptic_contacts: int
    published_motor_connection_pairs: int
    published_motor_synaptic_contacts: int
    executed_connection_pairs: int
    executed_synaptic_contacts: int
    visual_spike_counts: dict[str, int]
    visual_first_spike_s: dict[str, float | None]
    muscle_identity_event_counts: dict[str, int]
    muscle_identity_first_event_s: dict[str, float | None]
    lesion_node_ids: tuple[str, ...]
    lesion_muscle_fiber_ids: tuple[str, ...]
    visual_frames: tuple[VisualCircuitFrame, ...]

    def to_dict(self) -> dict[str, Any]:
        body = self.spatial_result
        return {
            "model_id": self.model_id,
            "status": self.status,
            "duration_s": body.duration_s,
            "visual_neuron_compartments": self.visual_neuron_compartments,
            "identified_descending_neurons": self.identified_descending_neurons,
            "identified_a1_motor_neurons": self.identified_a1_motor_neurons,
            "derived_a03o_homologs": self.derived_a03o_homologs,
            "derived_motor_target_channels": (
                self.derived_motor_target_channels
            ),
            "anatomy_derived_projection_edges": (
                self.anatomy_derived_projection_edges
            ),
            "muscle_atlas_fibers": self.muscle_atlas_fibers,
            "mapped_muscle_fibers": self.mapped_muscle_fibers,
            "unmapped_muscle_fibers": (
                self.muscle_atlas_fibers - self.mapped_muscle_fibers
            ),
            "observed_a1_identity_mappings": (
                self.observed_a1_identity_mappings
            ),
            "derived_a2_a6_identity_mappings": (
                self.derived_a2_a6_identity_mappings
            ),
            "muscle_identity_events": sum(
                self.muscle_identity_event_counts.values()
            ),
            "recruited_muscle_fibers": sum(
                count > 0 for count in self.muscle_identity_event_counts.values()
            ),
            "activation_dynamics_executed": False,
            "individual_muscle_geometry_executed": False,
            "downstream_spatial_neurons": body.neuron_count,
            "total_neuron_compartments": (
                self.visual_neuron_compartments + body.neuron_count
            ),
            "published_connection_pairs": self.published_connection_pairs,
            "published_synaptic_contacts": self.published_synaptic_contacts,
            "published_descending_connection_pairs": (
                self.published_descending_connection_pairs
            ),
            "published_descending_synaptic_contacts": (
                self.published_descending_synaptic_contacts
            ),
            "published_motor_connection_pairs": (
                self.published_motor_connection_pairs
            ),
            "published_motor_synaptic_contacts": (
                self.published_motor_synaptic_contacts
            ),
            "executed_connection_pairs": self.executed_connection_pairs,
            "executed_synaptic_contacts": self.executed_synaptic_contacts,
            "model_fitted_downstream_synapses": body.synapse_count,
            "displacement_x_um": body.displacement_x_um,
            "displacement_y_um": body.displacement_y_um,
            "displacement_z_um": body.displacement_z_um,
            "yaw_change_deg": body.yaw_change_deg,
            "head_pitch_change_deg": body.head_pitch_change_deg,
            "visual_spikes": sum(self.visual_spike_counts.values()),
            "downstream_spikes": sum(body.spike_counts.values()),
            "lesion_node_ids": list(self.lesion_node_ids),
            "lesion_muscle_fiber_ids": list(self.lesion_muscle_fiber_ids),
            "release_validated": False,
            "claim_boundary": (
                "published L1 LON, pOLP-to-LHN-to-CPf-to-A03o(A1), and "
                "A03o-to-14-A1-motor-identity structural contacts; an "
                "ANATOMY_DERIVED CPf-to-A03o-to-motor-target projection in "
                "A2-A6 with A7 blocked; 146 causal named-fiber identity "
                "event mappings with no activation dynamics or geometry; "
                "fitted effects, phototransduction, and a parallel "
                "A03o-to-body bridge; not validated natural phototaxis or "
                "a complete sensor-to-muscle connectome"
            ),
        }


def validation_light_field(
    config: dict[str, Any] | None = None,
    *,
    lateral_sign: float = 1.0,
) -> LinearScalarField:
    if lateral_sign not in {-1.0, 1.0}:
        raise ValueError("validation lateral sign must be -1 or 1")
    raw = config or load_visual_config()
    item = raw["validation_light_field"]
    gradient = list(map(float, item["gradient_per_m"]))
    gradient[1] *= lateral_sign
    return LinearScalarField(
        modality_id="light",
        unit=item["unit"],
        origin_m=Vec3(*map(float, item["origin_m"])),
        value_at_origin=float(item["value_at_origin"]),
        gradient_per_m=Vec3(*gradient),
        temporal_rate_per_s=float(item["temporal_rate_per_s"]),
        lower_bound=float(item["lower_bound"]),
        upper_bound=float(item["upper_bound"]),
    )


class L1VisualClosedLoopLarva:
    """Compose the explicit L1 LON model with the existing embodied core."""

    def __init__(
        self,
        *,
        field: ScalarField | None = None,
        config: dict[str, Any] | None = None,
        connectome: dict[str, Any] | None = None,
        descending_connectome: dict[str, Any] | None = None,
        motor_connectome: dict[str, Any] | None = None,
        segmental_projection: dict[str, Any] | None = None,
        muscle_identity_projection: NeuralMuscleIdentityProjection | None = None,
        lesion_node_ids: Iterable[str] = (),
        lesion_muscle_fiber_ids: Iterable[str] = (),
        ground_z_m: float | None = None,
        record_visual_frames: bool = False,
    ) -> None:
        self.config = config or load_visual_config()
        self.connectome = connectome or load_visual_connectome()
        self.descending_connectome = (
            descending_connectome or load_visual_descending_connectome()
        )
        self.motor_connectome = motor_connectome or load_a03o_motor_connectome()
        self.segmental_projection = (
            segmental_projection or load_a03o_segmental_projection()
        )
        self.muscle_identity_projection = (
            muscle_identity_projection
            or load_neural_muscle_identity_projection()
        )
        self.protocol = L1VisualCircuitProtocol(
            field or validation_light_field(self.config),
            config=self.config,
            connectome=self.connectome,
            descending_connectome=self.descending_connectome,
            motor_connectome=self.motor_connectome,
            segmental_projection=self.segmental_projection,
            muscle_identity_projection=self.muscle_identity_projection,
            lesion_node_ids=lesion_node_ids,
            lesion_muscle_fiber_ids=lesion_muscle_fiber_ids,
            record_frames=record_visual_frames,
        )
        self.spatial = SpatialClosedLoopLarva(
            ground_z_m=ground_z_m,
            input_labels=BRIDGE_INPUT_LABELS,
            asymmetry_labels=BRIDGE_DIFFERENCE_LABELS,
        )

    def run(
        self,
        *,
        duration_s: float = 4.5,
        record_trajectory_interval_s: float | None = None,
    ) -> VisualClosedLoopResult:
        spatial_result = self.spatial.run(
            stimulus_protocol=self.protocol,
            duration_s=duration_s,
            record_trajectory_interval_s=record_trajectory_interval_s,
        )
        return VisualClosedLoopResult(
            model_id=self.config["model_id"],
            status=self.config["status"],
            spatial_result=spatial_result,
            visual_neuron_compartments=len(self.protocol.neurons),
            identified_descending_neurons=int(
                self.descending_connectome["summary"]["identified_neurons"]
            ),
            identified_a1_motor_neurons=int(
                self.motor_connectome["summary"]["identified_a1_motor_neurons"]
            ),
            derived_a03o_homologs=int(
                self.segmental_projection["summary"]["derived_a03o_homologs"]
            ),
            derived_motor_target_channels=int(
                self.segmental_projection["summary"][
                    "derived_motor_target_channels"
                ]
            ),
            anatomy_derived_projection_edges=(
                self.protocol.executed_segmental_projection_edges
            ),
            muscle_atlas_fibers=len(
                self.muscle_identity_projection.atlas_fiber_ids
            ),
            mapped_muscle_fibers=len(
                self.muscle_identity_projection.mapped_fiber_ids
            ),
            observed_a1_identity_mappings=sum(
                item.mapping_provenance == "MEASURED_PUBLISHED"
                for item in self.muscle_identity_projection.mappings
            ),
            derived_a2_a6_identity_mappings=sum(
                item.mapping_provenance == "ANATOMY_DERIVED"
                for item in self.muscle_identity_projection.mappings
            ),
            published_connection_pairs=(
                int(self.connectome["summary"]["nonzero_connection_pairs"])
                + int(
                    self.descending_connectome["summary"][
                        "axon_to_dendrite_connection_pairs"
                    ]
                )
                + int(
                    self.motor_connectome["summary"][
                        "axon_to_dendrite_connection_pairs"
                    ]
                )
            ),
            published_synaptic_contacts=(
                int(self.connectome["summary"]["within_lon_synaptic_contacts"])
                + int(
                    self.descending_connectome["summary"][
                        "axon_to_dendrite_synaptic_contacts"
                    ]
                )
                + int(
                    self.motor_connectome["summary"][
                        "axon_to_dendrite_synaptic_contacts"
                    ]
                )
            ),
            published_descending_connection_pairs=int(
                self.descending_connectome["summary"][
                    "axon_to_dendrite_connection_pairs"
                ]
            ),
            published_descending_synaptic_contacts=int(
                self.descending_connectome["summary"][
                    "axon_to_dendrite_synaptic_contacts"
                ]
            ),
            published_motor_connection_pairs=int(
                self.motor_connectome["summary"][
                    "axon_to_dendrite_connection_pairs"
                ]
            ),
            published_motor_synaptic_contacts=int(
                self.motor_connectome["summary"][
                    "axon_to_dendrite_synaptic_contacts"
                ]
            ),
            executed_connection_pairs=self.protocol.executed_connection_pairs,
            executed_synaptic_contacts=self.protocol.executed_synaptic_contacts,
            visual_spike_counts=dict(self.protocol.spike_counts),
            visual_first_spike_s=dict(self.protocol.first_spike_s),
            muscle_identity_event_counts=dict(
                self.protocol.muscle_identity_event_counts
            ),
            muscle_identity_first_event_s=dict(
                self.protocol.muscle_identity_first_event_s
            ),
            lesion_node_ids=self.protocol.lesion_node_ids,
            lesion_muscle_fiber_ids=(
                self.protocol.lesion_muscle_fiber_ids
            ),
            visual_frames=tuple(self.protocol.frames),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the provenance-aware L1 visual connectome body loop"
    )
    parser.add_argument("--duration", type=float, default=4.5)
    parser.add_argument("--mirror", action="store_true")
    parser.add_argument("--lesion-class")
    parser.add_argument("--lesion-side", choices=LON_SIDES)
    parser.add_argument("--lesion-muscle-fiber", action="append", default=[])
    args = parser.parse_args(argv)
    config = load_visual_config()
    connectome = load_visual_connectome()
    descending_connectome = load_visual_descending_connectome()
    motor_connectome = load_a03o_motor_connectome()
    segmental_projection = load_a03o_segmental_projection()
    lesions: tuple[str, ...] = ()
    if args.lesion_class:
        lesions = tuple(
            dict.fromkeys(
                item["node_id"]
                for item in (
                    connectome["neurons"]
                    + descending_connectome["neurons"]
                    + motor_connectome["neurons"]
                    + segmental_projection["a03o_homologs"]
                    + segmental_projection["motor_target_channels"]
                )
                if item["neuron_class"] == args.lesion_class
                and (
                    args.lesion_side is None
                    or item.get("lon_side", item.get("side"))
                    == args.lesion_side
                )
            )
        )
        if not lesions:
            raise ValueError(
                f"visual neuron class {args.lesion_class!r} is absent"
            )
    result = L1VisualClosedLoopLarva(
        field=validation_light_field(
            config, lateral_sign=-1.0 if args.mirror else 1.0
        ),
        config=config,
        connectome=connectome,
        descending_connectome=descending_connectome,
        motor_connectome=motor_connectome,
        segmental_projection=segmental_projection,
        lesion_node_ids=lesions,
        lesion_muscle_fiber_ids=tuple(args.lesion_muscle_fiber),
    ).run(duration_s=args.duration)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
