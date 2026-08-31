import hashlib
import inspect
from pathlib import Path

import pytest

from oraclarva.body3d import Vec3
from oraclarva.environment_inputs import LinearScalarField
from oraclarva.spatial import SpatialSensoryState
from oraclarva.visual import (
    BRIDGE_INPUT_LABELS,
    L1VisualCircuitProtocol,
    L1VisualClosedLoopLarva,
    PHOTORECEPTOR_CLASSES,
    BolwigLightTransduction,
    load_visual_config,
    load_visual_connectome,
    load_visual_descending_connectome,
    load_a03o_motor_connectome,
    load_a03o_segmental_projection,
    validation_light_field,
    visual_node_ids_for_class,
)


def fixed_state() -> SpatialSensoryState:
    return SpatialSensoryState(
        left_head_position_m=Vec3(0.0, -100e-6, 0.0),
        right_head_position_m=Vec3(0.0, 100e-6, 0.0),
        dorsal_head_position_m=Vec3(0.0, 0.0, 100e-6),
        ventral_head_position_m=Vec3(0.0, 0.0, -100e-6),
    )


def test_visual_config_preserves_measured_and_fitted_boundaries():
    config = load_visual_config()
    assert config["stage"] == "L1"
    assert config["status"] == "research_approximation"
    assert config["connectome"]["provenance"] == "MEASURED_PUBLISHED"
    assert config["descending_connectome"]["provenance"] == "MEASURED_PUBLISHED"
    assert config["a03o_motor_connectome"]["provenance"] == "MEASURED_PUBLISHED"
    projection = config["a03o_segmental_projection"]
    assert projection["provenance"] == "ANATOMY_DERIVED"
    assert projection["blocked_segments"] == ["A7"]
    assert config["phototransduction"]["provenance"] == "MODEL_FITTED"
    assert config["lon_dynamics"]["effect_provenance"] == "MODEL_FITTED"
    assert config["descending_path_dynamics"]["effect_provenance"] == "MODEL_FITTED"
    assert config["a03o_motor_path_dynamics"]["effect_provenance"] == "MODEL_FITTED"
    assert (
        config["a03o_segmental_projection_dynamics"]["provenance"]
        == "MODEL_FITTED"
    )
    bridge = config["a03o_segmental_bridge"]
    assert bridge["provenance"] == "MODEL_FITTED"
    assert bridge["readout_class"] == "A03o_A1"
    assert bridge["readout_segment"] == "A1"
    assert bridge["direct_dorsoventral_difference_gain"] == 0.0
    assert config["release_validated"] is False


def test_compiled_lon_preserves_published_matrix_counts_and_unknown_signs():
    connectome = load_visual_connectome()
    summary = connectome["summary"]
    assert summary["side_scoped_matrix_entries"] == 60
    assert summary["nonzero_connection_pairs"] == 422
    assert summary["within_lon_synaptic_contacts"] == 3297
    assert summary["by_lon_side"]["left"] == {
        "matrix_entries": 28,
        "photoreceptors": 13,
        "nonzero_connection_pairs": 197,
        "synaptic_contacts": 1499,
    }
    assert summary["by_lon_side"]["right"] == {
        "matrix_entries": 32,
        "photoreceptors": 16,
        "nonzero_connection_pairs": 225,
        "synaptic_contacts": 1798,
    }
    assert len(visual_node_ids_for_class(connectome, "Rh5-PR", lon_side="left")) == 4
    assert len(visual_node_ids_for_class(connectome, "Rh5-PR", lon_side="right")) == 6
    assert all(item["synaptic_effect"] is None for item in connectome["neurons"])
    contacts = {
        (item["pre"], item["post"]): item["synaptic_contacts"]
        for item in connectome["connections"]
    }
    assert contacts[("left:Rh6-PR_1", "left:cha-lOLP")] == 31
    assert contacts[("left:Rh6-PR_1", "left:glu-lOLP")] == 25


def test_compiled_descending_path_preserves_vfb_identities_and_contacts():
    path = load_visual_descending_connectome()
    assert path["summary"] == {
        "bilateral_pairs": 5,
        "identified_neurons": 10,
        "new_runtime_compartments": 6,
        "axon_to_dendrite_connection_pairs": 8,
        "axon_to_dendrite_synaptic_contacts": 98,
    }
    by_id = {item["node_id"]: item for item in path["neurons"]}
    assert by_id["left:pOLP"]["catmaid_skeleton_id"] == 9940382
    assert by_id["right:PVL09"]["vfb_id"] == "VFB_00100584"
    assert by_id["left:CPf_DN"]["flybase_type_id"] == "FBbt_00049517"
    assert by_id["right:A03o_A1"]["catmaid_skeleton_id"] == 3180525
    contacts = {
        (item["pre"], item["post"]): item["synaptic_contacts"]
        for item in path["connections"]
    }
    assert contacts[("left:pOLP", "left:down_PVL09_PN-OLP")] == 33
    assert contacts[("right:pOLP", "right:down_PVL09_PN-OLP")] == 25
    assert contacts[("left:PVL09", "left:down_PVL09_PN-OLP")] == 12
    assert contacts[("right:PVL09", "right:down_PVL09_PN-OLP")] == 8
    assert contacts[("left:down_PVL09_PN-OLP", "left:CPf_DN")] == 4
    assert contacts[("right:down_PVL09_PN-OLP", "right:CPf_DN")] == 3
    assert contacts[("left:CPf_DN", "left:A03o_A1")] == 2
    assert contacts[("right:CPf_DN", "right:A03o_A1")] == 11
    assert all(
        item["connection_compartment"] == "axon_to_dendrite"
        and item["confidence"] == 5
        and item["physiological_effect"] is None
        for item in path["connections"]
    )


def test_compiled_a03o_motor_path_preserves_sparse_asymmetric_contacts():
    path = load_a03o_motor_connectome()
    assert path["summary"] == {
        "queried_a03o_neurons": 2,
        "identified_a1_motor_neurons": 14,
        "a1_motor_map_denominator": 56,
        "axon_to_dendrite_connection_pairs": 15,
        "axon_to_dendrite_synaptic_contacts": 26,
        "unique_target_muscle_numbers": 13,
        "motor_neurons_by_side": {"left": 6, "right": 8},
        "motor_neurons_by_spatial_group": {"DL": 5, "DO": 5, "T": 4},
    }
    by_id = {item["node_id"]: item for item in path["neurons"]}
    assert by_id["motor_identity:4488976:right"]["vfb_id"] == "VFB_00101465"
    assert by_id["motor_identity:10649843:left"]["target_muscles"] == [
        {"number": "1", "synonym": "DA1", "evidence": "listed"}
    ]
    contacts = {
        (item["pre"], item["post"]): item["synaptic_contacts"]
        for item in path["connections"]
    }
    assert contacts[
        ("right:A03o_A1", "motor_identity:4488976:right")
    ] == 4
    assert contacts[
        ("left:A03o_A1", "motor_identity:14085813:left")
    ] == 2
    assert contacts[
        ("right:A03o_A1", "motor_identity:14085813:left")
    ] == 1
    assert all(
        item["connection_compartment"] == "axon_to_dendrite"
        and item["confidence"] == 5
        and item["physiological_effect"] is None
        for item in path["connections"]
    )


def test_a03o_segmental_projection_is_derived_and_blocks_a7():
    projection = load_a03o_segmental_projection()
    assert projection["summary"] == {
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
    assert projection["projection_scope"]["derived_segments"] == [
        "A2",
        "A3",
        "A4",
        "A5",
        "A6",
    ]
    assert projection["projection_scope"]["blocked_segments"] == ["A7"]
    assert all(
        item["catmaid_skeleton_id"] is None
        and item["provenance"] == "ANATOMY_DERIVED"
        for item in projection["a03o_homologs"]
        + projection["motor_target_channels"]
    )
    assert all(
        item["synaptic_contacts"] is None
        and item["provenance"] == "ANATOMY_DERIVED"
        for item in projection["connections"]
    )
    assert not any(
        item.get("segment") == "A7"
        for item in projection["a03o_homologs"]
        + projection["motor_target_channels"]
    )


@pytest.mark.parametrize(
    "loader",
    [
        load_visual_connectome,
        load_visual_descending_connectome,
        load_a03o_motor_connectome,
        load_a03o_segmental_projection,
    ],
)
def test_bundled_source_data_matches_audited_sha256(loader):
    graph = loader()
    artifact = graph["source"]["local_artifact"]
    digest = hashlib.sha256(Path(artifact).read_bytes()).hexdigest()
    assert digest == graph["source"]["sha256"]


def test_bolwig_transduction_uses_only_two_bilateral_samples():
    field = LinearScalarField(
        modality_id="light",
        unit="W_m-2",
        origin_m=Vec3(0.0, 0.0, 0.0),
        value_at_origin=4.0,
        gradient_per_m=Vec3(0.0, 0.0, 6000.0),
        lower_bound=0.0,
        upper_bound=20.0,
    )
    frame = BolwigLightTransduction(field, load_visual_config()).sample(
        0.0, fixed_state()
    )
    assert set(frame.sample_positions_m) == {"left", "right"}
    assert frame.irradiance_w_m2["left"] == frame.irradiance_w_m2["right"]
    for neuron_class in PHOTORECEPTOR_CLASSES:
        assert (
            frame.receptor_drive[neuron_class]["left"]
            == frame.receptor_drive[neuron_class]["right"]
        )


def test_published_contacts_execute_without_relabeling_effects_as_measured():
    protocol = L1VisualCircuitProtocol(validation_light_field())
    assert protocol.network.neuron_count == 220
    assert protocol.executed_lon_connection_pairs == 368
    assert protocol.executed_lon_synaptic_contacts == 3035
    assert protocol.executed_descending_connection_pairs == 8
    assert protocol.executed_descending_synaptic_contacts == 98
    assert protocol.executed_motor_connection_pairs == 15
    assert protocol.executed_motor_synaptic_contacts == 26
    assert protocol.executed_segmental_projection_edges == 140
    assert protocol.executed_connection_pairs == 531
    assert protocol.executed_synaptic_contacts == 3159


def test_causal_trace_forks_after_a03o_to_motor_identities_and_fitted_body():
    result = L1VisualClosedLoopLarva(record_visual_frames=True).run(
        duration_s=0.3
    )
    connectome = load_visual_connectome()
    photoreceptors = sum(
        (
            visual_node_ids_for_class(connectome, neuron_class)
            for neuron_class in PHOTORECEPTOR_CLASSES
        ),
        (),
    )
    first = result.visual_first_spike_s
    first_pr = min(first[item] for item in photoreceptors if first[item] is not None)
    first_vpn = min(
        first[item]
        for item in ("right:PVL09", "right:pOLP")
        if first[item] is not None
    )
    first_lhn = first["right:down_PVL09_PN-OLP"]
    first_dn = first["right:CPf_DN"]
    first_a03o = first["right:A03o_A1"]
    first_a1_motor = min(
        value
        for label, value in first.items()
        if label.startswith("motor_identity:") and value is not None
    )
    body = result.spatial_result
    first_bridge = min(
        body.first_spike_s[item]
        for item in BRIDGE_INPUT_LABELS
        if body.first_spike_s[item] is not None
    )
    first_premotor = min(
        value
        for label, value in body.first_spike_s.items()
        if label.startswith("premotor_A27h_like:A7") and value is not None
    )
    first_motor = min(
        value
        for label, value in body.first_spike_s.items()
        if label.startswith("motor_pool:A7") and value is not None
    )
    assert first_pr < first_vpn < first_lhn < first_dn < first_a03o
    first_derived_a03o = min(
        value
        for label, value in first.items()
        if label.startswith("derived:") and value is not None
    )
    first_derived_motor = min(
        value
        for label, value in first.items()
        if label.startswith("derived_motor_target:") and value is not None
    )
    assert first_a03o < first_a1_motor
    assert first_dn < first_derived_a03o < first_derived_motor
    assert first_a03o < first_bridge < first_premotor < first_motor
    assert not any(
        label.startswith("environment_receptor") for label in body.spike_counts
    )


def test_lesions_break_each_expected_downstream_stage_without_fallback_action():
    connectome = load_visual_connectome()
    all_photoreceptors = sum(
        (
            visual_node_ids_for_class(connectome, neuron_class)
            for neuron_class in PHOTORECEPTOR_CLASSES
        ),
        (),
    )
    photoreceptor_lesion = L1VisualClosedLoopLarva(
        lesion_node_ids=all_photoreceptors
    ).run(duration_s=0.3)
    assert sum(photoreceptor_lesion.visual_spike_counts.values()) == 0
    assert sum(photoreceptor_lesion.spatial_result.spike_counts.values()) == 0

    stages = (
        (
            ("left:PVL09", "right:PVL09", "left:pOLP", "right:pOLP"),
            ("left:down_PVL09_PN-OLP", "right:down_PVL09_PN-OLP"),
        ),
        (
            ("left:down_PVL09_PN-OLP", "right:down_PVL09_PN-OLP"),
            ("left:CPf_DN", "right:CPf_DN"),
        ),
        (("left:CPf_DN", "right:CPf_DN"), ("left:A03o_A1", "right:A03o_A1")),
        (("left:A03o_A1", "right:A03o_A1"), ()),
    )
    for lesions, downstream in stages:
        result = L1VisualClosedLoopLarva(lesion_node_ids=lesions).run(
            duration_s=0.3
        )
        assert sum(result.visual_spike_counts.values()) > 0
        assert all(result.visual_spike_counts[item] == 0 for item in downstream)
        assert sum(result.spatial_result.spike_counts.values()) == 0
        assert result.spatial_result.displacement_y_um == pytest.approx(0.0)




def test_a1_motor_identity_lesion_blocks_only_observed_diagnostic_branch():
    motor_nodes = tuple(
        item["node_id"] for item in load_a03o_motor_connectome()["neurons"]
    )
    result = L1VisualClosedLoopLarva(
        lesion_node_ids=motor_nodes
    ).run(duration_s=0.3)
    assert all(result.visual_spike_counts[item] == 0 for item in motor_nodes)
    assert result.visual_spike_counts["right:A03o_A1"] > 0
    assert sum(result.spatial_result.spike_counts.values()) > 0
    assert result.spatial_result.displacement_y_um != pytest.approx(0.0)



def test_segment_specific_derived_a03o_lesion_is_local_to_proxy_branch():
    lesioned = "derived:right:A03o_A4"
    result = L1VisualClosedLoopLarva(
        lesion_node_ids=(lesioned,)
    ).run(duration_s=0.3)
    assert result.visual_spike_counts[lesioned] == 0
    assert all(
        count == 0
        for label, count in result.visual_spike_counts.items()
        if label.startswith("derived_motor_target:A4:right:")
    )
    for segment in ("A2", "A3", "A5", "A6"):
        assert result.visual_spike_counts[f"derived:right:A03o_{segment}"] > 0
        assert any(
            count > 0
            for label, count in result.visual_spike_counts.items()
            if label.startswith(
                f"derived_motor_target:{segment}:right:"
            )
        )
    assert sum(result.spatial_result.spike_counts.values()) > 0
    assert result.spatial_result.displacement_y_um != pytest.approx(0.0)


def test_mirrored_bilateral_light_fields_reverse_steering_with_specimen_asymmetry():
    negative = L1VisualClosedLoopLarva(
        field=validation_light_field(lateral_sign=-1.0)
    ).run(duration_s=0.3).spatial_result
    positive = L1VisualClosedLoopLarva(
        field=validation_light_field(lateral_sign=1.0)
    ).run(duration_s=0.3).spatial_result

    assert positive.displacement_y_um < 0.0 < negative.displacement_y_um
    assert positive.yaw_change_deg > 0.0 > negative.yaw_change_deg
    assert abs(positive.displacement_y_um) != pytest.approx(
        abs(negative.displacement_y_um)
    )


def test_visual_path_exposes_no_movement_or_behavior_commands():
    source = (
        inspect.getsource(BolwigLightTransduction)
        + inspect.getsource(L1VisualCircuitProtocol)
    ).lower()
    forbidden = (
        "turn_left",
        "turn_right",
        "pitch_up",
        "pitch_down",
        "crawl(",
        "move_3d",
        "behavior_tree",
        "target_selector",
        "policy_network",
        "fsm",
    )
    assert all(token not in source for token in forbidden)
