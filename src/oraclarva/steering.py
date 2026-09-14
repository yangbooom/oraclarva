"""Axial-v1-integrated bilateral field steering without behavior commands.

A bounded world field is sampled at the current left and right head surface.
Only field values enter the sensory transform. Side-resolved sensory and
premotor LIF activity supplies current to the existing axial-v1 motor-neuron
nodes; their real spikes enter the shared muscle state. Body yaw is an outcome
of asymmetric activation and 3D contact mechanics.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from math import acos, atan2, degrees, isfinite, sqrt
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from .axial import (
    AXIAL_SEGMENTS,
    AxialLocomotionLarva,
    load_axial_locomotion_config,
)
from .body3d import ScientificBody3D, Vec3
from .lif import SparseLIFNetwork, Synapse
from .muscles import (
    NeuralMuscleIdentityProjection,
    load_neural_muscle_identity_projection,
)


SIDES = ("left", "right")


def default_axial_steering_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "organism"
        / "l1_axial_steering_v1.json"
    )


def load_axial_steering_config(
    path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(path) if path else default_axial_steering_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    axial = load_axial_locomotion_config()
    if (
        raw.get("model_id") != "dmel_l1_axial_steering_v1"
        or raw.get("status") != "research_approximation"
        or raw.get("stage") != "L1"
        or raw.get("base_model_id") != axial["model_id"]
        or raw.get("release_validated") is not False
    ):
        raise ValueError("axial-steering model boundary is invalid")
    expected_contract = [
        "environment_scalar_field",
        "bilateral_head_sensory_transduction",
        "side_resolved_neural_dynamics",
        "side_resolved_motor_neurons",
        "shared_named_muscle_activation",
        "active_curvature_and_axial_body_physics",
        "continuous_ground_contact",
        "environment_scalar_field",
    ]
    topology = raw.get("topology", {})
    pivot = topology.get("anterior_pivot", {})
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
        or pivot.get("published_stage") != "L2"
        or tuple(pivot.get("published_segment_support", ()))
        != ("T3", "A1", "A2", "A3")
        or pivot.get("published_peak_segment") != "A1"
        or pivot.get("published_support_provenance")
        != "MEASURED_PUBLISHED"
        or tuple(pivot.get("modeled_motor_segments", ()))
        != ("A1", "A2", "A3")
        or tuple(pivot.get("mechanical_joint_support", ()))
        != ("T3-A1", "A1-A2", "A2-A3", "A3-A4")
        or tuple(pivot.get("allowed_dominant_joints", ()))
        != ("T3-A1", "A1-A2")
        or pivot.get("numeric_profile_provenance") != "MODEL_FITTED"
    ):
        raise ValueError("axial-steering causal topology is invalid")
    parameters = raw.get("parameters", {})
    positive = (
        "sensory_current_a",
        "premotor_current_a",
        "motor_current_a",
        "contrast_gain",
        "motor_delay_s",
        "active_curvature_gain",
        "default_lateral_gradient_per_m",
    )
    if any(
        not isfinite(float(parameters.get(name, 0.0)))
        or float(parameters.get(name, 0.0)) <= 0.0
        for name in positive
    ):
        raise ValueError("axial-steering parameters must be finite and positive")
    expected_segments = ("A1", "A2", "A3")
    current_scales = parameters.get("motor_current_scale_by_segment", {})
    if (
        not 0.0 <= float(parameters.get("contrast_threshold", -1.0)) < 1.0
        or not 0.0 <= float(parameters.get("default_field_baseline", -1.0)) <= 1.0
        or tuple(parameters.get("steering_segments", ())) != expected_segments
        or set(parameters.get("premotor_delay_s_by_segment", {}))
        != set(expected_segments)
        or set(current_scales) != set(expected_segments)
        or any(
            float(value) < 0.0
            for value in parameters["premotor_delay_s_by_segment"].values()
        )
        or any(
            not isfinite(float(value)) or not 0.0 < float(value) <= 1.0
            for value in current_scales.values()
        )
    ):
        raise ValueError("axial-steering bounded parameters are invalid")
    environment = raw.get("environment", {})
    mechanics = raw.get("mechanics", {})
    if (
        environment.get("range") != [0.0, 1.0]
        or environment.get("body_state_feedback") is not True
        or environment.get("desired_heading_input") is not False
        or mechanics.get("yaw_angle_input") is not False
        or mechanics.get("authored_translation") is not False
        or raw.get("parameter_provenance", {}).get("provenance")
        != "MODEL_FITTED"
        or raw.get("validation", {}).get("release_validated") is not False
    ):
        raise ValueError("axial-steering environment or mechanics boundary is invalid")
    return raw


class ScalarField(Protocol):
    def sample(self, position_m: Vec3, time_s: float) -> float:
        """Return a bounded environmental intensity at a world position."""

    def as_mapping(self) -> Mapping[str, object]:
        """Return the reproducible field definition."""


@dataclass(frozen=True, slots=True)
class PlanarLinearField:
    baseline: float = 0.5
    gradient_x_per_m: float = 0.0
    gradient_y_per_m: float = 0.0

    def __post_init__(self) -> None:
        if not all(
            isfinite(value)
            for value in (
                self.baseline,
                self.gradient_x_per_m,
                self.gradient_y_per_m,
            )
        ):
            raise ValueError("field parameters must be finite")
        if not 0.0 <= self.baseline <= 1.0:
            raise ValueError("field baseline must be in [0, 1]")

    def sample(self, position_m: Vec3, time_s: float) -> float:
        del time_s
        value = (
            self.baseline
            + self.gradient_x_per_m * position_m.x
            + self.gradient_y_per_m * position_m.y
        )
        return min(1.0, max(0.0, value))

    def as_mapping(self) -> Mapping[str, object]:
        return {
            "type": "bounded_planar_linear_scalar",
            "baseline": self.baseline,
            "gradient_x_per_m": self.gradient_x_per_m,
            "gradient_y_per_m": self.gradient_y_per_m,
            "range": [0.0, 1.0],
            "provenance": "MODEL_FITTED",
        }


@dataclass(frozen=True, slots=True)
class BilateralFieldSample:
    time_s: float
    left_position_m: Vec3
    right_position_m: Vec3
    left_intensity: float
    right_intensity: float

    @property
    def signed_contrast(self) -> float:
        return self.left_intensity - self.right_intensity

    @classmethod
    def from_body(
        cls,
        body: ScientificBody3D,
        field: ScalarField,
        time_s: float,
    ) -> "BilateralFieldSample":
        left = body.bilateral_surface_position_m(0, "left")
        right = body.bilateral_surface_position_m(0, "right")
        return cls(
            time_s=time_s,
            left_position_m=left,
            right_position_m=right,
            left_intensity=field.sample(left, time_s),
            right_intensity=field.sample(right, time_s),
        )


@dataclass(frozen=True, slots=True)
class SteeringCircuitFrame:
    motor_current_by_source: Mapping[str, float]
    motor_origin_by_source: Mapping[str, Mapping[str, object]]
    field_sample: BilateralFieldSample
    rectified_contrast_by_side: Mapping[str, float]


class BilateralSteeringCircuit:
    """Side sensory/premotor LIF circuit targeting existing axial MNs."""

    def __init__(
        self,
        config: Mapping[str, Any],
        projection: NeuralMuscleIdentityProjection,
        *,
        lesion_node_ids: Iterable[str] = (),
    ) -> None:
        self.config = config
        self.parameters = config["parameters"]
        self.projection = projection
        self.segments = tuple(self.parameters["steering_segments"])
        mappings_by_source: dict[str, list[Any]] = {}
        muscle_numbers_by_channel: dict[tuple[str, str], set[str]] = {}
        for mapping in projection.mappings:
            if mapping.segment_id not in self.segments:
                continue
            mappings_by_source.setdefault(mapping.source_node_id, []).append(mapping)
            muscle_numbers_by_channel.setdefault(
                (mapping.segment_id, mapping.side), set()
            ).add(mapping.muscle_number)
        paired_numbers_by_segment = {
            segment: muscle_numbers_by_channel[(segment, "left")]
            & muscle_numbers_by_channel[(segment, "right")]
            for segment in self.segments
        }
        channel_by_source: dict[str, tuple[str, str]] = {}
        for source, mappings in mappings_by_source.items():
            channels = {(item.segment_id, item.side) for item in mappings}
            if len(channels) != 1:
                raise ValueError("steering motor identity crosses segment or side")
            channel = next(iter(channels))
            segment, _ = channel
            if any(
                item.muscle_number not in paired_numbers_by_segment[segment]
                for item in mappings
            ):
                continue
            channel_by_source[source] = channel
        self.channel_by_source = channel_by_source
        self.paired_muscle_numbers_by_segment = {
            segment: tuple(sorted(values, key=int))
            for segment, values in paired_numbers_by_segment.items()
        }
        self.motor_sources_by_channel = {
            (segment, side): tuple(
                sorted(
                    source
                    for source, channel in channel_by_source.items()
                    if channel == (segment, side)
                )
            )
            for segment in self.segments
            for side in SIDES
        }
        if any(not values for values in self.motor_sources_by_channel.values()):
            raise ValueError("steering requires mirror-paired A1-A2 MN outputs")
        for segment in self.segments:
            counts = {
                len(self.motor_sources_by_channel[(segment, side)]) for side in SIDES
            }
            if len(counts) != 1:
                raise ValueError("steering mirror-paired MN counts differ by side")

        labels = [f"field_sensory:{side}" for side in SIDES]
        labels.extend(
            f"premotor:steering:{segment}:{side}"
            for segment in self.segments
            for side in SIDES
        )
        if len(labels) != len(set(labels)):
            raise ValueError("steering neural labels must be unique")
        self.labels = tuple(labels)
        self.index_by_id = {label: index for index, label in enumerate(labels)}
        dt = float(load_axial_locomotion_config()["parameters"]["dt_s"])
        synapses: list[Synapse] = []
        for segment in self.segments:
            premotor_delay = round(
                float(self.parameters["premotor_delay_s_by_segment"][segment]) / dt
            )
            for side in SIDES:
                sensory = f"field_sensory:{side}"
                premotor = f"premotor:steering:{segment}:{side}"
                synapses.append(
                    Synapse(
                        self.index_by_id[sensory],
                        self.index_by_id[premotor],
                        float(self.parameters["premotor_current_a"]),
                        delay_steps=premotor_delay,
                    )
                )
        self.network = SparseLIFNetwork(len(labels), synapses)
        lesions = tuple(lesion_node_ids)
        if len(lesions) != len(set(lesions)):
            raise ValueError("steering neural lesions must be unique")
        unknown = set(lesions) - set(labels)
        if unknown:
            raise ValueError(f"unknown steering neural lesion nodes: {sorted(unknown)}")
        self.network.lesion(self.index_by_id[node] for node in lesions)
        self.spike_counts = dict.fromkeys(labels, 0)
        self.first_spike_s: dict[str, float | None] = dict.fromkeys(labels, None)
        self.last_sensor_origin: dict[str, dict[str, object]] = {}
        self.last_premotor_origin: dict[tuple[str, str], dict[str, object]] = {}
        self.pending_motor_drive: list[
            tuple[float, str, Mapping[str, object]]
        ] = []

    @property
    def motor_source_ids(self) -> frozenset[str]:
        return frozenset(self.channel_by_source)

    def step(self, sample: BilateralFieldSample) -> SteeringCircuitFrame:
        p = self.parameters
        time_s = sample.time_s
        due = [
            item for item in self.pending_motor_drive
            if item[0] <= time_s + 1e-12
        ]
        self.pending_motor_drive = [
            item for item in self.pending_motor_drive
            if item[0] > time_s + 1e-12
        ]
        motor_current: dict[str, float] = {}
        motor_origins: dict[str, Mapping[str, object]] = {}
        current_scales = p["motor_current_scale_by_segment"]
        for _, source, origin in due:
            segment = str(origin["segment_id"])
            motor_current[source] = (
                float(p["motor_current_a"]) * float(current_scales[segment])
            )
            motor_origins[source] = origin

        threshold = float(p["contrast_threshold"])
        signed = sample.signed_contrast
        rectified = {
            "left": min(
                1.0,
                max(0.0, signed - threshold) * float(p["contrast_gain"]),
            ),
            "right": min(
                1.0,
                max(0.0, -signed - threshold) * float(p["contrast_gain"]),
            ),
        }
        external = {
            self.index_by_id[f"field_sensory:{side}"]:
            value * float(p["sensory_current_a"])
            for side, value in rectified.items()
            if value > 0.0
        }
        spikes = self.network.step(external)
        spiked = tuple(self.labels[index] for index in spikes)
        for label in spiked:
            self.spike_counts[label] += 1
            if self.first_spike_s[label] is None:
                self.first_spike_s[label] = time_s
        for side in SIDES:
            sensor = f"field_sensory:{side}"
            if sensor in spiked:
                self.last_sensor_origin[side] = {
                    "body_state_time_s": time_s,
                    "sensor_node_id": sensor,
                    "sensor_spike_time_s": time_s,
                    "field_left_intensity": sample.left_intensity,
                    "field_right_intensity": sample.right_intensity,
                }
        motor_delay = float(p["motor_delay_s"])
        for segment in self.segments:
            for side in SIDES:
                premotor = f"premotor:steering:{segment}:{side}"
                origin = self.last_sensor_origin.get(side)
                if premotor in spiked and origin is not None:
                    if float(origin["sensor_spike_time_s"]) >= time_s:
                        continue
                    premotor_origin = {
                        **origin,
                        "premotor_node_id": premotor,
                        "premotor_spike_time_s": time_s,
                        "direction": f"steering_{side}",
                        "segment_id": segment,
                        "side": side,
                        "path_provenance": "ANATOMY_DERIVED",
                    }
                    self.last_premotor_origin[(segment, side)] = premotor_origin
                    for source in self.motor_sources_by_channel[(segment, side)]:
                        self.pending_motor_drive.append(
                            (
                                time_s + motor_delay,
                                source,
                                {**premotor_origin, "motor_node_id": source},
                            )
                        )
        return SteeringCircuitFrame(
            motor_current_by_source=motor_current,
            motor_origin_by_source=motor_origins,
            field_sample=sample,
            rectified_contrast_by_side=rectified,
        )


@dataclass(frozen=True, slots=True)
class AxialSteeringResult:
    model_id: str
    duration_s: float
    field: Mapping[str, object]
    displacement_x_um: float
    displacement_y_um: float
    anatomical_forward_displacement_um: float
    heading_change_deg: float
    maximum_abs_lateral_um: float
    maximum_abs_field_contrast: float
    field_sample_range: tuple[float, float]
    side_peak_activation: Mapping[str, Mapping[str, float]]
    steering_spike_counts: Mapping[str, int]
    steering_first_spike_s: Mapping[str, float | None]
    axial_spike_counts: Mapping[str, int]
    contact_retention_range: tuple[float, float]
    all_active_forces_sensory_traced: bool
    steering_active_force_samples: int
    steering_traced_force_samples: int
    steering_causal_trace_examples: Mapping[str, Mapping[str, object]]
    maximum_segment_extension_fraction: float
    minimum_head_tail_chord_ratio: float
    maximum_local_bend_deg: float
    integrated_local_bend_deg_s_by_joint: Mapping[str, float]
    integrated_lateral_slip_um: float
    trajectory_samples: tuple[dict[str, Any], ...]
    release_validated: bool = False


class AxialSteeringLarva:
    """Run field-driven bilateral steering on one frozen axial-v1 body."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        lesion_sensory_sides: Iterable[str] = (),
        lesion_premotor_channels: Iterable[tuple[str, str]] = (),
        lesion_motor_channels: Iterable[tuple[str, str]] = (),
        lesion_muscle_channels: Iterable[tuple[str, str]] = (),
        lesion_axial_node_ids: Iterable[str] = (),
    ) -> None:
        self.config = config or load_axial_steering_config()
        self.axial_config = load_axial_locomotion_config()
        steering_segments = tuple(self.config["parameters"]["steering_segments"])

        def validate_sides(values: Iterable[str]) -> tuple[str, ...]:
            result = tuple(values)
            if len(result) != len(set(result)) or set(result) - set(SIDES):
                raise ValueError("invalid steering sensory lesion sides")
            return result

        def validate_channels(
            values: Iterable[tuple[str, str]], name: str
        ) -> tuple[tuple[str, str], ...]:
            result = tuple(values)
            if (
                len(result) != len(set(result))
                or any(
                    len(item) != 2
                    or item[0] not in steering_segments
                    or item[1] not in SIDES
                    for item in result
                )
            ):
                raise ValueError(f"invalid steering {name} lesion channels")
            return result

        sensory_lesions = validate_sides(lesion_sensory_sides)
        premotor_lesions = validate_channels(
            lesion_premotor_channels, "premotor"
        )
        motor_lesions = validate_channels(
            lesion_motor_channels, "motor"
        )
        muscle_lesions = validate_channels(lesion_muscle_channels, "muscle")

        projection = load_neural_muscle_identity_projection()
        mapping_circuit = BilateralSteeringCircuit(self.config, projection)
        muscle_fiber_lesions = tuple(
            mapping.fiber_id
            for mapping in projection.mappings
            if (mapping.segment_id, mapping.side) in muscle_lesions
        )
        motor_node_lesions = tuple(
            source
            for channel in motor_lesions
            for source in mapping_circuit.motor_sources_by_channel[channel]
        )
        axial_node_lesions = tuple(
            dict.fromkeys((*lesion_axial_node_ids, *motor_node_lesions))
        )
        self.axial = AxialLocomotionLarva(
            self.axial_config,
            lesion_node_ids=axial_node_lesions,
            lesion_fiber_ids=muscle_fiber_lesions,
        )
        circuit_lesions = [f"field_sensory:{side}" for side in sensory_lesions]
        circuit_lesions.extend(
            f"premotor:steering:{segment}:{side}"
            for segment, side in premotor_lesions
        )
        self.circuit = BilateralSteeringCircuit(
            self.config,
            self.axial.projection,
            lesion_node_ids=circuit_lesions,
        )
        self.motor_node_lesions = motor_node_lesions
        self.muscle_fiber_lesions = muscle_fiber_lesions
        self.body = self.axial.body
        self.protocol = self.axial.protocol
        self.coupling = self.axial.coupling
        self.transducer = self.axial.transducer
        group_by_fiber = {
            item.fiber_id: item.spatial_group for item in self.coupling.geometries
        }
        muscle_numbers_by_channel = {
            (segment, side): {
                mapping.muscle_number
                for mapping in self.axial.projection.mappings
                if mapping.segment_id == segment and mapping.side == side
            }
            for segment in AXIAL_SEGMENTS
            for side in SIDES
        }
        paired_numbers = {
            segment: muscle_numbers_by_channel[(segment, "left")]
            & muscle_numbers_by_channel[(segment, "right")]
            for segment in AXIAL_SEGMENTS
        }
        self.axial_fibers_by_channel = {
            (segment, side): tuple(
                mapping.fiber_id
                for mapping in self.axial.projection.mappings
                if mapping.segment_id == segment
                and mapping.side == side
                and mapping.muscle_number in paired_numbers[segment]
                and group_by_fiber[mapping.fiber_id] != "T"
            )
            for segment in AXIAL_SEGMENTS
            for side in SIDES
        }
        if any(not values for values in self.axial_fibers_by_channel.values()):
            raise ValueError("steering requires paired non-transverse fibers")

    @staticmethod
    def _center(body: ScientificBody3D) -> Vec3:
        count = len(body.particles)
        return Vec3(
            sum(item.position.x for item in body.particles) / count,
            sum(item.position.y for item in body.particles) / count,
            sum(item.position.z for item in body.particles) / count,
        )

    @staticmethod
    def _anatomical_forward_xy(body: ScientificBody3D) -> Vec3:
        vector = body.particles[0].position - body.particles[-1].position
        planar = Vec3(vector.x, vector.y, 0.0)
        return planar.normalized()

    def _shape_metrics(
        self,
    ) -> tuple[float, float, Mapping[str, float]]:
        lengths = [
            self.body.segment_length_m(index)
            for index in range(len(self.body.geometry))
        ]
        maximum_extension = max(
            max(0.0, length / geometry.rest_length_m - 1.0)
            for length, geometry in zip(lengths, self.body.geometry, strict=True)
        )
        chord = (
            self.body.particles[0].position
            - self.body.particles[-1].position
        ).norm()
        chord_ratio = chord / sum(lengths)
        local_bends = {}
        for index in range(1, len(self.body.particles) - 1):
            first = (
                self.body.particles[index].position
                - self.body.particles[index - 1].position
            ).normalized()
            second = (
                self.body.particles[index + 1].position
                - self.body.particles[index].position
            ).normalized()
            angle = degrees(acos(min(1.0, max(-1.0, first.dot(second)))))
            left_segment = self.body.geometry[index - 1].id
            right_segment = self.body.geometry[index].id
            local_bends[f"{left_segment}-{right_segment}"] = angle
        return maximum_extension, chord_ratio, local_bends

    def run(
        self,
        field: ScalarField,
        *,
        posterior_touch: bool = True,
        duration_s: float | None = None,
        record_trajectory_interval_s: float | None = 0.01,
    ) -> AxialSteeringResult:
        p = self.axial_config["parameters"]
        coupling = self.axial_config["named_fiber_body_coupling"]
        contact = self.axial_config["continuous_ground_contact"]
        dt = float(p["dt_s"])
        duration = float(p["duration_s"] if duration_s is None else duration_s)
        steps = round(duration / dt)
        if steps <= 0:
            raise ValueError("steering duration must span at least one step")
        stride = (
            None
            if record_trajectory_interval_s is None
            else max(1, round(record_trajectory_interval_s / dt))
        )
        initial_center = self._center(self.body)
        initial_forward = self._anatomical_forward_xy(self.body)
        initial_heading = degrees(atan2(initial_forward.y, initial_forward.x))
        initial_lateral = Vec3(-initial_forward.y, initial_forward.x, 0.0)
        previous_center = initial_center
        local_tension_drive = dict.fromkeys(AXIAL_SEGMENTS, 0.0)
        last_retention = {
            index: float(contact["planted_velocity_retention"])
            for index in range(len(self.body.particles))
        }
        samples: list[dict[str, Any]] = []
        minimum_retention = 1.0
        maximum_retention = 0.0
        minimum_field = 1.0
        maximum_field = 0.0
        maximum_contrast = 0.0
        maximum_lateral = 0.0
        maximum_extension = 0.0
        minimum_chord_ratio = 1.0
        maximum_bend = 0.0
        integrated_local_bend = {
            f"{self.body.geometry[index - 1].id}-{self.body.geometry[index].id}": 0.0
            for index in range(1, len(self.body.geometry))
        }
        integrated_slip = 0.0
        all_traced = True
        steering_active_force_samples = 0
        steering_traced_force_samples = 0
        trace_examples: dict[str, Mapping[str, object]] = {}
        side_peaks = {
            segment: {side: 0.0 for side in SIDES}
            for segment in AXIAL_SEGMENTS
        }
        steering_motor_counts = dict.fromkeys(
            self.circuit.motor_source_ids, 0
        )
        steering_motor_first: dict[str, float | None] = dict.fromkeys(
            self.circuit.motor_source_ids, None
        )

        def trajectory_sample(
            time_s: float,
            field_sample: BilateralFieldSample,
            side_activation: Mapping[str, tuple[float, float]],
        ) -> dict[str, Any]:
            forward = self._anatomical_forward_xy(self.body)
            heading = degrees(atan2(forward.y, forward.x))
            return {
                "time_s": round(time_s, 9),
                "nodes_um": [
                    [
                        round(item.position.x * 1e6, 9),
                        round(item.position.y * 1e6, 9),
                        round(item.position.z * 1e6, 9),
                    ]
                    for item in self.body.particles
                ],
                "field_left": round(field_sample.left_intensity, 9),
                "field_right": round(field_sample.right_intensity, 9),
                "heading_change_deg": round(
                    (heading - initial_heading + 180.0) % 360.0 - 180.0, 9
                ),
                "contact_retention_by_node": [
                    round(last_retention[index], 9)
                    for index in range(len(self.body.particles))
                ],
                "segment_activation_left": {
                    segment: round(side_activation.get(segment, (0.0, 0.0))[0], 9)
                    for segment in AXIAL_SEGMENTS
                },
                "segment_activation_right": {
                    segment: round(side_activation.get(segment, (0.0, 0.0))[1], 9)
                    for segment in AXIAL_SEGMENTS
                },
            }

        first_sample = BilateralFieldSample.from_body(self.body, field, 0.0)
        if stride is not None:
            samples.append(trajectory_sample(0.0, first_sample, {}))
        for step in range(steps):
            time_s = step * dt
            body_state = self.transducer.sample(time_s)
            field_sample = BilateralFieldSample.from_body(self.body, field, time_s)
            circuit_frame = self.circuit.step(field_sample)
            activation = self.protocol.step(
                time_s,
                body_state,
                posterior_touch=posterior_touch,
                anterior_touch=False,
                local_tension_drive=local_tension_drive,
                additional_motor_current_by_source=(
                    circuit_frame.motor_current_by_source
                ),
                additional_motor_origin_by_source=(
                    circuit_frame.motor_origin_by_source
                ),
            )
            for source in self.circuit.motor_source_ids.intersection(
                self.protocol.last_spiked_labels
            ):
                trace = self.protocol.pending_motor_trace.get((source, time_s))
                if trace is not None and trace.direction.startswith("steering_"):
                    steering_motor_counts[source] += 1
                    if steering_motor_first[source] is None:
                        steering_motor_first[source] = time_s
            force = self.coupling.step(
                activation,
                last_source_by_fiber=self.protocol.activation_model.last_applied_source,
                last_spike_time_s_by_fiber=(
                    self.protocol.activation_model.last_applied_spike_s
                ),
                feedback_trace_by_source=self.protocol.last_force_trace_by_source,
            )
            if force.active_fiber_count:
                all_traced = all_traced and (
                    force.feedback_driven_fiber_count
                    == force.active_fiber_count
                    == force.feedback_traced_fiber_count
                )
            for output in force.fibers.values():
                if (
                    output.activation > 0.0
                    and output.source_node_id in self.circuit.motor_source_ids
                    and output.feedback_sensor_node_id is not None
                    and output.feedback_sensor_node_id.startswith("field_sensory:")
                ):
                    steering_active_force_samples += 1
                    if (
                        output.feedback_body_state_time_s is not None
                        and output.feedback_sensor_spike_time_s is not None
                        and output.source_spike_time_s is not None
                        and output.feedback_body_state_time_s
                        <= output.feedback_sensor_spike_time_s
                        < output.source_spike_time_s
                        < time_s
                    ):
                        steering_traced_force_samples += 1
                        trace = self.protocol.last_force_trace_by_source.get(
                            output.source_node_id
                        )
                        if trace is not None:
                            side = str(trace["direction"]).removeprefix("steering_")
                            key = f"{side}:{trace['segment_id']}"
                            trace_examples.setdefault(key, trace)

            side_activation: dict[str, tuple[float, float]] = {}
            for segment in AXIAL_SEGMENTS:
                values = []
                for side in SIDES:
                    fibers = self.axial_fibers_by_channel[(segment, side)]
                    value = sum(
                        activation.activations[fiber_id] for fiber_id in fibers
                    ) / len(fibers)
                    values.append(value)
                    side_peaks[segment][side] = max(
                        side_peaks[segment][side], value
                    )
                side_activation[segment] = (values[0], values[1])
            self.body.set_bilateral_activations(side_activation)
            contact_activation = {
                segment: sum(
                    activation.activations[fiber_id]
                    for fiber_id in self.axial.contact_fiber_ids_by_segment[segment]
                )
                / len(self.axial.contact_fiber_ids_by_segment[segment])
                for segment in AXIAL_SEGMENTS
            }
            contact_activation["T3"] = self.protocol.t3_contact_proxy_activation
            active_gain = float(coupling["active_tension_gain_model_units"])
            local_tension_drive = {
                segment: sum(
                    force.fibers[fiber_id].active_tension_model_units / active_gain
                    for fiber_id in self.axial.axial_fiber_ids_by_segment[segment]
                )
                / len(self.axial.axial_fiber_ids_by_segment[segment])
                for segment in AXIAL_SEGMENTS
            }
            acceleration_scale = float(
                coupling["acceleration_scale_m_s2_per_model_force"]
            )
            accelerations = {}
            for index, raw_force in force.node_forces_model_units.items():
                tangent = self.body.node_tangent_xy(index)
                axial_force = tangent * raw_force.dot(tangent)
                accelerations[index] = axial_force * acceleration_scale
            last_retention, _ = self.axial._contact_retention(contact_activation)
            self.body.step(
                dt,
                gravity=Vec3(0.0, 0.0, -9.81),
                ground_z=0.0,
                external_accelerations_m_s2=accelerations,
                velocity_retention=float(coupling["body_velocity_retention"]),
                ground_velocity_retention_by_node=last_retention,
                active_curvature_gain=float(
                    self.config["parameters"]["active_curvature_gain"]
                ),
                passive_planar_bending_stiffness_ratio=float(
                    coupling["passive_planar_bending_stiffness_ratio"]
                ),
                iterations=int(contact["body_iterations"]),
            )
            center = self._center(self.body)
            movement = center - previous_center
            current_forward = self._anatomical_forward_xy(self.body)
            current_lateral = Vec3(-current_forward.y, current_forward.x, 0.0)
            integrated_slip += abs(movement.dot(current_lateral)) * 1e6
            previous_center = center
            relative = center - initial_center
            maximum_lateral = max(
                maximum_lateral, abs(relative.dot(initial_lateral)) * 1e6
            )
            minimum_field = min(
                minimum_field,
                field_sample.left_intensity,
                field_sample.right_intensity,
            )
            maximum_field = max(
                maximum_field,
                field_sample.left_intensity,
                field_sample.right_intensity,
            )
            maximum_contrast = max(
                maximum_contrast, abs(field_sample.signed_contrast)
            )
            minimum_retention = min(minimum_retention, *last_retention.values())
            maximum_retention = max(maximum_retention, *last_retention.values())
            extension, chord_ratio, local_bends = self._shape_metrics()
            maximum_extension = max(maximum_extension, extension)
            minimum_chord_ratio = min(minimum_chord_ratio, chord_ratio)
            maximum_bend = max(maximum_bend, *local_bends.values())
            for joint, bend in local_bends.items():
                integrated_local_bend[joint] += bend * dt
            if stride is not None and (
                (step + 1) % stride == 0 or step + 1 == steps
            ):
                samples.append(
                    trajectory_sample((step + 1) * dt, field_sample, side_activation)
                )

        final_center = self._center(self.body)
        displacement = final_center - initial_center
        final_forward = self._anatomical_forward_xy(self.body)
        final_heading = degrees(atan2(final_forward.y, final_forward.x))
        heading_change = (
            final_heading - initial_heading + 180.0
        ) % 360.0 - 180.0
        return AxialSteeringResult(
            model_id=self.config["model_id"],
            duration_s=steps * dt,
            field=dict(field.as_mapping()),
            displacement_x_um=displacement.x * 1e6,
            displacement_y_um=displacement.y * 1e6,
            anatomical_forward_displacement_um=(
                displacement.dot(initial_forward) * 1e6
            ),
            heading_change_deg=heading_change,
            maximum_abs_lateral_um=maximum_lateral,
            maximum_abs_field_contrast=maximum_contrast,
            field_sample_range=(minimum_field, maximum_field),
            side_peak_activation=side_peaks,
            steering_spike_counts={
                **self.circuit.spike_counts,
                **steering_motor_counts,
            },
            steering_first_spike_s={
                **self.circuit.first_spike_s,
                **steering_motor_first,
            },
            axial_spike_counts=dict(self.protocol.spike_counts),
            contact_retention_range=(minimum_retention, maximum_retention),
            all_active_forces_sensory_traced=all_traced,
            steering_active_force_samples=steering_active_force_samples,
            steering_traced_force_samples=steering_traced_force_samples,
            steering_causal_trace_examples=trace_examples,
            maximum_segment_extension_fraction=maximum_extension,
            minimum_head_tail_chord_ratio=minimum_chord_ratio,
            maximum_local_bend_deg=maximum_bend,
            integrated_local_bend_deg_s_by_joint=integrated_local_bend,
            integrated_lateral_slip_um=integrated_slip,
            trajectory_samples=tuple(samples),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gradient-y", type=float)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--trajectory-interval", type=float)
    args = parser.parse_args(argv)
    config = load_axial_steering_config()
    gradient = (
        float(config["parameters"]["default_lateral_gradient_per_m"])
        if args.gradient_y is None
        else args.gradient_y
    )
    field = PlanarLinearField(
        baseline=float(config["parameters"]["default_field_baseline"]),
        gradient_y_per_m=gradient,
    )
    result = AxialSteeringLarva(config).run(
        field,
        duration_s=args.duration,
        record_trajectory_interval_s=args.trajectory_interval,
    )
    summary = {
        "model_id": result.model_id,
        "duration_s": result.duration_s,
        "field": result.field,
        "displacement_x_um": result.displacement_x_um,
        "displacement_y_um": result.displacement_y_um,
        "anatomical_forward_displacement_um": (
            result.anatomical_forward_displacement_um
        ),
        "heading_change_deg": result.heading_change_deg,
        "all_active_forces_sensory_traced": (
            result.all_active_forces_sensory_traced
        ),
        "release_validated": result.release_validated,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
