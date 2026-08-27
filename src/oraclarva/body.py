"""Provenance-aware body specification and scaling calculations."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from math import pi
from pathlib import Path
from typing import Any


ALLOWED_PROVENANCE = {"observed", "derived", "fit", "hypothesis", "synthetic", "constraint"}


@dataclass(frozen=True, slots=True)
class Estimate:
    nominal: float
    lower: float
    upper: float
    provenance: str
    source_id: str | None
    note: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Estimate":
        estimate = cls(
            nominal=float(raw["nominal"]),
            lower=float(raw["lower"]),
            upper=float(raw["upper"]),
            provenance=str(raw["provenance"]),
            source_id=raw.get("source_id"),
            note=str(raw.get("note", "")),
        )
        if not estimate.lower <= estimate.nominal <= estimate.upper:
            raise ValueError("estimate nominal must lie within its bounds")
        if estimate.provenance not in ALLOWED_PROVENANCE:
            raise ValueError(f"unsupported provenance: {estimate.provenance}")
        return estimate


@dataclass(frozen=True, slots=True)
class SegmentSpec:
    id: str
    anatomy: str
    length_fraction: float
    width_scale: float


@dataclass(frozen=True, slots=True)
class SegmentGeometry:
    id: str
    rest_length_m: float
    width_m: float
    height_m: float
    volume_m3: float
    mass_kg: float


@dataclass(frozen=True, slots=True)
class ScaledMechanics:
    linear_scale: float
    segment_k1_n_per_m: float
    segment_k2_n_per_m: float
    segment_c_n_s_per_m: float
    maximum_muscle_force_n: float
    whole_body_mass_kg_from_l3_similarity: float

    @property
    def instantaneous_stiffness_n_per_m(self) -> float:
        return self.segment_k1_n_per_m + self.segment_k2_n_per_m

    @property
    def equilibrium_stiffness_n_per_m(self) -> float:
        return self.segment_k1_n_per_m

    @property
    def relaxation_time_s(self) -> float:
        return self.segment_c_n_s_per_m / self.segment_k2_n_per_m


@dataclass(frozen=True, slots=True)
class BodyModelSpec:
    model_id: str
    total_length: Estimate
    maximum_width: Estimate
    height_to_width_ratio: Estimate
    density: Estimate
    maximum_shortening_fraction: Estimate
    segments: tuple[SegmentSpec, ...]
    l3_mechanics: dict[str, float]
    raw: dict[str, Any]

    def validate(self) -> None:
        if len(self.segments) != 12:
            raise ValueError("L1 v0 requires PSC, T1-T3, and A1-A8 (12 mechanical regions)")
        if len({segment.id for segment in self.segments}) != len(self.segments):
            raise ValueError("segment ids must be unique")
        fraction_sum = sum(segment.length_fraction for segment in self.segments)
        if abs(fraction_sum - 1.0) > 1e-9:
            raise ValueError(f"segment length fractions sum to {fraction_sum}, expected 1")
        if any(segment.length_fraction <= 0 or segment.width_scale <= 0 for segment in self.segments):
            raise ValueError("segment geometry values must be positive")
        if self.total_length.upper > 0.001:
            raise ValueError("L1 upper length exceeds the cited <1 mm cohort constraint")

    def segment_geometry(self) -> tuple[SegmentGeometry, ...]:
        length = self.total_length.nominal
        width = self.maximum_width.nominal
        height_ratio = self.height_to_width_ratio.nominal
        density = self.density.nominal
        result = []
        for segment in self.segments:
            segment_length = length * segment.length_fraction
            segment_width = width * segment.width_scale
            segment_height = segment_width * height_ratio
            volume = pi * (segment_width / 2) * (segment_height / 2) * segment_length
            result.append(
                SegmentGeometry(
                    id=segment.id,
                    rest_length_m=segment_length,
                    width_m=segment_width,
                    height_m=segment_height,
                    volume_m3=volume,
                    mass_kg=volume * density,
                )
            )
        return tuple(result)

    def scaled_mechanics(self) -> ScaledMechanics:
        source = self.l3_mechanics
        scale = self.total_length.nominal / source["total_length_m"]
        return ScaledMechanics(
            linear_scale=scale,
            segment_k1_n_per_m=source["segment_k1_n_per_m"] * scale,
            segment_k2_n_per_m=source["segment_k2_n_per_m"] * scale,
            segment_c_n_s_per_m=source["segment_c_n_s_per_m"] * scale,
            maximum_muscle_force_n=source["maximum_muscle_force_n"] * scale**2,
            whole_body_mass_kg_from_l3_similarity=source["whole_body_mass_kg"] * scale**3,
        )

    @property
    def geometry_mass_kg(self) -> float:
        return sum(segment.mass_kg for segment in self.segment_geometry())

    def provenance_counts(self) -> dict[str, int]:
        counts = {name: 0 for name in sorted(ALLOWED_PROVENANCE)}
        for estimate in (
            self.total_length,
            self.maximum_width,
            self.height_to_width_ratio,
            self.density,
            self.maximum_shortening_fraction,
        ):
            counts[estimate.provenance] += 1
        geometry_provenance = self.raw["segment_geometry_provenance"]["provenance"]
        counts[geometry_provenance] += len(self.segments) * 2
        counts[self.raw["source_l3_mechanics"]["provenance"]] += 6
        return {key: value for key, value in counts.items() if value}


def default_spec_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "body" / "l1_body_v0.json"


def load_body_spec(path: str | Path | None = None) -> BodyModelSpec:
    source_path = Path(path) if path else default_spec_path()
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    geometry = raw["global_geometry"]
    active = raw["active_mechanics"]
    spec = BodyModelSpec(
        model_id=str(raw["model_id"]),
        total_length=Estimate.from_dict(geometry["total_length_m"]),
        maximum_width=Estimate.from_dict(geometry["maximum_width_m"]),
        height_to_width_ratio=Estimate.from_dict(geometry["height_to_width_ratio"]),
        density=Estimate.from_dict(geometry["density_kg_m3"]),
        maximum_shortening_fraction=Estimate.from_dict(active["maximum_shortening_fraction"]),
        segments=tuple(
            SegmentSpec(
                id=str(segment["id"]),
                anatomy=str(segment["anatomy"]),
                length_fraction=float(segment["length_fraction"]),
                width_scale=float(segment["width_scale"]),
            )
            for segment in raw["segments"]
        ),
        l3_mechanics={
            key: float(value)
            for key, value in raw["source_l3_mechanics"].items()
            if key not in {"provenance", "source_id"}
        },
        raw=raw,
    )
    spec.validate()
    return spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect and validate an Oraclarva body specification")
    parser.add_argument("path", nargs="?", default=None)
    args = parser.parse_args(argv)
    spec = load_body_spec(args.path)
    mechanics = spec.scaled_mechanics()
    summary = {
        "model_id": spec.model_id,
        "segments": len(spec.segments),
        "nominal_length_um": spec.total_length.nominal * 1e6,
        "nominal_maximum_width_um": spec.maximum_width.nominal * 1e6,
        "geometry_mass_ug": spec.geometry_mass_kg * 1e9,
        "similarity_mass_ug": mechanics.whole_body_mass_kg_from_l3_similarity * 1e9,
        "scaled_k1_n_per_m": mechanics.segment_k1_n_per_m,
        "scaled_k2_n_per_m": mechanics.segment_k2_n_per_m,
        "scaled_c_n_s_per_m": mechanics.segment_c_n_s_per_m,
        "scaled_maximum_muscle_force_mn": mechanics.maximum_muscle_force_n * 1e3,
        "provenance_counts": spec.provenance_counts(),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
