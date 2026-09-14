"""Evidence-bounded named-fiber attachment mechanics for field steering."""

from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
from typing import Any, Iterable, Mapping

from .steering import AxialSteeringLarva, load_axial_steering_config


MODEL_ID = "dmel_l1_named_fiber_steering_v1"
FORCE_MODE = "paired_activation_excess_attachment_3d"


def default_named_fiber_steering_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "organism"
        / "l1_named_fiber_steering_v1.json"
    )


def validate_named_fiber_steering_config(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    previous = load_axial_steering_config()
    if (
        raw.get("model_id") != MODEL_ID
        or raw.get("status") != "research_approximation"
        or raw.get("stage") != "L1"
        or raw.get("base_model_id") != previous["model_id"]
        or raw.get("release_validated") is not False
    ):
        raise ValueError("named-fiber steering model boundary is invalid")
    expected_contract = [
        "environment_scalar_field",
        "bilateral_head_sensory_transduction",
        "side_resolved_neural_dynamics",
        "side_resolved_motor_neurons",
        "shared_named_muscle_activation",
        "paired_active_tension_excess",
        "anatomy_derived_attachment_line_force",
        "equal_and_opposite_3d_node_force",
        "axial_body_physics_and_continuous_ground_contact",
        "environment_scalar_field",
    ]
    topology = raw.get("topology", {})
    attachment = topology.get("attachment_scope", {})
    if (
        raw.get("causal_contract") != expected_contract
        or topology.get("provenance") != "ANATOMY_DERIVED"
        or topology.get("action_command") is not False
        or topology.get("behavior_fsm") is not False
        or topology.get("external_policy") is not False
        or topology.get("target_heading_input") is not False
        or topology.get("yaw_input_to_body") is not False
        or topology.get("shared_axial_protocol") is not True
        or topology.get("shared_motor_and_muscle_atlas") is not True
        or topology.get("duplicated_motor_neuron_nodes") is not False
        or tuple(attachment.get("segments", ())) != ("A1", "A2", "A3")
        or attachment.get("mirrored_non_transverse_pair_count") != 17
        or attachment.get("coordinate_provenance") != "ANATOMY_DERIVED"
        or attachment.get("metric_coordinates_measured") is not False
        or attachment.get("csa_measured") is not False
        or attachment.get("fmax_measured") is not False
    ):
        raise ValueError("named-fiber steering topology is invalid")
    parameters = raw.get("parameters", {})
    shared_parameter_names = (
        "sensory_current_a",
        "premotor_current_a",
        "motor_current_a",
        "contrast_threshold",
        "contrast_gain",
        "steering_segments",
        "premotor_delay_s_by_segment",
        "motor_current_scale_by_segment",
        "motor_delay_s",
        "default_field_baseline",
        "default_lateral_gradient_per_m",
    )
    if any(
        parameters.get(name) != previous["parameters"].get(name)
        for name in shared_parameter_names
    ):
        raise ValueError("named-fiber steering must preserve the frozen neural path")
    spatial_scale = parameters.get("spatial_attachment_force_scale", 0.0)
    if (
        parameters.get("active_curvature_gain") != 0.0
        or not isfinite(float(spatial_scale))
        or not 0.0 < float(spatial_scale) <= 1.0
    ):
        raise ValueError("named-fiber steering mechanics parameters are invalid")
    mechanics = raw.get("mechanics", {})
    if (
        mechanics.get("force_projection_mode") != FORCE_MODE
        or mechanics.get("active_curvature_constraint") is not False
        or mechanics.get("active_curvature_gain") != 0.0
        or mechanics.get("axial_proxy_replacement") is not True
        or mechanics.get("equal_and_opposite_force") is not True
        or mechanics.get("yaw_angle_input") is not False
        or mechanics.get("curvature_input_to_body") is not False
        or mechanics.get("authored_translation") is not False
        or mechanics.get("force_unit") != "model_unit_not_newton"
        or mechanics.get("coordinate_provenance") != "ANATOMY_DERIVED"
        or mechanics.get("parameter_provenance") != "MODEL_FITTED"
    ):
        raise ValueError("named-fiber steering mechanics boundary is invalid")
    environment = raw.get("environment", {})
    if (
        environment.get("range") != [0.0, 1.0]
        or environment.get("body_state_feedback") is not True
        or environment.get("desired_heading_input") is not False
        or raw.get("parameter_provenance", {}).get("provenance")
        != "MODEL_FITTED"
        or raw.get("validation", {}).get("release_validated") is not False
    ):
        raise ValueError("named-fiber steering claim boundary is invalid")
    return dict(raw)


def load_named_fiber_steering_config(
    path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(path) if path else default_named_fiber_steering_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    return validate_named_fiber_steering_config(raw)


class NamedFiberSteeringLarva(AxialSteeringLarva):
    """Run the frozen neural path with A1-A3 attachment-force steering."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        lesion_sensory_sides: Iterable[str] = (),
        lesion_premotor_channels: Iterable[tuple[str, str]] = (),
        lesion_motor_channels: Iterable[tuple[str, str]] = (),
        lesion_muscle_channels: Iterable[tuple[str, str]] = (),
        lesion_attachment_channels: Iterable[tuple[str, str]] = (),
        lesion_axial_node_ids: Iterable[str] = (),
    ) -> None:
        selected = (
            load_named_fiber_steering_config()
            if config is None
            else validate_named_fiber_steering_config(config)
        )
        super().__init__(
            selected,
            lesion_sensory_sides=lesion_sensory_sides,
            lesion_premotor_channels=lesion_premotor_channels,
            lesion_motor_channels=lesion_motor_channels,
            lesion_muscle_channels=lesion_muscle_channels,
            lesion_attachment_channels=lesion_attachment_channels,
            lesion_axial_node_ids=lesion_axial_node_ids,
        )
