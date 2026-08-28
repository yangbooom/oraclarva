"""Evidence-bounded body-wall muscle identity atlas."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .neuromuscular import SPATIAL_GROUPS


SIDES = ("left", "right")


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
