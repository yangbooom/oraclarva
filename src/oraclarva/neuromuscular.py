"""Auditable motor-neuron to muscle-target projection contract."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .body import ALLOWED_PROVENANCE, BodyModelSpec, load_body_spec
from .body3d import ScientificBody3D


SIDES = {"left", "right", "bilateral"}
MUSCLE_GROUPS = {"longitudinal", "transverse"}
SPATIAL_GROUPS = {"DL", "DO", "VL", "VA", "VO", "T", "Broad"}
SYNAPSE_TYPES = {"Ib", "Is", "II", "III"}
TARGET_EVIDENCE = {"listed", "bracketed_in_source"}
SCIENTIFIC_MAPPING_PROVENANCE = {"observed"}
SCIENTIFIC_GAIN_PROVENANCE = {"observed", "fit"}


class UnvalidatedMappingError(RuntimeError):
    """Raised before an incomplete neuron-to-muscle map can drive the body."""


@dataclass(frozen=True, slots=True)
class MuscleTarget:
    number: str
    synonym: str
    evidence: str = "listed"


@dataclass(frozen=True, slots=True)
class MuscleChannel:
    segment_id: str
    side: str
    muscle_group: str | None = None
    spatial_group: str | None = None
    target_muscles: tuple[MuscleTarget, ...] = ()
    synapse_type: str | None = None


@dataclass(frozen=True, slots=True)
class MotorProjection:
    neuron_id: str
    channel: MuscleChannel
    weight: float | None
    provenance: str
    source_id: str | None = None
    neuron_name: str | None = None
    dataset_id: str | None = None
    gain_provenance: str = "unknown"


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
    unresolved_neuron_ids: tuple[str, ...] = ()
    dataset_id: str | None = None
    note: str = ""

    def validate(self) -> None:
        segment_ids = set(self.body_segment_ids)
        neuron_ids = [projection.neuron_id for projection in self.projections]
        if len(neuron_ids) != len(set(neuron_ids)):
            raise ValueError(
                "v1 motor identity crosswalk requires one projection per neuron"
            )
        for projection in self.projections:
            if not projection.neuron_id:
                raise ValueError("motor projection requires a neuron id")
            if projection.channel.segment_id not in segment_ids:
                raise ValueError(f"unknown body segment {projection.channel.segment_id}")
            if projection.channel.side not in SIDES:
                raise ValueError(f"unsupported muscle side {projection.channel.side}")
            if projection.channel.muscle_group is not None:
                if projection.channel.muscle_group not in MUSCLE_GROUPS:
                    raise ValueError(
                        f"unsupported muscle group {projection.channel.muscle_group}"
                    )
            if projection.channel.target_muscles:
                if projection.channel.spatial_group not in SPATIAL_GROUPS:
                    raise ValueError(
                        f"unsupported spatial group {projection.channel.spatial_group}"
                    )
                if projection.channel.synapse_type not in SYNAPSE_TYPES:
                    raise ValueError(
                        f"unsupported synapse type {projection.channel.synapse_type}"
                    )
                target_numbers = [
                    target.number for target in projection.channel.target_muscles
                ]
                if len(target_numbers) != len(set(target_numbers)):
                    raise ValueError("muscle targets must be unique within a projection")
                for target in projection.channel.target_muscles:
                    if not target.number or not target.synonym:
                        raise ValueError("muscle target requires number and synonym")
                    if target.evidence not in TARGET_EVIDENCE:
                        raise ValueError(
                            f"unsupported target evidence {target.evidence}"
                        )
            elif projection.channel.spatial_group is not None:
                raise ValueError("spatial group requires exact muscle targets")
            elif projection.channel.muscle_group is None:
                raise ValueError("projection requires an anatomical or mechanical channel")
            if projection.weight is not None and projection.weight <= 0:
                raise ValueError("motor projection weight must be positive")
            if projection.provenance not in ALLOWED_PROVENANCE:
                raise ValueError(f"unsupported provenance {projection.provenance}")

    @property
    def is_identity_curated(self) -> bool:
        return bool(self.projections) and all(
            projection.provenance in SCIENTIFIC_MAPPING_PROVENANCE
            and projection.source_id
            and projection.neuron_name
            and projection.dataset_id
            and projection.channel.target_muscles
            for projection in self.projections
        )

    @property
    def is_scientifically_ready(self) -> bool:
        return (
            self.status == "curated"
            and self.is_identity_curated
            and not self.unresolved_neuron_ids
            and all(
                projection.weight is not None
                and projection.gain_provenance in SCIENTIFIC_GAIN_PROVENANCE
                and projection.channel.muscle_group in MUSCLE_GROUPS
                for projection in self.projections
            )
        )

    def audit_summary(self) -> dict[str, Any]:
        segment_counts = Counter(
            projection.channel.segment_id for projection in self.projections
        )
        side_counts = Counter(projection.channel.side for projection in self.projections)
        group_counts = Counter(
            projection.channel.spatial_group for projection in self.projections
        )
        return {
            "model_id": self.model_id,
            "dataset_id": self.dataset_id,
            "status": self.status,
            "identity_curated": self.is_identity_curated,
            "release_ready": self.is_scientifically_ready,
            "resolved_neurons": len({item.neuron_id for item in self.projections}),
            "projections": len(self.projections),
            "unresolved_neuron_ids": list(self.unresolved_neuron_ids),
            "segments": dict(sorted(segment_counts.items())),
            "sides": dict(sorted(side_counts.items())),
            "spatial_groups": dict(sorted(group_counts.items())),
            "missing_gain": sum(item.weight is None for item in self.projections),
            "missing_mechanical_action": sum(
                item.channel.muscle_group is None for item in self.projections
            ),
        }

    def require_scientifically_ready(self) -> None:
        if not self.is_scientifically_ready:
            raise UnvalidatedMappingError(
                "the motor map is not release-ready: unresolved identifiers, muscle "
                "gains, or biomechanical actions remain"
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
        if any(projection.weight is None for projection in self.projections):
            raise UnvalidatedMappingError(
                "anatomical targets are curated, but motor-neuron to muscle gains are not"
            )

        weighted: dict[MuscleChannel, float] = {}
        total_weights: dict[MuscleChannel, float] = {}
        for projection in self.projections:
            assert projection.weight is not None
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
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "neuromuscular"
        / "l1_motor_map_v1.json"
    )


def load_neuromuscular_map(
    spec: BodyModelSpec,
    path: str | Path | None = None,
) -> NeuromuscularMap:
    source_path = Path(path) if path else default_neuromuscular_path()
    raw: dict[str, Any] = json.loads(source_path.read_text(encoding="utf-8"))
    projections = tuple(
        MotorProjection(
            neuron_id=str(item["neuron_id"]),
            neuron_name=item.get("neuron_name"),
            dataset_id=item.get("dataset_id", raw.get("dataset", {}).get("id")),
            channel=MuscleChannel(
                segment_id=str(item["segment_id"]),
                side=str(item["side"]),
                muscle_group=item.get("muscle_group"),
                spatial_group=item.get("spatial_group"),
                target_muscles=tuple(
                    MuscleTarget(
                        number=str(target["number"]),
                        synonym=str(target["synonym"]),
                        evidence=str(target.get("evidence", "listed")),
                    )
                    for target in item.get("target_muscles", [])
                ),
                synapse_type=item.get("synapse_type"),
            ),
            weight=float(item["weight"]) if item.get("weight") is not None else None,
            provenance=str(item["provenance"]),
            source_id=item.get("source_id"),
            gain_provenance=str(item.get("gain_provenance", "unknown")),
        )
        for item in raw["projections"]
    )
    result = NeuromuscularMap(
        model_id=str(raw["model_id"]),
        status=str(raw["status"]),
        projections=projections,
        body_segment_ids=tuple(segment.id for segment in spec.segments),
        unresolved_neuron_ids=tuple(
            str(item["neuron_id"]) for item in raw.get("unresolved_neurons", [])
        ),
        dataset_id=raw.get("dataset", {}).get("id"),
        note=str(raw.get("note", "")),
    )
    result.validate()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit the curated L1 motor-neuron to muscle-target crosswalk"
    )
    parser.add_argument("path", nargs="?", default=None)
    parser.add_argument("--require-release-ready", action="store_true")
    args = parser.parse_args(argv)
    mapping = load_neuromuscular_map(load_body_spec(), args.path)
    print(json.dumps(mapping.audit_summary(), indent=2))
    if args.require_release_ready and not mapping.is_scientifically_ready:
        return 2
    return 0
