"""Reduced oriented-cross-section rod state for off-axis muscle loads.

The existing :class:`ScientificBody3D` centerline remains the translational
solver.  This module adds one material cross-section at every centerline node.
The section tangent follows the centerline (the unshearable rod assumption),
while a dynamic twist degree of freedom rotates its lateral/dorsal directors.

All angular parameters are MODEL_FITTED engineering quantities.  The module
does not claim measured L1 torsional stiffness, inertia, pressure, or cuticle
material constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, degrees, isfinite, pi, sin
from typing import Mapping

from .body import BodyModelSpec, SegmentGeometry
from .body3d import ScientificBody3D, Vec3
from .hemisegment import BodyFixedCoordinate


@dataclass(frozen=True, slots=True)
class MaterialFrame:
    """Right-handed frame attached to a body cross-section."""

    tangent: Vec3
    lateral: Vec3
    dorsal: Vec3

    def validate(self, tolerance: float = 1e-9) -> None:
        axes = (self.tangent, self.lateral, self.dorsal)
        if any(abs(axis.norm() - 1.0) > tolerance for axis in axes):
            raise ValueError("material-frame axes must be unit length")
        if any(
            abs(left.dot(right)) > tolerance
            for left, right in (
                (self.tangent, self.lateral),
                (self.tangent, self.dorsal),
                (self.lateral, self.dorsal),
            )
        ):
            raise ValueError("material-frame axes must be orthogonal")
        if (self.tangent.cross(self.lateral) - self.dorsal).norm() > tolerance:
            raise ValueError("material frame must be right handed")


@dataclass(slots=True)
class OrientedSectionState:
    """Independent torsional state around a centerline-constrained tangent."""

    reference_lateral: Vec3
    reference_dorsal: Vec3
    twist_angle_rad: float = 0.0
    twist_velocity_rad_s: float = 0.0


def _rotate(vector: Vec3, axis: Vec3, angle_rad: float) -> Vec3:
    """Rotate a vector with Rodrigues' formula."""

    axis = axis.normalized()
    cosine = cos(angle_rad)
    sine = sin(angle_rad)
    return (
        vector * cosine
        + axis.cross(vector) * sine
        + axis * (axis.dot(vector) * (1.0 - cosine))
    )


def _transport(vector: Vec3, old_tangent: Vec3, new_tangent: Vec3) -> Vec3:
    """Parallel-transport ``vector`` through the shortest tangent rotation."""

    old_tangent = old_tangent.normalized()
    new_tangent = new_tangent.normalized()
    axis = old_tangent.cross(new_tangent)
    sine = axis.norm()
    cosine = max(-1.0, min(1.0, old_tangent.dot(new_tangent)))
    if sine <= 1e-15:
        if cosine >= 0.0:
            transported = vector
        else:
            fallback = old_tangent.cross(Vec3(0.0, 0.0, 1.0))
            if fallback.norm() <= 1e-15:
                fallback = old_tangent.cross(Vec3(0.0, 1.0, 0.0))
            transported = _rotate(vector, fallback, pi)
    else:
        # atan2 is avoided here because Rodrigues can use normalized axis and
        # the angle reconstructed from a numerically stable acos equivalent.
        from math import atan2

        transported = _rotate(vector, axis, atan2(sine, cosine))
    # Remove accumulated floating-point shear before returning the director.
    projected = transported - new_tangent * transported.dot(new_tangent)
    if projected.norm() <= 1e-15:
        raise ValueError("material director collapsed during parallel transport")
    return projected.normalized()


class OrientedScientificBody3D(ScientificBody3D):
    """ScientificBody3D plus unshearable material sections and torsion.

    Bending remains represented by the centerline particles.  Cross-section
    twist is integrated from the axial component of supplied section torque;
    neighboring sections exchange equal-and-opposite fitted torsional torque.
    """

    orientation_model = "unshearable_oriented_cross_section_rod_v2"
    orientation_provenance = "MODEL_FITTED"

    def __init__(
        self,
        spec: BodyModelSpec,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(spec, *args, **kwargs)
        self.sections: list[OrientedSectionState] = []
        self._section_tangents: list[Vec3] = []
        self.maximum_abs_twist_rad = 0.0
        self.maximum_abs_twist_gradient_rad = 0.0
        self.reset_material_frames_from_centerline()

    def reset_material_frames_from_centerline(self) -> None:
        """Rebuild zero-twist frames after initialization/equilibration."""

        self.sections = []
        self._section_tangents = []
        previous_lateral: Vec3 | None = None
        previous_tangent: Vec3 | None = None
        for index in range(len(self.particles)):
            tangent = self._node_tangent_3d(index)
            if previous_lateral is None or previous_tangent is None:
                lateral = Vec3(0.0, 0.0, 1.0).cross(tangent)
                if lateral.norm() <= 1e-15:
                    lateral = Vec3(0.0, 1.0, 0.0)
                else:
                    lateral = lateral.normalized()
            else:
                lateral = _transport(previous_lateral, previous_tangent, tangent)
            dorsal = tangent.cross(lateral).normalized()
            self.sections.append(OrientedSectionState(lateral, dorsal))
            self._section_tangents.append(tangent)
            previous_lateral = lateral
            previous_tangent = tangent
        self.maximum_abs_twist_rad = 0.0
        self.maximum_abs_twist_gradient_rad = 0.0

    def material_frame(self, node_index: int) -> MaterialFrame:
        if not 0 <= node_index < len(self.sections):
            raise IndexError("material section index out of range")
        state = self.sections[node_index]
        tangent = self._section_tangents[node_index]
        cosine = cos(state.twist_angle_rad)
        sine = sin(state.twist_angle_rad)
        lateral = (
            state.reference_lateral * cosine
            + state.reference_dorsal * sine
        ).normalized()
        dorsal = tangent.cross(lateral).normalized()
        frame = MaterialFrame(tangent, lateral, dorsal)
        frame.validate(tolerance=1e-7)
        return frame

    def material_attachment_point(
        self,
        segment_index: int,
        coordinate: BodyFixedCoordinate,
        segment: SegmentGeometry,
    ) -> Vec3:
        """Evaluate a normalized attachment on oriented endpoint sections."""

        if not 0 <= segment_index < len(self.geometry):
            raise IndexError("attachment segment index out of range")
        if not 0.0 <= coordinate.s <= 1.0:
            raise ValueError("attachment axial coordinate must be in [0, 1]")
        radial = 1.0 - coordinate.depth_fraction
        lateral_radius = (
            0.5 * segment.width_m * radial * sin(coordinate.theta_rad)
        )
        dorsal_radius = (
            0.5 * segment.height_m * radial * cos(coordinate.theta_rad)
        )
        surface_points = []
        for node in (segment_index, segment_index + 1):
            frame = self.material_frame(node)
            surface_points.append(
                self.particles[node].position
                + frame.lateral * lateral_radius
                + frame.dorsal * dorsal_radius
            )
        return (
            surface_points[0] * (1.0 - coordinate.s)
            + surface_points[1] * coordinate.s
        )

    @property
    def twist_angles_rad(self) -> tuple[float, ...]:
        return tuple(section.twist_angle_rad for section in self.sections)

    @property
    def twist_angles_deg(self) -> tuple[float, ...]:
        return tuple(degrees(value) for value in self.twist_angles_rad)

    def _transport_sections_after_centerline_step(
        self, old_tangents: tuple[Vec3, ...]
    ) -> None:
        for index, (state, old_tangent) in enumerate(
            zip(self.sections, old_tangents, strict=True)
        ):
            new_tangent = self._node_tangent_3d(index)
            lateral = _transport(
                state.reference_lateral, old_tangent, new_tangent
            )
            state.reference_lateral = lateral
            state.reference_dorsal = new_tangent.cross(lateral).normalized()
            self._section_tangents[index] = new_tangent

    def step(
        self,
        dt_s: float,
        *,
        external_section_torques_model_units_m: Mapping[int, Vec3] | None = None,
        twist_torque_scale_rad_s2_per_model_torque: float = 0.0,
        twist_velocity_retention: float = 1.0,
        twist_stiffness_model_units_m_per_rad: float = 0.0,
        **kwargs,
    ) -> None:
        torques = external_section_torques_model_units_m or {}
        known = set(range(len(self.sections)))
        if set(torques) - known:
            raise ValueError("section torque references an unknown body node")
        values = (
            twist_torque_scale_rad_s2_per_model_torque,
            twist_velocity_retention,
            twist_stiffness_model_units_m_per_rad,
        )
        if any(not isfinite(float(value)) for value in values):
            raise ValueError("oriented-section parameters must be finite")
        if twist_torque_scale_rad_s2_per_model_torque < 0.0:
            raise ValueError("twist torque scale must be non-negative")
        if not 0.0 <= twist_velocity_retention <= 1.0:
            raise ValueError("twist velocity retention must be in [0, 1]")
        if twist_stiffness_model_units_m_per_rad < 0.0:
            raise ValueError("twist stiffness must be non-negative")
        if any(
            not all(isfinite(component) for component in (value.x, value.y, value.z))
            for value in torques.values()
        ):
            raise ValueError("section torque must be finite")

        old_tangents = tuple(self._section_tangents)
        angles = self.twist_angles_rad
        elastic_torque = [0.0] * len(self.sections)
        for index in range(len(self.sections) - 1):
            difference = angles[index + 1] - angles[index]
            exchange = twist_stiffness_model_units_m_per_rad * difference
            elastic_torque[index] += exchange
            elastic_torque[index + 1] -= exchange
        for index, state in enumerate(self.sections):
            applied = torques.get(index, Vec3(0.0, 0.0, 0.0)).dot(
                self._section_tangents[index]
            )
            angular_acceleration = (
                applied + elastic_torque[index]
            ) * twist_torque_scale_rad_s2_per_model_torque
            state.twist_velocity_rad_s = (
                state.twist_velocity_rad_s * twist_velocity_retention
                + angular_acceleration * dt_s
            )
            state.twist_angle_rad += state.twist_velocity_rad_s * dt_s

        super().step(dt_s, **kwargs)
        self._transport_sections_after_centerline_step(old_tangents)
        self.maximum_abs_twist_rad = max(
            self.maximum_abs_twist_rad,
            *(abs(value) for value in self.twist_angles_rad),
        )
        if len(self.sections) > 1:
            self.maximum_abs_twist_gradient_rad = max(
                self.maximum_abs_twist_gradient_rad,
                *(
                    abs(self.sections[index + 1].twist_angle_rad
                        - self.sections[index].twist_angle_rad)
                    for index in range(len(self.sections) - 1)
                ),
            )
