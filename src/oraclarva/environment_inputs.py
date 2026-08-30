"""Provenance-aware scalar fields and adaptive four-point transduction."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from math import exp, isfinite
from pathlib import Path
from typing import Any, Protocol

from .body3d import Vec3
from .spatial import (
    CHANNELS,
    SpatialClosedLoopLarva,
    SpatialSensoryState,
    SpatialStimulus,
)


MODALITIES = ("light", "temperature", "odor")
POLARITIES = {"increased_excites": 1.0, "decreased_excites": -1.0}


def default_environment_input_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "environment"
        / "l1_multimodal_environment_input_v0.json"
    )


def load_environment_input_config(
    path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(path) if path else default_environment_input_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("status") != "research_approximation":
        raise ValueError("environment input must remain a research approximation")
    if raw.get("stage") != "L1":
        raise ValueError("environment input target stage must remain L1")
    if raw.get("provenance") != "MODEL_FITTED":
        raise ValueError("environment input parameters must remain model-fitted")
    if tuple(raw.get("modalities", ())) != MODALITIES:
        raise ValueError("environment input modalities are invalid")
    if tuple(raw.get("causal_contract", ())) != (
        "analytic_environment_fields",
        "four_head_surface_samples_per_modality",
        "adaptive_receptor_transduction",
        "weighted_receptor_currents",
        "spatial_neural_dynamics",
        "motor_pools",
        "muscle_activation",
        "3d_body_physics",
        "analytic_environment_fields",
    ):
        raise ValueError("environment input causal contract is invalid")
    baseline = float(raw.get("baseline_intensity", -1.0))
    if not 0.0 <= baseline <= 1.0:
        raise ValueError("environment input baseline must be in [0, 1]")
    parameters = raw.get("transduction", {})
    if tuple(parameters) != MODALITIES:
        raise ValueError("environment transduction definitions are invalid")
    for modality, item in parameters.items():
        if item.get("polarity") not in POLARITIES:
            raise ValueError(f"{modality} transduction polarity is invalid")
        if not isinstance(item.get("unit"), str) or not item["unit"]:
            raise ValueError(f"{modality} unit is invalid")
        for key in ("response_scale", "adaptation_tau_s", "weight"):
            value = float(item.get(key, 0.0))
            if not isfinite(value) or value <= 0.0:
                raise ValueError(f"{modality} {key} must be positive")
        gains = (
            float(item.get("spatial_contrast_gain", -1.0)),
            float(item.get("temporal_contrast_gain", -1.0)),
        )
        if (
            any(not isfinite(value) or value < 0.0 for value in gains)
            or not any(gains)
        ):
            raise ValueError(f"{modality} contrast gains are invalid")
        if item.get("provenance") != "MODEL_FITTED":
            raise ValueError(f"{modality} transduction must remain model-fitted")
    if float(parameters["light"]["spatial_contrast_gain"]) <= 0.0:
        raise ValueError("light must retain directional spatial contrast")
    if any(
        float(parameters[modality]["spatial_contrast_gain"]) != 0.0
        for modality in ("temperature", "odor")
    ):
        raise ValueError("temperature and odor must remain temporal-only")
    fixtures = raw.get("validation_fields", {})
    if tuple(fixtures) != MODALITIES:
        raise ValueError("environment validation fields are invalid")
    for modality, fixture in fixtures.items():
        if fixture.get("type") != "linear":
            raise ValueError(f"{modality} validation field must be linear")
        if fixture.get("unit") != parameters[modality]["unit"]:
            raise ValueError(f"{modality} field/transduction units differ")
        if len(fixture.get("origin_m", ())) != 3 or len(
            fixture.get("gradient_per_m", ())
        ) != 3:
            raise ValueError(f"{modality} validation field vectors are invalid")
        numeric = (
            *fixture["origin_m"],
            fixture.get("value_at_origin"),
            *fixture["gradient_per_m"],
            fixture.get("temporal_rate_per_s"),
        )
        if any(value is None or not isfinite(float(value)) for value in numeric):
            raise ValueError(f"{modality} validation field values are invalid")
        if fixture.get("provenance") != "MODEL_FITTED":
            raise ValueError(f"{modality} validation field must remain model-fitted")
    evidence = {
        item.get("doi"): (item.get("stage"), item.get("provenance"))
        for item in raw.get("evidence", ())
    }
    if evidence != {
        "10.7554/eLife.28387": ("L1", "MEASURED_PUBLISHED"),
        "10.7554/eLife.14859": ("L1", "MEASURED_PUBLISHED"),
        "10.1523/JNEUROSCI.4090-09.2010": (
            "L1",
            "MEASURED_PUBLISHED",
        ),
        "10.1073/pnas.1215295110": ("L2", "MEASURED_PUBLISHED"),
        "10.1038/nmeth.1853": ("L2", "MEASURED_PUBLISHED"),
    }:
        raise ValueError("environment input evidence set is invalid")
    if raw.get("release_validated") is not False:
        raise ValueError("environment input cannot be release-validated")
    return raw


class ScalarField(Protocol):
    modality_id: str
    unit: str
    provenance: str

    def sample(self, position_m: Vec3, time_s: float) -> float:
        """Return the scalar value at a physical position and time."""


@dataclass(frozen=True, slots=True)
class LinearScalarField:
    modality_id: str
    unit: str
    origin_m: Vec3
    value_at_origin: float
    gradient_per_m: Vec3
    temporal_rate_per_s: float = 0.0
    lower_bound: float | None = None
    upper_bound: float | None = None
    provenance: str = "MODEL_FITTED"

    def __post_init__(self) -> None:
        if self.modality_id not in MODALITIES:
            raise ValueError("unknown environment modality")
        if not self.unit:
            raise ValueError("field unit cannot be empty")
        numeric = (
            self.origin_m.x,
            self.origin_m.y,
            self.origin_m.z,
            self.value_at_origin,
            self.gradient_per_m.x,
            self.gradient_per_m.y,
            self.gradient_per_m.z,
            self.temporal_rate_per_s,
        )
        if any(not isfinite(value) for value in numeric):
            raise ValueError("field parameters must be finite")
        if self.lower_bound is not None and not isfinite(self.lower_bound):
            raise ValueError("field lower bound must be finite")
        if self.upper_bound is not None and not isfinite(self.upper_bound):
            raise ValueError("field upper bound must be finite")
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError("field lower bound cannot exceed upper bound")
        if self.provenance != "MODEL_FITTED":
            raise ValueError("analytic validation fields must remain model-fitted")

    def sample(self, position_m: Vec3, time_s: float) -> float:
        if time_s < 0.0 or not isfinite(time_s):
            raise ValueError("field sample time must be finite and non-negative")
        if any(
            not isfinite(value)
            for value in (position_m.x, position_m.y, position_m.z)
        ):
            raise ValueError("field sample position must be finite")
        value = (
            self.value_at_origin
            + (position_m - self.origin_m).dot(self.gradient_per_m)
            + self.temporal_rate_per_s * time_s
        )
        if self.lower_bound is not None:
            value = max(self.lower_bound, value)
        if self.upper_bound is not None:
            value = min(self.upper_bound, value)
        return value


@dataclass(frozen=True, slots=True)
class ModalityTransduction:
    modality_id: str
    unit: str
    polarity: str
    response_scale: float
    spatial_contrast_gain: float
    temporal_contrast_gain: float
    adaptation_tau_s: float
    weight: float
    provenance: str = "MODEL_FITTED"

    def __post_init__(self) -> None:
        if self.modality_id not in MODALITIES:
            raise ValueError("unknown transduction modality")
        if not self.unit:
            raise ValueError("transduction unit cannot be empty")
        if self.polarity not in POLARITIES:
            raise ValueError("unknown transduction polarity")
        numeric = (
            self.response_scale,
            self.spatial_contrast_gain,
            self.temporal_contrast_gain,
            self.adaptation_tau_s,
            self.weight,
        )
        if any(not isfinite(value) for value in numeric):
            raise ValueError("transduction parameters must be finite")
        if self.response_scale <= 0.0:
            raise ValueError("response scale must be positive")
        if self.spatial_contrast_gain < 0.0:
            raise ValueError("spatial contrast gain cannot be negative")
        if self.temporal_contrast_gain < 0.0:
            raise ValueError("temporal contrast gain cannot be negative")
        if not self.spatial_contrast_gain and not self.temporal_contrast_gain:
            raise ValueError("at least one contrast gain must be positive")
        if self.adaptation_tau_s <= 0.0:
            raise ValueError("adaptation time constant must be positive")
        if self.weight <= 0.0:
            raise ValueError("modality weight must be positive")
        if self.provenance != "MODEL_FITTED":
            raise ValueError("transduction parameters must remain model-fitted")


@dataclass(frozen=True, slots=True)
class FieldTransductionFrame:
    time_s: float
    raw_values: dict[str, tuple[float, float, float, float]]
    adapted_values: dict[str, tuple[float, float, float, float]]
    drive_values: dict[str, tuple[float, float, float, float]]
    stimulus: SpatialStimulus

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_s": self.time_s,
            "raw_values": {key: list(value) for key, value in self.raw_values.items()},
            "adapted_values": {
                key: list(value) for key, value in self.adapted_values.items()
            },
            "drive_values": {
                key: list(value) for key, value in self.drive_values.items()
            },
            "stimulus": dict(zip(CHANNELS, self.stimulus.values(), strict=True)),
        }


@dataclass(slots=True)
class MultimodalFieldTransduction:
    fields: tuple[ScalarField, ...]
    modalities: tuple[ModalityTransduction, ...]
    baseline_intensity: float = 0.5
    record_frames: bool = False
    provenance: str = "MODEL_FITTED"
    frames: list[FieldTransductionFrame] = field(default_factory=list, init=False)
    _adapted: dict[str, tuple[float, float, float, float]] = field(
        default_factory=dict, init=False
    )
    _last_time_s: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not self.fields or not self.modalities:
            raise ValueError("multimodal transduction requires fields and modalities")
        field_ids = [item.modality_id for item in self.fields]
        modality_ids = [item.modality_id for item in self.modalities]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("environment field modalities must be unique")
        if len(modality_ids) != len(set(modality_ids)):
            raise ValueError("transduction modalities must be unique")
        if set(field_ids) != set(modality_ids):
            raise ValueError("field and transduction modalities must match")
        field_by_id = {item.modality_id: item for item in self.fields}
        for item in self.modalities:
            if field_by_id[item.modality_id].unit != item.unit:
                raise ValueError("field and transduction units must match")
        if not 0.0 <= self.baseline_intensity <= 1.0:
            raise ValueError("baseline intensity must be in [0, 1]")
        if self.provenance != "MODEL_FITTED":
            raise ValueError("multimodal transduction must remain model-fitted")

    @classmethod
    def from_config(
        cls,
        fields: tuple[ScalarField, ...],
        path: str | Path | None = None,
        *,
        enabled_modalities: tuple[str, ...] | None = None,
        record_frames: bool = False,
    ) -> "MultimodalFieldTransduction":
        raw = load_environment_input_config(path)
        enabled = (
            tuple(item.modality_id for item in fields)
            if enabled_modalities is None
            else enabled_modalities
        )
        if not enabled or len(enabled) != len(set(enabled)):
            raise ValueError("enabled modalities must be non-empty and unique")
        if any(item not in MODALITIES for item in enabled):
            raise ValueError("enabled modalities contain an unknown modality")
        field_by_id = {item.modality_id: item for item in fields}
        if set(field_by_id) != set(enabled):
            raise ValueError("provided fields must exactly match enabled modalities")
        specs = []
        for modality_id in enabled:
            item = raw["transduction"][modality_id]
            specs.append(ModalityTransduction(
                modality_id=modality_id,
                unit=item["unit"],
                polarity=item["polarity"],
                response_scale=float(item["response_scale"]),
                spatial_contrast_gain=float(item["spatial_contrast_gain"]),
                temporal_contrast_gain=float(item["temporal_contrast_gain"]),
                adaptation_tau_s=float(item["adaptation_tau_s"]),
                weight=float(item["weight"]),
            ))
        return cls(
            fields=tuple(field_by_id[item] for item in enabled),
            modalities=tuple(specs),
            baseline_intensity=float(raw["baseline_intensity"]),
            record_frames=record_frames,
        )

    def reset(self) -> None:
        self.frames.clear()
        self._adapted.clear()
        self._last_time_s = None

    @staticmethod
    def _positions(
        state: SpatialSensoryState,
    ) -> tuple[Vec3, Vec3, Vec3, Vec3]:
        return (
            state.left_head_position_m,
            state.right_head_position_m,
            state.dorsal_head_position_m,
            state.ventral_head_position_m,
        )

    def __call__(
        self,
        time_s: float,
        state: SpatialSensoryState,
    ) -> SpatialStimulus:
        if time_s < 0.0 or not isfinite(time_s):
            raise ValueError("sensory time must be finite and non-negative")
        if self._last_time_s is not None and time_s < self._last_time_s:
            raise ValueError("sensory time cannot move backwards")
        elapsed = (
            0.0 if self._last_time_s is None else time_s - self._last_time_s
        )
        positions = self._positions(state)
        field_by_id = {item.modality_id: item for item in self.fields}
        total_drive = [0.0] * len(CHANNELS)
        raw_values: dict[str, tuple[float, float, float, float]] = {}
        adapted_values: dict[str, tuple[float, float, float, float]] = {}
        drive_values: dict[str, tuple[float, float, float, float]] = {}
        next_adapted: dict[str, tuple[float, float, float, float]] = {}
        for modality in self.modalities:
            scalar_field = field_by_id[modality.modality_id]
            raw = tuple(
                scalar_field.sample(position, time_s) for position in positions
            )
            adapted = self._adapted.get(modality.modality_id, raw)
            center = sum(raw) / len(raw)
            sign = POLARITIES[modality.polarity]
            drive = tuple(
                modality.weight
                * sign
                * (
                    modality.spatial_contrast_gain
                    * (value - center)
                    / modality.response_scale
                    + modality.temporal_contrast_gain
                    * (value - adapted[index])
                    / modality.response_scale
                )
                for index, value in enumerate(raw)
            )
            for index, value in enumerate(drive):
                total_drive[index] += value
            coupling = (
                0.0
                if elapsed == 0.0
                else 1.0 - exp(-elapsed / modality.adaptation_tau_s)
            )
            next_adapted[modality.modality_id] = tuple(
                value + (raw[index] - value) * coupling
                for index, value in enumerate(adapted)
            )
            raw_values[modality.modality_id] = raw
            adapted_values[modality.modality_id] = adapted
            drive_values[modality.modality_id] = drive
        stimulus = SpatialStimulus(*(
            min(1.0, max(0.0, self.baseline_intensity + value))
            for value in total_drive
        ))
        frame = FieldTransductionFrame(
            time_s=time_s,
            raw_values=raw_values,
            adapted_values=adapted_values,
            drive_values=drive_values,
            stimulus=stimulus,
        )
        if self.record_frames:
            self.frames.append(frame)
        self._adapted = next_adapted
        self._last_time_s = time_s
        return stimulus


def validation_fields(
    path: str | Path | None = None,
    *,
    modalities: tuple[str, ...] = MODALITIES,
) -> tuple[LinearScalarField, ...]:
    raw = load_environment_input_config(path)
    if not modalities or len(modalities) != len(set(modalities)):
        raise ValueError("validation modalities must be non-empty and unique")
    if any(item not in MODALITIES for item in modalities):
        raise ValueError("validation modalities contain an unknown modality")
    result = []
    for modality_id in modalities:
        item = raw["validation_fields"][modality_id]
        result.append(LinearScalarField(
            modality_id=modality_id,
            unit=item["unit"],
            origin_m=Vec3(*map(float, item["origin_m"])),
            value_at_origin=float(item["value_at_origin"]),
            gradient_per_m=Vec3(*map(float, item["gradient_per_m"])),
            temporal_rate_per_s=float(item["temporal_rate_per_s"]),
            lower_bound=(
                None if item.get("lower_bound") is None else float(item["lower_bound"])
            ),
            upper_bound=(
                None if item.get("upper_bound") is None else float(item["upper_bound"])
            ),
        ))
    return tuple(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run provenance-aware multimodal environment input"
    )
    parser.add_argument("--modality", choices=(*MODALITIES, "all"), default="all")
    parser.add_argument("--duration", type=float, default=4.5)
    parser.add_argument("--free", action="store_true")
    args = parser.parse_args(argv)
    enabled = MODALITIES if args.modality == "all" else (args.modality,)
    fields = validation_fields(modalities=enabled)
    protocol = MultimodalFieldTransduction.from_config(
        fields,
        enabled_modalities=enabled,
        record_frames=True,
    )
    result = SpatialClosedLoopLarva(
        ground_z_m=None if args.free else 0.0
    ).run(
        stimulus_protocol=protocol,
        duration_s=args.duration,
    )
    payload = result.to_dict()
    payload["environment_input"] = {
        "modalities": list(enabled),
        "sample_count": len(protocol.frames),
        "first_sample": protocol.frames[0].to_dict(),
        "last_sample": protocol.frames[-1].to_dict(),
        "provenance": protocol.provenance,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
