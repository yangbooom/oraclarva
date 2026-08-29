"""Environment-to-receptor transduction for the spatial research core."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .spatial import SpatialSensoryState, SpatialStimulus
from .terrain import ContactWorld


def default_environment_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "environment"
        / "l1_synthetic_3d_environment_v0.json"
    )


def load_environment_config(
    path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(path) if path else default_environment_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("status") != "research_approximation":
        raise ValueError("3D environment must remain a research approximation")
    if raw.get("provenance") != "MODEL_FITTED":
        raise ValueError("3D environment parameters must remain model-fitted")
    if tuple(raw.get("causal_contract", ())) != (
        "synthetic_contact_geometry",
        "four_head_receptor_samples",
        "phasic_sensory_transduction",
        "spatial_neural_dynamics",
        "motor_pools",
        "muscle_activation",
        "3d_contact_body_physics",
        "synthetic_contact_geometry",
    ):
        raise ValueError("3D environment causal contract is invalid")
    parameters = raw.get("parameters", {})
    required_positive = (
        "sensing_range_m",
        "pulse_period_s",
        "pulse_duration_s",
        "contact_friction_coefficient",
    )
    if any(float(parameters.get(key, 0.0)) <= 0.0 for key in required_positive):
        raise ValueError("3D environment positive parameters are invalid")
    if any(
        not 0.0 <= float(parameters.get(key, -1.0)) <= 1.0
        for key in ("baseline_intensity", "obstacle_gain")
    ):
        raise ValueError("3D environment intensities must be in [0, 1]")
    if raw.get("release_validated") is not False:
        raise ValueError("synthetic 3D environment cannot be release-validated")
    return raw


@dataclass(frozen=True, slots=True)
class RhythmicObstacleTransduction:
    """Sample four receptor points during fitted phasic sensory windows."""

    world: ContactWorld
    sensing_range_m: float = 120e-6
    pulse_period_s: float = 5.0
    pulse_duration_s: float = 0.1
    baseline_intensity: float = 0.5
    obstacle_gain: float = 0.5
    provenance: str = "MODEL_FITTED"

    @classmethod
    def from_config(
        cls,
        world: ContactWorld,
        path: str | Path | None = None,
    ) -> "RhythmicObstacleTransduction":
        parameters = load_environment_config(path)["parameters"]
        return cls(
            world=world,
            sensing_range_m=float(parameters["sensing_range_m"]),
            pulse_period_s=float(parameters["pulse_period_s"]),
            pulse_duration_s=float(parameters["pulse_duration_s"]),
            baseline_intensity=float(parameters["baseline_intensity"]),
            obstacle_gain=float(parameters["obstacle_gain"]),
        )

    def __post_init__(self) -> None:
        if self.sensing_range_m <= 0.0:
            raise ValueError("sensing range must be positive")
        if self.pulse_period_s <= 0.0:
            raise ValueError("pulse period must be positive")
        if not 0.0 < self.pulse_duration_s <= self.pulse_period_s:
            raise ValueError("pulse duration must be in (0, period]")
        if not 0.0 <= self.baseline_intensity <= 1.0:
            raise ValueError("baseline intensity must be in [0, 1]")
        if not 0.0 <= self.obstacle_gain <= 1.0:
            raise ValueError("obstacle gain must be in [0, 1]")
        if self.baseline_intensity + self.obstacle_gain > 1.0:
            raise ValueError("baseline plus obstacle gain cannot exceed 1")
        if self.provenance != "MODEL_FITTED":
            raise ValueError("obstacle transduction must remain model-fitted")

    def __call__(
        self,
        time_s: float,
        state: SpatialSensoryState,
    ) -> SpatialStimulus:
        if time_s < 0.0:
            raise ValueError("sensory time must be non-negative")
        if time_s % self.pulse_period_s >= self.pulse_duration_s:
            return SpatialStimulus(0.0, 0.0, 0.0, 0.0)
        positions = (
            state.left_head_position_m,
            state.right_head_position_m,
            state.dorsal_head_position_m,
            state.ventral_head_position_m,
        )
        intensities = tuple(
            self.baseline_intensity
            + self.obstacle_gain
            * self.world.receptor_intensity(
                position,
                sensing_range_m=self.sensing_range_m,
            )
            for position in positions
        )
        return SpatialStimulus(*intensities)
