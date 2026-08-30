"""Four-receptor neural-muscle spatial steering without behavior commands."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from math import atan2, cos, degrees, exp, hypot, isfinite, radians, sin
from pathlib import Path
from typing import Any, Callable

from .bilateral import SIDES
from .body import load_body_spec
from .body3d import ContactSurface, ScientificBody3D, Vec3
from .dorsoventral import AXES
from .lif import SparseLIFNetwork, Synapse
from .muscles import AggregateMuscleIdentityProjection, load_muscle_atlas
from .organism import load_closed_loop_config


CHANNELS = SIDES + AXES


def default_spatial_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "organism"
        / "l1_spatial_steering_v0.json"
    )


def load_spatial_config(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else default_spatial_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("status") != "research_approximation":
        raise ValueError("spatial steering must remain a research approximation")
    if tuple(raw.get("channels", ())) != CHANNELS:
        raise ValueError("spatial steering requires four opposed channels")
    if tuple(raw.get("causal_contract", ())) != (
        "environment",
        "four_receptor_sensory_transduction",
        "sparse_spatial_neural_dynamics",
        "four_opposed_motor_pools",
        "side_and_spatial_group_muscle_activation",
        "yaw_and_pitch_body_physics",
        "environment",
    ):
        raise ValueError("spatial causal contract is invalid")
    if raw.get("topology", {}).get("provenance") != "ANATOMY_DERIVED":
        raise ValueError("spatial topology must remain anatomy-derived")
    if raw.get("parameter_provenance", {}).get("provenance") != "MODEL_FITTED":
        raise ValueError("spatial parameters must remain model-fitted")
    p = raw.get("parameters", {})
    if float(p.get("active_yaw_curvature_gain", 0.0)) <= 0.0:
        raise ValueError("spatial yaw curvature gain must be positive")
    if float(p.get("active_pitch_curvature_gain", 0.0)) <= 0.0:
        raise ValueError("spatial pitch curvature gain must be positive")
    if tuple(p.get("yaw_asymmetric_segments", ())) != ("T3", "A1", "A2"):
        raise ValueError("spatial yaw projection must remain T3-A2")
    if tuple(p.get("pitch_asymmetric_segments", ())) != (
        "T1", "T2", "T3", "A1", "A2"
    ):
        raise ValueError("spatial pitch projection must remain T1-A2")
    if raw.get("release_validated") is not False:
        raise ValueError("spatial research approximation cannot be release-validated")
    expected_dois = {
        "10.1016/j.cub.2015.03.023",
        "10.1152/jn.00731.2015",
        "10.7554/eLife.51781",
        "10.7554/eLife.38740",
        "10.1371/journal.pone.0135011",
    }
    if {item.get("doi") for item in raw.get("evidence", ())} != expected_dois:
        raise ValueError("spatial evidence set is invalid")
    return raw


@dataclass(frozen=True, slots=True)
class SpatialStimulus:
    left_intensity: float = 1.0
    right_intensity: float = 1.0
    dorsal_intensity: float = 1.0
    ventral_intensity: float = 1.0

    def __post_init__(self) -> None:
        if any(not 0.0 <= value <= 1.0 for value in self.values()):
            raise ValueError("spatial receptor intensity must be in [0, 1]")

    def values(self) -> tuple[float, float, float, float]:
        return (
            self.left_intensity,
            self.right_intensity,
            self.dorsal_intensity,
            self.ventral_intensity,
        )


@dataclass(frozen=True, slots=True)
class SpatialSensoryState:
    left_head_position_m: Vec3
    right_head_position_m: Vec3
    dorsal_head_position_m: Vec3
    ventral_head_position_m: Vec3

    @classmethod
    def from_body(cls, body: ScientificBody3D) -> "SpatialSensoryState":
        return cls(
            left_head_position_m=body.bilateral_surface_position_m(0, "left"),
            right_head_position_m=body.bilateral_surface_position_m(0, "right"),
            dorsal_head_position_m=body.dorsoventral_surface_position_m(
                0, "dorsal"
            ),
            ventral_head_position_m=body.dorsoventral_surface_position_m(
                0, "ventral"
            ),
        )


SpatialStimulusProtocol = Callable[[float, SpatialSensoryState], SpatialStimulus]


@dataclass(frozen=True, slots=True)
class SpatialClosedLoopResult:
    model_id: str
    status: str
    neuron_count: int
    synapse_count: int
    duration_s: float
    displacement_x_um: float
    displacement_y_um: float
    displacement_z_um: float
    yaw_change_deg: float
    head_pitch_change_deg: float
    minimum_head_pitch_deg: float
    maximum_head_pitch_deg: float
    minimum_head_height_um: float
    maximum_head_height_um: float
    spike_counts: dict[str, int]
    first_spike_s: dict[str, float | None]
    peak_activation: dict[str, dict[str, float]]
    peak_yaw_recruited_fibers: int
    peak_pitch_recruited_fibers: int
    trajectory_samples: tuple[dict[str, Any], ...]
    trajectory_sample_interval_s: float | None
    premotor_lesion: tuple[str, str] | None
    muscle_lesion: tuple[str, str] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "status": self.status,
            "neuron_count": self.neuron_count,
            "synapse_count": self.synapse_count,
            "duration_s": self.duration_s,
            "displacement_x_um": self.displacement_x_um,
            "displacement_y_um": self.displacement_y_um,
            "displacement_z_um": self.displacement_z_um,
            "yaw_change_deg": self.yaw_change_deg,
            "head_pitch_change_deg": self.head_pitch_change_deg,
            "minimum_head_pitch_deg": self.minimum_head_pitch_deg,
            "maximum_head_pitch_deg": self.maximum_head_pitch_deg,
            "minimum_head_height_um": self.minimum_head_height_um,
            "maximum_head_height_um": self.maximum_head_height_um,
            "peak_yaw_recruited_fibers": self.peak_yaw_recruited_fibers,
            "peak_pitch_recruited_fibers": self.peak_pitch_recruited_fibers,
            "release_validated": False,
            "claim_boundary": (
                "four-channel research approximation; not a complete spatial "
                "L1 connectome or measured 3D muscle attachment model"
            ),
        }


class SpatialClosedLoopLarva:
    """Four sensory-neural-muscle channels driving one 3D physical body."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        lesion_premotor_channel: tuple[str, str] | None = None,
        lesion_muscle_channel: tuple[str, str] | None = None,
        initial_yaw_deg: float = 0.0,
        initial_pitch_deg: float = 0.0,
        ground_z_m: float | None = 0.0,
        contact_surface: ContactSurface | None = None,
        input_labels: tuple[str, str, str, str] | None = None,
        asymmetry_labels: tuple[str, str, str, str] | None = None,
    ) -> None:
        if ground_z_m is not None and contact_surface is not None:
            raise ValueError("provide either ground_z_m or a contact surface")
        if not isfinite(initial_yaw_deg):
            raise ValueError("initial yaw must be finite")
        if not isfinite(initial_pitch_deg):
            raise ValueError("initial pitch must be finite")
        self.config = config or load_spatial_config()
        self.base = load_closed_loop_config()
        self.params = self.base["parameters"]
        self.spatial_params = self.config["parameters"]
        self.segments = tuple(
            self.config["wave_segments_posterior_to_anterior"]
        )
        self.initial_yaw_deg = float(initial_yaw_deg)
        self.initial_pitch_deg = float(initial_pitch_deg)
        self.ground_z_m = ground_z_m
        self.contact_surface = contact_surface
        self.input_labels = self._validate_labels(
            input_labels,
            tuple(f"environment_receptor:{channel}" for channel in CHANNELS),
            "input",
        )
        self.asymmetry_labels = self._validate_labels(
            asymmetry_labels,
            tuple(
                f"rectified_sensory_difference:{channel}"
                for channel in CHANNELS
            ),
            "asymmetry",
        )

        shortening = dict(
            self.params["maximum_shortening_fraction_by_segment"]
        )
        shortening.update(
            self.spatial_params[
                "maximum_shortening_fraction_by_segment_overrides"
            ]
        )
        self.rise_tau = dict(
            self.params["muscle_activation_rise_tau_s_by_segment"]
        )
        self.rise_tau.update(
            self.spatial_params[
                "muscle_activation_rise_tau_s_by_segment_overrides"
            ]
        )
        self.fall_tau = dict(
            self.params["muscle_activation_fall_tau_s_by_segment"]
        )
        self.fall_tau.update(
            self.spatial_params[
                "muscle_activation_fall_tau_s_by_segment_overrides"
            ]
        )
        self.relay_delay = dict(self.params["intersegmental_relay_delay_s"])
        self.relay_delay.update(
            self.spatial_params["intersegmental_relay_delay_s_overrides"]
        )
        self.body = ScientificBody3D(
            load_body_spec(),
            maximum_shortening_by_segment=shortening,
            initial_yaw_rad=radians(self.initial_yaw_deg),
            initial_pitch_rad=radians(self.initial_pitch_deg),
        )
        self.body_indices = {
            segment.id: index for index, segment in enumerate(self.body.geometry)
        }
        self.muscle_projection = AggregateMuscleIdentityProjection(
            load_muscle_atlas()
        )
        self.premotor_lesion = self._validate_channel(
            lesion_premotor_channel, set(self.segments), "premotor"
        )
        self.muscle_lesion = self._validate_channel(
            lesion_muscle_channel,
            set(self.muscle_projection.atlas.supported_segments),
            "muscle",
        )

        count = len(self.segments)
        width = len(CHANNELS)
        self.touch_offset = 0
        self.asymmetry_offset = width
        self.proprioceptor_offset = 2 * width
        self.premotor_offset = self.proprioceptor_offset + width * count
        self.inhibitory_offset = self.premotor_offset + width * count
        self.motor_offset = self.inhibitory_offset + width * count
        neuron_count = self.motor_offset + width * count

        current = float(self.params["synaptic_current_a"])
        inhibitory_delay_steps = round(
            float(self.params["pmsi_recruitment_delay_s"])
            / float(self.params["dt_s"])
        )
        synapses: list[Synapse] = []
        for receptor_index in range(width):
            for channel_index in range(width):
                synapses.append(Synapse(
                    self.touch_offset + receptor_index,
                    self._channel_index(
                        self.premotor_offset, 0, channel_index
                    ),
                    current,
                ))
        for channel_index, channel in enumerate(CHANNELS):
            if channel in SIDES:
                segments = self.spatial_params["yaw_asymmetric_segments"]
                delays = self.spatial_params[
                    "yaw_asymmetric_delay_s_by_segment"
                ]
            else:
                segments = self.spatial_params["pitch_asymmetric_segments"]
                delays = self.spatial_params[
                    "pitch_asymmetric_delay_s_by_segment"
                ]
            for segment in segments:
                synapses.append(Synapse(
                    self.asymmetry_offset + channel_index,
                    self._channel_index(
                        self.premotor_offset,
                        self.segments.index(segment),
                        channel_index,
                    ),
                    float(
                        self.spatial_params[
                            "asymmetric_synaptic_current_a"
                        ]
                    ),
                    delay_steps=round(
                        float(delays[segment])
                        / float(self.params["dt_s"])
                    ),
                ))
            for segment_index in range(count):
                premotor = self._channel_index(
                    self.premotor_offset, segment_index, channel_index
                )
                inhibitory = self._channel_index(
                    self.inhibitory_offset, segment_index, channel_index
                )
                motor = self._channel_index(
                    self.motor_offset, segment_index, channel_index
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
                synapses.append(Synapse(
                    self._channel_index(
                        self.proprioceptor_offset,
                        segment_index,
                        channel_index,
                    ),
                    self._channel_index(
                        self.premotor_offset,
                        segment_index + 1,
                        channel_index,
                    ),
                    current,
                    delay_steps=round(
                        float(self.relay_delay[segment])
                        / float(self.params["dt_s"])
                    ),
                ))
        self.network = SparseLIFNetwork(neuron_count, synapses)
        self.synapse_count = len(synapses)
        if self.premotor_lesion:
            segment, channel = self.premotor_lesion
            self.network.lesion([
                self._channel_index(
                    self.premotor_offset,
                    self.segments.index(segment),
                    CHANNELS.index(channel),
                )
            ])
        self._equilibrate_initial_body()

    @staticmethod
    def _channel_index(offset: int, segment_index: int, channel_index: int) -> int:
        return offset + len(CHANNELS) * segment_index + channel_index

    @staticmethod
    def _center_xyz(body: ScientificBody3D) -> tuple[float, float, float]:
        count = len(body.particles)
        return (
            sum(p.position.x for p in body.particles) / count,
            sum(p.position.y for p in body.particles) / count,
            sum(p.position.z for p in body.particles) / count,
        )

    @staticmethod
    def _body_axis_pitch_deg(body: ScientificBody3D) -> float:
        axis = body.particles[-1].position - body.particles[0].position
        return degrees(atan2(axis.z, hypot(axis.x, axis.y)))

    @staticmethod
    def _validate_channel(
        channel: tuple[str, str] | None,
        valid_segments: set[str],
        name: str,
    ) -> tuple[str, str] | None:
        if channel is None:
            return None
        if (
            len(channel) != 2
            or channel[0] not in valid_segments
            or channel[1] not in CHANNELS
        ):
            raise ValueError(f"invalid spatial {name} channel")
        return channel

    @staticmethod
    def _validate_labels(
        labels: tuple[str, str, str, str] | None,
        default: tuple[str, str, str, str],
        name: str,
    ) -> tuple[str, str, str, str]:
        result = default if labels is None else tuple(labels)
        if (
            len(result) != len(CHANNELS)
            or len(set(result)) != len(result)
            or any(not isinstance(label, str) or not label for label in result)
        ):
            raise ValueError(f"spatial {name} labels must be four unique strings")
        return result  # type: ignore[return-value]

    def _equilibrate_initial_body(self) -> None:
        dt = float(self.params["dt_s"])
        gravity = (
            Vec3(0.0, 0.0, -9.81)
            if self.ground_z_m is not None or self.contact_surface is not None
            else Vec3(0.0, 0.0, 0.0)
        )
        for _ in range(50):
            self.body.step(
                dt,
                gravity=gravity,
                ground_z=self.ground_z_m,
                velocity_retention=float(
                    self.params["body_velocity_retention"]
                ),
                ground_velocity_retention_x=(
                    float(self.params["ground_negative_x_retention"]),
                    float(self.params["ground_positive_x_retention"]),
                ),
                use_local_tangent_friction=True,
                contact_surface=self.contact_surface,
                contact_friction_coefficient=(
                    float(
                        self.spatial_params["contact_friction_coefficient"]
                    )
                    if self.contact_surface is not None
                    else 0.0
                ),
            )
        for particle in self.body.particles:
            particle.previous_position = particle.position

    def _rail_length(
        self, segment_index: int, channel_index: int
    ) -> float:
        channel = CHANNELS[channel_index]
        if channel in SIDES:
            return self.body.bilateral_segment_length_m(
                segment_index, channel
            )
        return self.body.dorsoventral_segment_length_m(
            segment_index, channel
        )

    def _labels(self) -> tuple[str, ...]:
        labels = list(self.input_labels)
        labels.extend(self.asymmetry_labels)
        for role in (
            "proprioceptor",
            "premotor_A27h_like",
            "inhibitory_PMSI_like",
            "motor_pool",
        ):
            labels.extend(
                f"{role}:{segment}:{channel}"
                for segment in self.segments
                for channel in CHANNELS
            )
        if len(labels) != self.network.neuron_count:
            raise RuntimeError("spatial neuron label count mismatch")
        return tuple(labels)

    def _trajectory_sample(
        self,
        time_s: float,
        yaw_activation: dict[str, tuple[float, float]],
        pitch_activation: dict[str, tuple[float, float]],
    ) -> dict[str, Any]:
        return {
            "time_s": round(time_s, 9),
            "nodes_um": [
                [
                    round(p.position.x * 1e6, 9),
                    round(p.position.y * 1e6, 9),
                    round(p.position.z * 1e6, 9),
                ]
                for p in self.body.particles
            ],
            "segment_activation_left": [
                round(yaw_activation.get(g.id, (0.0, 0.0))[0], 9)
                for g in self.body.geometry
            ],
            "segment_activation_right": [
                round(yaw_activation.get(g.id, (0.0, 0.0))[1], 9)
                for g in self.body.geometry
            ],
            "segment_activation_dorsal": [
                round(pitch_activation.get(g.id, (0.0, 0.0))[0], 9)
                for g in self.body.geometry
            ],
            "segment_activation_ventral": [
                round(pitch_activation.get(g.id, (0.0, 0.0))[1], 9)
                for g in self.body.geometry
            ],
        }

    def run(
        self,
        stimulus: SpatialStimulus | None = None,
        *,
        stimulus_protocol: SpatialStimulusProtocol | None = None,
        duration_s: float | None = None,
        record_trajectory_interval_s: float | None = None,
    ) -> SpatialClosedLoopResult:
        if stimulus is not None and stimulus_protocol is not None:
            raise ValueError("provide either a fixed stimulus or a stimulus protocol")
        fixed_stimulus = stimulus or SpatialStimulus()
        dt = float(self.params["dt_s"])
        actual_duration = float(
            self.params["duration_s"] if duration_s is None else duration_s
        )
        if actual_duration <= 0.0:
            raise ValueError("duration must be positive")
        steps = round(actual_duration / dt)
        if steps <= 0:
            raise ValueError("duration must span at least one simulation step")
        if (
            record_trajectory_interval_s is not None
            and record_trajectory_interval_s <= 0.0
        ):
            raise ValueError("trajectory sample interval must be positive")
        stride = (
            None
            if record_trajectory_interval_s is None
            else max(1, round(record_trajectory_interval_s / dt))
        )
        actual_interval = None if stride is None else stride * dt

        count = len(self.segments)
        width = len(CHANNELS)
        excitation = [[0.0] * width for _ in range(count)]
        activation = [[0.0] * width for _ in range(count)]
        adaptation = [[0.0] * width for _ in range(count)]
        rail_rest = [
            [
                self._rail_length(self.body_indices[segment], channel_index)
                for channel_index in range(width)
            ]
            for segment in self.segments
        ]
        previous_length = [row[:] for row in rail_rest]
        peak_activation = [[0.0] * width for _ in range(count)]
        labels = self._labels()
        spike_counts = {label: 0 for label in labels}
        first_spike = {label: None for label in labels}
        initial_center = self._center_xyz(self.body)
        initial_axis = self.body.particles[-1].position - self.body.particles[0].position
        initial_yaw = degrees(atan2(initial_axis.y, initial_axis.x))
        initial_pitch = self._body_axis_pitch_deg(self.body)
        initial_head_z = self.body.particles[0].position.z
        minimum_pitch = maximum_pitch = 0.0
        minimum_height = maximum_height = 0.0
        peak_yaw_fibers = 0
        peak_pitch_fibers = 0
        samples: list[dict[str, Any]] = []
        if stride is not None:
            samples.append(self._trajectory_sample(0.0, {}, {}))

        for step in range(steps):
            time_s = step * dt
            value = (
                stimulus_protocol(
                    time_s, SpatialSensoryState.from_body(self.body)
                )
                if stimulus_protocol is not None
                else fixed_stimulus
            )
            if not isinstance(value, SpatialStimulus):
                raise TypeError("stimulus protocol must return SpatialStimulus")
            external: dict[int, float] = {}
            sensory_active = (
                stimulus_protocol is not None
                or time_s < float(
                    self.params["posterior_touch_duration_s"]
                )
            )
            values = value.values()
            if sensory_active:
                for channel_index, intensity in enumerate(values):
                    if intensity:
                        external[self.touch_offset + channel_index] = (
                            intensity
                            * float(self.params["posterior_touch_current_a"])
                        )
                for first, second in ((0, 1), (2, 3)):
                    difference = values[first] - values[second]
                    if difference:
                        channel_index = first if difference > 0.0 else second
                        external[
                            self.asymmetry_offset + channel_index
                        ] = abs(difference) * float(
                            self.spatial_params[
                                "asymmetric_sensory_current_a"
                            ]
                        )

            for segment_index, segment in enumerate(self.segments):
                body_index = self.body_indices[segment]
                for channel_index in range(width):
                    length = self._rail_length(body_index, channel_index)
                    rest = rail_rest[segment_index][channel_index]
                    strain = max(0.0, 1.0 - length / rest)
                    shortening_rate = max(
                        0.0,
                        (
                            previous_length[segment_index][channel_index]
                            - length
                        )
                        / dt,
                    )
                    previous_length[segment_index][channel_index] = length
                    adaptation[segment_index][channel_index] *= exp(
                        -dt
                        / float(self.params["sensory_adaptation_tau_s"])
                    )
                    drive = 0.0
                    if strain >= float(
                        self.params["proprioceptor_min_strain"]
                    ):
                        excess_rate = max(
                            0.0,
                            shortening_rate
                            - float(
                                self.params[
                                    "proprioceptor_min_shortening_rate_m_s"
                                ]
                            ),
                        )
                        drive = min(
                            float(
                                self.params[
                                    "proprioceptor_max_current_a"
                                ]
                            ),
                            excess_rate
                            * float(
                                self.params[
                                    "proprioceptor_current_gain_a_s_m"
                                ]
                            ),
                        )
                    adapted = max(
                        0.0,
                        drive
                        - adaptation[segment_index][channel_index],
                    )
                    if adapted:
                        external[self._channel_index(
                            self.proprioceptor_offset,
                            segment_index,
                            channel_index,
                        )] = adapted
                        adaptation[segment_index][channel_index] += (
                            drive
                            * float(
                                self.params[
                                    "sensory_adaptation_fraction"
                                ]
                            )
                        )

            spikes = self.network.step(external)
            spiked = set(spikes)
            for neuron in spikes:
                label = labels[neuron]
                spike_counts[label] += 1
                if first_spike[label] is None:
                    first_spike[label] = time_s

            excitation_decay = exp(
                -dt / float(self.params["motor_excitation_tau_s"])
            )
            threshold = float(
                self.params["muscle_activation_excitation_threshold"]
            )
            for segment_index, segment in enumerate(self.segments):
                for channel_index in range(width):
                    excitation[segment_index][channel_index] *= (
                        excitation_decay
                    )
                    motor = self._channel_index(
                        self.motor_offset,
                        segment_index,
                        channel_index,
                    )
                    if motor in spiked:
                        excitation[segment_index][channel_index] += float(
                            self.params["excitation_per_motor_spike"]
                        )
                    target = (
                        1.0
                        if excitation[segment_index][channel_index]
                        >= threshold
                        else 0.0
                    )
                    tau = (
                        self.rise_tau[segment]
                        if target > activation[segment_index][channel_index]
                        else self.fall_tau[segment]
                    )
                    coupling = 1.0 - exp(-dt / float(tau))
                    activation[segment_index][channel_index] += (
                        target - activation[segment_index][channel_index]
                    ) * coupling
                    activation[segment_index][channel_index] = min(
                        1.0,
                        max(
                            0.0,
                            activation[segment_index][channel_index],
                        ),
                    )
                    peak_activation[segment_index][channel_index] = max(
                        peak_activation[segment_index][channel_index],
                        activation[segment_index][channel_index],
                    )

            yaw_activation = {
                segment: (
                    activation[index][0],
                    activation[index][1],
                )
                for index, segment in enumerate(self.segments)
            }
            pitch_activation = {
                segment: (
                    activation[index][2],
                    activation[index][3],
                )
                for index, segment in enumerate(self.segments)
            }
            yaw_lesions = (
                ()
                if self.muscle_lesion is None
                or self.muscle_lesion[1] not in SIDES
                else (self.muscle_lesion,)
            )
            pitch_lesions = (
                ()
                if self.muscle_lesion is None
                or self.muscle_lesion[1] not in AXES
                else (self.muscle_lesion,)
            )
            yaw_frame = self.muscle_projection.project_bilateral(
                yaw_activation,
                lesioned_channels=yaw_lesions,
            )
            pitch_frame = self.muscle_projection.project_dorsoventral(
                pitch_activation,
                lesioned_channels=pitch_lesions,
            )
            applied_yaw = self.muscle_projection.bilateral_axial_proxy(
                yaw_frame, yaw_activation
            )
            applied_pitch = (
                self.muscle_projection.dorsoventral_axial_proxy(
                    pitch_frame, pitch_activation
                )
            )
            peak_yaw_fibers = max(
                peak_yaw_fibers, yaw_frame.active_fiber_count
            )
            peak_pitch_fibers = max(
                peak_pitch_fibers, pitch_frame.active_fiber_count
            )
            self.body.set_spatial_activations(
                applied_yaw, applied_pitch
            )
            self.body.step(
                dt,
                gravity=(
                    Vec3(0.0, 0.0, -9.81)
                    if self.ground_z_m is not None or self.contact_surface is not None
                    else Vec3(0.0, 0.0, 0.0)
                ),
                ground_z=self.ground_z_m,
                velocity_retention=float(
                    self.params["body_velocity_retention"]
                ),
                ground_velocity_retention_x=(
                    float(self.params["ground_negative_x_retention"]),
                    float(self.params["ground_positive_x_retention"]),
                ),
                active_curvature_gain=float(
                    self.spatial_params[
                        "active_yaw_curvature_gain"
                    ]
                ),
                active_pitch_curvature_gain=float(
                    self.spatial_params[
                        "active_pitch_curvature_gain"
                    ]
                ),
                active_bending_stiffness_ratio=float(
                    self.spatial_params[
                        "active_bending_stiffness_ratio"
                    ]
                ),
                use_local_tangent_friction=True,
                contact_surface=self.contact_surface,
                contact_friction_coefficient=(
                    float(
                        self.spatial_params["contact_friction_coefficient"]
                    )
                    if self.contact_surface is not None
                    else 0.0
                ),
            )
            pitch = -(
                self._body_axis_pitch_deg(self.body) - initial_pitch
            )
            height = (
                self.body.particles[0].position.z - initial_head_z
            ) * 1e6
            minimum_pitch = min(minimum_pitch, pitch)
            maximum_pitch = max(maximum_pitch, pitch)
            minimum_height = min(minimum_height, height)
            maximum_height = max(maximum_height, height)
            if stride is not None and (
                (step + 1) % stride == 0 or step + 1 == steps
            ):
                samples.append(self._trajectory_sample(
                    (step + 1) * dt,
                    applied_yaw,
                    applied_pitch,
                ))

        final_center = self._center_xyz(self.body)
        final_axis = self.body.particles[-1].position - self.body.particles[0].position
        final_yaw = degrees(atan2(final_axis.y, final_axis.x))
        yaw_change = (final_yaw - initial_yaw + 180.0) % 360.0 - 180.0
        final_pitch = -(
            self._body_axis_pitch_deg(self.body) - initial_pitch
        )
        return SpatialClosedLoopResult(
            model_id=self.config["model_id"],
            status=self.config["status"],
            neuron_count=self.network.neuron_count,
            synapse_count=self.synapse_count,
            duration_s=steps * dt,
            displacement_x_um=(final_center[0] - initial_center[0]) * 1e6,
            displacement_y_um=(final_center[1] - initial_center[1]) * 1e6,
            displacement_z_um=(final_center[2] - initial_center[2]) * 1e6,
            yaw_change_deg=yaw_change,
            head_pitch_change_deg=final_pitch,
            minimum_head_pitch_deg=minimum_pitch,
            maximum_head_pitch_deg=maximum_pitch,
            minimum_head_height_um=minimum_height,
            maximum_head_height_um=maximum_height,
            spike_counts=spike_counts,
            first_spike_s=first_spike,
            peak_activation={
                segment: {
                    channel: peak_activation[index][channel_index]
                    for channel_index, channel in enumerate(CHANNELS)
                }
                for index, segment in enumerate(self.segments)
            },
            peak_yaw_recruited_fibers=peak_yaw_fibers,
            peak_pitch_recruited_fibers=peak_pitch_fibers,
            trajectory_samples=tuple(samples),
            trajectory_sample_interval_s=actual_interval,
            premotor_lesion=self.premotor_lesion,
            muscle_lesion=self.muscle_lesion,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run four-receptor neural spatial steering research model"
    )
    parser.add_argument("--left", type=float, default=1.0)
    parser.add_argument("--right", type=float, default=1.0)
    parser.add_argument("--dorsal", type=float, default=1.0)
    parser.add_argument("--ventral", type=float, default=1.0)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--free", action="store_true")
    args = parser.parse_args(argv)
    result = SpatialClosedLoopLarva(
        ground_z_m=None if args.free else 0.0
    ).run(
        SpatialStimulus(
            args.left, args.right, args.dorsal, args.ventral
        ),
        duration_s=args.duration,
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
