"""Auditable motor-neuron to muscle-channel projection contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .body import ALLOWED_PROVENANCE, BodyModelSpec
from .body3d import ScientificBody3D


SIDES = {"left", "right", "bilateral"}
MUSCLE_GROUPS = {"longitudinal", "transverse"}
SCIENTIFIC_MAPPING_PROVENANCE = {"observed"}


class UnvalidatedMappingError(RuntimeError):
    """Raised before an uncurated neuron-to-muscle map can drive the body."""


@dataclass(frozen=True, slots=True)
class MuscleChannel:
    segment_id: str
    side: str
    muscle_group: str


@dataclass(frozen=True, slots=True)
class MotorProjection:
    neuron_id: str
    channel: MuscleChannel
    weight: float
    provenance: str
    source_id: str | None = None


@dataclass(frozen=True, slots=True)
class MuscleActivationFrame:
    activations: Mapping[MuscleChannel, float]

    def axial_by_segment(self, segment_ids: tuple[str, ...]) -> dict[str, float]:
        result: dict[str, float] = {}
        for segment_id in segment_ids:
            values = [
                activation
                for channel, activation in self.activations.items()
                if channel.segment_id == segment_id
                and channel.muscle_group == "longitudinal"
            ]
            result[segment_id] = sum(values) / len(values) if values else 0.0
        return result


@dataclass(frozen=True, slots=True)
class NeuromuscularMap:
    model_id: str
    status: str
    projections: tuple[MotorProjection, ...]
    body_segment_ids: tuple[str, ...]
    note: str = ""

    def validate(self) -> None:
        segment_ids = set(self.body_segment_ids)
        for projection in self.projections:
            if not projection.neuron_id:
                raise ValueError("motor projection requires a neuron id")
            if projection.channel.segment_id not in segment_ids:
                raise ValueError(f"unknown body segment {projection.channel.segment_id}")
            if projection.channel.side not in SIDES:
                raise ValueError(f"unsupported muscle side {projection.channel.side}")
            if projection.channel.muscle_group not in MUSCLE_GROUPS:
                raise ValueError(f"unsupported muscle group {projection.channel.muscle_group}")
            if projection.weight <= 0:
                raise ValueError("motor projection weight must be positive")
            if projection.provenance not in ALLOWED_PROVENANCE:
                raise ValueError(f"unsupported provenance {projection.provenance}")

    @property
    def is_scientifically_ready(self) -> bool:
        return (
            self.status == "curated"
            and bool(self.projections)
            and all(
                projection.provenance in SCIENTIFIC_MAPPING_PROVENANCE
                and projection.source_id
                for projection in self.projections
            )
        )

    def require_scientifically_ready(self) -> None:
        if not self.is_scientifically_ready:
            raise UnvalidatedMappingError(
                "motor-neuron identifiers are not yet cross-walked to observed muscle targets"
            )

    def project(
        self,
        normalized_motor_activity: Mapping[str, float],
        *,
        allow_unvalidated: bool = False,
    ) -> MuscleActivationFrame:
        if not allow_unvalidated:
            self.require_scientifically_ready()
        for neuron_id, activity in normalized_motor_activity.items():
            if not 0.0 <= activity <= 1.0:
                raise ValueError(f"motor activity for {neuron_id} must be in [0, 1]")

        weighted: dict[MuscleChannel, float] = {}
        total_weights: dict[MuscleChannel, float] = {}
        for projection in self.projections:
            activity = normalized_motor_activity.get(projection.neuron_id, 0.0)
            weighted[projection.channel] = (
                weighted.get(projection.channel, 0.0) + projection.weight * activity
            )
            total_weights[projection.channel] = (
                total_weights.get(projection.channel, 0.0) + projection.weight
            )
        activations = {
            channel: min(1.0, weighted[channel] / total_weights[channel])
            for channel in weighted
        }
        return MuscleActivationFrame(activations)

    def apply_axial_activation(
        self,
        body: ScientificBody3D,
        frame: MuscleActivationFrame,
    ) -> None:
        segment_ids = tuple(segment.id for segment in body.geometry)
        if segment_ids != self.body_segment_ids:
            raise ValueError("neuromuscular map and body regions do not match")
        body.set_activations(frame.axial_by_segment(segment_ids))


def default_neuromuscular_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "neuromuscular" / "l1_motor_map_v0.json"


def load_neuromuscular_map(
    spec: BodyModelSpec,
    path: str | Path | None = None,
) -> NeuromuscularMap:
    source_path = Path(path) if path else default_neuromuscular_path()
    raw: dict[str, Any] = json.loads(source_path.read_text(encoding="utf-8"))
    projections = tuple(
        MotorProjection(
            neuron_id=str(item["neuron_id"]),
            channel=MuscleChannel(
                segment_id=str(item["segment_id"]),
                side=str(item["side"]),
                muscle_group=str(item["muscle_group"]),
            ),
            weight=float(item["weight"]),
            provenance=str(item["provenance"]),
            source_id=item.get("source_id"),
        )
        for item in raw["projections"]
    )
    result = NeuromuscularMap(
        model_id=str(raw["model_id"]),
        status=str(raw["status"]),
        projections=projections,
        body_segment_ids=tuple(segment.id for segment in spec.segments),
        note=str(raw.get("note", "")),
    )
    result.validate()
    return result
