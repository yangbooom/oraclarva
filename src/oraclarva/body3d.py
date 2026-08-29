"""Minimal 3D XPBD reference body driven only by per-segment muscle activation.

This is a numerical and integration fixture, not a finished biomechanical model.
Geometry and mechanics come from the provenance-aware body specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt
from typing import Iterable, Mapping

from .body import BodyModelSpec, SegmentGeometry


@dataclass(frozen=True, slots=True)
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def norm(self) -> float:
        return sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def normalized(self) -> "Vec3":
        magnitude = self.norm()
        return Vec3(1.0, 0.0, 0.0) if magnitude == 0 else self * (1.0 / magnitude)


@dataclass(slots=True)
class Particle:
    position: Vec3
    previous_position: Vec3
    inverse_mass: float


class ScientificBody3D:
    """Axial 3D body using stable compliant length constraints.

    The body has no crawl/turn action methods. Neural or test code can supply
    only continuous segment activations in [0, 1].
    """

    def __init__(
        self,
        spec: BodyModelSpec,
        pinned_nodes: Iterable[int] = (),
        *,
        maximum_shortening_by_segment: Mapping[str, float] | None = None,
    ) -> None:
        self.spec = spec
        self.geometry: tuple[SegmentGeometry, ...] = spec.segment_geometry()
        self.pinned_nodes = set(pinned_nodes)
        self.activations = [0.0] * len(self.geometry)
        self.left_activations = [0.0] * len(self.geometry)
        self.right_activations = [0.0] * len(self.geometry)
        shortening_overrides = maximum_shortening_by_segment or {}
        known_segments = {segment.id for segment in self.geometry}
        unknown_segments = set(shortening_overrides) - known_segments
        if unknown_segments:
            raise KeyError(
                f"unknown segment shortening capacities: {sorted(unknown_segments)}"
            )
        upper = spec.maximum_shortening_fraction.upper
        if any(
            not 0.0 <= float(value) <= upper
            for value in shortening_overrides.values()
        ):
            raise ValueError(
                "segment shortening capacity must be non-negative and no greater "
                "than the declared body-model upper bound"
            )
        self.maximum_shortening_fractions = [
            float(
                shortening_overrides.get(
                    segment.id, spec.maximum_shortening_fraction.nominal
                )
            )
            for segment in self.geometry
        ]
        self._instantaneous_stiffness = spec.scaled_mechanics().instantaneous_stiffness_n_per_m
        node_masses = [0.0] * (len(self.geometry) + 1)
        for index, segment in enumerate(self.geometry):
            node_masses[index] += segment.mass_kg / 2
            node_masses[index + 1] += segment.mass_kg / 2

        clearances = [self._node_clearance(index) for index in range(len(node_masses))]
        x = 0.0
        self.particles: list[Particle] = []
        for index, mass in enumerate(node_masses):
            clearance = clearances[index]
            position = Vec3(x, 0.0, clearance)
            self.particles.append(
                Particle(
                    position=position,
                    previous_position=position,
                    inverse_mass=0.0 if index in self.pinned_nodes else 1.0 / mass,
                )
            )
            if index < len(self.geometry):
                vertical_delta = clearances[index + 1] - clearance
                rest_length = self.geometry[index].rest_length_m
                if abs(vertical_delta) >= rest_length:
                    raise ValueError("cross-section profile is too steep for segment rest length")
                x += sqrt(rest_length * rest_length - vertical_delta * vertical_delta)

    def set_activations(self, activations: Mapping[str, float]) -> None:
        by_id = {segment.id: index for index, segment in enumerate(self.geometry)}
        for segment_id, activation in activations.items():
            if segment_id not in by_id:
                raise KeyError(f"unknown segment {segment_id}")
            if not 0.0 <= activation <= 1.0:
                raise ValueError("muscle activation must be in [0, 1]")
            self.activations[by_id[segment_id]] = float(activation)
            self.left_activations[by_id[segment_id]] = float(activation)
            self.right_activations[by_id[segment_id]] = float(activation)

    def set_bilateral_activations(
        self,
        activations: Mapping[str, tuple[float, float]],
    ) -> None:
        """Set left/right continuous muscle activation for active-curvature physics."""
        by_id = {segment.id: index for index, segment in enumerate(self.geometry)}
        for segment_id, pair in activations.items():
            if segment_id not in by_id:
                raise KeyError(f"unknown segment {segment_id}")
            if len(pair) != 2:
                raise ValueError("bilateral activation requires a left/right pair")
            left, right = (float(value) for value in pair)
            if not 0.0 <= left <= 1.0 or not 0.0 <= right <= 1.0:
                raise ValueError("bilateral muscle activation must be in [0, 1]")
            index = by_id[segment_id]
            self.left_activations[index] = left
            self.right_activations[index] = right
            self.activations[index] = (left + right) / 2.0

    def target_length_m(self, index: int) -> float:
        shortening = (
            self.maximum_shortening_fractions[index] * self.activations[index]
        )
        return self.geometry[index].rest_length_m * (1.0 - shortening)

    def segment_length_m(self, index: int) -> float:
        return (self.particles[index + 1].position - self.particles[index].position).norm()

    def bilateral_segment_length_m(self, index: int, side: str) -> float:
        """Length of a virtual left/right muscle rail around the centerline."""
        if side not in {"left", "right"}:
            raise ValueError("side must be left or right")
        sign = -1.0 if side == "left" else 1.0
        left = self._side_node_position(index, sign)
        right = self._side_node_position(index + 1, sign)
        return (right - left).norm()

    def cross_section_scale(self, index: int) -> float:
        """Whole-cavity volume approximation shared by every body region.

        Drosophila abdominal regions are not sealed by intersegmental septa. The
        v0 model therefore preserves the aggregate body-cavity volume rather
        than forcing every mechanical region to preserve its own volume.
        ``index`` remains part of the API for render-core compatibility.
        """
        if not 0 <= index < len(self.geometry):
            raise IndexError("segment index out of range")
        rest_volume = sum(segment.volume_m3 for segment in self.geometry)
        reference_volume = 0.0
        for segment_index, segment in enumerate(self.geometry):
            current_length = self.segment_length_m(segment_index)
            if current_length <= 0:
                raise ValueError("segment collapsed to zero length")
            reference_volume += (
                pi * (segment.width_m / 2) * (segment.height_m / 2) * current_length
            )
        return sqrt(rest_volume / reference_volume)

    def current_width_m(self, index: int) -> float:
        return self.geometry[index].width_m * self.cross_section_scale(index)

    def current_height_m(self, index: int) -> float:
        return self.geometry[index].height_m * self.cross_section_scale(index)

    def step(
        self,
        dt_s: float,
        *,
        gravity: Vec3 = Vec3(0.0, 0.0, -9.81),
        ground_z: float | None = 0.0,
        iterations: int = 12,
        velocity_retention: float = 0.98,
        ground_velocity_retention_x: tuple[float, float] | None = None,
        active_curvature_gain: float = 0.0,
        active_bending_stiffness_ratio: float = 0.25,
        use_local_tangent_friction: bool = False,
    ) -> None:
        if dt_s <= 0 or iterations <= 0:
            raise ValueError("dt and iterations must be positive")
        if not 0 <= velocity_retention <= 1:
            raise ValueError("velocity_retention must be in [0, 1]")
        if ground_velocity_retention_x is not None and any(
            not 0 <= value <= 1 for value in ground_velocity_retention_x
        ):
            raise ValueError("ground tangential retention must be in [0, 1]")
        if active_curvature_gain < 0:
            raise ValueError("active curvature gain must be non-negative")
        if active_bending_stiffness_ratio <= 0:
            raise ValueError("active bending stiffness ratio must be positive")

        for index, particle in enumerate(self.particles):
            if particle.inverse_mass == 0:
                continue
            velocity = (particle.position - particle.previous_position) * velocity_retention
            if ground_z is not None and ground_velocity_retention_x is not None:
                clearance = self._node_clearance(index)
                if particle.position.z <= ground_z + clearance + 1e-15:
                    negative_x, positive_x = ground_velocity_retention_x
                    if use_local_tangent_friction:
                        tangent = self._node_tangent_xy(index)
                        lateral = Vec3(-tangent.y, tangent.x, 0.0)
                        tangential_speed = velocity.dot(tangent)
                        lateral_speed = velocity.dot(lateral)
                        tangential_retention = (
                            negative_x if tangential_speed < 0 else positive_x
                        )
                        planar_velocity = (
                            tangent * (tangential_speed * tangential_retention)
                            + lateral
                            * (lateral_speed * min(negative_x, positive_x))
                        )
                        velocity = Vec3(
                            planar_velocity.x, planar_velocity.y, velocity.z
                        )
                    else:
                        tangential_retention = (
                            negative_x if velocity.x < 0 else positive_x
                        )
                        velocity = Vec3(
                            velocity.x * tangential_retention,
                            velocity.y * min(negative_x, positive_x),
                            velocity.z,
                        )
            old_position = particle.position
            particle.position = particle.position + velocity + gravity * (dt_s * dt_s)
            particle.previous_position = old_position
            if ground_z is not None:
                clearance = self._node_clearance(index)
                if particle.position.z < ground_z + clearance:
                    particle.position = Vec3(
                        particle.position.x,
                        particle.position.y,
                        ground_z + clearance,
                    )

        compliance = 1.0 / self._instantaneous_stiffness
        alpha = compliance / (dt_s * dt_s)
        bending_alpha = (
            compliance
            / active_bending_stiffness_ratio
            / (dt_s * dt_s)
        )
        for _ in range(iterations):
            for index in range(len(self.geometry)):
                left = self.particles[index]
                right = self.particles[index + 1]
                delta = right.position - left.position
                distance = delta.norm()
                if distance == 0:
                    continue
                constraint = distance - self.target_length_m(index)
                denominator = left.inverse_mass + right.inverse_mass + alpha
                lagrange = -constraint / denominator
                direction = delta * (1.0 / distance)
                if left.inverse_mass:
                    left.position = left.position - direction * (left.inverse_mass * lagrange)
                if right.inverse_mass:
                    right.position = right.position + direction * (right.inverse_mass * lagrange)
            if active_curvature_gain:
                for index in range(1, len(self.particles) - 1):
                    left = self.particles[index - 1]
                    middle = self.particles[index]
                    right = self.particles[index + 1]
                    differential = 0.5 * (
                        self.left_activations[index - 1]
                        - self.right_activations[index - 1]
                        + self.left_activations[index]
                        - self.right_activations[index]
                    )
                    mean_rest_length = 0.5 * (
                        self.geometry[index - 1].rest_length_m
                        + self.geometry[index].rest_length_m
                    )
                    target_offset = (
                        active_curvature_gain
                        * mean_rest_length
                        * differential
                    )
                    span = right.position - left.position
                    planar_span = sqrt(span.x * span.x + span.y * span.y)
                    if planar_span == 0:
                        continue
                    normal = Vec3(
                        -span.y / planar_span, span.x / planar_span, 0.0
                    )
                    midpoint = (left.position + right.position) * 0.5
                    constraint = (
                        (middle.position - midpoint).dot(normal)
                        - target_offset
                    )
                    denominator = (
                        0.25 * left.inverse_mass
                        + middle.inverse_mass
                        + 0.25 * right.inverse_mass
                        + bending_alpha
                    )
                    lagrange = -constraint / denominator
                    if left.inverse_mass:
                        left.position = left.position + normal * (
                            -0.5 * left.inverse_mass * lagrange
                        )
                    if middle.inverse_mass:
                        middle.position = middle.position + normal * (
                            middle.inverse_mass * lagrange
                        )
                    if right.inverse_mass:
                        right.position = right.position + normal * (
                            -0.5 * right.inverse_mass * lagrange
                        )

    def _node_clearance(self, node_index: int) -> float:
        adjacent = []
        if node_index > 0:
            adjacent.append(self.geometry[node_index - 1].height_m / 2)
        if node_index < len(self.geometry):
            adjacent.append(self.geometry[node_index].height_m / 2)
        return max(adjacent)

    def _node_width(self, node_index: int) -> float:
        adjacent = []
        if node_index > 0:
            adjacent.append(self.geometry[node_index - 1].width_m)
        if node_index < len(self.geometry):
            adjacent.append(self.geometry[node_index].width_m)
        return max(adjacent)

    def _node_tangent_xy(self, node_index: int) -> Vec3:
        if node_index == 0:
            delta = self.particles[1].position - self.particles[0].position
        elif node_index == len(self.particles) - 1:
            delta = self.particles[-1].position - self.particles[-2].position
        else:
            delta = (
                self.particles[node_index + 1].position
                - self.particles[node_index - 1].position
            )
        magnitude = sqrt(delta.x * delta.x + delta.y * delta.y)
        if magnitude == 0:
            return Vec3(1.0, 0.0, 0.0)
        return Vec3(delta.x / magnitude, delta.y / magnitude, 0.0)

    def _side_node_position(self, node_index: int, sign: float) -> Vec3:
        center = self.particles[node_index].position
        tangent = self._node_tangent_xy(node_index)
        normal = Vec3(-tangent.y, tangent.x, 0.0)
        return center + normal * (sign * self._node_width(node_index) / 2.0)
