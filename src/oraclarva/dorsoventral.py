"""Dorsal/ventral neural-muscle pitch research model without actions."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from math import atan2, degrees, hypot
from pathlib import Path
from typing import Any, Callable

from .bilateral import BilateralClosedLoopLarva, BilateralStimulus
from .body3d import ScientificBody3D, Vec3


AXES = ("dorsal", "ventral")


def default_dorsoventral_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "organism"
        / "l1_dorsoventral_pitch_v0.json"
    )


def load_dorsoventral_config(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else default_dorsoventral_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("status") != "research_approximation":
        raise ValueError("dorsoventral pitch must remain a research approximation")
    if tuple(raw.get("channels", ())) != AXES:
        raise ValueError("dorsoventral pitch requires dorsal and ventral channels")
    expected_contract = (
        "environment",
        "dorsoventral_sensory_transduction",
        "dorsoventral_neural_dynamics",
        "opposed_motor_pools",
        "spatial_group_muscle_activation",
        "local_binormal_body_physics",
        "environment",
    )
    if tuple(raw.get("causal_contract", ())) != expected_contract:
        raise ValueError("dorsoventral causal contract is invalid")
    if raw.get("topology", {}).get("provenance") != "ANATOMY_DERIVED":
        raise ValueError("dorsoventral topology must remain anatomy-derived")
    if raw.get("parameter_provenance", {}).get("provenance") != "MODEL_FITTED":
        raise ValueError("dorsoventral parameters must remain model-fitted")
    parameters = raw.get("parameters", {})
    if float(parameters.get("active_pitch_curvature_gain", 0.0)) <= 0.0:
        raise ValueError("active pitch curvature gain must be positive")
    if tuple(parameters.get("asymmetric_anterior_segments", ())) != (
        "T1", "T2", "T3", "A1", "A2"
    ):
        raise ValueError("dorsoventral asymmetric output must remain T1-A2")
    muscles = raw.get("muscle_identity_projection", {})
    if muscles.get("spatial_group_mapping_provenance") != "MEASURED_PUBLISHED":
        raise ValueError("dorsoventral spatial groups must remain source-backed")
    if set(muscles.get("dorsal_groups", ())) != {"DL", "DO"}:
        raise ValueError("dorsal muscle groups are invalid")
    if set(muscles.get("ventral_groups", ())) != {"VL", "VA", "VO"}:
        raise ValueError("ventral muscle groups are invalid")
    if muscles.get("mechanically_executable_individual_geometry") is not False:
        raise ValueError("individual pitch geometry cannot be release-ready")
    evidence_dois = {item.get("doi") for item in raw.get("evidence", ())}
    if evidence_dois != {
        "10.7554/eLife.51781",
        "10.7554/eLife.38740",
        "10.1371/journal.pone.0135011",
    }:
        raise ValueError("dorsoventral evidence set is invalid")
    if raw.get("release_validated") is not False:
        raise ValueError("dorsoventral approximation cannot be release-validated")
    return raw


@dataclass(frozen=True, slots=True)
class DorsoventralStimulus:
    dorsal_touch_intensity: float = 1.0
    ventral_touch_intensity: float = 1.0

    def __post_init__(self) -> None:
        if any(
            not 0.0 <= value <= 1.0
            for value in (
                self.dorsal_touch_intensity,
                self.ventral_touch_intensity,
            )
        ):
            raise ValueError("dorsoventral touch intensity must be in [0, 1]")

    def as_opposed_stimulus(self) -> BilateralStimulus:
        return BilateralStimulus(
            self.dorsal_touch_intensity,
            self.ventral_touch_intensity,
        )


@dataclass(frozen=True, slots=True)
class DorsoventralSensoryState:
    dorsal_head_position_m: Vec3
    ventral_head_position_m: Vec3

    @classmethod
    def from_body(cls, body: ScientificBody3D) -> "DorsoventralSensoryState":
        return cls(
            dorsal_head_position_m=body.dorsoventral_surface_position_m(
                0, "dorsal"
            ),
            ventral_head_position_m=body.dorsoventral_surface_position_m(
                0, "ventral"
            ),
        )


DorsoventralStimulusProtocol = Callable[
    [float, DorsoventralSensoryState], DorsoventralStimulus
]


@dataclass(frozen=True, slots=True)
class DorsoventralClosedLoopResult:
    model_id: str
    status: str
    neuron_count: int
    duration_s: float
    displacement_x_um: float
    displacement_y_um: float
    displacement_z_um: float
    head_pitch_change_deg: float
    head_height_change_um: float
    minimum_head_pitch_deg: float
    maximum_head_pitch_deg: float
    minimum_head_height_um: float
    maximum_head_height_um: float
    spike_counts: dict[str, int]
    first_spike_s: dict[str, float | None]
    peak_activation: dict[str, dict[str, float]]
    peak_shortening_fraction: dict[str, dict[str, float]]
    peak_recruited_fibers: int
    trajectory_samples: tuple[dict[str, Any], ...]
    trajectory_sample_interval_s: float | None
    premotor_lesion: tuple[str, str] | None
    muscle_lesion: tuple[str, str] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "status": self.status,
            "neuron_count": self.neuron_count,
            "duration_s": self.duration_s,
            "displacement_x_um": self.displacement_x_um,
            "displacement_y_um": self.displacement_y_um,
            "displacement_z_um": self.displacement_z_um,
            "head_pitch_change_deg": self.head_pitch_change_deg,
            "head_height_change_um": self.head_height_change_um,
            "minimum_head_pitch_deg": self.minimum_head_pitch_deg,
            "maximum_head_pitch_deg": self.maximum_head_pitch_deg,
            "minimum_head_height_um": self.minimum_head_height_um,
            "maximum_head_height_um": self.maximum_head_height_um,
            "peak_recruited_fibers": self.peak_recruited_fibers,
            "release_validated": False,
            "claim_boundary": (
                "opposed dorsal/ventral research approximation; not a complete "
                "L1 pitch connectome or measured attachment/moment-arm model"
            ),
        }


class DorsoventralClosedLoopLarva(BilateralClosedLoopLarva):
    """Opposed dorsal/ventral circuit driving local-binormal body curvature."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        lesion_premotor_channel: tuple[str, str] | None = None,
        lesion_muscle_channel: tuple[str, str] | None = None,
        ground_z_m: float | None = 0.0,
    ) -> None:
        super().__init__(
            config or load_dorsoventral_config(),
            lesion_premotor_channel=lesion_premotor_channel,
            lesion_muscle_channel=lesion_muscle_channel,
            _opposed_channels=AXES,
            _actuation_axis="pitch",
            _include_motor_identities=False,
            _sensory_state_factory=DorsoventralSensoryState.from_body,
            _ground_z_m=ground_z_m,
            _wave_segments=(
                "A7", "A6", "A5", "A4", "A3",
                "A2", "A1", "T3", "T2", "T1",
            ),
        )
        self._equilibrate_initial_body()

    def _equilibrate_initial_body(self) -> None:
        dt = float(self.params["dt_s"])
        gravity = (
            Vec3(0.0, 0.0, -9.81)
            if self.ground_z_m is not None
            else Vec3(0.0, 0.0, 0.0)
        )
        for _ in range(50):
            self.body.step(
                dt,
                gravity=gravity,
                ground_z=self.ground_z_m,
                velocity_retention=float(self.params["body_velocity_retention"]),
                ground_velocity_retention_x=(
                    float(self.params["ground_negative_x_retention"]),
                    float(self.params["ground_positive_x_retention"]),
                ),
                use_local_tangent_friction=True,
            )
        for particle in self.body.particles:
            particle.previous_position = particle.position

    def _observe_body_step(
        self, time_s: float, body: ScientificBody3D
    ) -> None:
        del time_s
        head_pitch = -(
            self._body_axis_pitch_deg(body) - self._initial_axis_pitch_deg
        )
        head_height_um = (
            body.particles[0].position.z - self._initial_head_z_m
        ) * 1e6
        self._minimum_head_pitch_deg = min(
            self._minimum_head_pitch_deg, head_pitch
        )
        self._maximum_head_pitch_deg = max(
            self._maximum_head_pitch_deg, head_pitch
        )
        self._minimum_head_height_um = min(
            self._minimum_head_height_um, head_height_um
        )
        self._maximum_head_height_um = max(
            self._maximum_head_height_um, head_height_um
        )

    @staticmethod
    def _body_axis_pitch_deg(body: ScientificBody3D) -> float:
        axis = body.particles[-1].position - body.particles[0].position
        return degrees(atan2(axis.z, hypot(axis.x, axis.y)))

    @staticmethod
    def _center_xyz(body: ScientificBody3D) -> tuple[float, float, float]:
        count = len(body.particles)
        return (
            sum(p.position.x for p in body.particles) / count,
            sum(p.position.y for p in body.particles) / count,
            sum(p.position.z for p in body.particles) / count,
        )

    def run(
        self,
        stimulus: DorsoventralStimulus | None = None,
        *,
        stimulus_protocol: DorsoventralStimulusProtocol | None = None,
        duration_s: float | None = None,
        record_trajectory_interval_s: float | None = None,
    ) -> DorsoventralClosedLoopResult:
        if stimulus is not None and stimulus_protocol is not None:
            raise ValueError("provide either a fixed stimulus or a stimulus protocol")
        initial_center = self._center_xyz(self.body)
        initial_head_z = self.body.particles[0].position.z
        initial_axis_pitch = self._body_axis_pitch_deg(self.body)
        self._initial_head_z_m = initial_head_z
        self._initial_axis_pitch_deg = initial_axis_pitch
        self._minimum_head_pitch_deg = 0.0
        self._maximum_head_pitch_deg = 0.0
        self._minimum_head_height_um = 0.0
        self._maximum_head_height_um = 0.0
        self.body_step_observer = self._observe_body_step

        adapted_protocol = None
        if stimulus_protocol is not None:
            def adapted_protocol(time_s, state):
                value = stimulus_protocol(time_s, state)
                if not isinstance(value, DorsoventralStimulus):
                    raise TypeError(
                        "stimulus protocol must return DorsoventralStimulus"
                    )
                return value.as_opposed_stimulus()

        base_result = super().run(
            None if stimulus is None else stimulus.as_opposed_stimulus(),
            stimulus_protocol=adapted_protocol,
            duration_s=duration_s,
            record_trajectory_interval_s=record_trajectory_interval_s,
        )
        final_center = self._center_xyz(self.body)
        final_axis_pitch = self._body_axis_pitch_deg(self.body)
        frames = tuple(
            {
                "time_s": frame["time_s"],
                "nodes_um": frame["nodes_um"],
                "segment_activation_dorsal": frame["segment_activation_left"],
                "segment_activation_ventral": frame["segment_activation_right"],
            }
            for frame in base_result.trajectory_samples
        )
        return DorsoventralClosedLoopResult(
            model_id=base_result.model_id,
            status=base_result.status,
            neuron_count=base_result.neuron_count,
            duration_s=base_result.duration_s,
            displacement_x_um=(final_center[0] - initial_center[0]) * 1e6,
            displacement_y_um=(final_center[1] - initial_center[1]) * 1e6,
            displacement_z_um=(final_center[2] - initial_center[2]) * 1e6,
            head_pitch_change_deg=-(final_axis_pitch - initial_axis_pitch),
            head_height_change_um=(
                self.body.particles[0].position.z - initial_head_z
            ) * 1e6,
            minimum_head_pitch_deg=self._minimum_head_pitch_deg,
            maximum_head_pitch_deg=self._maximum_head_pitch_deg,
            minimum_head_height_um=self._minimum_head_height_um,
            maximum_head_height_um=self._maximum_head_height_um,
            spike_counts=base_result.spike_counts,
            first_spike_s=base_result.first_spike_s,
            peak_activation=base_result.peak_activation,
            peak_shortening_fraction=base_result.peak_shortening_fraction,
            peak_recruited_fibers=base_result.peak_recruited_fibers,
            trajectory_samples=frames,
            trajectory_sample_interval_s=base_result.trajectory_sample_interval_s,
            premotor_lesion=base_result.premotor_lesion,
            muscle_lesion=base_result.muscle_lesion,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run dorsal/ventral neural head-pitch research model"
    )
    parser.add_argument("--dorsal", type=float, default=1.0)
    parser.add_argument("--ventral", type=float, default=1.0)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--free", action="store_true")
    args = parser.parse_args(argv)
    result = DorsoventralClosedLoopLarva(
        ground_z_m=None if args.free else 0.0
    ).run(
        DorsoventralStimulus(args.dorsal, args.ventral),
        duration_s=args.duration,
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
