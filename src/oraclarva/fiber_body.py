"""Map named-fiber attachment tensions onto shared ScientificBody3D nodes.

The coupling uses model-force units and a MODEL_FITTED acceleration conversion.
It does not claim newtons, CSA, Fmax, or measured attachment coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, isfinite, sin
from typing import Mapping

from .body3d import ContactSurface, ScientificBody3D, Vec3
from .body_sensing import BodyStateSensoryFrame, BodyStateSensoryTransducer
from .hemisegment import (
    BodyFixedCoordinate,
    derive_a1_left_attachment_geometry,
    load_a1_hemisegment_spec,
)
from .muscles import (
    NeuralMuscleActivationFrame,
    NeuralMuscleIdentityProjection,
    load_muscle_atlas,
)


@dataclass(frozen=True, slots=True)
class FullBodyFiberGeometry:
    fiber_id: str
    segment_id: str
    side: str
    muscle_number: str
    spatial_group: str
    origin: BodyFixedCoordinate
    insertion: BodyFixedCoordinate
    segment_index: int
    mapping_provenance: str
    coordinate_provenance: str = "ANATOMY_DERIVED"
    mirror_or_homology: str = "A1_left_reference"


@dataclass(frozen=True, slots=True)
class FiberForceOutput:
    fiber_id: str
    activation: float
    current_length_m: float
    rest_length_m: float
    length_rate_body_units_s: float
    active_tension_model_units: float
    passive_tension_model_units: float
    damping_tension_model_units: float
    total_tension_model_units: float
    source_node_id: str | None
    source_spike_time_s: float | None
    mapping_provenance: str
    coordinate_provenance: str = "ANATOMY_DERIVED"
    mechanics_provenance: str = "MODEL_FITTED"
    feedback_sensor_node_id: str | None = None
    feedback_sensor_spike_time_s: float | None = None
    feedback_body_state_time_s: float | None = None
    feedback_path_provenance: str | None = None


@dataclass(frozen=True, slots=True)
class NamedFiberBodyForceFrame:
    time_s: float
    fibers: Mapping[str, FiberForceOutput]
    node_forces_model_units: Mapping[int, Vec3]
    node_accelerations_m_s2: Mapping[int, Vec3]
    active_fiber_count: int
    traced_active_fiber_count: int
    feedback_driven_fiber_count: int = 0
    feedback_traced_fiber_count: int = 0
    mapped_fiber_count: int = 146
    unmapped_fiber_count: int = 212
    blocked_segments: tuple[str, ...] = ("A7",)
    parallel_fitted_bridge_executed: bool = False
    force_unit: str = "model_unit_not_newton"
    acceleration_parameter_provenance: str = "MODEL_FITTED"


@dataclass(slots=True)
class NamedFiberBodyCoupling:
    body: ScientificBody3D
    projection: NeuralMuscleIdentityProjection
    dt_s: float
    active_tension_gain: float
    passive_stiffness: float
    damping: float
    acceleration_scale_m_s2_per_model_force: float
    fiber_force_scale_by_id: Mapping[str, float] | None = None
    geometries: tuple[FullBodyFiberGeometry, ...] = field(init=False)
    rest_lengths_m: dict[str, float] = field(init=False)
    previous_lengths_m: dict[str, float] = field(init=False)
    _step_index: int = field(init=False, default=0, repr=False)

    def __post_init__(self) -> None:
        parameters = (
            self.dt_s,
            self.active_tension_gain,
            self.passive_stiffness,
            self.damping,
            self.acceleration_scale_m_s2_per_model_force,
        )
        if any(not isfinite(value) or value <= 0.0 for value in parameters):
            raise ValueError("named-fiber body coupling parameters must be positive")
        if len(self.projection.mappings) != 146:
            raise ValueError("body coupling requires exactly 146 mapped fibers")
        self.geometries = self._derive_geometries()
        if self.fiber_force_scale_by_id is not None:
            unknown = set(self.fiber_force_scale_by_id) - {
                item.fiber_id for item in self.geometries
            }
            if unknown:
                raise ValueError(
                    f"fiber force scale references unknown fibers: {sorted(unknown)}"
                )
            if any(
                not isfinite(float(value)) or float(value) <= 0.0
                for value in self.fiber_force_scale_by_id.values()
            ):
                raise ValueError("fiber force projection scales must be positive")
        self.rest_lengths_m = {}
        for geometry in self.geometries:
            origin, insertion = self._attachment_points(geometry)
            self.rest_lengths_m[geometry.fiber_id] = (insertion - origin).norm()
        if any(value <= 0.0 for value in self.rest_lengths_m.values()):
            raise ValueError("body attachment rest lengths must be positive")
        self.previous_lengths_m = dict(self.rest_lengths_m)

    def _derive_geometries(self) -> tuple[FullBodyFiberGeometry, ...]:
        atlas = load_muscle_atlas()
        base = {
            item.muscle_number: item
            for item in derive_a1_left_attachment_geometry(
                load_a1_hemisegment_spec(), atlas
            )
        }
        body_index = {
            geometry.id: index for index, geometry in enumerate(self.body.geometry)
        }
        result = []
        for mapping in self.projection.mappings:
            if mapping.segment_id not in {"A1", "A2", "A3", "A4", "A5", "A6"}:
                raise ValueError("mapped fiber outside supported A1-A6 body scope")
            reference = base[mapping.muscle_number]
            if mapping.side == "left":
                origin = reference.origin
                insertion = reference.insertion
            elif mapping.side == "right":
                origin = BodyFixedCoordinate(
                    reference.origin.s,
                    -reference.origin.theta_rad,
                    reference.origin.depth_fraction,
                )
                insertion = BodyFixedCoordinate(
                    reference.insertion.s,
                    -reference.insertion.theta_rad,
                    reference.insertion.depth_fraction,
                )
            else:
                raise ValueError("mapped fiber side must be left or right")
            result.append(
                FullBodyFiberGeometry(
                    fiber_id=mapping.fiber_id,
                    segment_id=mapping.segment_id,
                    side=mapping.side,
                    muscle_number=mapping.muscle_number,
                    spatial_group=reference.spatial_group,
                    origin=origin,
                    insertion=insertion,
                    segment_index=body_index[mapping.segment_id],
                    mapping_provenance=mapping.mapping_provenance,
                    mirror_or_homology=(
                        "A1_left_reference"
                        if mapping.segment_id == "A1" and mapping.side == "left"
                        else "bilateral_mirror"
                        if mapping.segment_id == "A1"
                        else "A2_A6_homology"
                        if mapping.side == "left"
                        else "A2_A6_homology_and_bilateral_mirror"
                    ),
                )
            )
        if len(result) != 146 or len({item.fiber_id for item in result}) != 146:
            raise ValueError("full-body coupling geometry must contain 146 fibers")
        return tuple(result)

    def _attachment_point(
        self,
        segment_index: int,
        coordinate: BodyFixedCoordinate,
    ) -> Vec3:
        left = self.body.particles[segment_index].position
        right = self.body.particles[segment_index + 1].position
        tangent = (right - left).normalized()
        up = Vec3(0.0, 0.0, 1.0)
        lateral = up.cross(tangent)
        if lateral.norm() < 1e-12:
            lateral = Vec3(0.0, 1.0, 0.0)
        else:
            lateral = lateral.normalized()
        dorsal = tangent.cross(lateral).normalized()
        center = left * (1.0 - coordinate.s) + right * coordinate.s
        radial = 1.0 - coordinate.depth_fraction
        segment = self.body.geometry[segment_index]
        return (
            center
            + lateral
            * (
                0.5
                * segment.width_m
                * radial
                * sin(coordinate.theta_rad)
            )
            + dorsal
            * (
                0.5
                * segment.height_m
                * radial
                * cos(coordinate.theta_rad)
            )
        )

    def _attachment_points(
        self, geometry: FullBodyFiberGeometry
    ) -> tuple[Vec3, Vec3]:
        return (
            self._attachment_point(geometry.segment_index, geometry.origin),
            self._attachment_point(geometry.segment_index, geometry.insertion),
        )

    @staticmethod
    def _add_force(forces: dict[int, Vec3], node: int, value: Vec3) -> None:
        forces[node] = forces[node] + value

    def step(
        self,
        frame: NeuralMuscleActivationFrame,
        *,
        last_source_by_fiber: Mapping[str, str | None],
        last_spike_time_s_by_fiber: Mapping[str, float | None],
        feedback_trace_by_source: Mapping[str, Mapping[str, object]] | None = None,
    ) -> NamedFiberBodyForceFrame:
        expected_time = self._step_index * self.dt_s
        if abs(frame.time_s - expected_time) > 1e-9:
            raise ValueError("fiber-body coupling must be stepped once per dt")
        node_forces = {
            index: Vec3(0.0, 0.0, 0.0)
            for index in range(len(self.body.particles))
        }
        outputs: dict[str, FiberForceOutput] = {}
        traced = 0
        feedback_driven = 0
        feedback_traced = 0
        feedback_traces = feedback_trace_by_source or {}
        for geometry in self.geometries:
            origin, insertion = self._attachment_points(geometry)
            delta = insertion - origin
            length = delta.norm()
            direction = delta.normalized()
            rest = self.rest_lengths_m[geometry.fiber_id]
            segment_length = self.body.geometry[
                geometry.segment_index
            ].rest_length_m
            length_rate = (
                (length - self.previous_lengths_m[geometry.fiber_id])
                / self.dt_s
                / segment_length
            )
            self.previous_lengths_m[geometry.fiber_id] = length
            activation = float(frame.activations[geometry.fiber_id])
            source = last_source_by_fiber.get(geometry.fiber_id)
            spike_time = last_spike_time_s_by_fiber.get(geometry.fiber_id)
            feedback_trace = None if source is None else feedback_traces.get(source)
            if (
                feedback_trace is not None
                and spike_time is not None
                and feedback_trace.get("motor_spike_time_s") != spike_time
            ):
                feedback_trace = None
            if activation > 0.0:
                if source is None or spike_time is None or not spike_time < frame.time_s:
                    raise ValueError("active body force lacks an earlier source spike")
                traced += 1
                if feedback_trace is not None:
                    feedback_driven += 1
                    sensory_spike = feedback_trace.get("sensor_spike_time_s")
                    body_state_time = feedback_trace.get("body_state_time_s")
                    motor_spike = feedback_trace.get("motor_spike_time_s")
                    if (
                        isinstance(sensory_spike, (int, float))
                        and isinstance(body_state_time, (int, float))
                        and isinstance(motor_spike, (int, float))
                        and body_state_time <= sensory_spike < motor_spike <= spike_time < frame.time_s
                    ):
                        feedback_traced += 1
                    else:
                        raise ValueError("feedback-driven force lacks ordered body/sensory/MN trace")
            active = self.active_tension_gain * activation
            extension = max(0.0, (length - rest) / segment_length)
            passive = self.passive_stiffness * extension
            damping = self.damping * length_rate
            total = max(0.0, active + passive + damping)
            projection_scale = (
                1.0
                if self.fiber_force_scale_by_id is None
                else float(
                    self.fiber_force_scale_by_id.get(geometry.fiber_id, 1.0)
                )
            )
            force = direction * (total * projection_scale)
            left_node = geometry.segment_index
            right_node = left_node + 1
            self._add_force(
                node_forces,
                left_node,
                force * (1.0 - geometry.origin.s),
            )
            self._add_force(node_forces, right_node, force * geometry.origin.s)
            self._add_force(
                node_forces,
                left_node,
                force * (-(1.0 - geometry.insertion.s)),
            )
            self._add_force(
                node_forces,
                right_node,
                force * (-geometry.insertion.s),
            )
            outputs[geometry.fiber_id] = FiberForceOutput(
                fiber_id=geometry.fiber_id,
                activation=activation,
                current_length_m=length,
                rest_length_m=rest,
                length_rate_body_units_s=length_rate,
                active_tension_model_units=active,
                passive_tension_model_units=passive,
                damping_tension_model_units=damping,
                total_tension_model_units=total,
                source_node_id=source,
                source_spike_time_s=spike_time,
                mapping_provenance=geometry.mapping_provenance,
                feedback_sensor_node_id=(
                    None if feedback_trace is None else str(feedback_trace["sensor_node_id"])
                ),
                feedback_sensor_spike_time_s=(
                    None if feedback_trace is None else float(feedback_trace["sensor_spike_time_s"])
                ),
                feedback_body_state_time_s=(
                    None if feedback_trace is None else float(feedback_trace["body_state_time_s"])
                ),
                feedback_path_provenance=(
                    None if feedback_trace is None else str(feedback_trace["path_provenance"])
                ),
            )
        accelerations = {
            node: force * self.acceleration_scale_m_s2_per_model_force
            for node, force in node_forces.items()
        }
        active_count = sum(item.activation > 0.0 for item in outputs.values())
        if traced != active_count:
            raise ValueError("every active fiber body force must be traced")
        self._step_index += 1
        return NamedFiberBodyForceFrame(
            time_s=frame.time_s,
            fibers=outputs,
            node_forces_model_units=node_forces,
            node_accelerations_m_s2=accelerations,
            active_fiber_count=active_count,
            traced_active_fiber_count=traced,
            feedback_driven_fiber_count=feedback_driven,
            feedback_traced_fiber_count=feedback_traced,
        )


class NamedFiberVisualBodyRunner:
    """Run the visual protocol and named-fiber forces on one shared body."""

    def __init__(
        self,
        protocol,
        parameters: Mapping[str, object],
        *,
        ground_z_m: float | None = None,
        contact_surface: ContactSurface | None = None,
    ) -> None:
        from .body import load_body_spec

        self.protocol = protocol
        self.parameters = parameters
        self.ground_z_m = ground_z_m
        self.contact_surface = contact_surface
        if ground_z_m is not None and contact_surface is not None:
            raise ValueError("provide either ground_z or a contact surface")
        self.body = ScientificBody3D(load_body_spec())
        self.coupling = NamedFiberBodyCoupling(
            body=self.body,
            projection=protocol.muscle_identity_projection,
            dt_s=float(parameters["dt_s"]),
            active_tension_gain=float(parameters["active_tension_gain_model_units"]),
            passive_stiffness=float(parameters["passive_stiffness_model_units"]),
            damping=float(parameters["damping_model_units"]),
            acceleration_scale_m_s2_per_model_force=float(
                parameters["acceleration_scale_m_s2_per_model_force"]
            ),
        )
        self.force_frames: list[NamedFiberBodyForceFrame] = []
        self.sensory_frames: list[BodyStateSensoryFrame] = []
        self._equilibrate()
        self.body_state_transducer = BodyStateSensoryTransducer(
            self.body,
            protocol.config["body_state_sensory_feedback"],
            ground_z_m=ground_z_m,
            contact_surface=contact_surface,
        )

    @staticmethod
    def _center(body: ScientificBody3D) -> tuple[float, float, float]:
        count = len(body.particles)
        return (
            sum(item.position.x for item in body.particles) / count,
            sum(item.position.y for item in body.particles) / count,
            sum(item.position.z for item in body.particles) / count,
        )

    @staticmethod
    def _yaw_pitch(body: ScientificBody3D) -> tuple[float, float]:
        from math import atan2, degrees, hypot

        axis = body.particles[-1].position - body.particles[0].position
        return (
            degrees(atan2(axis.y, axis.x)),
            degrees(atan2(axis.z, hypot(axis.x, axis.y))),
        )

    def _equilibrate(self) -> None:
        dt = float(self.parameters["dt_s"])
        gravity = (
            Vec3(0.0, 0.0, -9.81)
            if self.ground_z_m is not None or self.contact_surface is not None
            else Vec3(0.0, 0.0, 0.0)
        )
        for _ in range(50):
            self.body.step(
                dt,
                gravity=gravity,
                ground_z=self.ground_z_m,
                contact_surface=self.contact_surface,
                velocity_retention=float(self.parameters["body_velocity_retention"]),
                ground_velocity_retention_x=(
                    float(self.parameters["ground_negative_x_retention"]),
                    float(self.parameters["ground_positive_x_retention"]),
                ),
                use_local_tangent_friction=True,
            )
        for particle in self.body.particles:
            particle.previous_position = particle.position
        self.coupling = NamedFiberBodyCoupling(
            body=self.body,
            projection=self.protocol.muscle_identity_projection,
            dt_s=float(self.parameters["dt_s"]),
            active_tension_gain=float(self.parameters["active_tension_gain_model_units"]),
            passive_stiffness=float(self.parameters["passive_stiffness_model_units"]),
            damping=float(self.parameters["damping_model_units"]),
            acceleration_scale_m_s2_per_model_force=float(
                self.parameters["acceleration_scale_m_s2_per_model_force"]
            ),
        )

    def _segment_activation(self, frame: NamedFiberBodyForceFrame):
        sums = {
            (segment, side): 0.0
            for segment in ("A1", "A2", "A3", "A4", "A5", "A6")
            for side in ("left", "right")
        }
        counts = dict.fromkeys(sums, 0)
        for geometry in self.coupling.geometries:
            channel = (geometry.segment_id, geometry.side)
            sums[channel] += frame.fibers[geometry.fiber_id].activation
            counts[channel] += 1
        return {
            segment: tuple(
                sums[(segment, side)] / counts[(segment, side)]
                for side in ("left", "right")
            )
            for segment in ("A1", "A2", "A3", "A4", "A5", "A6")
        }

    def _sample(self, time_s, activation):
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
            "segment_activation_left": [
                round(activation.get(item.id, (0.0, 0.0))[0], 9)
                for item in self.body.geometry
            ],
            "segment_activation_right": [
                round(activation.get(item.id, (0.0, 0.0))[1], 9)
                for item in self.body.geometry
            ],
            "segment_activation_dorsal": [0.0 for _ in self.body.geometry],
            "segment_activation_ventral": [0.0 for _ in self.body.geometry],
        }

    def run(self, *, duration_s: float, record_trajectory_interval_s=None):
        from math import inf
        from .spatial import SpatialClosedLoopResult, SpatialSensoryState

        dt = float(self.parameters["dt_s"])
        steps = round(duration_s / dt)
        if steps <= 0:
            raise ValueError("duration must span at least one step")
        stride = (
            None
            if record_trajectory_interval_s is None
            else max(1, round(record_trajectory_interval_s / dt))
        )
        initial_center = self._center(self.body)
        initial_yaw, initial_pitch = self._yaw_pitch(self.body)
        initial_height = self.body.particles[0].position.z
        samples = []
        peak = {
            segment: {"left": 0.0, "right": 0.0, "dorsal": 0.0, "ventral": 0.0}
            for segment in ("A1", "A2", "A3", "A4", "A5", "A6")
        }
        minimum_pitch = minimum_height = inf
        maximum_pitch = maximum_height = -inf
        if stride is not None:
            samples.append(self._sample(0.0, {}))
        for step in range(steps):
            time_s = step * dt
            body_sensory_frame = self.body_state_transducer.sample(time_s)
            self.sensory_frames.append(body_sensory_frame)
            activation_frame = self.protocol(
                time_s,
                SpatialSensoryState.from_body(self.body),
                body_sensory_frame,
            )
            force_frame = self.coupling.step(
                activation_frame,
                last_source_by_fiber=(
                    self.protocol.muscle_activation_model.last_applied_source
                ),
                last_spike_time_s_by_fiber=(
                    self.protocol.muscle_activation_model.last_applied_spike_s
                ),
                feedback_trace_by_source=(
                    self.protocol.last_body_feedback_trace_by_source
                ),
            )
            self.force_frames.append(force_frame)
            activation = self._segment_activation(force_frame)
            for segment, pair in activation.items():
                peak[segment]["left"] = max(peak[segment]["left"], pair[0])
                peak[segment]["right"] = max(peak[segment]["right"], pair[1])
            self.body.step(
                dt,
                gravity=(
                    Vec3(0.0, 0.0, -9.81)
                    if self.ground_z_m is not None or self.contact_surface is not None
                    else Vec3(0.0, 0.0, 0.0)
                ),
                ground_z=self.ground_z_m,
                contact_surface=self.contact_surface,
                velocity_retention=float(self.parameters["body_velocity_retention"]),
                ground_velocity_retention_x=(
                    float(self.parameters["ground_negative_x_retention"]),
                    float(self.parameters["ground_positive_x_retention"]),
                ),
                use_local_tangent_friction=True,
                external_accelerations_m_s2=force_frame.node_accelerations_m_s2,
            )
            _, pitch = self._yaw_pitch(self.body)
            height = (self.body.particles[0].position.z - initial_height) * 1e6
            pitch_change = -(pitch - initial_pitch)
            minimum_pitch = min(minimum_pitch, pitch_change)
            maximum_pitch = max(maximum_pitch, pitch_change)
            minimum_height = min(minimum_height, height)
            maximum_height = max(maximum_height, height)
            if stride is not None and (
                (step + 1) % stride == 0 or step + 1 == steps
            ):
                samples.append(self._sample((step + 1) * dt, activation))
        final_center = self._center(self.body)
        final_yaw, final_pitch = self._yaw_pitch(self.body)
        yaw_change = (final_yaw - initial_yaw + 180.0) % 360.0 - 180.0
        return SpatialClosedLoopResult(
            model_id="dmel_l1_named_fiber_body_v0",
            status="research_approximation",
            neuron_count=0,
            synapse_count=0,
            duration_s=steps * dt,
            displacement_x_um=(final_center[0] - initial_center[0]) * 1e6,
            displacement_y_um=(final_center[1] - initial_center[1]) * 1e6,
            displacement_z_um=(final_center[2] - initial_center[2]) * 1e6,
            yaw_change_deg=yaw_change,
            head_pitch_change_deg=-(final_pitch - initial_pitch),
            minimum_head_pitch_deg=minimum_pitch if minimum_pitch != inf else 0.0,
            maximum_head_pitch_deg=maximum_pitch if maximum_pitch != -inf else 0.0,
            minimum_head_height_um=minimum_height if minimum_height != inf else 0.0,
            maximum_head_height_um=maximum_height if maximum_height != -inf else 0.0,
            spike_counts={},
            first_spike_s={},
            peak_activation=peak,
            peak_yaw_recruited_fibers=max(
                (frame.active_fiber_count for frame in self.force_frames),
                default=0,
            ),
            peak_pitch_recruited_fibers=0,
            trajectory_samples=tuple(samples),
            trajectory_sample_interval_s=(
                None if stride is None else stride * dt
            ),
            premotor_lesion=None,
            muscle_lesion=None,
        )
