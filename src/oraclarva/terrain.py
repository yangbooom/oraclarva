"""Passive 3D contact geometry and receptor-distance sampling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .body3d import ContactProjection, Vec3


class Collider(Protocol):
    sensory_enabled: bool

    def signed_distance_m(self, position: Vec3) -> float:
        """Positive outside, zero on, negative inside the solid."""

    def query(
        self,
        position: Vec3,
        clearance_m: float,
        margin_m: float = 0.0,
    ) -> ContactProjection | None:
        """Return a projected non-penetrating point when in contact."""


@dataclass(frozen=True, slots=True)
class PlaneCollider:
    point_m: Vec3
    normal: Vec3
    sensory_enabled: bool = False

    def __post_init__(self) -> None:
        if self.normal.norm() == 0.0:
            raise ValueError("plane normal must be non-zero")
        object.__setattr__(self, "normal", self.normal.normalized())

    @classmethod
    def from_slopes(
        cls,
        slope_x: float,
        slope_y: float,
        *,
        origin_m: Vec3 = Vec3(0.0, 0.0, 0.0),
        sensory_enabled: bool = False,
    ) -> "PlaneCollider":
        return cls(
            point_m=origin_m,
            normal=Vec3(-slope_x, -slope_y, 1.0),
            sensory_enabled=sensory_enabled,
        )

    def signed_distance_m(self, position: Vec3) -> float:
        return (position - self.point_m).dot(self.normal)

    def query(
        self,
        position: Vec3,
        clearance_m: float,
        margin_m: float = 0.0,
    ) -> ContactProjection | None:
        signed_distance = self.signed_distance_m(position)
        if signed_distance > clearance_m + margin_m:
            return None
        correction = max(0.0, clearance_m - signed_distance)
        return ContactProjection(
            position=position + self.normal * correction,
            normal=self.normal,
        )


@dataclass(frozen=True, slots=True)
class SphereCollider:
    center_m: Vec3
    radius_m: float
    sensory_enabled: bool = True

    def __post_init__(self) -> None:
        if self.radius_m <= 0.0:
            raise ValueError("sphere radius must be positive")

    def signed_distance_m(self, position: Vec3) -> float:
        return (position - self.center_m).norm() - self.radius_m

    def query(
        self,
        position: Vec3,
        clearance_m: float,
        margin_m: float = 0.0,
    ) -> ContactProjection | None:
        radial = position - self.center_m
        distance = radial.norm()
        if distance - self.radius_m > clearance_m + margin_m:
            return None
        normal = (
            Vec3(1.0, 0.0, 0.0)
            if distance == 0.0
            else radial * (1.0 / distance)
        )
        target_distance = self.radius_m + clearance_m
        projected = (
            position
            if distance >= target_distance
            else self.center_m + normal * target_distance
        )
        return ContactProjection(position=projected, normal=normal)


@dataclass(frozen=True, slots=True)
class ContactWorld:
    colliders: tuple[Collider, ...]

    def __post_init__(self) -> None:
        if not self.colliders:
            raise ValueError("contact world requires at least one collider")

    def query(
        self,
        position: Vec3,
        clearance_m: float,
        margin_m: float = 0.0,
    ) -> ContactProjection | None:
        current = position
        contact_normals: list[Vec3] = []
        for _ in range(3):
            changed = False
            for collider in self.colliders:
                projection = collider.query(
                    current, clearance_m, margin_m
                )
                if projection is None:
                    continue
                contact_normals.append(projection.normal)
                if projection.position != current:
                    current = projection.position
                    changed = True
            if not changed:
                break
        if not contact_normals:
            return None
        combined = Vec3(0.0, 0.0, 0.0)
        for normal in contact_normals:
            combined = combined + normal
        return ContactProjection(
            position=current,
            normal=combined.normalized(),
        )

    def receptor_intensity(
        self,
        position: Vec3,
        *,
        sensing_range_m: float,
    ) -> float:
        if sensing_range_m <= 0.0:
            raise ValueError("sensing range must be positive")
        distances = [
            collider.signed_distance_m(position)
            for collider in self.colliders
            if collider.sensory_enabled
        ]
        if not distances:
            return 0.0
        distance = min(distances)
        return min(
            1.0,
            max(0.0, 1.0 - max(0.0, distance) / sensing_range_m),
        )
