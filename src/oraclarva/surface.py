"""Continuous watertight render surface derived from the physical body state."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import cos, pi, sin

from .body3d import ScientificBody3D, Vec3


Face = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class SurfaceMesh:
    """One connected skin; segment IDs label faces without splitting geometry."""

    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    face_segment_ids: tuple[str, ...]

    def validate(self) -> None:
        if not self.vertices or not self.faces:
            raise ValueError("surface mesh must not be empty")
        if len(self.faces) != len(self.face_segment_ids):
            raise ValueError("every surface face must have one anatomical region label")
        vertex_count = len(self.vertices)
        for face in self.faces:
            if len(set(face)) != 3:
                raise ValueError("surface face is degenerate")
            if any(index < 0 or index >= vertex_count for index in face):
                raise ValueError("surface face references an unknown vertex")

    def edge_use_counts(self) -> Counter[tuple[int, int]]:
        counts: Counter[tuple[int, int]] = Counter()
        for a, b, c in self.faces:
            for left, right in ((a, b), (b, c), (c, a)):
                counts[tuple(sorted((left, right)))] += 1
        return counts

    @property
    def is_watertight(self) -> bool:
        return all(count == 2 for count in self.edge_use_counts().values())


def _lerp(left: Vec3, right: Vec3, amount: float) -> Vec3:
    return left * (1.0 - amount) + right * amount


def _smoothstep(amount: float) -> float:
    return amount * amount * (3.0 - 2.0 * amount)


def _node_dimensions(body: ScientificBody3D) -> tuple[list[float], list[float]]:
    widths = [body.current_width_m(index) for index in range(len(body.geometry))]
    heights = [body.current_height_m(index) for index in range(len(body.geometry))]
    node_widths = [widths[0] * 0.55]
    node_heights = [heights[0] * 0.55]
    for index in range(1, len(body.geometry)):
        node_widths.append((widths[index - 1] + widths[index]) / 2)
        node_heights.append((heights[index - 1] + heights[index]) / 2)
    node_widths.append(widths[-1] * 0.45)
    node_heights.append(heights[-1] * 0.45)
    return node_widths, node_heights


def build_surface_mesh(
    body: ScientificBody3D,
    *,
    axial_subdivisions: int = 4,
    radial_samples: int = 24,
) -> SurfaceMesh:
    """Build a single tapered skin over all mechanical regions.

    Region boundaries share the same vertex rings. They remain available as
    per-face labels for selection and diagnostics, but are never separate
    ellipsoids or independent rigid bodies.
    """
    if axial_subdivisions < 1:
        raise ValueError("axial_subdivisions must be positive")
    if radial_samples < 8:
        raise ValueError("radial_samples must be at least 8")

    node_widths, node_heights = _node_dimensions(body)
    ring_centers: list[Vec3] = []
    ring_widths: list[float] = []
    ring_heights: list[float] = []

    for segment_index in range(len(body.geometry)):
        left = body.particles[segment_index].position
        right = body.particles[segment_index + 1].position
        for step in range(axial_subdivisions):
            amount = step / axial_subdivisions
            profile_amount = _smoothstep(amount)
            ring_centers.append(_lerp(left, right, amount))
            ring_widths.append(
                node_widths[segment_index] * (1.0 - profile_amount)
                + node_widths[segment_index + 1] * profile_amount
            )
            ring_heights.append(
                node_heights[segment_index] * (1.0 - profile_amount)
                + node_heights[segment_index + 1] * profile_amount
            )

    ring_centers.append(body.particles[-1].position)
    ring_widths.append(node_widths[-1])
    ring_heights.append(node_heights[-1])

    vertices: list[Vec3] = []
    up = Vec3(0.0, 0.0, 1.0)
    for index, center in enumerate(ring_centers):
        if index == 0:
            tangent = (ring_centers[1] - center).normalized()
        elif index == len(ring_centers) - 1:
            tangent = (center - ring_centers[index - 1]).normalized()
        else:
            tangent = (ring_centers[index + 1] - ring_centers[index - 1]).normalized()
        lateral = up.cross(tangent)
        if lateral.norm() < 1e-12:
            lateral = Vec3(0.0, 1.0, 0.0)
        else:
            lateral = lateral.normalized()
        dorsal = tangent.cross(lateral).normalized()

        for radial_index in range(radial_samples):
            angle = 2 * pi * radial_index / radial_samples
            vertices.append(
                center
                + lateral * (0.5 * ring_widths[index] * cos(angle))
                + dorsal * (0.5 * ring_heights[index] * sin(angle))
            )

    faces: list[Face] = []
    face_segment_ids: list[str] = []
    span_count = len(ring_centers) - 1
    for span_index in range(span_count):
        segment_index = min(span_index // axial_subdivisions, len(body.geometry) - 1)
        segment_id = body.geometry[segment_index].id
        left_start = span_index * radial_samples
        right_start = (span_index + 1) * radial_samples
        for radial_index in range(radial_samples):
            following = (radial_index + 1) % radial_samples
            faces.append(
                (left_start + radial_index, right_start + radial_index, right_start + following)
            )
            faces.append(
                (left_start + radial_index, right_start + following, left_start + following)
            )
            face_segment_ids.extend((segment_id, segment_id))

    start_center = len(vertices)
    vertices.append(ring_centers[0])
    end_center = len(vertices)
    vertices.append(ring_centers[-1])
    last_ring_start = (len(ring_centers) - 1) * radial_samples
    for radial_index in range(radial_samples):
        following = (radial_index + 1) % radial_samples
        faces.append((start_center, radial_index, following))
        face_segment_ids.append(body.geometry[0].id)
        faces.append((end_center, last_ring_start + following, last_ring_start + radial_index))
        face_segment_ids.append(body.geometry[-1].id)

    mesh = SurfaceMesh(tuple(vertices), tuple(faces), tuple(face_segment_ids))
    mesh.validate()
    return mesh
