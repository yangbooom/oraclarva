"""Evidence-bounded bidirectional axial locomotion reference.

Environmental touch is transformed into sparse neural dynamics before shared
motor identities, muscle activation, body mechanics, and continuous substrate
contact are evaluated.  No direction flag reaches the body and no behavior
command, FSM, or external policy selects displacement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import exp, isfinite
from pathlib import Path
from typing import Any, Iterable, Mapping

from .body import load_body_spec
from .body3d import ScientificBody3D, Vec3
from .body_sensing import BodyStateSensoryFrame, BodyStateSensoryTransducer
from .fiber_body import NamedFiberBodyCoupling
from .lif import SparseLIFNetwork, Synapse
from .muscles import (
    NeuralMuscleActivationFrame,
    NeuralMuscleActivationModel,
    NeuralMuscleIdentityProjection,
    load_muscle_atlas,
    load_neural_muscle_identity_projection,
)
from .repeat_crawl import WAVE_SEGMENTS


FORWARD_WAVE = WAVE_SEGMENTS
BACKWARD_WAVE = tuple(reversed(WAVE_SEGMENTS))
AXIAL_SEGMENTS = BACKWARD_WAVE
T3_CONTACT_PROXY_NODE = "motor_proxy:T3_transverse_backward"


def default_axial_locomotion_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "organism"
        / "l1_axial_locomotion_v1.json"
    )


def load_axial_locomotion_config(
    path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(path) if path else default_axial_locomotion_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if (
        raw.get("model_id") != "dmel_l1_axial_locomotion_v1"
        or raw.get("status") != "research_approximation"
        or raw.get("stage") != "L1"
        or tuple(raw.get("forward_wave_posterior_to_anterior", ()))
        != FORWARD_WAVE
        or tuple(raw.get("backward_wave_anterior_to_posterior", ()))
        != BACKWARD_WAVE
        or raw.get("release_validated") is not False
    ):
        raise ValueError("axial-locomotion model boundary is invalid")
    expected_contract = [
        "environment",
        "sensory_transduction",
        "neural_dynamics",
        "motor_neurons",
        "muscle_activation",
        "body_physics",
        "environment",
    ]
    topology = raw.get("topology", {})
    if (
        raw.get("causal_contract") != expected_contract
        or topology.get("action_command") is not False
        or topology.get("behavior_fsm") is not False
        or topology.get("external_policy") is not False
        or topology.get("shared_motor_and_muscle_atlas") is not True
    ):
        raise ValueError("axial-locomotion causal topology is invalid")
    parameters = raw.get("parameters", {})
    required_positive = (
        "dt_s",
        "duration_s",
        "touch_current_a",
        "touch_duration_s",
        "premotor_current_a",
        "motor_current_a",
        "inhibitory_current_a",
        "intersegmental_delay_s",
        "forward_recovery_delay_s",
        "backward_recovery_delay_s",
        "gdl_delay_s",
        "ifb_backward_delay_s",
        "canon_delay_s",
        "forward_transverse_motor_delay_s",
        "backward_transverse_motor_delay_s",
        "backward_longitudinal_motor_delay_s",
        "sensory_maximum_current_a",
        "sensory_adaptation_tau_s",
        "sensory_adaptation_fraction",
        "recovery_adaptation_fraction",
        "recovery_rate_threshold_s_1",
        "recovery_rate_gain_s",
        "local_tension_gate_gain",
        "trace_arrival_window_s",
        "pair1_gate_tau_s",
        "relaxation_decay_tau_s",
        "gdl_relaxation_impulse",
        "ifb_relaxation_impulse",
        "canon_relaxation_impulse",
        "relaxation_gain_s_1",
        "muscle_activation_rise_tau_s",
        "muscle_activation_decay_tau_s",
        "muscle_event_target",
        "muscle_excitation_decay_tau_s",
        "muscle_event_excitation",
    )
    if any(
        not isfinite(float(parameters.get(name, 0.0)))
        or float(parameters.get(name, 0.0)) <= 0.0
        for name in required_positive
    ):
        raise ValueError("axial-locomotion parameters must be finite and positive")
    required_segment_maps = {
        "muscle_activation_rise_tau_s_by_segment": set(AXIAL_SEGMENTS),
        "muscle_activation_decay_tau_s_by_segment": set(AXIAL_SEGMENTS),
        "muscle_excitation_decay_tau_s_by_segment": set(AXIAL_SEGMENTS),
    }
    for name, expected_segments in required_segment_maps.items():
        values = parameters.get(name, {})
        if set(values) != expected_segments or any(
            not isfinite(float(value)) or float(value) <= 0.0
            for value in values.values()
        ):
            raise ValueError(f"axial-locomotion {name} is incomplete or invalid")
    if not (
        0.0 < float(parameters["gdl_relaxation_impulse"]) <= 1.0
        and 0.0 < float(parameters["ifb_relaxation_impulse"]) <= 1.0
        and 0.0 < float(parameters["canon_relaxation_impulse"]) <= 1.0
    ):
        raise ValueError("axial relaxation impulses must be in (0, 1]")
    contact = raw.get("continuous_ground_contact", {})
    if (
        contact.get("provenance") != "MODEL_FITTED"
        or contact.get("movement_direction_input") is not False
        or contact.get("phase_labels_diagnostic_only") is not True
        or contact.get("finite_state_machine") is not False
        or contact.get("t3_backward_contact_proxy", {}).get("node_id")
        != T3_CONTACT_PROXY_NODE
        or contact.get("t3_backward_contact_proxy", {}).get("axial_force")
        is not False
    ):
        raise ValueError("continuous contact claim boundary is invalid")
    for name in ("planted_velocity_retention", "released_velocity_retention"):
        value = float(contact.get(name, -1.0))
        if not isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("contact retention must be finite in [0, 1]")
    if (
        float(contact["planted_velocity_retention"])
        >= float(contact["released_velocity_retention"])
        or not isfinite(float(contact.get("contact_activation_gain", 0.0)))
        or float(contact.get("contact_activation_gain", 0.0)) <= 0.0
        or int(contact.get("body_iterations", 0)) <= 0
    ):
        raise ValueError("continuous contact fitted values are invalid")
    coupling = raw.get("named_fiber_body_coupling", {})
    if (
        coupling.get("parameter_provenance") != "MODEL_FITTED"
        or coupling.get("force_unit") != "model_unit_not_newton"
        or coupling.get("force_projection_mode") != "local_tangent_axial"
        or float(coupling.get("transverse_axial_force_projection_scale", -1.0))
        != 0.0
        or "ground_negative_x_retention" in coupling
        or "ground_positive_x_retention" in coupling
    ):
        raise ValueError("axial mechanics must not contain directional retention")
    return raw


@dataclass(frozen=True, slots=True)
class AxialCausalTrace:
    direction: str
    body_state_time_s: float
    sensor_node_id: str
    sensor_spike_time_s: float
    premotor_node_id: str
    premotor_spike_time_s: float
    motor_node_id: str
    motor_spike_time_s: float
    segment_id: str
    path_provenance: str

    def as_mapping(self) -> dict[str, object]:
        return {
            "direction": self.direction,
            "body_state_time_s": self.body_state_time_s,
            "sensor_node_id": self.sensor_node_id,
            "sensor_spike_time_s": self.sensor_spike_time_s,
            "premotor_node_id": self.premotor_node_id,
            "premotor_spike_time_s": self.premotor_spike_time_s,
            "motor_node_id": self.motor_node_id,
            "motor_spike_time_s": self.motor_spike_time_s,
            "segment_id": self.segment_id,
            "path_provenance": self.path_provenance,
        }


@dataclass(frozen=True, slots=True)
class AxialLocomotionResult:
    duration_s: float
    displacement_x_um: float
    anatomical_forward_displacement_um: float
    stimulus: Mapping[str, bool]
    spike_counts: Mapping[str, int]
    first_spike_s: Mapping[str, float | None]
    premotor_spike_times_s: Mapping[str, Mapping[str, tuple[float, ...]]]
    relaxation_spike_times_s: Mapping[str, Mapping[str, tuple[float, ...]]]
    motor_spike_times_s: Mapping[str, tuple[float, ...]]
    contact_retention_range: tuple[float, float]
    contact_direction_input: bool
    trajectory_samples: tuple[dict[str, Any], ...]
    feedback_force_frames: int
    all_active_forces_sensory_traced: bool
    causal_trace_examples: Mapping[str, Mapping[str, object]]
    t3_contact_proxy_peak_activation: float
    t3_contact_proxy_neural_traced: bool
    release_validated: bool = False


class AxialLocomotionProtocol:
    """MDN/Pair1/A18b and A27h/GDL paths sharing the same motor pool."""

    def __init__(
        self,
        config: Mapping[str, Any],
        projection: NeuralMuscleIdentityProjection,
        *,
        lesion_node_ids: Iterable[str] = (),
        lesion_fiber_ids: Iterable[str] = (),
    ) -> None:
        self.config = config
        self.parameters = config["parameters"]
        self.projection = projection
        self.lesion_fiber_ids = tuple(lesion_fiber_ids)
        self.source_nodes_by_segment = {
            segment: tuple(
                sorted(
                    {
                        item.source_node_id
                        for item in projection.mappings
                        if item.segment_id == segment
                    }
                )
            )
            for segment in AXIAL_SEGMENTS
        }
        if any(not value for value in self.source_nodes_by_segment.values()):
            raise ValueError("axial locomotion requires A1-A6 motor mappings")

        labels = [
            "environment_touch:posterior",
            "environment_touch:anterior",
            "descending:MDN",
            "descending:Pair1",
        ]
        labels.extend(
            f"mechanosensory:shortening:{segment}" for segment in AXIAL_SEGMENTS
        )
        labels.extend(("mechanosensory:recovery:A1", "mechanosensory:recovery:A6"))
        labels.append(T3_CONTACT_PROXY_NODE)
        labels.extend(f"premotor:A27h:{segment}" for segment in AXIAL_SEGMENTS)
        labels.extend(f"inhibitory:GDL:{segment}" for segment in AXIAL_SEGMENTS)
        labels.extend(f"premotor:A18b:{segment}" for segment in AXIAL_SEGMENTS)
        labels.extend(f"inhibitory:Ifb-Bwd:{segment}" for segment in AXIAL_SEGMENTS)
        labels.extend(f"inhibitory:Canon-A18g:{segment}" for segment in AXIAL_SEGMENTS)
        labels.extend(sorted(projection.source_node_ids))
        if len(labels) != len(set(labels)):
            raise ValueError("axial neural labels must be unique")
        self.labels = tuple(labels)
        self.index_by_id = {label: index for index, label in enumerate(labels)}

        p = self.parameters
        dt = float(p["dt_s"])
        steps = lambda key: round(float(p[key]) / dt)
        premotor_current = float(p["premotor_current_a"])
        motor_current = float(p["motor_current_a"])
        inhibitory_current = float(p["inhibitory_current_a"])
        synapses = [
            Synapse(
                self.index_by_id["environment_touch:posterior"],
                self.index_by_id["premotor:A27h:A6"],
                premotor_current,
            ),
            Synapse(
                self.index_by_id["environment_touch:anterior"],
                self.index_by_id["descending:MDN"],
                premotor_current,
            ),
            Synapse(
                self.index_by_id["descending:MDN"],
                self.index_by_id["descending:Pair1"],
                premotor_current,
            ),
            Synapse(
                self.index_by_id["descending:MDN"],
                self.index_by_id["premotor:A18b:A1"],
                premotor_current,
            ),
            Synapse(
                self.index_by_id["mechanosensory:recovery:A1"],
                self.index_by_id["premotor:A27h:A6"],
                premotor_current,
                delay_steps=steps("forward_recovery_delay_s"),
            ),
            Synapse(
                self.index_by_id["mechanosensory:recovery:A6"],
                self.index_by_id["descending:MDN"],
                premotor_current,
                delay_steps=steps("backward_recovery_delay_s"),
            ),
            Synapse(
                self.index_by_id["premotor:A18b:A1"],
                self.index_by_id[T3_CONTACT_PROXY_NODE],
                motor_current,
                delay_steps=steps("backward_transverse_motor_delay_s"),
            ),
        ]
        for posterior, anterior in zip(
            FORWARD_WAVE[:-1], FORWARD_WAVE[1:], strict=True
        ):
            synapses.append(
                Synapse(
                    self.index_by_id[f"mechanosensory:shortening:{posterior}"],
                    self.index_by_id[f"premotor:A27h:{anterior}"],
                    premotor_current,
                    delay_steps=steps("intersegmental_delay_s"),
                )
            )
        for anterior, posterior in zip(
            BACKWARD_WAVE[:-1], BACKWARD_WAVE[1:], strict=True
        ):
            synapses.append(
                Synapse(
                    self.index_by_id[f"premotor:A18b:{anterior}"],
                    self.index_by_id[f"premotor:A18b:{posterior}"],
                    premotor_current,
                    delay_steps=steps("intersegmental_delay_s"),
                )
            )

        atlas = load_muscle_atlas()
        group_by_number = {
            muscle.number: muscle.spatial_group for muscle in atlas.template
        }
        groups_by_source: dict[str, set[str]] = {
            source: set() for source in projection.source_node_ids
        }
        for mapping in projection.mappings:
            groups_by_source[mapping.source_node_id].add(
                group_by_number[mapping.muscle_number]
            )
        transverse_sources = {
            source for source, groups in groups_by_source.items() if "T" in groups
        }
        self.transverse_source_node_ids = frozenset(transverse_sources)

        for segment in AXIAL_SEGMENTS:
            forward = self.index_by_id[f"premotor:A27h:{segment}"]
            gdl = self.index_by_id[f"inhibitory:GDL:{segment}"]
            backward = self.index_by_id[f"premotor:A18b:{segment}"]
            ifb = self.index_by_id[f"inhibitory:Ifb-Bwd:{segment}"]
            canon = self.index_by_id[f"inhibitory:Canon-A18g:{segment}"]
            pair1 = self.index_by_id["descending:Pair1"]
            synapses.extend(
                (
                    Synapse(
                        forward,
                        gdl,
                        premotor_current,
                        delay_steps=steps("gdl_delay_s"),
                    ),
                    Synapse(gdl, forward, inhibitory_current, kind="inhibitory"),
                    Synapse(pair1, forward, inhibitory_current, kind="inhibitory"),
                    Synapse(
                        backward,
                        ifb,
                        premotor_current,
                        delay_steps=steps("ifb_backward_delay_s"),
                    ),
                    Synapse(
                        backward,
                        canon,
                        premotor_current,
                        delay_steps=steps("canon_delay_s"),
                    ),
                )
            )
            for node_id in self.source_nodes_by_segment[segment]:
                motor = self.index_by_id[node_id]
                forward_motor_delay = (
                    steps("forward_transverse_motor_delay_s")
                    if node_id in transverse_sources
                    else 0
                )
                backward_motor_delay = (
                    steps("backward_transverse_motor_delay_s")
                    if node_id in transverse_sources
                    else steps("backward_longitudinal_motor_delay_s")
                )
                synapses.extend(
                    (
                        Synapse(
                            forward,
                            motor,
                            motor_current,
                            delay_steps=forward_motor_delay,
                        ),
                        Synapse(
                            backward,
                            motor,
                            motor_current,
                            delay_steps=backward_motor_delay,
                        ),
                        Synapse(gdl, motor, inhibitory_current, kind="inhibitory"),
                        Synapse(ifb, motor, inhibitory_current, kind="inhibitory"),
                        Synapse(canon, motor, inhibitory_current, kind="inhibitory"),
                    )
                )

        self.network = SparseLIFNetwork(len(labels), synapses)
        lesions = tuple(lesion_node_ids)
        if len(lesions) != len(set(lesions)):
            raise ValueError("axial neural lesions must be unique")
        unknown = set(lesions) - set(self.labels)
        if unknown:
            raise ValueError(f"unknown axial neural lesion nodes: {sorted(unknown)}")
        self.network.lesion(self.index_by_id[node] for node in lesions)
        projection.emit((), lesioned_fiber_ids=self.lesion_fiber_ids)

        self.activation_model = NeuralMuscleActivationModel(
            projection=projection,
            dt_s=dt,
            rise_tau_s=float(p["muscle_activation_rise_tau_s"]),
            decay_tau_s=float(p["muscle_activation_decay_tau_s"]),
            event_target=float(p["muscle_event_target"]),
            excitation_decay_tau_s=float(
                p["muscle_excitation_decay_tau_s"]
            ),
            event_excitation=float(p["muscle_event_excitation"]),
            excitation_decay_tau_s_by_segment=p[
                "muscle_excitation_decay_tau_s_by_segment"
            ],
            rise_tau_s_by_segment=p["muscle_activation_rise_tau_s_by_segment"],
            decay_tau_s_by_segment=p["muscle_activation_decay_tau_s_by_segment"],
        )
        self.adaptation = {
            f"mechanosensory:shortening:{segment}": 0.0
            for segment in AXIAL_SEGMENTS
        }
        self.adaptation["mechanosensory:recovery:A1"] = 0.0
        self.adaptation["mechanosensory:recovery:A6"] = 0.0
        self.pair1_gate = 0.0
        self.relaxation_drive = dict.fromkeys(AXIAL_SEGMENTS, 0.0)
        self.pending_origins = {
            (direction, segment): []
            for direction in ("forward", "backward")
            for segment in AXIAL_SEGMENTS
        }
        self.last_origin: dict[tuple[str, str], dict[str, object]] = {}
        self.pending_motor_trace: dict[
            tuple[str, float], AxialCausalTrace
        ] = {}
        self.additional_motor_origin_by_source: dict[
            str, Mapping[str, object]
        ] = {}
        self.last_force_trace_by_source: dict[str, dict[str, object]] = {}
        self.spike_counts = dict.fromkeys(self.labels, 0)
        self.first_spike_s: dict[str, float | None] = dict.fromkeys(
            self.labels, None
        )
        self.premotor_spike_times = {
            direction: {segment: [] for segment in AXIAL_SEGMENTS}
            for direction in ("forward", "backward")
        }
        self.relaxation_spike_times = {
            name: {segment: [] for segment in AXIAL_SEGMENTS}
            for name in ("GDL", "Ifb-Bwd", "Canon-A18g")
        }
        self.motor_spike_times = {segment: [] for segment in AXIAL_SEGMENTS}
        self._last_anterior_origin: dict[str, object] | None = None
        self.last_spiked_labels: tuple[str, ...] = ()
        self.t3_contact_proxy_activation = 0.0
        self.t3_contact_proxy_excitation = 0.0
        self.t3_contact_proxy_event_pending = False
        self.t3_contact_proxy_trace: dict[str, object] | None = None

    def _sensory_external(
        self,
        time_s: float,
        body_state: BodyStateSensoryFrame,
        posterior_touch: bool,
        anterior_touch: bool,
        local_tension_drive: Mapping[str, float],
    ) -> dict[int, float]:
        p = self.parameters
        dt = float(p["dt_s"])
        adaptation_decay = exp(-dt / float(p["sensory_adaptation_tau_s"]))
        for sensor_id in self.adaptation:
            self.adaptation[sensor_id] *= adaptation_decay
        self.pair1_gate *= exp(-dt / float(p["pair1_gate_tau_s"]))
        external: dict[int, float] = {}
        if self.pair1_gate > 0.0:
            pair1_inhibition = float(p["inhibitory_current_a"]) * self.pair1_gate
            for segment in AXIAL_SEGMENTS:
                external[self.index_by_id[f"premotor:A27h:{segment}"]] = (
                    -pair1_inhibition
                )
        if time_s < float(p["touch_duration_s"]):
            if posterior_touch:
                external[self.index_by_id["environment_touch:posterior"]] = float(
                    p["touch_current_a"]
                )
            if anterior_touch:
                external[self.index_by_id["environment_touch:anterior"]] = float(
                    p["touch_current_a"]
                )
        maximum = float(p["sensory_maximum_current_a"])
        forward_gate = max(0.0, 1.0 - self.pair1_gate)
        for segment in AXIAL_SEGMENTS:
            sensor_id = f"mechanosensory:shortening:{segment}"
            drive = (
                0.5
                * sum(
                    body_state.contraction_channels[
                        f"{segment}:{side}"
                    ].drive_0_1
                    for side in ("left", "right")
                )
                * min(
                    1.0,
                    max(0.0, float(local_tension_drive[segment]))
                    * float(p["local_tension_gate_gain"]),
                )
                * forward_gate
            )
            raw = drive * maximum
            adapted = max(0.0, raw - self.adaptation[sensor_id])
            if adapted > 0.0:
                external[self.index_by_id[sensor_id]] = adapted
        for segment, sensor_id in (
            ("A1", "mechanosensory:recovery:A1"),
            ("A6", "mechanosensory:recovery:A6"),
        ):
            state = body_state.segments[segment]
            gate = min(
                1.0,
                max(0.0, float(local_tension_drive[segment]))
                * float(p["local_tension_gate_gain"]),
            )
            drive = (
                min(
                    1.0,
                    max(
                        0.0,
                        state.strain_rate_s_1
                        - float(p["recovery_rate_threshold_s_1"]),
                    )
                    * float(p["recovery_rate_gain_s"]),
                )
                * gate
            )
            if segment == "A1":
                drive *= forward_gate
            else:
                drive *= min(1.0, self.pair1_gate)
            raw = drive * maximum
            adapted = max(0.0, raw - self.adaptation[sensor_id])
            if adapted > 0.0:
                external[self.index_by_id[sensor_id]] = adapted
        return external

    def _queue_origin(
        self,
        direction: str,
        segment: str,
        *,
        body_state_time_s: float,
        sensor_node_id: str,
        sensor_spike_time_s: float,
        available_time_s: float,
        path_provenance: str,
    ) -> None:
        self.pending_origins[(direction, segment)].append(
            {
                "body_state_time_s": body_state_time_s,
                "sensor_node_id": sensor_node_id,
                "sensor_spike_time_s": sensor_spike_time_s,
                "available_time_s": available_time_s,
                "path_provenance": path_provenance,
            }
        )

    def _apply_relaxation(
        self,
        frame: NeuralMuscleActivationFrame,
    ) -> NeuralMuscleActivationFrame:
        p = self.parameters
        dt = float(p["dt_s"])
        multiplier_by_segment = {
            segment: exp(
                -dt
                * float(p["relaxation_gain_s_1"])
                * self.relaxation_drive[segment]
            )
            for segment in AXIAL_SEGMENTS
        }
        adjusted = {
            mapping.fiber_id: (
                frame.activations[mapping.fiber_id]
                * multiplier_by_segment[mapping.segment_id]
            )
            for mapping in self.projection.mappings
        }
        self.activation_model.activations.update(adjusted)
        return NeuralMuscleActivationFrame(
            time_s=frame.time_s,
            activations=adjusted,
            applied_event_fibers=frame.applied_event_fibers,
            applied_source_by_fiber=frame.applied_source_by_fiber,
            applied_spike_time_s_by_fiber=frame.applied_spike_time_s_by_fiber,
            mapping_provenance_by_fiber=frame.mapping_provenance_by_fiber,
        )

    def step(
        self,
        time_s: float,
        body_state: BodyStateSensoryFrame,
        *,
        posterior_touch: bool,
        anterior_touch: bool,
        local_tension_drive: Mapping[str, float],
        additional_motor_current_by_source: Mapping[str, float] | None = None,
        additional_motor_origin_by_source: Mapping[
            str, Mapping[str, object]
        ] | None = None,
    ) -> NeuralMuscleActivationFrame:
        p = self.parameters
        dt = float(p["dt_s"])
        expected = self.network.step_index * self.network.config.dt_s
        if abs(time_s - expected) > 1e-9:
            raise ValueError("axial protocol must be stepped in time order")
        relaxation_decay = exp(-dt / float(p["relaxation_decay_tau_s"]))
        for segment in AXIAL_SEGMENTS:
            self.relaxation_drive[segment] *= relaxation_decay
        external = self._sensory_external(
            time_s,
            body_state,
            posterior_touch,
            anterior_touch,
            local_tension_drive,
        )
        additional_current = additional_motor_current_by_source or {}
        additional_origins = additional_motor_origin_by_source or {}
        if set(additional_current) != set(additional_origins):
            raise ValueError(
                "every additional MN current requires exactly one causal origin"
            )
        unknown_additional = set(additional_current) - self.projection.source_node_ids
        if unknown_additional:
            raise ValueError(
                "additional MN current targets are not mapped identities: "
                f"{sorted(unknown_additional)}"
            )
        for node_id, current in additional_current.items():
            value = float(current)
            origin = additional_origins[node_id]
            if (
                not isfinite(value)
                or value <= 0.0
                or origin.get("motor_node_id") != node_id
                or not isinstance(origin.get("sensor_spike_time_s"), (int, float))
                or not isinstance(origin.get("premotor_spike_time_s"), (int, float))
                or not (
                    float(origin["body_state_time_s"])
                    <= float(origin["sensor_spike_time_s"])
                    < float(origin["premotor_spike_time_s"])
                    < time_s
                )
            ):
                raise ValueError("additional MN current lacks an ordered neural origin")
            index = self.index_by_id[node_id]
            external[index] = external.get(index, 0.0) + value
            self.additional_motor_origin_by_source[node_id] = origin
        spikes = self.network.step(external)
        spiked_labels = tuple(self.labels[index] for index in spikes)
        self.last_spiked_labels = spiked_labels
        for label in spiked_labels:
            self.spike_counts[label] += 1
            if self.first_spike_s[label] is None:
                self.first_spike_s[label] = time_s

        for sensor_id in set(self.adaptation).intersection(spiked_labels):
            fraction = float(
                p[
                    "recovery_adaptation_fraction"
                    if ":recovery:" in sensor_id
                    else "sensory_adaptation_fraction"
                ]
            )
            self.adaptation[sensor_id] = max(
                self.adaptation[sensor_id],
                float(p["sensory_maximum_current_a"]) * fraction,
            )
        if "environment_touch:posterior" in spiked_labels:
            self._queue_origin(
                "forward",
                "A6",
                body_state_time_s=body_state.time_s,
                sensor_node_id="environment_touch:posterior",
                sensor_spike_time_s=time_s,
                available_time_s=time_s,
                path_provenance="MODEL_FITTED",
            )
        if "environment_touch:anterior" in spiked_labels:
            self._last_anterior_origin = {
                "body_state_time_s": body_state.time_s,
                "sensor_node_id": "environment_touch:anterior",
                "sensor_spike_time_s": time_s,
                "path_provenance": "ANATOMY_DERIVED",
            }
        if (
            "descending:MDN" in spiked_labels
            and self._last_anterior_origin is not None
        ):
            self._queue_origin(
                "backward",
                "A1",
                **self._last_anterior_origin,
                available_time_s=time_s,
            )
        if "descending:Pair1" in spiked_labels:
            self.pair1_gate = 1.0

        if self.t3_contact_proxy_event_pending:
            self.t3_contact_proxy_excitation = max(
                self.t3_contact_proxy_excitation,
                float(p["muscle_event_excitation"]),
            )
        proxy_target = float(p["muscle_event_target"]) * min(
            1.0, self.t3_contact_proxy_excitation
        )
        proxy_rising = proxy_target > self.t3_contact_proxy_activation
        proxy_tau_map = p[
            "muscle_activation_rise_tau_s_by_segment"
            if proxy_rising
            else "muscle_activation_decay_tau_s_by_segment"
        ]
        proxy_tau = float(proxy_tau_map["A1"])
        self.t3_contact_proxy_activation += (
            proxy_target - self.t3_contact_proxy_activation
        ) * (1.0 - exp(-dt / proxy_tau))
        self.t3_contact_proxy_excitation *= exp(
            -dt / float(p["muscle_excitation_decay_tau_s_by_segment"]["A1"])
        )
        self.t3_contact_proxy_event_pending = (
            T3_CONTACT_PROXY_NODE in spiked_labels
        )
        if self.t3_contact_proxy_event_pending:
            origin = self.last_origin.get(("backward", "A1"))
            if origin is not None:
                self.t3_contact_proxy_trace = AxialCausalTrace(
                    direction="backward",
                    body_state_time_s=float(origin["body_state_time_s"]),
                    sensor_node_id=str(origin["sensor_node_id"]),
                    sensor_spike_time_s=float(origin["sensor_spike_time_s"]),
                    premotor_node_id=str(origin["premotor_node_id"]),
                    premotor_spike_time_s=float(origin["premotor_spike_time_s"]),
                    motor_node_id=T3_CONTACT_PROXY_NODE,
                    motor_spike_time_s=time_s,
                    segment_id="T3",
                    path_provenance="MODEL_FITTED",
                ).as_mapping()
        for posterior, anterior in zip(
            FORWARD_WAVE[:-1], FORWARD_WAVE[1:], strict=True
        ):
            sensor_id = f"mechanosensory:shortening:{posterior}"
            if sensor_id in spiked_labels:
                self._queue_origin(
                    "forward",
                    anterior,
                    body_state_time_s=body_state.time_s,
                    sensor_node_id=sensor_id,
                    sensor_spike_time_s=time_s,
                    available_time_s=(
                        time_s + float(p["intersegmental_delay_s"])
                    ),
                    path_provenance="ANATOMY_DERIVED",
                )
        if "mechanosensory:recovery:A1" in spiked_labels:
            self._queue_origin(
                "forward",
                "A6",
                body_state_time_s=body_state.time_s,
                sensor_node_id="mechanosensory:recovery:A1",
                sensor_spike_time_s=time_s,
                available_time_s=time_s + float(p["forward_recovery_delay_s"]),
                path_provenance="ANATOMY_DERIVED",
            )
        if (
            "mechanosensory:recovery:A6" in spiked_labels
            and self._last_anterior_origin is not None
        ):
            self._last_anterior_origin = {
                "body_state_time_s": body_state.time_s,
                "sensor_node_id": "mechanosensory:recovery:A6",
                "sensor_spike_time_s": time_s,
                "path_provenance": "ANATOMY_DERIVED",
            }

        window = float(p["trace_arrival_window_s"])
        for direction, prefix, order in (
            ("forward", "premotor:A27h", FORWARD_WAVE),
            ("backward", "premotor:A18b", BACKWARD_WAVE),
        ):
            for order_index, segment in enumerate(order):
                premotor_id = f"{prefix}:{segment}"
                if premotor_id not in spiked_labels:
                    continue
                self.premotor_spike_times[direction][segment].append(time_s)
                candidates = [
                    item
                    for item in self.pending_origins[(direction, segment)]
                    if float(item["available_time_s"]) <= time_s
                    and time_s - float(item["available_time_s"]) <= window
                ]
                if candidates:
                    origin = max(
                        candidates,
                        key=lambda item: float(item["available_time_s"]),
                    )
                    self.last_origin[(direction, segment)] = {
                        **origin,
                        "premotor_node_id": premotor_id,
                        "premotor_spike_time_s": time_s,
                    }
                    if direction == "backward" and order_index + 1 < len(order):
                        next_segment = order[order_index + 1]
                        self._queue_origin(
                            "backward",
                            next_segment,
                            body_state_time_s=float(origin["body_state_time_s"]),
                            sensor_node_id=str(origin["sensor_node_id"]),
                            sensor_spike_time_s=float(origin["sensor_spike_time_s"]),
                            available_time_s=(
                                time_s + float(p["intersegmental_delay_s"])
                            ),
                            path_provenance=str(origin["path_provenance"]),
                        )
                self.pending_origins[(direction, segment)] = [
                    item
                    for item in self.pending_origins[(direction, segment)]
                    if time_s - float(item["available_time_s"]) <= window
                ]

        for name, prefix, impulse_key in (
            ("GDL", "inhibitory:GDL", "gdl_relaxation_impulse"),
            ("Ifb-Bwd", "inhibitory:Ifb-Bwd", "ifb_relaxation_impulse"),
            (
                "Canon-A18g",
                "inhibitory:Canon-A18g",
                "canon_relaxation_impulse",
            ),
        ):
            for segment in AXIAL_SEGMENTS:
                if f"{prefix}:{segment}" in spiked_labels:
                    self.relaxation_spike_times[name][segment].append(time_s)
                    self.relaxation_drive[segment] = max(
                        self.relaxation_drive[segment],
                        float(p[impulse_key]),
                    )

        source_segment = {
            node_id: segment
            for segment, nodes in self.source_nodes_by_segment.items()
            for node_id in nodes
        }
        axial_motor_spikes = tuple(
            label for label in spiked_labels if label in source_segment
        )
        for node_id in axial_motor_spikes:
            segment = source_segment[node_id]
            self.motor_spike_times[segment].append(time_s)
            steering_origin = self.additional_motor_origin_by_source.get(node_id)
            if (
                steering_origin is not None
                and float(steering_origin["premotor_spike_time_s"]) < time_s
                and time_s - float(steering_origin["premotor_spike_time_s"]) <= window
            ):
                self.pending_motor_trace[(node_id, time_s)] = AxialCausalTrace(
                    direction=str(steering_origin["direction"]),
                    body_state_time_s=float(steering_origin["body_state_time_s"]),
                    sensor_node_id=str(steering_origin["sensor_node_id"]),
                    sensor_spike_time_s=float(steering_origin["sensor_spike_time_s"]),
                    premotor_node_id=str(steering_origin["premotor_node_id"]),
                    premotor_spike_time_s=float(
                        steering_origin["premotor_spike_time_s"]
                    ),
                    motor_node_id=node_id,
                    motor_spike_time_s=time_s,
                    segment_id=segment,
                    path_provenance=str(steering_origin["path_provenance"]),
                )
                continue
            origins = [
                value
                for (direction, origin_segment), value in self.last_origin.items()
                if origin_segment == segment
                and float(value["premotor_spike_time_s"]) < time_s
                and time_s - float(value["premotor_spike_time_s"])
                <= window
                + max(
                    float(p["forward_transverse_motor_delay_s"]),
                    float(p["backward_transverse_motor_delay_s"]),
                )
            ]
            if not origins:
                continue
            origin = max(
                origins,
                key=lambda item: float(item["premotor_spike_time_s"]),
            )
            direction = (
                "forward"
                if str(origin["premotor_node_id"]).startswith("premotor:A27h")
                else "backward"
            )
            self.pending_motor_trace[(node_id, time_s)] = AxialCausalTrace(
                direction=direction,
                body_state_time_s=float(origin["body_state_time_s"]),
                sensor_node_id=str(origin["sensor_node_id"]),
                sensor_spike_time_s=float(origin["sensor_spike_time_s"]),
                premotor_node_id=str(origin["premotor_node_id"]),
                premotor_spike_time_s=float(origin["premotor_spike_time_s"]),
                motor_node_id=node_id,
                motor_spike_time_s=time_s,
                segment_id=segment,
                path_provenance=str(origin["path_provenance"]),
            )

        events = self.projection.emit(
            axial_motor_spikes, lesioned_fiber_ids=self.lesion_fiber_ids
        )
        activation = self._apply_relaxation(
            self.activation_model.step(time_s, events)
        )
        for fiber_id in activation.applied_event_fibers:
            source = activation.applied_source_by_fiber[fiber_id]
            spike_time = activation.applied_spike_time_s_by_fiber[fiber_id]
            trace = self.pending_motor_trace.get((source, spike_time))
            if trace is None:
                self.last_force_trace_by_source.pop(source, None)
            else:
                self.last_force_trace_by_source[source] = trace.as_mapping()
        return activation


class AxialLocomotionLarva:
    """Execute touch-selected axial neural paths through shared body physics."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        lesion_node_ids: Iterable[str] = (),
        lesion_fiber_ids: Iterable[str] = (),
    ) -> None:
        self.config = config or load_axial_locomotion_config()
        self.projection = load_neural_muscle_identity_projection()
        self.protocol = AxialLocomotionProtocol(
            self.config,
            self.projection,
            lesion_node_ids=lesion_node_ids,
            lesion_fiber_ids=lesion_fiber_ids,
        )
        coupling = self.config["named_fiber_body_coupling"]
        self.body = ScientificBody3D(
            load_body_spec(),
            maximum_shortening_by_segment=coupling[
                "maximum_shortening_fraction_by_segment"
            ],
        )
        dt = float(self.config["parameters"]["dt_s"])
        planted = float(
            self.config["continuous_ground_contact"][
                "planted_velocity_retention"
            ]
        )
        equilibrium_contact = {
            index: planted for index in range(len(self.body.particles))
        }
        for _ in range(50):
            self.body.step(
                dt,
                gravity=Vec3(0.0, 0.0, -9.81),
                ground_z=0.0,
                velocity_retention=float(coupling["body_velocity_retention"]),
                ground_velocity_retention_by_node=equilibrium_contact,
                iterations=int(
                    self.config["continuous_ground_contact"]["body_iterations"]
                ),
            )
        for particle in self.body.particles:
            particle.previous_position = particle.position

        side_counts: dict[tuple[str, str], int] = {}
        group_by_number = {
            item.number: item.spatial_group for item in load_muscle_atlas().template
        }
        for item in self.projection.mappings:
            key = (item.segment_id, item.side)
            side_counts[key] = side_counts.get(key, 0) + 1
        segment_totals = {
            segment: sum(
                side_counts.get((segment, side), 0)
                for side in ("left", "right")
            )
            for segment in AXIAL_SEGMENTS
        }
        fiber_force_scale_by_id = {
            item.fiber_id: (
                float(coupling["transverse_axial_force_projection_scale"])
                if group_by_number[item.muscle_number] == "T"
                else (
                    segment_totals[item.segment_id]
                    / 2.0
                    / side_counts[(item.segment_id, item.side)]
                )
            )
            for item in self.projection.mappings
        }
        self.coupling = NamedFiberBodyCoupling(
            body=self.body,
            projection=self.projection,
            dt_s=dt,
            fiber_force_scale_by_id=fiber_force_scale_by_id,
            active_tension_gain=float(
                coupling["active_tension_gain_model_units"]
            ),
            passive_stiffness=float(coupling["passive_stiffness_model_units"]),
            damping=float(coupling["damping_model_units"]),
            acceleration_scale_m_s2_per_model_force=float(
                coupling["acceleration_scale_m_s2_per_model_force"]
            ),
        )
        self.transducer = BodyStateSensoryTransducer(
            self.body,
            self.config["body_state_transduction"],
            ground_z_m=0.0,
        )
        self.body_index = {
            geometry.id: index
            for index, geometry in enumerate(self.body.geometry)
        }
        group_by_fiber = {
            item.fiber_id: item.spatial_group for item in self.coupling.geometries
        }
        self.contact_fiber_ids_by_segment = {
            segment: tuple(
                item.fiber_id
                for item in self.projection.mappings
                if item.segment_id == segment
                and group_by_fiber[item.fiber_id] == "T"
            )
            for segment in AXIAL_SEGMENTS
        }
        if any(not fibers for fibers in self.contact_fiber_ids_by_segment.values()):
            raise ValueError("continuous contact requires transverse fibers in A1-A6")
        self.axial_fiber_ids_by_segment = {
            segment: tuple(
                item.fiber_id
                for item in self.projection.mappings
                if item.segment_id == segment
                and group_by_fiber[item.fiber_id] != "T"
            )
            for segment in AXIAL_SEGMENTS
        }
        if any(not fibers for fibers in self.axial_fiber_ids_by_segment.values()):
            raise ValueError("axial mechanics requires non-transverse fibers in A1-A6")

    @staticmethod
    def _center(body: ScientificBody3D) -> Vec3:
        count = len(body.particles)
        return Vec3(
            sum(item.position.x for item in body.particles) / count,
            sum(item.position.y for item in body.particles) / count,
            sum(item.position.z for item in body.particles) / count,
        )

    def _contact_retention(
        self,
        contact_activation_by_segment: Mapping[str, float],
    ) -> tuple[dict[int, float], dict[str, float]]:
        contact = self.config["continuous_ground_contact"]
        planted = float(contact["planted_velocity_retention"])
        released = float(contact["released_velocity_retention"])
        activation_gain = float(contact["contact_activation_gain"])
        contact_activation_by_body_index = [
            float(contact_activation_by_segment.get(geometry.id, 0.0))
            for geometry in self.body.geometry
        ]
        retention: dict[int, float] = {}
        for node in range(len(self.body.particles)):
            anterior = (
                contact_activation_by_body_index[node - 1] if node else 0.0
            )
            sequestration = min(
                1.0,
                max(0.0, activation_gain * anterior),
            )
            retention[node] = planted + (released - planted) * sequestration
        return retention, {
            segment: float(contact_activation_by_segment.get(segment, 0.0))
            for segment in AXIAL_SEGMENTS
        }

    def run(
        self,
        *,
        posterior_touch: bool = False,
        anterior_touch: bool = False,
        duration_s: float | None = None,
        record_trajectory_interval_s: float | None = 0.03,
    ) -> AxialLocomotionResult:
        p = self.config["parameters"]
        coupling = self.config["named_fiber_body_coupling"]
        contact = self.config["continuous_ground_contact"]
        dt = float(p["dt_s"])
        duration = float(p["duration_s"] if duration_s is None else duration_s)
        steps = round(duration / dt)
        if steps <= 0:
            raise ValueError("axial duration must span at least one step")
        stride = (
            None
            if record_trajectory_interval_s is None
            else max(1, round(record_trajectory_interval_s / dt))
        )
        initial_center = self._center(self.body)
        local_tension_drive = dict.fromkeys(AXIAL_SEGMENTS, 0.0)
        feedback_frames = 0
        all_traced = True
        samples: list[dict[str, Any]] = []
        minimum_retention = 1.0
        maximum_retention = 0.0
        maximum_t3_contact_proxy_activation = 0.0
        t3_contact_proxy_neural_traced = True
        last_retention = {
            index: float(contact["planted_velocity_retention"])
            for index in range(len(self.body.particles))
        }
        if stride is not None:
            samples.append(
                {
                    "time_s": 0.0,
                    "nodes_um": [
                        [item.position.x * 1e6, item.position.y * 1e6, item.position.z * 1e6]
                        for item in self.body.particles
                    ],
                    "contact_retention_by_node": list(last_retention.values()),
                    "segment_activation": dict.fromkeys(AXIAL_SEGMENTS, 0.0),
                }
            )
        for step in range(steps):
            time_s = step * dt
            body_state = self.transducer.sample(time_s)
            activation = self.protocol.step(
                time_s,
                body_state,
                posterior_touch=posterior_touch,
                anterior_touch=anterior_touch,
                local_tension_drive=local_tension_drive,
            )
            force = self.coupling.step(
                activation,
                last_source_by_fiber=self.protocol.activation_model.last_applied_source,
                last_spike_time_s_by_fiber=self.protocol.activation_model.last_applied_spike_s,
                feedback_trace_by_source=self.protocol.last_force_trace_by_source,
            )
            activation_by_segment = {}
            for segment in AXIAL_SEGMENTS:
                values = [
                    activation.activations[fiber_id]
                    for fiber_id in self.axial_fiber_ids_by_segment[segment]
                ]
                activation_by_segment[segment] = sum(values) / len(values)
            self.body.set_activations(activation_by_segment)
            contact_activation_by_segment = {
                segment: sum(
                    activation.activations[fiber_id]
                    for fiber_id in self.contact_fiber_ids_by_segment[segment]
                )
                / len(self.contact_fiber_ids_by_segment[segment])
                for segment in AXIAL_SEGMENTS
            }
            contact_activation_by_segment["T3"] = (
                self.protocol.t3_contact_proxy_activation
            )
            maximum_t3_contact_proxy_activation = max(
                maximum_t3_contact_proxy_activation,
                self.protocol.t3_contact_proxy_activation,
            )
            if self.protocol.t3_contact_proxy_activation > 0.0:
                t3_contact_proxy_neural_traced = (
                    t3_contact_proxy_neural_traced
                    and self.protocol.t3_contact_proxy_trace is not None
                )
            if force.active_fiber_count > 0:
                feedback_frames += 1
                all_traced = all_traced and (
                    force.feedback_driven_fiber_count
                    == force.active_fiber_count
                    == force.feedback_traced_fiber_count
                )
            active_gain = float(coupling["active_tension_gain_model_units"])
            local_tension_drive = {}
            for segment in AXIAL_SEGMENTS:
                values = [
                    force.fibers[fiber_id].active_tension_model_units
                    / active_gain
                    for fiber_id in self.axial_fiber_ids_by_segment[segment]
                ]
                local_tension_drive[segment] = sum(values) / len(values)
            node_forces: dict[int, Vec3] = {}
            accelerations: dict[int, Vec3] = {}
            acceleration_scale = float(
                coupling["acceleration_scale_m_s2_per_model_force"]
            )
            for index, raw_force in force.node_forces_model_units.items():
                tangent = self.body.node_tangent_xy(index)
                axial_force = tangent * raw_force.dot(tangent)
                node_forces[index] = axial_force
                accelerations[index] = axial_force * acceleration_scale
            last_retention, _ = self._contact_retention(
                contact_activation_by_segment
            )
            minimum_retention = min(minimum_retention, *last_retention.values())
            maximum_retention = max(maximum_retention, *last_retention.values())
            self.body.step(
                dt,
                gravity=Vec3(0.0, 0.0, -9.81),
                ground_z=0.0,
                external_accelerations_m_s2=accelerations,
                velocity_retention=float(coupling["body_velocity_retention"]),
                ground_velocity_retention_by_node=last_retention,
                passive_planar_bending_stiffness_ratio=float(
                    coupling["passive_planar_bending_stiffness_ratio"]
                ),
                iterations=int(contact["body_iterations"]),
            )
            if stride is not None and (
                (step + 1) % stride == 0 or step + 1 == steps
            ):
                samples.append(
                    {
                        "time_s": round((step + 1) * dt, 9),
                        "nodes_um": [
                            [
                                round(item.position.x * 1e6, 9),
                                round(item.position.y * 1e6, 9),
                                round(item.position.z * 1e6, 9),
                            ]
                            for item in self.body.particles
                        ],
                        "contact_retention_by_node": [
                            round(last_retention[index], 9)
                            for index in range(len(self.body.particles))
                        ],
                        "segment_activation": {
                            segment: round(activation_by_segment[segment], 9)
                            for segment in AXIAL_SEGMENTS
                        },
                    }
                )
        displacement = self._center(self.body) - initial_center
        trace_examples: dict[str, Mapping[str, object]] = {}
        for trace in self.protocol.last_force_trace_by_source.values():
            key = f"{trace['direction']}:{trace['segment_id']}"
            trace_examples.setdefault(key, trace)
        return AxialLocomotionResult(
            duration_s=steps * dt,
            displacement_x_um=displacement.x * 1e6,
            anatomical_forward_displacement_um=-displacement.x * 1e6,
            stimulus={
                "posterior_touch": posterior_touch,
                "anterior_touch": anterior_touch,
            },
            spike_counts=dict(self.protocol.spike_counts),
            first_spike_s=dict(self.protocol.first_spike_s),
            premotor_spike_times_s={
                direction: {
                    segment: tuple(values)
                    for segment, values in by_segment.items()
                }
                for direction, by_segment in self.protocol.premotor_spike_times.items()
            },
            relaxation_spike_times_s={
                name: {
                    segment: tuple(values)
                    for segment, values in by_segment.items()
                }
                for name, by_segment in self.protocol.relaxation_spike_times.items()
            },
            motor_spike_times_s={
                segment: tuple(values)
                for segment, values in self.protocol.motor_spike_times.items()
            },
            contact_retention_range=(minimum_retention, maximum_retention),
            contact_direction_input=bool(contact["movement_direction_input"]),
            trajectory_samples=tuple(samples),
            feedback_force_frames=feedback_frames,
            all_active_forces_sensory_traced=all_traced,
            causal_trace_examples=trace_examples,
            t3_contact_proxy_peak_activation=(
                maximum_t3_contact_proxy_activation
            ),
            t3_contact_proxy_neural_traced=t3_contact_proxy_neural_traced,
        )
