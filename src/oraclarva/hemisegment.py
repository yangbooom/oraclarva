"""Isolated provenance-aware A1-left hemisegment muscle mechanics.

Coordinates and forces are normalized model units. This fixture never drives the
full body and makes no measured attachment, CSA, Fmax, or SI-force claim.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from math import cos, isfinite, pi, sin, sqrt
from pathlib import Path
from typing import Any, Iterable, Mapping

from .muscles import (
    AbdominalMuscleAtlas,
    AggregateMuscleIdentityProjection,
    NeuralMuscleActivationFrame,
    load_muscle_atlas,
)

Point = tuple[float, float, float]


def _sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a: Point, value: float) -> Point:
    return (a[0] * value, a[1] * value, a[2] * value)


def _norm(a: Point) -> float:
    return sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)


def _unit(a: Point) -> Point:
    magnitude = _norm(a)
    if magnitude <= 0.0:
        raise ValueError("attachment origin and insertion must differ")
    return _scale(a, 1.0 / magnitude)


@dataclass(frozen=True, slots=True)
class BodyFixedCoordinate:
    s: float
    theta_rad: float
    depth_fraction: float

    def validate(self) -> None:
        if not 0.0 <= self.s <= 1.0:
            raise ValueError("attachment s must be in [0, 1]")
        if not -pi <= self.theta_rad <= pi:
            raise ValueError("attachment theta must be in [-pi, pi]")
        if not 0.0 <= self.depth_fraction < 1.0:
            raise ValueError("attachment depth must be in [0, 1)")


@dataclass(frozen=True, slots=True)
class FiberAttachmentGeometry:
    fiber_id: str
    muscle_number: str
    synonym: str
    spatial_group: str
    origin: BodyFixedCoordinate
    insertion: BodyFixedCoordinate
    origin_point: Point
    insertion_point: Point
    rest_length_body_units: float
    line_of_action: Point
    coordinate_provenance: str = "ANATOMY_DERIVED"
    rest_length_provenance: str = "ANATOMY_DERIVED"
    quantitative_image_coordinates_used: bool = False
    individual_layer_claimed: bool = False


@dataclass(frozen=True, slots=True)
class A1HemisegmentSpec:
    model_id: str
    status: str
    side: str
    coordinate_provenance: str
    mechanics_provenance: str
    absolute_scale_claimed: bool
    full_body_motion_enabled: bool
    width: float
    height: float
    depth: float
    group_rules: Mapping[str, Mapping[str, float]]
    transverse_rule: Mapping[str, float]
    dt_s: float
    stiffness: float
    damping: float
    inertia: float
    active_gain: float
    maximum_shortening_fraction: float
    raw: Mapping[str, Any]

    def validate(self) -> None:
        if self.side != "left":
            raise ValueError("v0 fixture is restricted to the A1 left hemisegment")
        if self.coordinate_provenance != "ANATOMY_DERIVED":
            raise ValueError("attachment coordinates must remain ANATOMY_DERIVED")
        if self.mechanics_provenance != "MODEL_FITTED":
            raise ValueError("mechanics parameters must remain MODEL_FITTED")
        if self.absolute_scale_claimed or self.full_body_motion_enabled:
            raise ValueError("isolated fixture cannot claim scale or drive the body")
        values = (
            self.width,
            self.height,
            self.dt_s,
            self.stiffness,
            self.damping,
            self.inertia,
            self.active_gain,
            self.maximum_shortening_fraction,
        )
        if any(not isfinite(value) or value <= 0.0 for value in values):
            raise ValueError("hemisegment values must be positive")
        if not 0.0 <= self.depth < 1.0:
            raise ValueError("attachment depth must be in [0, 1)")
        if self.maximum_shortening_fraction >= 1.0:
            raise ValueError("maximum shortening fraction must be below one")
        if set(self.group_rules) != {"DL", "DO", "VL", "VO", "VA"}:
            raise ValueError("placement rules are incomplete")


@dataclass(slots=True)
class FiberMechanicalState:
    shortening: float = 0.0
    velocity: float = 0.0


@dataclass(frozen=True, slots=True)
class FiberMechanicalOutput:
    fiber_id: str
    activation: float
    shortening_body_units: float
    shortening_fraction: float
    current_length_body_units: float
    active_tension_model_units: float
    passive_elastic_force_model_units: float
    damping_force_model_units: float
    insertion_point: Point
    source_node_id: str | None
    mapping_provenance: str | None
    mechanics_enabled: bool


@dataclass(frozen=True, slots=True)
class A1HemisegmentMechanicsFrame:
    time_s: float
    fibers: Mapping[str, FiberMechanicalOutput]
    geometry_provenance: str = "ANATOMY_DERIVED"
    mechanics_provenance: str = "MODEL_FITTED"
    absolute_force_unit: str = "model_unit_not_newton"
    full_body_motion_executed: bool = False

    @property
    def deformed_fiber_count(self) -> int:
        return sum(item.shortening_body_units > 0.0 for item in self.fibers.values())

    @property
    def maximum_shortening_fraction(self) -> float:
        return max((item.shortening_fraction for item in self.fibers.values()), default=0.0)


@dataclass(slots=True)
class IsolatedA1HemisegmentMechanics:
    spec: A1HemisegmentSpec
    atlas: AbdominalMuscleAtlas = field(default_factory=load_muscle_atlas)
    geometries: tuple[FiberAttachmentGeometry, ...] = field(init=False)
    states: dict[str, FiberMechanicalState] = field(init=False)
    _step_index: int = field(init=False, default=0, repr=False)

    def __post_init__(self) -> None:
        self.spec.validate()
        self.geometries = derive_a1_left_attachment_geometry(self.spec, self.atlas)
        self.states = {geometry.fiber_id: FiberMechanicalState() for geometry in self.geometries}

    @property
    def fiber_ids(self) -> tuple[str, ...]:
        return tuple(geometry.fiber_id for geometry in self.geometries)

    def step(
        self,
        time_s: float,
        activations: Mapping[str, float],
        *,
        lesioned_fiber_ids: Iterable[str] = (),
        source_by_fiber: Mapping[str, str] | None = None,
        mapping_provenance_by_fiber: Mapping[str, str] | None = None,
    ) -> A1HemisegmentMechanicsFrame:
        if not isfinite(time_s) or abs(time_s - self._step_index * self.spec.dt_s) > 1e-9:
            raise ValueError("hemisegment mechanics must be stepped once per dt in order")
        known = set(self.states)
        if set(activations) - known:
            raise ValueError("activation outside A1-left fixture")
        lesions = set(lesioned_fiber_ids)
        if lesions - known:
            raise ValueError("lesion outside A1-left fixture")
        if any(not isfinite(float(value)) or not 0.0 <= float(value) <= 1.0 for value in activations.values()):
            raise ValueError("activation must be in [0, 1]")

        geometry_by_id = {geometry.fiber_id: geometry for geometry in self.geometries}
        source_trace = source_by_fiber or {}
        provenance_trace = mapping_provenance_by_fiber or {}
        outputs: dict[str, FiberMechanicalOutput] = {}
        for fiber_id in self.fiber_ids:
            geometry = geometry_by_id[fiber_id]
            state = self.states[fiber_id]
            activation = float(activations.get(fiber_id, 0.0))
            mechanics_enabled = fiber_id not in lesions
            active = self.spec.active_gain * activation if mechanics_enabled else 0.0
            passive = self.spec.stiffness * state.shortening
            drag = self.spec.damping * state.velocity
            acceleration = (active - passive - drag) / self.spec.inertia
            state.velocity += acceleration * self.spec.dt_s
            state.shortening += state.velocity * self.spec.dt_s
            maximum = self.spec.maximum_shortening_fraction * geometry.rest_length_body_units
            if state.shortening <= 0.0:
                state.shortening = 0.0
                state.velocity = max(0.0, state.velocity)
            elif state.shortening >= maximum:
                state.shortening = maximum
                state.velocity = min(0.0, state.velocity)
            insertion = _sub(geometry.insertion_point, _scale(geometry.line_of_action, state.shortening))
            outputs[fiber_id] = FiberMechanicalOutput(
                fiber_id=fiber_id,
                activation=activation,
                shortening_body_units=state.shortening,
                shortening_fraction=state.shortening / geometry.rest_length_body_units,
                current_length_body_units=geometry.rest_length_body_units - state.shortening,
                active_tension_model_units=active,
                passive_elastic_force_model_units=self.spec.stiffness * state.shortening,
                damping_force_model_units=self.spec.damping * state.velocity,
                insertion_point=insertion,
                source_node_id=source_trace.get(fiber_id),
                mapping_provenance=provenance_trace.get(fiber_id),
                mechanics_enabled=mechanics_enabled,
            )
        self._step_index += 1
        return A1HemisegmentMechanicsFrame(time_s=time_s, fibers=outputs)

    def step_activation_frame(
        self,
        frame: NeuralMuscleActivationFrame,
        *,
        lesioned_fiber_ids: Iterable[str] = (),
        source_by_fiber: Mapping[str, str] | None = None,
        mapping_provenance_by_fiber: Mapping[str, str] | None = None,
    ) -> A1HemisegmentMechanicsFrame:
        activations = {
            fiber_id: frame.activations[fiber_id]
            for fiber_id in self.fiber_ids
            if fiber_id in frame.activations
        }
        return self.step(
            frame.time_s,
            activations,
            lesioned_fiber_ids=lesioned_fiber_ids,
            source_by_fiber=source_by_fiber,
            mapping_provenance_by_fiber=mapping_provenance_by_fiber,
        )


def _point(coordinate: BodyFixedCoordinate, spec: A1HemisegmentSpec) -> Point:
    radius = 1.0 - coordinate.depth_fraction
    return (
        coordinate.s,
        0.5 * spec.width * radius * sin(coordinate.theta_rad),
        0.5 * spec.height * radius * cos(coordinate.theta_rad),
    )


def derive_a1_left_attachment_geometry(
    spec: A1HemisegmentSpec,
    atlas: AbdominalMuscleAtlas,
) -> tuple[FiberAttachmentGeometry, ...]:
    fibers = tuple(fiber for fiber in atlas.fibers_for_segment("A1") if fiber.side == "left")
    by_group: dict[str, list[Any]] = {}
    for fiber in fibers:
        by_group.setdefault(fiber.muscle.spatial_group, []).append(fiber)
    for members in by_group.values():
        members.sort(key=lambda item: int(item.muscle.number))

    aggregate = AggregateMuscleIdentityProjection(atlas)
    result: list[FiberAttachmentGeometry] = []
    for fiber in fibers:
        group = fiber.muscle.spatial_group
        members = by_group[group]
        rank = members.index(fiber)
        relative = 0.0 if len(members) == 1 else rank / (len(members) - 1) - 0.5
        if group == "T":
            rule = spec.transverse_rule
            s = float(rule["first_s"]) + rank * (
                float(rule["last_s"]) - float(rule["first_s"])
            ) / max(1, len(members) - 1)
            tilt = float(rule["s_tilt"]) * (1.0 if rank % 2 == 0 else -1.0)
            origin = BodyFixedCoordinate(
                s - tilt / 2.0,
                float(rule["dorsal_theta_rad"]),
                spec.depth,
            )
            insertion = BodyFixedCoordinate(
                s + tilt / 2.0,
                float(rule["ventral_theta_rad"]),
                spec.depth,
            )
        else:
            rule = spec.group_rules[group]
            theta = float(rule["theta_center_rad"]) + relative * float(rule["theta_spread_rad"])
            stagger = relative * float(rule["axial_stagger"])
            twist = float(rule["theta_twist_rad"])
            origin = BodyFixedCoordinate(
                float(rule["origin_s"]) + stagger,
                theta - twist / 2.0,
                spec.depth,
            )
            insertion = BodyFixedCoordinate(
                float(rule["insertion_s"]) - stagger,
                theta + twist / 2.0,
                spec.depth,
            )
        origin.validate()
        insertion.validate()
        origin_point = _point(origin, spec)
        insertion_point = _point(insertion, spec)
        displacement = _sub(insertion_point, origin_point)
        result.append(
            FiberAttachmentGeometry(
                fiber_id=aggregate.fiber_id(fiber),
                muscle_number=fiber.muscle.number,
                synonym=fiber.muscle.synonym,
                spatial_group=group,
                origin=origin,
                insertion=insertion,
                origin_point=origin_point,
                insertion_point=insertion_point,
                rest_length_body_units=_norm(displacement),
                line_of_action=_unit(displacement),
            )
        )
    if len(result) != 29 or len({geometry.fiber_id for geometry in result}) != 29:
        raise ValueError("A1-left fixture must contain 29 unique fibers")
    return tuple(result)


def default_a1_hemisegment_spec_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "muscles" / "l1_a1_left_hemisegment_mechanics_v0.json"


def load_a1_hemisegment_spec(path: str | Path | None = None) -> A1HemisegmentSpec:
    raw = json.loads((Path(path) if path else default_a1_hemisegment_spec_path()).read_text())
    coordinates = raw["body_fixed_coordinate_system"]
    mechanics = raw["isolated_mechanics"]
    spec = A1HemisegmentSpec(
        model_id=str(raw["model_id"]),
        status=str(raw["status"]),
        side=str(raw["scope"]["side"]),
        coordinate_provenance=str(raw["attachment_hypothesis"]["provenance"]),
        mechanics_provenance=str(mechanics["provenance"]),
        absolute_scale_claimed=bool(raw["claim_boundary"]["absolute_scale_claimed"]),
        full_body_motion_enabled=bool(raw["claim_boundary"]["full_body_motion_enabled"]),
        width=float(coordinates["cross_section_width_body_units"]),
        height=float(coordinates["cross_section_height_body_units"]),
        depth=float(coordinates["attachment_depth_fraction"]),
        group_rules=raw["attachment_hypothesis"]["longitudinal_and_oblique_groups"],
        transverse_rule=raw["attachment_hypothesis"]["transverse_group"],
        dt_s=float(mechanics["dt_s"]),
        stiffness=float(mechanics["passive_stiffness_model_units"]),
        damping=float(mechanics["damping_model_units"]),
        inertia=float(mechanics["inertial_scale_model_units"]),
        active_gain=float(mechanics["active_tension_gain_model_units"]),
        maximum_shortening_fraction=float(mechanics["maximum_shortening_fraction"]),
        raw=raw,
    )
    spec.validate()
    return spec
