"""Generate deterministic trajectories for the L1 visual-connectome loop."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from oraclarva.artifacts import NUMERIC_TOLERANCE, first_mismatch
from oraclarva.body3d import Vec3
from oraclarva.environment_inputs import LinearScalarField
from oraclarva.visual import (
    L1VisualClosedLoopLarva,
    PHOTORECEPTOR_CLASSES,
    load_a03o_motor_connectome,
    load_a03o_segmental_projection,
    load_l1_dbd_motor_feedback,
    load_visual_config,
    load_visual_connectome,
    load_visual_descending_connectome,
    validation_light_field,
    visual_node_ids_for_class,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "data" / "trajectories" / "l1_visual_closed_loop_v0.json"
)
SAMPLE_INTERVAL_S = 0.03
DT_S = 0.001
DURATION_S = 1.5
PROJECTION_CLASSES = ("PVL09", "pOLP")


def _earliest(values: list[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return None if not available else round(min(available), 9)



def _first_spike_trace(result, connectome) -> dict[str, float | None]:
    visual = result.visual_first_spike_s
    photoreceptors = sum(
        (
            visual_node_ids_for_class(connectome, neuron_class)
            for neuron_class in PHOTORECEPTOR_CLASSES
        ),
        (),
    )
    local_classes = ("cha-lOLP", "glu-lOLP", "extra-glu-lOLP")
    local = sum(
        (visual_node_ids_for_class(connectome, item) for item in local_classes),
        (),
    )
    return {
        "photoreceptor": _earliest([visual[item] for item in photoreceptors]),
        "local_interneuron": _earliest([visual[item] for item in local]),
        "visual_projection": _earliest(
            [
                visual[item]
                for item in (
                    "left:PVL09",
                    "right:PVL09",
                    "left:pOLP",
                    "right:pOLP",
                )
            ]
        ),
        "lateral_horn_neuron": _earliest(
            [
                visual["left:down_PVL09_PN-OLP"],
                visual["right:down_PVL09_PN-OLP"],
            ]
        ),
        "cpf_descending_neuron": _earliest(
            [visual["left:CPf_DN"], visual["right:CPf_DN"]]
        ),
        "a03o_a1_premotor": _earliest(
            [visual["left:A03o_A1"], visual["right:A03o_A1"]]
        ),
        "a1_motor_identity": _earliest(
            [
                value
                for label, value in visual.items()
                if label.startswith("motor_identity:")
            ]
        ),
        "a03o_a2_a6_derived": _earliest(
            [
                value
                for label, value in visual.items()
                if label.startswith("derived:")
            ]
        ),
        "a2_a6_motor_target_derived": _earliest(
            [
                value
                for label, value in visual.items()
                if label.startswith("derived_motor_target:")
            ]
        ),
        "named_muscle_identity_event": _earliest(
            list(result.muscle_identity_first_event_s.values())
        ),
        "named_muscle_activation": _earliest(
            list(result.muscle_first_activation_s.values())
        ),
        "body_state_dbd": _earliest(
            [
                frame.time_s if frame.maximum_dbd_drive > 0.0 else None
                for frame in result.body_sensory_frames
            ]
        ),
        "dbd_spike": _earliest(
            [
                value
                for label, value in visual.items()
                if label.startswith("proprioceptor:dbd:")
            ]
        ),
        "named_attachment_force": _earliest(
            [
                frame.time_s if frame.active_fiber_count else None
                for frame in result.body_force_frames
            ]
        ),
        "parallel_fitted_body_bridge": None,
        "a7_named_attachment_force": None,
    }

def _visual_frame_index(trajectory_index: int) -> int:
    if trajectory_index == 0:
        return 0
    return round(trajectory_index * SAMPLE_INTERVAL_S / DT_S) - 1


def _window_spike_counts(protocol, frame_index: int) -> dict[str, int]:
    first = max(0, frame_index - round(SAMPLE_INTERVAL_S / DT_S) + 1)
    groups = (
        "Rh5-PR",
        "Rh6-PR",
        "local",
        "projection",
        "lhn",
        "dn",
        "a03o",
        "a1_mn",
        "derived_a03o",
        "derived_mn",
        "dbd",
    )
    counts = {
        f"{side}:{group}": 0
        for side in ("left", "right")
        for group in groups
    }
    for frame in protocol.frames[first : frame_index + 1]:
        for node_id in frame.spiked_neurons:
            metadata = protocol.metadata_by_id[node_id]
            side = metadata["lon_side"]
            neuron_class = metadata["neuron_class"]
            if neuron_class in PHOTORECEPTOR_CLASSES:
                group = neuron_class
            elif neuron_class in {"cha-lOLP", "glu-lOLP", "extra-glu-lOLP"}:
                group = "local"
            elif neuron_class in PROJECTION_CLASSES:
                group = "projection"
            elif neuron_class == "down_PVL09_PN-OLP":
                group = "lhn"
            elif neuron_class == "CPf_DN":
                group = "dn"
            elif neuron_class == "A03o_A1":
                group = "a03o"
            elif neuron_class == "A1_motor_identity":
                group = "a1_mn"
            elif neuron_class == "A03o_homolog_proxy":
                group = "derived_a03o"
            elif neuron_class == "segmental_motor_target_proxy":
                group = "derived_mn"
            elif neuron_class == "dbd_A1":
                group = "dbd"
            else:
                continue
            counts[f"{side}:{group}"] += 1
    return counts



def _sampled_visual(
    protocol,
    force_frames,
    trajectory_index: int,
) -> dict[str, Any]:
    frame_index = _visual_frame_index(trajectory_index)
    frame = protocol.frames[frame_index]
    force_frame = force_frames[frame_index]
    transduction = frame.transduction
    first = max(0, frame_index - round(SAMPLE_INTERVAL_S / DT_S) + 1)
    event_frames = protocol.frames[first : frame_index + 1]
    event_counts = {
        "left": 0,
        "right": 0,
        "MEASURED_PUBLISHED": 0,
        "ANATOMY_DERIVED": 0,
    }
    active_fibers: set[str] = set()
    for event_frame in event_frames:
        events = event_frame.muscle_identity_events
        for fiber_id in events.fiber_events:
            event_counts[fiber_id.split(":", 2)[1]] += 1
            event_counts[events.mapping_provenance_by_fiber[fiber_id]] += 1
            active_fibers.add(fiber_id)
    activation_by_side = {"left": [], "right": []}
    for fiber_id, value in frame.muscle_activation.activations.items():
        activation_by_side[fiber_id.split(":", 2)[1]].append(value)
    tensions = [
        item.total_tension_model_units
        for item in force_frame.fibers.values()
    ]
    tension_by_side = {
        side: sum(
            item.total_tension_model_units
            for fiber_id, item in force_frame.fibers.items()
            if fiber_id.split(":", 2)[1] == side
        )
        for side in ("left", "right")
    }
    return {
        "sample_time_s": round(transduction.time_s, 9),
        "sample_positions_um": {
            side: [
                round(position.x * 1e6, 9),
                round(position.y * 1e6, 9),
                round(position.z * 1e6, 9),
            ]
            for side, position in transduction.sample_positions_m.items()
        },
        "irradiance_w_m2": {
            side: round(value, 9)
            for side, value in transduction.irradiance_w_m2.items()
        },
        "adapted_irradiance_w_m2": {
            side: round(value, 9)
            for side, value in transduction.adapted_irradiance_w_m2.items()
        },
        "receptor_drive": {
            neuron_class: {
                side: round(value, 9) for side, value in values.items()
            }
            for neuron_class, values in transduction.receptor_drive.items()
        },
        "body_state_feedback": {
            "a1_strain": round(frame.body_state_sensory.segments["A1"].strain, 9),
            "dbd_drive": {
                side: round(
                    frame.body_state_sensory.dbd_channels[f"A1:{side}"].drive_0_1,
                    9,
                )
                for side in ("left", "right")
            },
            "a1_contact": frame.body_state_sensory.segments["A1"].contact,
            "contact_neural_path_executed": False,
        },
        "spike_counts_in_window": _window_spike_counts(protocol, frame_index),
        "muscle_identity_events_in_window": event_counts,
        "active_mapped_fibers_in_window": len(active_fibers),
        "muscle_activation": {
            side: {
                "mean": round(sum(values) / len(values), 9),
                "maximum": round(max(values, default=0.0), 9),
                "active_fibers": sum(value > 0.0 for value in values),
            }
            for side, values in activation_by_side.items()
        },
        "applied_activation_events": len(
            frame.muscle_activation.applied_event_fibers
        ),
        "attachment_force": {
            "unit": force_frame.force_unit,
            "active_fibers": force_frame.active_fiber_count,
            "traced_active_fibers": force_frame.traced_active_fiber_count,
            "feedback_driven_fibers": force_frame.feedback_driven_fiber_count,
            "feedback_traced_fibers": force_frame.feedback_traced_fiber_count,
            "total_tension_model_units": round(sum(tensions), 9),
            "tension_model_units_by_side": {
                side: round(value, 9)
                for side, value in tension_by_side.items()
            },
            "peak_fiber_tension_model_units": round(max(tensions, default=0.0), 9),
            "peak_node_force_model_units": round(
                max(
                    (
                        value.norm()
                        for value in force_frame.node_forces_model_units.values()
                    ),
                    default=0.0,
                ),
                9,
            ),
            "parallel_fitted_bridge_executed": (
                force_frame.parallel_fitted_bridge_executed
            ),
        },
    }


def _summary(result) -> dict[str, Any]:
    body = result.spatial_result
    force_frames = result.body_force_frames
    return {
        "visual_neuron_compartments": result.visual_neuron_compartments,
        "identified_descending_neurons": result.identified_descending_neurons,
        "identified_a1_motor_neurons": result.identified_a1_motor_neurons,
        "derived_a03o_homologs": result.derived_a03o_homologs,
        "derived_motor_target_channels": result.derived_motor_target_channels,
        "anatomy_derived_projection_edges": result.anatomy_derived_projection_edges,
        "muscle_atlas_fibers": result.muscle_atlas_fibers,
        "mapped_muscle_fibers": result.mapped_muscle_fibers,
        "unmapped_muscle_fibers": (
            result.muscle_atlas_fibers - result.mapped_muscle_fibers
        ),
        "observed_a1_identity_mappings": result.observed_a1_identity_mappings,
        "derived_a2_a6_identity_mappings": result.derived_a2_a6_identity_mappings,
        "muscle_identity_events": sum(
            result.muscle_identity_event_counts.values()
        ),
        "recruited_mapped_fibers": sum(
            count > 0 for count in result.muscle_identity_event_counts.values()
        ),
        "activation_dynamics_executed": True,
        "activation_parameter_provenance": "MODEL_FITTED",
        "activation_input_events": sum(
            result.muscle_activation_input_counts.values()
        ),
        "activated_muscle_fibers": sum(
            value is not None for value in result.muscle_first_activation_s.values()
        ),
        "maximum_muscle_activation": round(
            max(result.muscle_peak_activations.values(), default=0.0), 9
        ),
        "minimum_spike_to_activation_delay_steps": 1,
        "individual_muscle_geometry_executed": True,
        "geometry_provenance": "ANATOMY_DERIVED",
        "mechanical_force_executed": True,
        "mechanics_provenance": "MODEL_FITTED",
        "body_force_unit": "model_unit_not_newton",
        "body_force_frames": len(force_frames),
        "body_sensory_frames": len(result.body_sensory_frames),
        "published_body_feedback_connection_pairs": (
            result.published_body_feedback_connection_pairs
        ),
        "published_body_feedback_synaptic_contacts": (
            result.published_body_feedback_synaptic_contacts
        ),
        "executed_body_feedback_connection_pairs": (
            result.executed_body_feedback_connection_pairs
        ),
        "executed_body_feedback_synaptic_contacts": (
            result.executed_body_feedback_synaptic_contacts
        ),
        "peak_dbd_drive": round(
            max((frame.maximum_dbd_drive for frame in result.body_sensory_frames), default=0.0),
            9,
        ),
        "peak_active_body_force_fibers": max(
            (frame.active_fiber_count for frame in force_frames),
            default=0,
        ),
        "all_active_body_forces_traced": all(
            frame.active_fiber_count == frame.traced_active_fiber_count
            for frame in force_frames
        ),
        "feedback_driven_force_frames": sum(
            frame.feedback_driven_fiber_count > 0 for frame in force_frames
        ),
        "all_feedback_forces_traced": all(
            frame.feedback_driven_fiber_count == frame.feedback_traced_fiber_count
            for frame in force_frames
        ),
        "parallel_fitted_bridge_executed": False,
        "published_connection_pairs": result.published_connection_pairs,
        "published_descending_connection_pairs": (
            result.published_descending_connection_pairs
        ),
        "published_synaptic_contacts": result.published_synaptic_contacts,
        "published_descending_synaptic_contacts": (
            result.published_descending_synaptic_contacts
        ),
        "published_motor_connection_pairs": result.published_motor_connection_pairs,
        "published_motor_synaptic_contacts": result.published_motor_synaptic_contacts,
        "executed_connection_pairs": result.executed_connection_pairs,
        "executed_synaptic_contacts": result.executed_synaptic_contacts,
        "generic_downstream_spatial_neurons": body.neuron_count,
        "generic_downstream_spatial_synapses": body.synapse_count,
        "visual_spikes": sum(result.visual_spike_counts.values()),
        "generic_downstream_spikes": sum(body.spike_counts.values()),
        "displacement_x_um": round(body.displacement_x_um, 9),
        "displacement_y_um": round(body.displacement_y_um, 9),
        "displacement_z_um": round(body.displacement_z_um, 9),
        "yaw_change_deg": round(body.yaw_change_deg, 9),
        "head_pitch_change_deg": round(body.head_pitch_change_deg, 9),
    }

def render_trajectory() -> str:
    config = load_visual_config()
    connectome = load_visual_connectome()
    descending_connectome = load_visual_descending_connectome()
    motor_connectome = load_a03o_motor_connectome()
    segmental_projection = load_a03o_segmental_projection()
    body_feedback_connectome = load_l1_dbd_motor_feedback()
    scenario_specs = (
        ("brighter_right_intact", 1.0, False),
        ("brighter_left_intact", -1.0, False),
        ("zero_light_a1_stretch_feedback", 0.0, True),
    )
    scenarios = []
    for scenario_id, lateral_sign, stretch_perturbation in scenario_specs:
        field = (
            LinearScalarField(
                modality_id="light",
                unit="W_m-2",
                origin_m=Vec3(0.0, 0.0, 0.0),
                value_at_origin=0.0,
                gradient_per_m=Vec3(0.0, 0.0, 0.0),
                lower_bound=0.0,
                upper_bound=0.0,
            )
            if stretch_perturbation
            else validation_light_field(config, lateral_sign=lateral_sign)
        )
        organism = L1VisualClosedLoopLarva(
            field=field,
            config=config,
            connectome=connectome,
            descending_connectome=descending_connectome,
            motor_connectome=motor_connectome,
            segmental_projection=segmental_projection,
            body_feedback_connectome=body_feedback_connectome,
            lesion_node_ids=(),
            lesion_muscle_fiber_ids=(),
            ground_z_m=None,
            record_visual_frames=True,
        )
        if stretch_perturbation:
            index = next(
                i for i, segment in enumerate(organism.spatial.body.geometry)
                if segment.id == "A1"
            )
            particle = organism.spatial.body.particles[index + 1]
            particle.position = Vec3(
                particle.position.x + 10e-6,
                particle.position.y,
                particle.position.z,
            )
            particle.previous_position = particle.position
        result = organism.run(
            duration_s=DURATION_S,
            record_trajectory_interval_s=SAMPLE_INTERVAL_S,
        )
        frames = []
        for index, trajectory_frame in enumerate(
            result.spatial_result.trajectory_samples
        ):
            frame = dict(trajectory_frame)
            frame["visual_input"] = _sampled_visual(
                organism.protocol,
                result.body_force_frames,
                index,
            )
            frames.append(frame)
        scenarios.append(
            {
                "id": scenario_id,
                "lateral_gradient_sign": lateral_sign,
                "lesion_node_ids": [],
                "lesion_muscle_fiber_ids": [],
                "initial_a1_stretch_perturbation_um": (
                    10.0 if stretch_perturbation else 0.0
                ),
                "summary": _summary(result),
                "first_spike_trace_s": _first_spike_trace(
                    result, connectome
                ),
                "frames": frames,
            }
        )

    artifact = {
        "schema_version": 2,
        "model_id": config["model_id"],
        "status": config["status"],
        "stage": config["stage"],
        "release_validated": False,
        "sample_interval_s": SAMPLE_INTERVAL_S,
        "duration_s": DURATION_S,
        "node_count": 13,
        "sources": {
            "lon": connectome["source"],
            "descending": descending_connectome["source"],
            "a03o_motor": motor_connectome["source"],
            "a03o_segmental_audit": segmental_projection["source"],
            "dbd_motor_feedback": body_feedback_connectome["source"],
        },
        "published_connectome_summary": {
            "lon": connectome["summary"],
            "descending": descending_connectome["summary"],
            "a03o_motor": motor_connectome["summary"],
            "a03o_segmental_projection": segmental_projection["summary"],
            "dbd_motor_feedback": body_feedback_connectome["summary"],
        },
        "phototransduction": config["phototransduction"],
        "lon_dynamics": config["lon_dynamics"],
        "descending_path_dynamics": config["descending_path_dynamics"],
        "a03o_motor_path_dynamics": config["a03o_motor_path_dynamics"],
        "a03o_segmental_projection_dynamics": config[
            "a03o_segmental_projection_dynamics"
        ],
        "neural_muscle_identity_projection": config[
            "neural_muscle_identity_projection"
        ],
        "neural_muscle_activation_dynamics": config[
            "neural_muscle_activation_dynamics"
        ],
        "a03o_segmental_bridge": config["a03o_segmental_bridge"],
        "named_fiber_body_coupling": config["named_fiber_body_coupling"],
        "body_state_sensory_feedback": config["body_state_sensory_feedback"],
        "validation_light_field": config["validation_light_field"],
        "scenarios": scenarios,
        "limitations": config["limitations"]
        + [
            "The diagnostic renderer reads checked physical-node frames and never authors body motion.",
            "The intact left/right scenarios exercise causal response reversal; this is not held-out behavioral validation.",
            "All body motion in this artifact follows named motor output, one-step-delayed activation, attachment tension, and shared-node physics.",
            "A1-left attachment coordinates, bilateral mirror, and A2-A6 homology are ANATOMY_DERIVED; A7 remains blocked.",
            "The third scenario applies a declared 10 um A1 stretch under zero light to isolate body-state to dbd to MN to named-fiber feedback; it is a perturbation fixture, not a natural stimulus.",
            "Every active attachment force records an earlier source spike and uses model force units rather than newtons.",
            "The historical fitted A03o-to-generic-body bridge and generic downstream neural/motor pools are not executed.",
        ],
    }
    return json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic L1 visual-connectome trajectories"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_trajectory()
    if args.check:
        if not args.output.exists():
            print(f"generated visual trajectory is stale: {args.output}")
            return 1
        expected = json.loads(args.output.read_text(encoding="utf-8"))
        actual = json.loads(rendered)
        mismatch = first_mismatch(expected, actual)
        if mismatch:
            print(
                f"generated visual trajectory is stale: {args.output}: "
                f"{mismatch}"
            )
            return 1
        print(
            "generated visual trajectory is current "
            f"(numeric tolerance {NUMERIC_TOLERANCE:g})"
        )
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
