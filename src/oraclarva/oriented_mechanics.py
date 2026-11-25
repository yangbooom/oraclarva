"""Configuration and free-space fixture for oriented body mechanics v2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import degrees, isfinite
from pathlib import Path
from typing import Any, Iterable, Mapping

from .body import load_body_spec
from .body3d import Vec3
from .muscles import (
    NeuralMuscleActivationModel,
    load_neural_muscle_identity_projection,
)
from .off_axis_mechanics import (
    GeneralizedAttachmentLoadFrame,
    OrientedNamedFiberBodyCoupling,
)
from .oriented_body import OrientedScientificBody3D


MODEL_ID = "dmel_l1_oriented_body_mechanics_v2"


def default_oriented_body_mechanics_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "organism"
        / "l1_oriented_body_mechanics_v2.json"
    )


def validate_oriented_body_mechanics_config(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        raw.get("model_id") != MODEL_ID
        or raw.get("status") != "research_approximation"
        or raw.get("stage") != "L1"
        or raw.get("base_model_id") != "dmel_l1_named_fiber_steering_v1"
        or raw.get("release_validated") is not False
        or raw.get("scope") != "mechanics_fixture_not_yet_contact_integrated"
    ):
        raise ValueError("oriented-body model boundary is invalid")
    topology = raw.get("topology", {})
    if (
        topology.get("body_state_space")
        != "unshearable_oriented_cross_section_rod_v2"
        or topology.get("centerline_nodes") != 13
        or topology.get("oriented_sections") != 13
        or topology.get("independent_section_degree_of_freedom")
        != "twist_about_centerline_tangent"
        or tuple(topology.get("attachment_segments", ()))
        != ("A1", "A2", "A3")
        or topology.get("mirrored_non_transverse_pair_count") != 17
        or topology.get("attachment_coordinate_provenance")
        != "ANATOMY_DERIVED"
        or topology.get("mechanics_parameter_provenance") != "MODEL_FITTED"
        or topology.get("metric_attachment_coordinates_measured") is not False
        or topology.get("csa_measured") is not False
        or topology.get("fmax_measured") is not False
        or any(
            topology.get(key) is not False
            for key in (
                "action_command",
                "behavior_fsm",
                "external_policy",
                "heading_input",
                "curvature_input",
                "authored_translation",
            )
        )
    ):
        raise ValueError("oriented-body topology is invalid")
    parameters = raw.get("parameters", {})
    positive = (
        "dt_s",
        "active_tension_gain_model_units",
        "passive_stiffness_model_units",
        "damping_model_units",
        "activation_rise_s",
        "activation_decay_s",
        "spatial_attachment_force_scale",
        "centerline_acceleration_scale_m_s2_per_model_force",
        "twist_torque_scale_rad_s2_per_model_torque",
        "twist_stiffness_model_units_m_per_rad",
        "fixture_duration_s",
        "sample_interval_s",
    )
    if any(
        not isfinite(float(parameters.get(name, 0.0)))
        or float(parameters.get(name, 0.0)) <= 0.0
        for name in positive
    ):
        raise ValueError("oriented-body parameters must be finite and positive")
    retention = float(parameters.get("twist_velocity_retention", -1.0))
    pair = tuple(parameters.get("fixture_fiber_pair", ()))
    if (
        not 0.0 <= retention <= 1.0
        or len(pair) != 2
        or not pair[0].startswith("A1:left:")
        or not pair[1].startswith("A1:right:")
        or raw.get("parameter_provenance", {}).get("provenance")
        != "MODEL_FITTED"
        or raw.get("validation", {}).get("release_validated") is not False
        or raw.get("validation", {}).get("independent_biological_validation")
        is not False
    ):
        raise ValueError("oriented-body claim boundary is invalid")
    return dict(raw)


def load_oriented_body_mechanics_config(
    path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(path) if path else default_oriented_body_mechanics_path()
    return validate_oriented_body_mechanics_config(
        json.loads(source.read_text(encoding="utf-8"))
    )


@dataclass(frozen=True, slots=True)
class OrientedMechanicsResult:
    scenario: str
    duration_s: float
    active_load_samples: int
    traced_load_samples: int
    endpoint_application_samples: int
    maximum_net_force_model_units: float
    maximum_centerline_force_moment_model_units_m: float
    maximum_net_generalized_torque_model_units_m: float
    maximum_abs_section_twist_deg: float
    maximum_abs_twist_gradient_deg: float
    maximum_segment_extension_fraction: float
    final_center_m: Vec3
    final_nodes_m: tuple[Vec3, ...]
    final_twist_deg: tuple[float, ...]
    trace_examples: Mapping[str, Mapping[str, object]]
    trajectory_samples: tuple[dict[str, Any], ...]


class OrientedBodyMechanicsFixture:
    """Exercise MN-to-muscle-to-off-axis-load mechanics without behavior rules."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        lesioned_fiber_ids: Iterable[str] = (),
    ) -> None:
        self.config = (
            load_oriented_body_mechanics_config()
            if config is None
            else validate_oriented_body_mechanics_config(config)
        )
        parameters = self.config["parameters"]
        self.dt_s = float(parameters["dt_s"])
        self.body = OrientedScientificBody3D(load_body_spec())
        self.projection = load_neural_muscle_identity_projection()
        self.coupling = OrientedNamedFiberBodyCoupling(
            body=self.body,
            projection=self.projection,
            dt_s=self.dt_s,
            active_tension_gain=float(
                parameters["active_tension_gain_model_units"]
            ),
            passive_stiffness=float(
                parameters["passive_stiffness_model_units"]
            ),
            damping=float(parameters["damping_model_units"]),
            acceleration_scale_m_s2_per_model_force=float(
                parameters[
                    "centerline_acceleration_scale_m_s2_per_model_force"
                ]
            ),
        )
        self.activation = NeuralMuscleActivationModel(
            self.projection,
            self.dt_s,
            float(parameters["activation_rise_s"]),
            float(parameters["activation_decay_s"]),
            1.0,
        )
        self.fiber_pair = tuple(parameters["fixture_fiber_pair"])
        known = {item.fiber_id for item in self.coupling.geometries}
        if set(self.fiber_pair) - known:
            raise ValueError("fixture fiber pair is absent from mapped atlas")
        lesions = tuple(lesioned_fiber_ids)
        if len(lesions) != len(set(lesions)) or set(lesions) - known:
            raise ValueError("invalid oriented fixture fiber lesion")
        self.lesioned_fiber_ids = lesions

    @staticmethod
    def _center(body: OrientedScientificBody3D) -> Vec3:
        center = Vec3(0.0, 0.0, 0.0)
        total_mass = 0.0
        for particle in body.particles:
            mass = (
                0.0
                if particle.inverse_mass == 0.0
                else 1.0 / particle.inverse_mass
            )
            center = center + particle.position * mass
            total_mass += mass
        if total_mass <= 0.0:
            raise ValueError("oriented fixture requires movable body mass")
        return center * (1.0 / total_mass)

    def _source_for_fiber(self, fiber_id: str) -> str:
        return next(
            mapping.source_node_id
            for mapping in self.projection.mappings
            if mapping.fiber_id == fiber_id
        )

    def run(
        self,
        scenario: str,
        *,
        duration_s: float | None = None,
        sample_interval_s: float | None = None,
    ) -> OrientedMechanicsResult:
        if scenario not in {"uniform", "left", "right"}:
            raise ValueError("scenario must be uniform, left, or right")
        parameters = self.config["parameters"]
        duration = float(
            parameters["fixture_duration_s"]
            if duration_s is None
            else duration_s
        )
        interval = float(
            parameters["sample_interval_s"]
            if sample_interval_s is None
            else sample_interval_s
        )
        steps = round(duration / self.dt_s)
        stride = max(1, round(interval / self.dt_s))
        if steps <= 1:
            raise ValueError("oriented fixture must span at least two steps")
        selected = (
            self.fiber_pair
            if scenario == "uniform"
            else (self.fiber_pair[0],)
            if scenario == "left"
            else (self.fiber_pair[1],)
        )
        selected_sources = tuple(self._source_for_fiber(item) for item in selected)
        initial_center = self._center(self.body)
        rest_lengths = tuple(
            geometry.rest_length_m for geometry in self.body.geometry
        )
        maximum_net_force = 0.0
        maximum_centerline_moment = 0.0
        maximum_generalized_torque = 0.0
        maximum_extension = 0.0
        active_samples = 0
        traced_samples = 0
        application_samples = 0
        trace_examples: dict[str, Mapping[str, object]] = {}
        samples: list[dict[str, Any]] = []

        def sample(time_s: float, load: GeneralizedAttachmentLoadFrame) -> None:
            samples.append(
                {
                    "time_s": round(time_s, 9),
                    "nodes_um": [
                        [
                            round(item.position.x * 1e6, 9),
                            round(item.position.y * 1e6, 9),
                            round(item.position.z * 1e6, 9),
                        ]
                        for item in self.body.particles
                    ],
                    "twist_deg": [
                        round(value, 9) for value in self.body.twist_angles_deg
                    ],
                    "active_fiber_count": load.active_fiber_count,
                    "net_force_model_units": round(
                        load.net_force_model_units.norm(), 15
                    ),
                    "centerline_force_moment_model_units_m": round(
                        load.centerline_force_moment_model_units_m.norm(), 18
                    ),
                    "net_generalized_torque_model_units_m": round(
                        load.net_generalized_torque_model_units_m.norm(), 18
                    ),
                }
            )

        for step in range(steps):
            time_s = step * self.dt_s
            events = self.projection.emit(
                selected_sources if step == 0 else (),
                lesioned_fiber_ids=(),
            )
            activation = self.activation.step(time_s, events)
            force = self.coupling.step(
                activation,
                last_source_by_fiber=self.activation.last_applied_source,
                last_spike_time_s_by_fiber=self.activation.last_applied_spike_s,
            )
            load = self.coupling.paired_generalized_active_excess_loads(
                force,
                (self.fiber_pair,),
                spatial_force_scale=float(
                    parameters["spatial_attachment_force_scale"]
                ),
                lesioned_fiber_ids=self.lesioned_fiber_ids,
            )
            active_samples += load.active_fiber_count
            traced_samples += load.traced_active_fiber_count
            application_samples += len(load.applications)
            maximum_net_force = max(
                maximum_net_force, load.net_force_model_units.norm()
            )
            maximum_centerline_moment = max(
                maximum_centerline_moment,
                load.centerline_force_moment_model_units_m.norm(),
            )
            maximum_generalized_torque = max(
                maximum_generalized_torque,
                load.net_generalized_torque_model_units_m.norm(),
            )
            for application in load.applications:
                trace_examples.setdefault(
                    application.fiber_id,
                    {
                        "fiber_id": application.fiber_id,
                        "source_node_id": application.source_node_id,
                        "source_spike_time_s": application.source_spike_time_s,
                        "first_force_time_s": time_s,
                        "coordinate_provenance": (
                            application.coordinate_provenance
                        ),
                        "mechanics_provenance": (
                            application.mechanics_provenance
                        ),
                    },
                )
            if step % stride == 0:
                sample(time_s, load)
            self.coupling.advance_body(
                load,
                spatial_force_scale_to_acceleration=float(
                    parameters[
                        "centerline_acceleration_scale_m_s2_per_model_force"
                    ]
                ),
                twist_torque_scale_rad_s2_per_model_torque=float(
                    parameters["twist_torque_scale_rad_s2_per_model_torque"]
                ),
                twist_velocity_retention=float(
                    parameters["twist_velocity_retention"]
                ),
                twist_stiffness_model_units_m_per_rad=float(
                    parameters["twist_stiffness_model_units_m_per_rad"]
                ),
            )
            maximum_extension = max(
                maximum_extension,
                *(
                    max(
                        0.0,
                        self.body.segment_length_m(index)
                        / rest_lengths[index]
                        - 1.0,
                    )
                    for index in range(len(rest_lengths))
                ),
            )

        final_time = steps * self.dt_s
        # Reuse a zero load with the final state only for deterministic media.
        empty = GeneralizedAttachmentLoadFrame(
            time_s=final_time,
            excess_tension_model_units_by_fiber={},
            replaced_axial_source_forces_model_units={
                index: Vec3(0.0, 0.0, 0.0)
                for index in range(len(self.body.particles))
            },
            centerline_forces_model_units={
                index: Vec3(0.0, 0.0, 0.0)
                for index in range(len(self.body.particles))
            },
            section_torques_model_units_m={
                index: Vec3(0.0, 0.0, 0.0)
                for index in range(len(self.body.particles))
            },
            applications=(),
            active_fiber_count=0,
            traced_active_fiber_count=0,
            net_force_model_units=Vec3(0.0, 0.0, 0.0),
            centerline_force_moment_model_units_m=Vec3(0.0, 0.0, 0.0),
            net_generalized_torque_model_units_m=Vec3(0.0, 0.0, 0.0),
        )
        if not samples or samples[-1]["time_s"] != round(final_time, 9):
            sample(final_time, empty)
        final_center = self._center(self.body)
        # Free-space internal loading must not author center-of-mass motion.
        if (final_center - initial_center).norm() > 1e-9:
            raise ValueError("free-space internal load translated body center")
        return OrientedMechanicsResult(
            scenario=scenario,
            duration_s=final_time,
            active_load_samples=active_samples,
            traced_load_samples=traced_samples,
            endpoint_application_samples=application_samples,
            maximum_net_force_model_units=maximum_net_force,
            maximum_centerline_force_moment_model_units_m=(
                maximum_centerline_moment
            ),
            maximum_net_generalized_torque_model_units_m=(
                maximum_generalized_torque
            ),
            maximum_abs_section_twist_deg=degrees(
                self.body.maximum_abs_twist_rad
            ),
            maximum_abs_twist_gradient_deg=degrees(
                self.body.maximum_abs_twist_gradient_rad
            ),
            maximum_segment_extension_fraction=maximum_extension,
            final_center_m=final_center,
            final_nodes_m=tuple(
                particle.position for particle in self.body.particles
            ),
            final_twist_deg=self.body.twist_angles_deg,
            trace_examples=trace_examples,
            trajectory_samples=tuple(samples),
        )
