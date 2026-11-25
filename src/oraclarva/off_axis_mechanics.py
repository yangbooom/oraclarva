"""Named-fiber off-axis generalized loads for oriented body sections.

This module is the mechanics boundary between named muscle tension and the
reduced oriented-section rod. It intentionally exposes no crawl, turn,
heading, curvature, or authored-translation command.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Mapping

from .body3d import Vec3
from .fiber_body import (
    DifferentialAttachmentForceFrame,
    FullBodyFiberGeometry,
    NamedFiberBodyCoupling,
    NamedFiberBodyForceFrame,
)
from .hemisegment import BodyFixedCoordinate
from .oriented_body import OrientedScientificBody3D


@dataclass(frozen=True, slots=True)
class OffAxisApplication:
    fiber_id: str
    endpoint: str
    point_m: Vec3
    force_model_units: Vec3
    segment_index: int
    coordinate_s: float
    radial_arm_m: Vec3
    source_node_id: str
    source_spike_time_s: float
    coordinate_provenance: str = "ANATOMY_DERIVED"
    mechanics_provenance: str = "MODEL_FITTED"


@dataclass(frozen=True, slots=True)
class GeneralizedAttachmentLoadFrame:
    time_s: float
    excess_tension_model_units_by_fiber: Mapping[str, float]
    replaced_axial_source_forces_model_units: Mapping[int, Vec3]
    centerline_forces_model_units: Mapping[int, Vec3]
    section_torques_model_units_m: Mapping[int, Vec3]
    applications: tuple[OffAxisApplication, ...]
    active_fiber_count: int
    traced_active_fiber_count: int
    net_force_model_units: Vec3
    centerline_force_moment_model_units_m: Vec3
    net_generalized_torque_model_units_m: Vec3
    force_unit: str = "model_unit_not_newton"
    coordinate_provenance: str = "ANATOMY_DERIVED"
    mechanics_provenance: str = "MODEL_FITTED"


class OrientedNamedFiberBodyCoupling(NamedFiberBodyCoupling):
    """Named-fiber coupling that retains off-axis section torque."""

    body: OrientedScientificBody3D

    def __post_init__(self) -> None:
        if not isinstance(self.body, OrientedScientificBody3D):
            raise TypeError("oriented coupling requires OrientedScientificBody3D")
        super().__post_init__()

    def _attachment_point(
        self,
        segment_index: int,
        coordinate: BodyFixedCoordinate,
    ) -> Vec3:
        return self.body.material_attachment_point(
            segment_index,
            coordinate,
            self.body.geometry[segment_index],
        )

    @staticmethod
    def _zero_nodes(body: OrientedScientificBody3D) -> dict[int, Vec3]:
        return {
            index: Vec3(0.0, 0.0, 0.0)
            for index in range(len(body.particles))
        }

    @staticmethod
    def _accumulate(
        values: dict[int, Vec3], node: int, contribution: Vec3
    ) -> None:
        values[node] = values[node] + contribution

    def _apply_endpoint(
        self,
        *,
        geometry: FullBodyFiberGeometry,
        coordinate: BodyFixedCoordinate,
        endpoint: str,
        point: Vec3,
        force: Vec3,
        source_node_id: str,
        source_spike_time_s: float,
        centerline_forces: dict[int, Vec3],
        section_torques: dict[int, Vec3],
    ) -> OffAxisApplication:
        left_node = geometry.segment_index
        right_node = left_node + 1
        center = (
            self.body.particles[left_node].position * (1.0 - coordinate.s)
            + self.body.particles[right_node].position * coordinate.s
        )
        radial_arm = point - center
        point_torque = radial_arm.cross(force)
        for node, weight in (
            (left_node, 1.0 - coordinate.s),
            (right_node, coordinate.s),
        ):
            self._accumulate(centerline_forces, node, force * weight)
            self._accumulate(section_torques, node, point_torque * weight)
        return OffAxisApplication(
            fiber_id=geometry.fiber_id,
            endpoint=endpoint,
            point_m=point,
            force_model_units=force,
            segment_index=geometry.segment_index,
            coordinate_s=coordinate.s,
            radial_arm_m=radial_arm,
            source_node_id=source_node_id,
            source_spike_time_s=source_spike_time_s,
        )

    def paired_generalized_active_excess_loads(
        self,
        frame: NamedFiberBodyForceFrame,
        fiber_pairs: Iterable[tuple[str, str]],
        *,
        spatial_force_scale: float,
        lesioned_fiber_ids: Iterable[str] = (),
    ) -> GeneralizedAttachmentLoadFrame:
        """Map stronger-side active excess into a balanced generalized load."""

        if (
            not isfinite(float(spatial_force_scale))
            or float(spatial_force_scale) <= 0.0
        ):
            raise ValueError("spatial attachment force scale must be positive")
        pairs = tuple(fiber_pairs)
        if len(pairs) != len(set(pairs)):
            raise ValueError("attachment fiber pairs must be unique")
        geometry_by_id = {item.fiber_id: item for item in self.geometries}
        lesions = tuple(lesioned_fiber_ids)
        if len(lesions) != len(set(lesions)):
            raise ValueError("attachment fiber lesions must be unique")
        unknown = set(lesions) - set(geometry_by_id)
        if unknown:
            raise ValueError(
                f"attachment lesion references unknown fibers: {sorted(unknown)}"
            )
        lesioned = set(lesions)
        replaced = self._zero_nodes(self.body)
        centerline = self._zero_nodes(self.body)
        torques = self._zero_nodes(self.body)
        excess_by_fiber: dict[str, float] = {}
        applications: list[OffAxisApplication] = []
        traced = 0

        for left_id, right_id in pairs:
            if left_id not in geometry_by_id or right_id not in geometry_by_id:
                raise ValueError("attachment pair references unknown fiber")
            left_geometry = geometry_by_id[left_id]
            right_geometry = geometry_by_id[right_id]
            if (
                left_geometry.side != "left"
                or right_geometry.side != "right"
                or left_geometry.segment_id != right_geometry.segment_id
                or left_geometry.muscle_number != right_geometry.muscle_number
            ):
                raise ValueError("attachment pair must be a mirrored identity")
            left_output = frame.fibers[left_id]
            right_output = frame.fibers[right_id]
            difference = (
                left_output.active_tension_model_units
                - right_output.active_tension_model_units
            )
            if difference == 0.0:
                continue
            if difference > 0.0:
                geometry = left_geometry
                output = left_output
            else:
                geometry = right_geometry
                output = right_output
            if geometry.fiber_id in lesioned:
                continue
            if (
                output.source_node_id is None
                or output.source_spike_time_s is None
                or not output.source_spike_time_s < frame.time_s
            ):
                raise ValueError(
                    "differential attachment load lacks an earlier MN spike"
                )
            traced += 1
            excess = abs(difference)
            excess_by_fiber[geometry.fiber_id] = excess
            origin, insertion = self._attachment_points(geometry)
            line_direction = (insertion - origin).normalized()
            projection_scale = (
                1.0
                if self.fiber_force_scale_by_id is None
                else float(
                    self.fiber_force_scale_by_id.get(geometry.fiber_id, 1.0)
                )
            )
            replacement_force = line_direction * (excess * projection_scale)
            for coordinate, signed_force in (
                (geometry.origin, replacement_force),
                (geometry.insertion, replacement_force * -1.0),
            ):
                for node, weight in (
                    (geometry.segment_index, 1.0 - coordinate.s),
                    (geometry.segment_index + 1, coordinate.s),
                ):
                    self._accumulate(replaced, node, signed_force * weight)

            spatial_force = line_direction * (
                excess * float(spatial_force_scale)
            )
            applications.append(
                self._apply_endpoint(
                    geometry=geometry,
                    coordinate=geometry.origin,
                    endpoint="origin",
                    point=origin,
                    force=spatial_force,
                    source_node_id=output.source_node_id,
                    source_spike_time_s=output.source_spike_time_s,
                    centerline_forces=centerline,
                    section_torques=torques,
                )
            )
            applications.append(
                self._apply_endpoint(
                    geometry=geometry,
                    coordinate=geometry.insertion,
                    endpoint="insertion",
                    point=insertion,
                    force=spatial_force * -1.0,
                    source_node_id=output.source_node_id,
                    source_spike_time_s=output.source_spike_time_s,
                    centerline_forces=centerline,
                    section_torques=torques,
                )
            )

        center = Vec3(0.0, 0.0, 0.0)
        for particle in self.body.particles:
            center = center + particle.position
        center = center * (1.0 / len(self.body.particles))
        net_force = Vec3(0.0, 0.0, 0.0)
        centerline_moment = Vec3(0.0, 0.0, 0.0)
        section_torque_sum = Vec3(0.0, 0.0, 0.0)
        for node, value in centerline.items():
            net_force = net_force + value
            arm = self.body.particles[node].position - center
            centerline_moment = centerline_moment + arm.cross(value)
            section_torque_sum = section_torque_sum + torques[node]
        generalized_torque = centerline_moment + section_torque_sum
        if traced != len(excess_by_fiber):
            raise ValueError("every off-axis attachment load must be traced")
        return GeneralizedAttachmentLoadFrame(
            time_s=frame.time_s,
            excess_tension_model_units_by_fiber=excess_by_fiber,
            replaced_axial_source_forces_model_units=replaced,
            centerline_forces_model_units=centerline,
            section_torques_model_units_m=torques,
            applications=tuple(applications),
            active_fiber_count=len(excess_by_fiber),
            traced_active_fiber_count=traced,
            net_force_model_units=net_force,
            centerline_force_moment_model_units_m=centerline_moment,
            net_generalized_torque_model_units_m=generalized_torque,
        )

    def advance_body(
        self,
        load: GeneralizedAttachmentLoadFrame,
        *,
        spatial_force_scale_to_acceleration: float,
        twist_torque_scale_rad_s2_per_model_torque: float,
        twist_velocity_retention: float,
        twist_stiffness_model_units_m_per_rad: float,
        iterations: int = 12,
    ) -> None:
        """Advance the free-space mechanics fixture by one coupling time step."""

        if spatial_force_scale_to_acceleration <= 0.0:
            raise ValueError("force-to-acceleration scale must be positive")
        movable_inverse_masses = [
            particle.inverse_mass
            for particle in self.body.particles
            if particle.inverse_mass > 0.0
        ]
        reference_inverse_mass = (
            sum(movable_inverse_masses) / len(movable_inverse_masses)
        )
        accelerations = {
            node: value
            * spatial_force_scale_to_acceleration
            * (self.body.particles[node].inverse_mass / reference_inverse_mass)
            for node, value in load.centerline_forces_model_units.items()
        }
        self.body.step(
            self.dt_s,
            gravity=Vec3(0.0, 0.0, 0.0),
            ground_z=None,
            external_accelerations_m_s2=accelerations,
            external_section_torques_model_units_m=(
                load.section_torques_model_units_m
            ),
            twist_torque_scale_rad_s2_per_model_torque=(
                twist_torque_scale_rad_s2_per_model_torque
            ),
            twist_velocity_retention=twist_velocity_retention,
            twist_stiffness_model_units_m_per_rad=(
                twist_stiffness_model_units_m_per_rad
            ),
            velocity_retention=1.0,
            iterations=iterations,
        )

    def paired_active_excess_forces(
        self,
        frame: NamedFiberBodyForceFrame,
        fiber_pairs: Iterable[tuple[str, str]],
        *,
        spatial_force_scale: float,
        lesioned_fiber_ids: Iterable[str] = (),
    ) -> DifferentialAttachmentForceFrame:
        """Keep the v1 API unavailable here to prevent torque loss by accident."""

        del frame, fiber_pairs, spatial_force_scale, lesioned_fiber_ids
        raise RuntimeError(
            "oriented mechanics requires paired_generalized_active_excess_loads"
        )
