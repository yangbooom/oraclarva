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
    assert config["phototransduction"]["provenance"] == "MODEL_FITTED"
    assert config["lon_dynamics"]["effect_provenance"] == "MODEL_FITTED"
    assert config["descending_bridge"]["provenance"] == "MODEL_FITTED"
    assert (
        config["descending_bridge"]["direct_dorsoventral_difference_gain"]
        == 0.0
    )
    assert config["release_validated"] is False


def test_compiled_connectome_preserves_published_matrix_counts_and_unknown_signs():
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
    assert len(visual_node_ids_for_class(connectome, "Rh6-PR", lon_side="left")) == 9
    assert len(visual_node_ids_for_class(connectome, "Rh6-PR", lon_side="right")) == 10
    assert all(item["synaptic_effect"] is None for item in connectome["neurons"])
    contacts = {
        (item["pre"], item["post"]): item["synaptic_contacts"]
        for item in connectome["connections"]
    }
    assert contacts[("left:Rh6-PR_1", "left:cha-lOLP")] == 31
    assert contacts[("left:Rh6-PR_1", "left:glu-lOLP")] == 25


def test_bundled_source_data_matches_audited_sha256():
    connectome = load_visual_connectome()
    artifact = connectome["source"]["local_artifact"]
    digest = hashlib.sha256(Path(artifact).read_bytes()).hexdigest()
    assert digest == connectome["source"]["sha256"]


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


def test_published_contacts_execute_without_relabeling_them_as_measured_effects():
    protocol = L1VisualCircuitProtocol(validation_light_field())
    assert protocol.network.neuron_count == 60
    assert protocol.executed_connection_pairs == 368
    assert protocol.executed_synaptic_contacts == 3035
    assert protocol.executed_synaptic_contacts < 3297
    assert set(protocol.config["lon_dynamics"]["unexecuted_presynaptic_classes"]) == {
        "SP2-1",
        "sVUM2",
        "Pdf-LaN",
    }


def test_causal_trace_runs_from_photoreceptor_through_vpn_bridge_and_motor():
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
    readouts = sum(
        (
            visual_node_ids_for_class(connectome, neuron_class)
            for neuron_class in (
                "VPLN",
                "nc-LaN",
                "5th-LaN",
                "PVL09",
                "pOLP",
            )
        ),
        (),
    )
    first_pr = min(
        result.visual_first_spike_s[item]
        for item in photoreceptors
        if result.visual_first_spike_s[item] is not None
    )
    first_vpn = min(
        result.visual_first_spike_s[item]
        for item in readouts
        if result.visual_first_spike_s[item] is not None
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
    assert first_pr < first_vpn < first_bridge < first_premotor < first_motor
    assert not any(
        label.startswith("environment_receptor") for label in body.spike_counts
    )


def test_photoreceptor_and_vpn_lesions_break_the_expected_downstream_stage():
    connectome = load_visual_connectome()
    all_photoreceptors = sum(
        (
            visual_node_ids_for_class(connectome, neuron_class)
            for neuron_class in PHOTORECEPTOR_CLASSES
        ),
        (),
    )
    all_readouts = sum(
        (
            visual_node_ids_for_class(connectome, neuron_class)
            for neuron_class in (
                "VPLN",
                "nc-LaN",
                "5th-LaN",
                "PVL09",
                "pOLP",
            )
        ),
        (),
    )
    photoreceptor_lesion = L1VisualClosedLoopLarva(
        lesion_node_ids=all_photoreceptors
    ).run(duration_s=0.3)
    vpn_lesion = L1VisualClosedLoopLarva(
        lesion_node_ids=all_readouts
    ).run(duration_s=0.3)

    assert sum(photoreceptor_lesion.visual_spike_counts.values()) == 0
    assert sum(photoreceptor_lesion.spatial_result.spike_counts.values()) == 0
    assert photoreceptor_lesion.spatial_result.displacement_y_um == pytest.approx(0.0)
    assert sum(vpn_lesion.visual_spike_counts.values()) > 0
    assert sum(vpn_lesion.spatial_result.spike_counts.values()) == 0
    assert vpn_lesion.spatial_result.displacement_y_um == pytest.approx(0.0)


def test_mirrored_bilateral_light_fields_reverse_steering_without_exact_symmetry_claim():
    negative = L1VisualClosedLoopLarva(
        field=validation_light_field(lateral_sign=-1.0)
    ).run(duration_s=0.3).spatial_result
    positive = L1VisualClosedLoopLarva(
        field=validation_light_field(lateral_sign=1.0)
    ).run(duration_s=0.3).spatial_result

    assert positive.displacement_y_um < 0.0 < negative.displacement_y_um
    assert positive.yaw_change_deg > 0.0 > negative.yaw_change_deg
    assert abs(abs(negative.displacement_y_um) - abs(positive.displacement_y_um)) < 0.2
    assert abs(abs(negative.yaw_change_deg) - abs(positive.yaw_change_deg)) < 0.05


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
