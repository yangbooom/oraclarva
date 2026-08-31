"""Evidence-bounded body-wall muscle identity atlas."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from math import exp, isfinite
from pathlib import Path
from typing import Any, Iterable, Mapping

from .neuromuscular import SPATIAL_GROUPS


SIDES = ("left", "right")
DORSOVENTRAL_AXES = ("dorsal", "ventral")
DORSAL_SPATIAL_GROUPS = frozenset({"DL", "DO"})
VENTRAL_SPATIAL_GROUPS = frozenset({"VL", "VA", "VO"})


@dataclass(frozen=True, slots=True)
class MuscleIdentity:
    number: str
    synonym: str
    spatial_group: str


@dataclass(frozen=True, slots=True)
class MuscleFiberIdentity:
    segment_id: str
    side: str
    muscle: MuscleIdentity
    provenance: str


@dataclass(frozen=True, slots=True)
class NeuralMuscleIdentityMapping:
    source_node_id: str
    fiber_id: str
    segment_id: str
    side: str
    muscle_number: str
    mapping_provenance: str


@dataclass(frozen=True, slots=True)
class NeuralMuscleIdentityEventFrame:
    source_spikes: tuple[str, ...]
    fiber_events: tuple[str, ...]
    source_by_fiber: Mapping[str, str]
    mapping_provenance_by_fiber: Mapping[str, str]
    event_rule_provenance: str = "ANATOMY_DERIVED"
    activation_dynamics_executed: bool = False
    individual_geometry_executed: bool = False


@dataclass(frozen=True, slots=True)
class NeuralMuscleActivationFrame:
    time_s: float
    activations: Mapping[str, float]
    applied_event_fibers: tuple[str, ...]
    applied_source_by_fiber: Mapping[str, str]
    applied_spike_time_s_by_fiber: Mapping[str, float]
    mapping_provenance_by_fiber: Mapping[str, str]
    parameter_provenance: str = "MODEL_FITTED"
    individual_geometry_executed: bool = False
    mechanical_force_executed: bool = False

    @property
    def active_fiber_count(self) -> int:
        return sum(value > 0.0 for value in self.activations.values())


@dataclass(slots=True)
class NeuralMuscleActivationModel:
    """One-step-delayed, bounded activation for mapped muscle identities."""

    projection: "NeuralMuscleIdentityProjection"
    dt_s: float
    rise_tau_s: float
    decay_tau_s: float
    event_target: float
    activations: dict[str, float] = field(init=False)
    first_activation_s: dict[str, float | None] = field(init=False)
    last_applied_spike_s: dict[str, float | None] = field(init=False)
    last_applied_source: dict[str, str | None] = field(init=False)
    _pending_event: dict[str, tuple[str, float, str]] = field(
        init=False, repr=False
    )
    _step_index: int = field(init=False, default=0, repr=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("dt_s", self.dt_s),
            ("rise_tau_s", self.rise_tau_s),
            ("decay_tau_s", self.decay_tau_s),
            ("event_target", self.event_target),
        ):
            if not isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError(f"muscle activation {name} must be positive")
        if self.dt_s >= min(self.rise_tau_s, self.decay_tau_s):
            raise ValueError(
                "muscle activation timestep must be below both time constants"
            )
        if self.event_target > 1.0:
            raise ValueError("muscle activation event target cannot exceed one")
        fiber_ids = self.projection.mapped_fiber_ids
        self.activations = {fiber_id: 0.0 for fiber_id in fiber_ids}
        self.first_activation_s = {fiber_id: None for fiber_id in fiber_ids}
        self.last_applied_spike_s = {fiber_id: None for fiber_id in fiber_ids}
        self.last_applied_source = {fiber_id: None for fiber_id in fiber_ids}
        self._pending_event = {}

    def step(
        self,
        time_s: float,
        events: NeuralMuscleIdentityEventFrame,
    ) -> NeuralMuscleActivationFrame:
        expected_time = self._step_index * self.dt_s
        if not isfinite(time_s) or abs(time_s - expected_time) > 1e-9:
            raise ValueError(
                "muscle activation must be stepped once per dt in order"
            )
        applied = dict(self._pending_event)
        rise_fraction = 1.0 - exp(-self.dt_s / self.rise_tau_s)
        decay_fraction = 1.0 - exp(-self.dt_s / self.decay_tau_s)
        for fiber_id, activation in self.activations.items():
            if fiber_id in applied:
                target = self.event_target
                updated = activation + (target - activation) * rise_fraction
                source, spike_time_s, _ = applied[fiber_id]
                if not spike_time_s < time_s:
                    raise ValueError(
                        "muscle activation input spike must precede activation"
                    )
                self.last_applied_spike_s[fiber_id] = spike_time_s
                self.last_applied_source[fiber_id] = source
            else:
                updated = activation + (0.0 - activation) * decay_fraction
            bounded = min(1.0, max(0.0, updated))
            self.activations[fiber_id] = bounded
            if bounded > 0.0 and self.first_activation_s[fiber_id] is None:
                self.first_activation_s[fiber_id] = time_s

        self._pending_event = {
            fiber_id: (
                events.source_by_fiber[fiber_id],
                time_s,
                events.mapping_provenance_by_fiber[fiber_id],
            )
            for fiber_id in events.fiber_events
        }
        self._step_index += 1
        return NeuralMuscleActivationFrame(
            time_s=time_s,
            activations=dict(self.activations),
            applied_event_fibers=tuple(applied),
            applied_source_by_fiber={
                fiber_id: value[0] for fiber_id, value in applied.items()
            },
            applied_spike_time_s_by_fiber={
                fiber_id: value[1] for fiber_id, value in applied.items()
            },
            mapping_provenance_by_fiber={
                fiber_id: value[2] for fiber_id, value in applied.items()
            },
        )


@dataclass(frozen=True, slots=True)
class NeuralMuscleIdentityProjection:
    """Emit named-fiber events from explicitly mapped neural outputs only."""

    model_id: str
    status: str
    mappings: tuple[NeuralMuscleIdentityMapping, ...]
    atlas_fiber_ids: frozenset[str]

    @property
    def mapped_fiber_ids(self) -> tuple[str, ...]:
        return tuple(item.fiber_id for item in self.mappings)

    @property
    def source_node_ids(self) -> frozenset[str]:
        return frozenset(item.source_node_id for item in self.mappings)

    def emit(
        self,
        spiked_node_ids: Iterable[str],
        *,
        lesioned_fiber_ids: Iterable[str] = (),
    ) -> NeuralMuscleIdentityEventFrame:
        spikes = tuple(spiked_node_ids)
        if len(spikes) != len(set(spikes)):
            raise ValueError("source spike ids must be unique within one step")
        unknown_sources = set(spikes) - self.source_node_ids
        if unknown_sources:
            raise ValueError(
                f"unmapped neural-muscle source spikes: {sorted(unknown_sources)}"
            )
        lesions = tuple(lesioned_fiber_ids)
        if len(lesions) != len(set(lesions)):
            raise ValueError("muscle fiber lesion ids must be unique")
        unknown_lesions = set(lesions) - self.atlas_fiber_ids
        if unknown_lesions:
            raise ValueError(
                f"muscle fiber lesion outside A1-A6 atlas: {sorted(unknown_lesions)}"
            )
        spiked = set(spikes)
        lesioned = set(lesions)
        recruited = tuple(
            item
            for item in self.mappings
            if item.source_node_id in spiked and item.fiber_id not in lesioned
        )
        return NeuralMuscleIdentityEventFrame(
            source_spikes=spikes,
            fiber_events=tuple(item.fiber_id for item in recruited),
            source_by_fiber={
                item.fiber_id: item.source_node_id for item in recruited
            },
            mapping_provenance_by_fiber={
                item.fiber_id: item.mapping_provenance for item in recruited
            },
        )


@dataclass(frozen=True, slots=True)
class AbdominalMuscleAtlas:
    model_id: str
    status: str
    supported_segments: tuple[str, ...]
    blocked_segments: tuple[str, ...]
    a1_missing_muscles: tuple[str, ...]
    template: tuple[MuscleIdentity, ...]
    mechanically_executable: bool
    geometry_gate: dict[str, Any]

    def validate(self) -> None:
        numbers = tuple(muscle.number for muscle in self.template)
        if numbers != tuple(str(number) for number in range(1, 31)):
            raise ValueError("abdominal template must contain muscles 1-30 exactly once")
        if set(self.supported_segments) & set(self.blocked_segments):
            raise ValueError("muscle coverage cannot be both supported and blocked")
        if self.supported_segments != ("A1", "A2", "A3", "A4", "A5", "A6"):
            raise ValueError("v0 homology evidence is restricted to A1-A6")
        if self.a1_missing_muscles != ("25",):
            raise ValueError("A1 must differ from A2-A6 by muscle 25")
        for muscle in self.template:
            if muscle.spatial_group not in SPATIAL_GROUPS - {"Broad"}:
                raise ValueError(f"unsupported muscle spatial group {muscle.spatial_group}")
        if self.mechanically_executable:
            required = (
                "individual_layer_assignments_complete",
                "attachment_coordinates_complete",
                "lines_of_action_complete",
            )
            if not all(self.geometry_gate.get(key) for key in required):
                raise ValueError("mechanical execution requires complete muscle geometry")

    def fibers_for_segment(self, segment_id: str) -> tuple[MuscleFiberIdentity, ...]:
        if segment_id not in self.supported_segments:
            raise ValueError(f"segment {segment_id} has no supported v0 muscle homology")
        absent = set(self.a1_missing_muscles) if segment_id == "A1" else set()
        provenance = "observed_identity" if segment_id == "A1" else "derived_homology"
        return tuple(
            MuscleFiberIdentity(segment_id, side, muscle, provenance)
            for side in SIDES
            for muscle in self.template
            if muscle.number not in absent
        )

    @property
    def all_supported_fibers(self) -> tuple[MuscleFiberIdentity, ...]:
        return tuple(
            fiber
            for segment in self.supported_segments
            for fiber in self.fibers_for_segment(segment)
        )

    @property
    def is_full_body_ready(self) -> bool:
        return not self.blocked_segments and self.mechanically_executable

    def audit_summary(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "status": self.status,
            "supported_segments": list(self.supported_segments),
            "blocked_segments": list(self.blocked_segments),
            "fibers_per_segment": {
                segment: len(self.fibers_for_segment(segment))
                for segment in self.supported_segments
            },
            "supported_fibers": len(self.all_supported_fibers),
            "mechanically_executable": self.mechanically_executable,
            "full_body_ready": self.is_full_body_ready,
            "geometry_gate": self.geometry_gate,
        }


@dataclass(frozen=True, slots=True)
class MuscleIdentityRecruitmentFrame:
    activations: Mapping[str, float]
    segment_by_fiber: Mapping[str, str]
    provenance: str = "MODEL_FITTED"
    individual_geometry_executed: bool = False

    @property
    def active_fiber_count(self) -> int:
        return sum(value > 0.0 for value in self.activations.values())


@dataclass(frozen=True, slots=True)
class BilateralMuscleIdentityRecruitmentFrame:
    activations: Mapping[str, float]
    segment_by_fiber: Mapping[str, str]
    side_by_fiber: Mapping[str, str]
    provenance: str = "MODEL_FITTED"
    individual_geometry_executed: bool = False

    @property
    def active_fiber_count(self) -> int:
        return sum(value > 0.0 for value in self.activations.values())


@dataclass(frozen=True, slots=True)
class DorsoventralMuscleIdentityRecruitmentFrame:
    activations: Mapping[str, float]
    segment_by_fiber: Mapping[str, str]
    axis_by_fiber: Mapping[str, str | None]
    provenance: str = "MODEL_FITTED"
    individual_geometry_executed: bool = False

    @property
    def active_fiber_count(self) -> int:
        return sum(value > 0.0 for value in self.activations.values())


@dataclass(frozen=True, slots=True)
class AggregateMuscleIdentityProjection:
    """Research proxy from aggregate activation through named A1-A6 fibers.

    Equal recruitment is MODEL_FITTED and is aggregated back to one axial
    actuator per segment. No individual attachment, line of action, CSA, or
    force gain is implied.
    """

    atlas: AbdominalMuscleAtlas
    fibers: tuple[MuscleFiberIdentity, ...] = field(init=False, repr=False)
    identities: tuple[str, ...] = field(init=False, repr=False)
    segment_by_fiber: Mapping[str, str] = field(init=False, repr=False)
    expected_counts: Mapping[str, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        fibers = self.atlas.all_supported_fibers
        identities = tuple(self.fiber_id(fiber) for fiber in fibers)
        object.__setattr__(self, "fibers", fibers)
        object.__setattr__(self, "identities", identities)
        object.__setattr__(
            self,
            "segment_by_fiber",
            {
                identity: fiber.segment_id
                for identity, fiber in zip(identities, fibers, strict=True)
            },
        )
        object.__setattr__(
            self,
            "expected_counts",
            {
                segment_id: len(self.atlas.fibers_for_segment(segment_id))
                for segment_id in self.atlas.supported_segments
            },
        )

    @staticmethod
    def fiber_id(fiber: MuscleFiberIdentity) -> str:
        return (
            f"{fiber.segment_id}:{fiber.side}:"
            f"M{fiber.muscle.number}:{fiber.muscle.synonym}"
        )

    def project(
        self,
        segment_activations: Mapping[str, float],
        *,
        lesioned_segments: tuple[str, ...] = (),
    ) -> MuscleIdentityRecruitmentFrame:
        unknown_lesions = set(lesioned_segments) - set(self.atlas.supported_segments)
        if unknown_lesions:
            raise ValueError(
                f"muscle identity lesion outside A1-A6 atlas: {sorted(unknown_lesions)}"
            )
        for segment_id, activation in segment_activations.items():
            if not 0.0 <= float(activation) <= 1.0:
                raise ValueError(
                    f"aggregate activation for {segment_id} must be in [0, 1]"
                )
        lesioned = set(lesioned_segments)
        activations = {
            identity: (
                0.0
                if fiber.segment_id in lesioned
                else float(segment_activations.get(fiber.segment_id, 0.0))
            )
            for identity, fiber in zip(
                self.identities, self.fibers, strict=True
            )
        }
        return MuscleIdentityRecruitmentFrame(
            activations=activations,
            segment_by_fiber=self.segment_by_fiber,
        )

    def project_bilateral(
        self,
        segment_activations: Mapping[str, tuple[float, float]],
        *,
        lesioned_channels: tuple[tuple[str, str], ...] = (),
    ) -> BilateralMuscleIdentityRecruitmentFrame:
        valid_channels = {
            (segment, side)
            for segment in self.atlas.supported_segments
            for side in SIDES
        }
        unknown_lesions = set(lesioned_channels) - valid_channels
        if unknown_lesions:
            raise ValueError(
                f"bilateral muscle lesion outside A1-A6 atlas: {sorted(unknown_lesions)}"
            )
        for segment_id, pair in segment_activations.items():
            if len(pair) != 2 or any(
                not 0.0 <= float(value) <= 1.0 for value in pair
            ):
                raise ValueError(
                    f"bilateral activation for {segment_id} must be a left/right pair in [0, 1]"
                )
        lesioned = set(lesioned_channels)
        activations = {}
        side_by_fiber = {}
        for identity, fiber in zip(self.identities, self.fibers, strict=True):
            pair = segment_activations.get(fiber.segment_id, (0.0, 0.0))
            side_index = SIDES.index(fiber.side)
            activations[identity] = (
                0.0
                if (fiber.segment_id, fiber.side) in lesioned
                else float(pair[side_index])
            )
            side_by_fiber[identity] = fiber.side
        return BilateralMuscleIdentityRecruitmentFrame(
            activations=activations,
            segment_by_fiber=self.segment_by_fiber,
            side_by_fiber=side_by_fiber,
        )

    def project_dorsoventral(
        self,
        segment_activations: Mapping[str, tuple[float, float]],
        *,
        lesioned_channels: tuple[tuple[str, str], ...] = (),
    ) -> DorsoventralMuscleIdentityRecruitmentFrame:
        valid_channels = {
            (segment, axis)
            for segment in self.atlas.supported_segments
            for axis in DORSOVENTRAL_AXES
        }
        unknown_lesions = set(lesioned_channels) - valid_channels
        if unknown_lesions:
            raise ValueError(
                "dorsoventral muscle lesion outside A1-A6 atlas: "
                f"{sorted(unknown_lesions)}"
            )
        for segment_id, pair in segment_activations.items():
            if len(pair) != 2 or any(
                not 0.0 <= float(value) <= 1.0 for value in pair
            ):
                raise ValueError(
                    f"dorsoventral activation for {segment_id} must be a "
                    "dorsal/ventral pair in [0, 1]"
                )
        lesioned = set(lesioned_channels)
        activations = {}
        axis_by_fiber: dict[str, str | None] = {}
        for identity, fiber in zip(self.identities, self.fibers, strict=True):
            if fiber.muscle.spatial_group in DORSAL_SPATIAL_GROUPS:
                axis = "dorsal"
                axis_index = 0
            elif fiber.muscle.spatial_group in VENTRAL_SPATIAL_GROUPS:
                axis = "ventral"
                axis_index = 1
            else:
                axis = None
                axis_index = 0
            pair = segment_activations.get(fiber.segment_id, (0.0, 0.0))
            activations[identity] = (
                0.0
                if axis is None or (fiber.segment_id, axis) in lesioned
                else float(pair[axis_index])
            )
            axis_by_fiber[identity] = axis
        return DorsoventralMuscleIdentityRecruitmentFrame(
            activations=activations,
            segment_by_fiber=self.segment_by_fiber,
            axis_by_fiber=axis_by_fiber,
        )

    def dorsoventral_axial_proxy(
        self,
        frame: DorsoventralMuscleIdentityRecruitmentFrame,
        segment_activations: Mapping[str, tuple[float, float]],
    ) -> dict[str, tuple[float, float]]:
        result = {
            key: (float(value[0]), float(value[1]))
            for key, value in segment_activations.items()
        }
        sums = {
            (segment_id, axis): 0.0
            for segment_id in self.atlas.supported_segments
            for axis in DORSOVENTRAL_AXES
        }
        counts = {channel: 0 for channel in sums}
        for identity, activation in frame.activations.items():
            axis = frame.axis_by_fiber[identity]
            if axis is None:
                continue
            channel = (frame.segment_by_fiber[identity], axis)
            sums[channel] += activation
            counts[channel] += 1
        for segment_id in self.atlas.supported_segments:
            values = []
            for axis in DORSOVENTRAL_AXES:
                channel = (segment_id, axis)
                if counts[channel] == 0:
                    raise ValueError(
                        f"missing dorsoventral identities for {segment_id}:{axis}"
                    )
                values.append(sums[channel] / counts[channel])
            result[segment_id] = (values[0], values[1])
        return result

    def bilateral_axial_proxy(
        self,
        frame: BilateralMuscleIdentityRecruitmentFrame,
        segment_activations: Mapping[str, tuple[float, float]],
    ) -> dict[str, tuple[float, float]]:
        result = {
            key: (float(value[0]), float(value[1]))
            for key, value in segment_activations.items()
        }
        sums = {
            (segment_id, side): 0.0
            for segment_id in self.atlas.supported_segments
            for side in SIDES
        }
        counts = {channel: 0 for channel in sums}
        for identity, activation in frame.activations.items():
            channel = (
                frame.segment_by_fiber[identity],
                frame.side_by_fiber[identity],
            )
            sums[channel] += activation
            counts[channel] += 1
        for segment_id in self.atlas.supported_segments:
            expected_per_side = self.expected_counts[segment_id] // 2
            values = []
            for side in SIDES:
                channel = (segment_id, side)
                if counts[channel] != expected_per_side:
                    raise ValueError(
                        f"incomplete bilateral identity recruitment for {segment_id}:{side}"
                    )
                values.append(sums[channel] / counts[channel])
            result[segment_id] = (values[0], values[1])
        return result

    def axial_proxy(
        self,
        frame: MuscleIdentityRecruitmentFrame,
        segment_activations: Mapping[str, float],
    ) -> dict[str, float]:
        result = {key: float(value) for key, value in segment_activations.items()}
        sums = {segment_id: 0.0 for segment_id in self.atlas.supported_segments}
        counts = {segment_id: 0 for segment_id in self.atlas.supported_segments}
        for identity, activation in frame.activations.items():
            segment_id = frame.segment_by_fiber[identity]
            sums[segment_id] += activation
            counts[segment_id] += 1
        for segment_id in self.atlas.supported_segments:
            expected = self.expected_counts[segment_id]
            if counts[segment_id] != expected:
                raise ValueError(
                    f"incomplete identity recruitment for {segment_id}"
                )
            result[segment_id] = sums[segment_id] / counts[segment_id]
        return result


def default_muscle_atlas_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "muscles"
        / "l1_abdominal_muscle_template_v0.json"
    )


def load_muscle_atlas(path: str | Path | None = None) -> AbdominalMuscleAtlas:
    source_path = Path(path) if path else default_muscle_atlas_path()
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    scope = raw["scope"]
    result = AbdominalMuscleAtlas(
        model_id=str(raw["model_id"]),
        status=str(raw["status"]),
        supported_segments=tuple(scope["homology_supported_segments"]),
        blocked_segments=tuple(scope["blocked_segments"]),
        a1_missing_muscles=tuple(scope["A1_missing_muscles"]),
        template=tuple(
            MuscleIdentity(
                number=str(item["number"]),
                synonym=str(item["synonym"]),
                spatial_group=str(item["spatial_group"]),
            )
            for item in raw["muscles"]
        ),
        mechanically_executable=bool(raw["geometry_gate"]["mechanically_executable"]),
        geometry_gate=dict(raw["geometry_gate"]),
    )
    result.validate()
    return result


def default_neural_muscle_identity_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "neuromuscular"
        / "l1_neural_muscle_identity_v0.json"
    )


def load_neural_muscle_identity_projection(
    path: str | Path | None = None,
    *,
    atlas: AbdominalMuscleAtlas | None = None,
) -> NeuralMuscleIdentityProjection:
    source_path = Path(path) if path else default_neural_muscle_identity_path()
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    if (
        raw.get("model_id") != "dmel_l1_neural_muscle_identity_v0"
        or raw.get("stage") != "L1"
        or raw.get("status")
        != "identity_event_mapping_only_not_activation_or_mechanics"
    ):
        raise ValueError("unexpected neural-muscle identity mapping")
    semantics = raw.get("event_semantics", {})
    if (
        semantics.get("provenance") != "ANATOMY_DERIVED"
        or semantics.get("activation_dynamics_executed") is not False
        or semantics.get("individual_geometry_executed") is not False
        or semantics.get("mechanical_force_executed") is not False
        or semantics.get("nmj_location_claimed") is not False
    ):
        raise ValueError("neural-muscle event claim boundary is invalid")
    muscle_atlas = atlas or load_muscle_atlas()
    aggregate = AggregateMuscleIdentityProjection(muscle_atlas)
    atlas_ids = frozenset(aggregate.identities)
    mappings = tuple(
        NeuralMuscleIdentityMapping(
            source_node_id=str(item["source_node_id"]),
            fiber_id=str(item["fiber_id"]),
            segment_id=str(item["segment"]),
            side=str(item["side"]),
            muscle_number=str(item["muscle"]["number"]),
            mapping_provenance=str(item["mapping_provenance"]),
        )
        for item in raw.get("mappings", ())
    )
    fiber_ids = tuple(item.fiber_id for item in mappings)
    pairs = tuple((item.source_node_id, item.fiber_id) for item in mappings)
    if (
        len(mappings) != 146
        or len(fiber_ids) != len(set(fiber_ids))
        or len(pairs) != len(set(pairs))
        or not set(fiber_ids) <= atlas_ids
    ):
        raise ValueError("neural-muscle mapping identity boundary is invalid")
    for item in mappings:
        expected_prefix = (
            f"{item.segment_id}:{item.side}:M{item.muscle_number}:"
        )
        if not item.fiber_id.startswith(expected_prefix):
            raise ValueError(f"fiber metadata mismatch for {item.fiber_id}")
        expected_provenance = (
            "MEASURED_PUBLISHED"
            if item.segment_id == "A1"
            else "ANATOMY_DERIVED"
        )
        if item.mapping_provenance != expected_provenance:
            raise ValueError(f"mapping provenance mismatch for {item.fiber_id}")
    summary = raw.get("summary", {})
    if summary != {
        "atlas_fibers": 358,
        "mapped_unique_fibers": 146,
        "unmapped_fibers": 212,
        "observed_a1_motor_identities": 14,
        "observed_a1_identity_mappings": 16,
        "derived_a2_a6_identity_mappings": 130,
        "total_identity_mappings": 146,
        "blocked_segments": ["A7"],
    }:
        raise ValueError("neural-muscle mapping count contract is invalid")
    return NeuralMuscleIdentityProjection(
        model_id=str(raw["model_id"]),
        status=str(raw["status"]),
        mappings=mappings,
        atlas_fiber_ids=atlas_ids,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the L1 abdominal muscle atlas")
    parser.add_argument("path", nargs="?", default=None)
    parser.add_argument("--require-full-body-ready", action="store_true")
    args = parser.parse_args(argv)
    atlas = load_muscle_atlas(args.path)
    print(json.dumps(atlas.audit_summary(), indent=2))
    if args.require_full_body_ready and not atlas.is_full_body_ready:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
