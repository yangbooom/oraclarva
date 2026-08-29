"""Bilateral neural-muscle steering research model without behavior commands."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from math import atan2, cos, degrees, exp, isfinite, radians, sin
from pathlib import Path
from typing import Any, Callable

from .body import load_body_spec
from .body3d import ScientificBody3D, Vec3
from .lif import SparseLIFNetwork, Synapse
from .muscles import AggregateMuscleIdentityProjection, load_muscle_atlas
from .neuromuscular import load_neuromuscular_map
from .organism import load_closed_loop_config


SIDES = ("left", "right")


def default_bilateral_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "organism"
        / "l1_bilateral_steering_v0.json"
    )


def load_bilateral_config(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else default_bilateral_path()
    raw = json.loads(source.read_text())
    base = load_closed_loop_config()
    if raw.get("status") != "research_approximation":
        raise ValueError("bilateral steering must remain a research approximation")
    if raw.get("base_model_id") != base["model_id"]:
        raise ValueError("bilateral steering base model is stale")
    if tuple(raw.get("sides", ())) != SIDES:
        raise ValueError("bilateral steering requires left and right channels")
    if tuple(raw.get("causal_contract", ())) != (
        "environment",
        "bilateral_sensory_transduction",
        "bilateral_neural_dynamics",
        "side_resolved_motor_neurons",
        "bilateral_muscle_activation",
        "active_curvature_body_physics",
        "environment",
    ):
        raise ValueError("bilateral steering causal contract is invalid")
    if raw.get("topology", {}).get("provenance") != "ANATOMY_DERIVED":
        raise ValueError("bilateral topology must remain anatomy-derived")
    if raw.get("parameter_provenance", {}).get("provenance") != "MODEL_FITTED":
        raise ValueError("bilateral mechanics must remain model-fitted")
    if raw.get("release_validated") is not False:
        raise ValueError("bilateral research approximation cannot be release-validated")
    parameters = raw.get("parameters", {})
    if float(parameters.get("active_curvature_gain", 0.0)) <= 0:
        raise ValueError("active curvature gain must be positive")
    if float(parameters.get("active_bending_stiffness_ratio", 0.0)) <= 0:
        raise ValueError("active bending stiffness ratio must be positive")
    if float(parameters.get("asymmetric_sensory_current_a", 0.0)) <= 0:
        raise ValueError("asymmetric sensory current must be positive")
    if float(parameters.get("asymmetric_synaptic_current_a", 0.0)) <= 0:
        raise ValueError("asymmetric synaptic current must be positive")
    anterior_segments = tuple(parameters.get("asymmetric_anterior_segments", ()))
    if anterior_segments != ("T3", "A1", "A2"):
        raise ValueError("asymmetric output must remain restricted to T3-A2")
    delays = parameters.get("asymmetric_anterior_delay_s_by_segment", {})
    if set(delays) != set(anterior_segments) or any(
        float(value) < 0.0 for value in delays.values()
    ):
        raise ValueError("asymmetric anterior delays must cover T3-A2")
    if (
        float(parameters.get("stimulus_intensity_min", -1.0)) != 0.0
        or float(parameters.get("stimulus_intensity_max", -1.0)) != 1.0
    ):
        raise ValueError("bilateral stimulus bounds must remain [0, 1]")
    identities = raw.get("motor_identity_projection", {})
    if identities.get("mapping_provenance") != "MEASURED_PUBLISHED":
        raise ValueError("motor identity laterality must remain source-backed")
    if identities.get("gain_provenance") != "MODEL_FITTED":
        raise ValueError("bilateral motor identity gains must remain fitted")
    if identities.get("release_ready") is not False:
        raise ValueError("partial bilateral motor map cannot be release-ready")
    evidence_dois = {item.get("doi") for item in raw.get("evidence", ())}
    if evidence_dois != {
        "10.1016/j.cub.2015.03.023",
        "10.1152/jn.00731.2015",
    }:
        raise ValueError("bilateral topology evidence set is invalid")
    return raw


@dataclass(frozen=True, slots=True)
class BilateralStimulus:
    left_touch_intensity: float = 1.0
    right_touch_intensity: float = 1.0

    def __post_init__(self) -> None:
        if any(
            not 0.0 <= value <= 1.0
            for value in (self.left_touch_intensity, self.right_touch_intensity)
        ):
            raise ValueError("bilateral touch intensity must be in [0, 1]")

    def by_side(self) -> dict[str, float]:
        return {
            "left": self.left_touch_intensity,
            "right": self.right_touch_intensity,
        }


@dataclass(frozen=True, slots=True)
class BilateralSensoryState:
    left_head_position_m: Vec3
    right_head_position_m: Vec3

    @classmethod
    def from_body(cls, body: ScientificBody3D) -> "BilateralSensoryState":
        return cls(
            left_head_position_m=body.bilateral_surface_position_m(0, "left"),
            right_head_position_m=body.bilateral_surface_position_m(0, "right"),
        )


BilateralStimulusProtocol = Callable[
    [float, BilateralSensoryState], BilateralStimulus
]


@dataclass(frozen=True, slots=True)
class BilateralClosedLoopResult:
    model_id: str
    status: str
    neuron_count: int
    duration_s: float
    displacement_x_um: float
    displacement_y_um: float
    heading_change_deg: float
    maximum_abs_lateral_um: float
    spike_counts: dict[str, int]
    first_spike_s: dict[str, float | None]
    peak_activation: dict[str, dict[str, float]]
    peak_shortening_fraction: dict[str, dict[str, float]]
    active_motor_identities: int
    peak_recruited_fibers: int
    trajectory_samples: tuple[dict[str, Any], ...]
    trajectory_sample_interval_s: float | None
    premotor_lesion: tuple[str, str] | None
    muscle_lesion: tuple[str, str] | None
    motor_identity_lesion: tuple[str, str] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "status": self.status,
            "neuron_count": self.neuron_count,
            "duration_s": self.duration_s,
            "displacement_x_um": self.displacement_x_um,
            "displacement_y_um": self.displacement_y_um,
            "heading_change_deg": self.heading_change_deg,
            "maximum_abs_lateral_um": self.maximum_abs_lateral_um,
            "spike_counts": self.spike_counts,
            "first_spike_s": self.first_spike_s,
            "peak_activation": self.peak_activation,
            "peak_shortening_fraction": self.peak_shortening_fraction,
            "active_motor_identities": self.active_motor_identities,
            "peak_recruited_fibers": self.peak_recruited_fibers,
            "trajectory_frames": len(self.trajectory_samples),
            "trajectory_sample_interval_s": self.trajectory_sample_interval_s,
            "release_validated": False,
            "claim_boundary": (
                "mirrored bilateral research approximation; not a complete "
                "steering connectome or measured muscle moment-arm model"
            ),
        }

    def trajectory_artifact(self) -> dict[str, Any]:
        if not self.trajectory_samples or self.trajectory_sample_interval_s is None:
            raise ValueError("run must record trajectory samples first")
        return {
            "schema_version": 1,
            "model_id": self.model_id,
            "status": self.status,
            "neuron_count": self.neuron_count,
            "release_validated": False,
            "units": {"time": "second", "position": "micrometre"},
            "sample_interval_s": self.trajectory_sample_interval_s,
            "body_segment_ids": [
                "PSC", "T1", "T2", "T3", "A1", "A2",
                "A3", "A4", "A5", "A6", "A7", "A8",
            ],
            "sides": list(SIDES),
            "node_count": 13,
            "frames": list(self.trajectory_samples),
            "limitations": [
                "The bilateral topology and curvature mechanics are research approximations.",
                "Individual muscle attachment geometry and force gains are not executed.",
                "No modality-specific approach or avoidance policy is present.",
            ],
        }


class BilateralClosedLoopLarva:
    """Mirrored side-resolved embodied circuit; stimulus is receptor intensity only."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        lesion_premotor_channel: tuple[str, str] | None = None,
        lesion_muscle_channel: tuple[str, str] | None = None,
        lesion_motor_identity_channel: tuple[str, str] | None = None,
        initial_yaw_deg: float = 0.0,
        _opposed_channels: tuple[str, str] = SIDES,
        _actuation_axis: str = "yaw",
        _include_motor_identities: bool = True,
        _sensory_state_factory: Callable[[ScientificBody3D], Any] | None = None,
        _ground_z_m: float | None = 0.0,
        _wave_segments: tuple[str, ...] | None = None,
        _body_step_observer: Callable[[float, ScientificBody3D], None] | None = None,
    ) -> None:
        if len(_opposed_channels) != 2 or len(set(_opposed_channels)) != 2:
            raise ValueError("opposed circuit requires two distinct channels")
        if _actuation_axis not in {"yaw", "pitch"}:
            raise ValueError("actuation axis must be yaw or pitch")
        self.channels = tuple(_opposed_channels)
        self.actuation_axis = _actuation_axis
        self.include_motor_identities = _include_motor_identities
        self.sensory_state_factory = (
            _sensory_state_factory or BilateralSensoryState.from_body
        )
        self.ground_z_m = _ground_z_m
        self.body_step_observer = _body_step_observer
        if not isfinite(initial_yaw_deg):
            raise ValueError("initial yaw must be finite")
        self.initial_yaw_deg = float(initial_yaw_deg)
        self.config = config or load_bilateral_config()
        self.base = load_closed_loop_config()
        self.params = self.base["parameters"]
        self.bilateral_params = self.config["parameters"]
        self.segments = tuple(
            _wave_segments or self.base["wave_segments_posterior_to_anterior"]
        )
        shortening = dict(self.params["maximum_shortening_fraction_by_segment"])
        shortening.update(
            self.bilateral_params.get(
                "maximum_shortening_fraction_by_segment_overrides", {}
            )
        )
        self.activation_rise_tau_by_segment = dict(
            self.params["muscle_activation_rise_tau_s_by_segment"]
        )
        self.activation_rise_tau_by_segment.update(
            self.bilateral_params.get(
                "muscle_activation_rise_tau_s_by_segment_overrides", {}
            )
        )
        self.activation_fall_tau_by_segment = dict(
            self.params["muscle_activation_fall_tau_s_by_segment"]
        )
        self.activation_fall_tau_by_segment.update(
            self.bilateral_params.get(
                "muscle_activation_fall_tau_s_by_segment_overrides", {}
            )
        )
        self.relay_delay_by_segment = dict(
            self.params["intersegmental_relay_delay_s"]
        )
        self.relay_delay_by_segment.update(
            self.bilateral_params.get(
                "intersegmental_relay_delay_s_overrides", {}
            )
        )
        missing_parameters = set(self.segments) - set(
            self.activation_rise_tau_by_segment
        )
        missing_parameters |= set(self.segments) - set(
            self.activation_fall_tau_by_segment
        )
        missing_parameters |= set(self.segments[:-1]) - set(
            self.relay_delay_by_segment
        )
        if missing_parameters:
            raise ValueError(
                f"missing opposed-axis segment parameters: {sorted(missing_parameters)}"
            )
        self.body = ScientificBody3D(
            load_body_spec(),
            maximum_shortening_by_segment=shortening,
            initial_yaw_rad=radians(self.initial_yaw_deg),
        )
        self.body_indices = {
            segment.id: index for index, segment in enumerate(self.body.geometry)
        }
        self.neuromuscular_map = load_neuromuscular_map(self.body.spec)
        self.motor_identities = (
            self.neuromuscular_map.projections
            if self.include_motor_identities
            else ()
        )
        self.motor_identities_by_channel = {
            (segment, side): tuple(
                projection
                for projection in self.motor_identities
                if projection.channel.segment_id == segment
                and projection.channel.side == side
            )
            for segment in ("A1", "A2")
            for side in self.channels
        }
        if self.include_motor_identities and any(
            len(self.motor_identities_by_channel[("A1", side)]) != 28
            or len(self.motor_identities_by_channel[("A2", side)]) != 1
            for side in self.channels
        ):
            raise ValueError("bilateral motor identity coverage must remain 28/1 per side")
        self.muscle_atlas = load_muscle_atlas()
        self.muscle_projection = AggregateMuscleIdentityProjection(self.muscle_atlas)
        self.premotor_lesion = self._validate_channel(
            lesion_premotor_channel, set(self.segments), "premotor"
        )
        self.muscle_lesion = self._validate_channel(
            lesion_muscle_channel,
            set(self.muscle_atlas.supported_segments),
            "muscle",
        )
        if lesion_motor_identity_channel and not self.include_motor_identities:
            raise ValueError("motor identity lesion requires identity neurons")
        self.motor_identity_lesion = self._validate_channel(
            lesion_motor_identity_channel, {"A1"}, "motor identity"
        )

        count = len(self.segments)
        self.touch_offset = 0
        self.asymmetry_offset = 2
        self.proprioceptor_offset = 4
        self.premotor_offset = self.proprioceptor_offset + 2 * count
        self.inhibitory_offset = self.premotor_offset + 2 * count
        self.motor_offset = self.inhibitory_offset + 2 * count
        self.motor_identity_offset = self.motor_offset + 2 * count
        self.motor_identity_indices = {
            projection.neuron_id: self.motor_identity_offset + index
            for index, projection in enumerate(self.motor_identities)
        }
        current = float(self.params["synaptic_current_a"])
        inhibitory_delay_steps = round(
            float(self.params["pmsi_recruitment_delay_s"])
            / float(self.params["dt_s"])
        )
        synapses: list[Synapse] = []
        # Either receptor can initiate the shared bilateral forward-wave circuit.
        # Side differences are encoded separately below; no turn command exists.
        for receptor_side_index in range(2):
            for motor_side_index in range(2):
                synapses.append(Synapse(
                    self.touch_offset + receptor_side_index,
                    self._channel_index(
                        self.premotor_offset, 0, motor_side_index
                    ),
                    current,
                ))
        for side_index, side in enumerate(self.channels):
            for segment in self.bilateral_params["asymmetric_anterior_segments"]:
                delay = round(
                    float(
                        self.bilateral_params[
                            "asymmetric_anterior_delay_s_by_segment"
                        ][segment]
                    )
                    / float(self.params["dt_s"])
                )
                synapses.append(Synapse(
                    self.asymmetry_offset + side_index,
                    self._channel_index(
                        self.premotor_offset,
                        self.segments.index(segment),
                        side_index,
                    ),
                    float(self.bilateral_params["asymmetric_synaptic_current_a"]),
                    delay_steps=delay,
                ))
            for segment_index in range(count):
                premotor = self._channel_index(
                    self.premotor_offset, segment_index, side_index
                )
                inhibitory = self._channel_index(
                    self.inhibitory_offset, segment_index, side_index
                )
                motor = self._channel_index(
                    self.motor_offset, segment_index, side_index
                )
                synapses.extend((
                    Synapse(premotor, motor, current),
                    Synapse(
                        premotor,
                        inhibitory,
                        current,
                        delay_steps=inhibitory_delay_steps,
                    ),
                    Synapse(
                        inhibitory,
                        motor,
                        float(self.params["pmsi_inhibitory_current_a"]),
                        kind="inhibitory",
                    ),
                ))
            for segment_index, segment in enumerate(self.segments[:-1]):
                delay = round(
                    float(self.relay_delay_by_segment[segment])
                    / float(self.params["dt_s"])
                )
                synapses.append(Synapse(
                    self._channel_index(
                        self.proprioceptor_offset, segment_index, side_index
                    ),
                    self._channel_index(
                        self.premotor_offset, segment_index + 1, side_index
                    ),
                    current,
                    delay_steps=delay,
                ))
        identity_current = float(self.params["motor_identity_synaptic_current_a"])
        for projection in self.motor_identities:
            segment = projection.channel.segment_id
            side_index = self.channels.index(projection.channel.side)
            segment_index = self.segments.index(segment)
            synapses.append(Synapse(
                self._channel_index(self.motor_offset, segment_index, side_index),
                self.motor_identity_indices[projection.neuron_id],
                identity_current,
            ))
        self.network = SparseLIFNetwork(
            self.motor_identity_offset + len(self.motor_identities), synapses
        )
        if self.premotor_lesion:
            segment, side = self.premotor_lesion
            self.network.lesion([self._channel_index(
                self.premotor_offset,
                self.segments.index(segment),
                self.channels.index(side),
            )])
        if self.motor_identity_lesion:
            for projection in self.motor_identities_by_channel[
                self.motor_identity_lesion
            ]:
                self.network.lesion([
                    self.motor_identity_indices[projection.neuron_id]
                ])

    def _validate_channel(
        self,
        channel: tuple[str, str] | None,
        valid_segments: set[str],
        name: str,
    ) -> tuple[str, str] | None:
        if channel is None:
            return None
        if len(channel) != 2 or channel[0] not in valid_segments or channel[1] not in self.channels:
            raise ValueError(f"invalid bilateral {name} channel")
        return channel

    @staticmethod
    def _channel_index(offset: int, segment_index: int, side_index: int) -> int:
        return offset + 2 * segment_index + side_index

    def run(
        self,
        stimulus: BilateralStimulus | None = None,
        *,
        stimulus_protocol: BilateralStimulusProtocol | None = None,
        duration_s: float | None = None,
        record_trajectory_interval_s: float | None = None,
    ) -> BilateralClosedLoopResult:
        if stimulus is not None and stimulus_protocol is not None:
            raise ValueError("provide either a fixed stimulus or a stimulus protocol")
        fixed_stimulus = stimulus or BilateralStimulus()
        p = self.params
        dt = float(p["dt_s"])
        actual_duration_s = float(p["duration_s"] if duration_s is None else duration_s)
        if actual_duration_s <= 0:
            raise ValueError("duration must be positive")
        steps = round(actual_duration_s / dt)
        if steps <= 0:
            raise ValueError("duration must span at least one simulation step")
        if record_trajectory_interval_s is not None and record_trajectory_interval_s <= 0:
            raise ValueError("trajectory sample interval must be positive")
        stride = (
            None
            if record_trajectory_interval_s is None
            else max(1, round(record_trajectory_interval_s / dt))
        )
        actual_interval = None if stride is None else stride * dt
        count = len(self.segments)
        excitation = [[0.0, 0.0] for _ in range(count)]
        activation = [[0.0, 0.0] for _ in range(count)]
        adaptation = [[0.0, 0.0] for _ in range(count)]
        rail_length = (
            self.body.bilateral_segment_length_m
            if self.actuation_axis == "yaw"
            else self.body.dorsoventral_segment_length_m
        )
        rail_rest = [
            [
                rail_length(self.body_indices[segment], channel)
                for channel in self.channels
            ]
            for segment in self.segments
        ]
        previous_length = [row[:] for row in rail_rest]
        peak_activation = [[0.0, 0.0] for _ in range(count)]
        peak_shortening = [[0.0, 0.0] for _ in range(count)]
        labels = self._labels()
        spike_counts = {label: 0 for label in labels}
        first_spike = {label: None for label in labels}
        active_identity_ids: set[str] = set()
        peak_recruited_fibers = 0
        initial_center = self._center_xy()
        maximum_abs_lateral = 0.0
        initial_origin = self.body.particles[0].position
        initial_normal = Vec3(
            -sin(radians(self.initial_yaw_deg)),
            cos(radians(self.initial_yaw_deg)),
            0.0,
        )
        samples: list[dict[str, Any]] = []
        if stride is not None:
            samples.append(self._trajectory_sample(0.0, {}))
        for step in range(steps):
            time_s = step * dt
            external: dict[int, float] = {}
            sensory_stimulus = (
                stimulus_protocol(
                    time_s, self.sensory_state_factory(self.body)
                )
                if stimulus_protocol is not None
                else fixed_stimulus
            )
            if not isinstance(sensory_stimulus, BilateralStimulus):
                raise TypeError("stimulus protocol must return BilateralStimulus")
            sensory_active = (
                stimulus_protocol is not None
                or time_s < float(p["posterior_touch_duration_s"])
            )
            if sensory_active:
                stimulus_values = (
                    sensory_stimulus.left_touch_intensity,
                    sensory_stimulus.right_touch_intensity,
                )
                for side_index, side in enumerate(self.channels):
                    intensity = stimulus_values[side_index]
                    if intensity:
                        external[self.touch_offset + side_index] = (
                            intensity * float(p["posterior_touch_current_a"])
                        )
                difference = (
                    sensory_stimulus.left_touch_intensity
                    - sensory_stimulus.right_touch_intensity
                )
                if difference:
                    side_index = 0 if difference > 0 else 1
                    external[self.asymmetry_offset + side_index] = (
                        abs(difference)
                        * float(
                            self.bilateral_params[
                                "asymmetric_sensory_current_a"
                            ]
                        )
                    )
            for segment_index, segment in enumerate(self.segments):
                body_index = self.body_indices[segment]
                for side_index, side in enumerate(self.channels):
                    length = rail_length(body_index, side)
                    rest = rail_rest[segment_index][side_index]
                    strain = max(0.0, 1.0 - length / rest)
                    shortening_rate = max(
                        0.0,
                        (
                            previous_length[segment_index][side_index] - length
                        ) / dt,
                    )
                    previous_length[segment_index][side_index] = length
                    adaptation[segment_index][side_index] *= exp(
                        -dt / float(p["sensory_adaptation_tau_s"])
                    )
                    drive = 0.0
                    if strain >= float(p["proprioceptor_min_strain"]):
                        excess_rate = max(
                            0.0,
                            shortening_rate
                            - float(p["proprioceptor_min_shortening_rate_m_s"]),
                        )
                        drive = min(
                            float(p["proprioceptor_max_current_a"]),
                            excess_rate
                            * float(p["proprioceptor_current_gain_a_s_m"]),
                        )
                    adapted = max(
                        0.0, drive - adaptation[segment_index][side_index]
                    )
                    if adapted:
                        external[self._channel_index(
                            self.proprioceptor_offset,
                            segment_index,
                            side_index,
                        )] = adapted
                        adaptation[segment_index][side_index] += (
                            drive * float(p["sensory_adaptation_fraction"])
                        )
                    peak_shortening[segment_index][side_index] = max(
                        peak_shortening[segment_index][side_index], strain
                    )

            spikes = self.network.step(external)
            spiked = set(spikes)
            for neuron in spikes:
                label = labels[neuron]
                spike_counts[label] += 1
                if first_spike[label] is None:
                    first_spike[label] = time_s
                if neuron >= self.motor_identity_offset:
                    active_identity_ids.add(
                        self.motor_identities[
                            neuron - self.motor_identity_offset
                        ].neuron_id
                    )
            excitation_decay = exp(-dt / float(p["motor_excitation_tau_s"]))
            threshold = float(p["muscle_activation_excitation_threshold"])
            for segment_index, segment in enumerate(self.segments):
                for side_index, side in enumerate(self.channels):
                    excitation[segment_index][side_index] *= excitation_decay
                    if segment == "A1" and self.include_motor_identities:
                        identities = self.motor_identities_by_channel[("A1", side)]
                        fraction = sum(
                            self.motor_identity_indices[projection.neuron_id]
                            in spiked
                            for projection in identities
                        ) / len(identities)
                        excitation[segment_index][side_index] += (
                            float(p["excitation_per_motor_spike"]) * fraction
                        )
                    elif self._channel_index(
                        self.motor_offset, segment_index, side_index
                    ) in spiked:
                        excitation[segment_index][side_index] += float(
                            p["excitation_per_motor_spike"]
                        )
                    target = (
                        1.0
                        if excitation[segment_index][side_index] >= threshold
                        else 0.0
                    )
                    tau_by_segment = (
                        self.activation_rise_tau_by_segment
                        if target > activation[segment_index][side_index]
                        else self.activation_fall_tau_by_segment
                    )
                    coupling = 1.0 - exp(
                        -dt / float(tau_by_segment[segment])
                    )
                    activation[segment_index][side_index] += (
                        target - activation[segment_index][side_index]
                    ) * coupling
                    activation[segment_index][side_index] = min(
                        1.0, max(0.0, activation[segment_index][side_index])
                    )
                    peak_activation[segment_index][side_index] = max(
                        peak_activation[segment_index][side_index],
                        activation[segment_index][side_index],
                    )
            segment_activation = {
                segment: (
                    activation[index][0], activation[index][1]
                )
                for index, segment in enumerate(self.segments)
            }
            lesion_channels = (
                () if self.muscle_lesion is None else (self.muscle_lesion,)
            )
            if self.actuation_axis == "yaw":
                identity_frame = self.muscle_projection.project_bilateral(
                    segment_activation, lesioned_channels=lesion_channels
                )
                applied = self.muscle_projection.bilateral_axial_proxy(
                    identity_frame, segment_activation
                )
                self.body.set_bilateral_activations(applied)
            else:
                identity_frame = self.muscle_projection.project_dorsoventral(
                    segment_activation, lesioned_channels=lesion_channels
                )
                applied = self.muscle_projection.dorsoventral_axial_proxy(
                    identity_frame, segment_activation
                )
                self.body.set_dorsoventral_activations(applied)
            peak_recruited_fibers = max(
                peak_recruited_fibers, identity_frame.active_fiber_count
            )
            self.body.step(
                dt,
                gravity=(
                    Vec3(0.0, 0.0, -9.81)
                    if self.ground_z_m is not None
                    else Vec3(0.0, 0.0, 0.0)
                ),
                ground_z=self.ground_z_m,
                velocity_retention=float(p["body_velocity_retention"]),
                ground_velocity_retention_x=(
                    float(p["ground_negative_x_retention"]),
                    float(p["ground_positive_x_retention"]),
                ),
                active_curvature_gain=(
                    float(self.bilateral_params["active_curvature_gain"])
                    if self.actuation_axis == "yaw"
                    else 0.0
                ),
                active_pitch_curvature_gain=(
                    float(self.bilateral_params["active_pitch_curvature_gain"])
                    if self.actuation_axis == "pitch"
                    else 0.0
                ),
                active_bending_stiffness_ratio=float(
                    self.bilateral_params["active_bending_stiffness_ratio"]
                ),
                use_local_tangent_friction=True,
            )
            if self.body_step_observer is not None:
                self.body_step_observer((step + 1) * dt, self.body)
            maximum_abs_lateral = max(
                maximum_abs_lateral,
                *(
                    abs((particle.position - initial_origin).dot(initial_normal))
                    for particle in self.body.particles
                ),
            )
            if stride is not None and (
                (step + 1) % stride == 0 or step + 1 == steps
            ):
                samples.append(self._trajectory_sample((step + 1) * dt, applied))

        final_center = self._center_xy()
        axis = self.body.particles[-1].position - self.body.particles[0].position
        final_heading = degrees(atan2(axis.y, axis.x))
        heading = (final_heading - self.initial_yaw_deg + 180.0) % 360.0 - 180.0
        return BilateralClosedLoopResult(
            model_id=self.config["model_id"],
            status=self.config["status"],
            neuron_count=self.network.neuron_count,
            duration_s=steps * dt,
            displacement_x_um=(final_center[0] - initial_center[0]) * 1e6,
            displacement_y_um=(final_center[1] - initial_center[1]) * 1e6,
            heading_change_deg=heading,
            maximum_abs_lateral_um=maximum_abs_lateral * 1e6,
            spike_counts=spike_counts,
            first_spike_s=first_spike,
            peak_activation={
                segment: {
                    side: peak_activation[index][side_index]
                    for side_index, side in enumerate(self.channels)
                }
                for index, segment in enumerate(self.segments)
            },
            peak_shortening_fraction={
                segment: {
                    side: peak_shortening[index][side_index]
                    for side_index, side in enumerate(self.channels)
                }
                for index, segment in enumerate(self.segments)
            },
            active_motor_identities=len(active_identity_ids),
            peak_recruited_fibers=peak_recruited_fibers,
            trajectory_samples=tuple(samples),
            trajectory_sample_interval_s=actual_interval,
            premotor_lesion=self.premotor_lesion,
            muscle_lesion=self.muscle_lesion,
            motor_identity_lesion=self.motor_identity_lesion,
        )

    def _labels(self) -> tuple[str, ...]:
        labels = [f"environment_touch:{side}" for side in self.channels]
        labels.extend(f"rectified_sensory_difference:{side}" for side in self.channels)
        for role in ("proprioceptor", "premotor_A27h_like", "inhibitory_PMSI_like", "motor_pool"):
            labels.extend(
                f"{role}:{segment}:{side}"
                for segment in self.segments
                for side in self.channels
            )
        labels.extend(
            f"motor_identity:{projection.neuron_id}:{projection.channel.side}"
            for projection in self.motor_identities
        )
        if len(labels) != self.network.neuron_count:
            raise RuntimeError("bilateral neuron label count mismatch")
        return tuple(labels)

    def _center_xy(self) -> tuple[float, float]:
        count = len(self.body.particles)
        return (
            sum(particle.position.x for particle in self.body.particles) / count,
            sum(particle.position.y for particle in self.body.particles) / count,
        )

    def _trajectory_sample(
        self,
        time_s: float,
        activation: dict[str, tuple[float, float]],
    ) -> dict[str, Any]:
        return {
            "time_s": round(time_s, 9),
            "nodes_um": [
                [
                    round(particle.position.x * 1e6, 9),
                    round(particle.position.y * 1e6, 9),
                    round(particle.position.z * 1e6, 9),
                ]
                for particle in self.body.particles
            ],
            "segment_activation_left": [
                round(float(activation.get(segment.id, (0.0, 0.0))[0]), 9)
                for segment in self.body.geometry
            ],
            "segment_activation_right": [
                round(float(activation.get(segment.id, (0.0, 0.0))[1]), 9)
                for segment in self.body.geometry
            ],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bilateral neural steering v0")
    parser.add_argument("--left", type=float, default=1.0)
    parser.add_argument("--right", type=float, default=1.0)
    parser.add_argument("--trajectory-interval", type=float)
    args = parser.parse_args(argv)
    result = BilateralClosedLoopLarva().run(
        BilateralStimulus(args.left, args.right),
        record_trajectory_interval_s=args.trajectory_interval,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
