"""Repeat-cycle A1-A6 crawl reference with no behavioral controller.

One initial posterior touch enters a sparse LIF network.  Later waves can only
restart through physical shortening and recovery sampled from the shared body.
The reduced sensory relay topology is an anatomy-derived hypothesis; every
numeric transduction, neural, activation, and mechanical value is model-fitted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import exp, isfinite
from pathlib import Path
from statistics import median
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
    load_neural_muscle_identity_projection,
)


WAVE_SEGMENTS = ("A6", "A5", "A4", "A3", "A2", "A1")


def default_repeat_crawl_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "organism"
        / "l1_repeat_crawl_v0.json"
    )


def load_repeat_crawl_config(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else default_repeat_crawl_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if (
        raw.get("model_id") != "dmel_l1_repeat_crawl_v0"
        or raw.get("status") != "research_approximation"
        or raw.get("stage") != "L1"
        or tuple(raw.get("supported_wave_segments_posterior_to_anterior", ()))
        != WAVE_SEGMENTS
        or raw.get("release_validated") is not False
    ):
        raise ValueError("repeat-crawl model boundary is invalid")
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
        or topology.get("provenance") != "ANATOMY_DERIVED"
        or topology.get("periodic_stimulus") is not False
        or topology.get("action_command") is not False
    ):
        raise ValueError("repeat-crawl causal topology is invalid")
    parameters = raw.get("parameters", {})
    positive = (
        "dt_s",
        "duration_s",
        "posterior_touch_current_a",
        "posterior_touch_duration_s",
        "premotor_synaptic_current_a",
        "motor_synaptic_current_a",
        "pmsi_inhibitory_current_a",
        "pmsi_delay_s",
        "intersegmental_relay_delay_s",
        "a1_recovery_to_a6_delay_s",
        "sensory_maximum_current_a",
        "sensory_adaptation_tau_s",
        "sensory_adaptation_fraction",
        "recovery_adaptation_fraction",
        "recovery_rate_threshold_s_1",
        "recovery_rate_gain_s",
        "local_tension_gate_gain",
        "trace_arrival_window_s",
        "muscle_activation_rise_tau_s",
        "muscle_activation_decay_tau_s",
        "muscle_event_target",
    )
    if any(
        not isfinite(float(parameters.get(name, 0.0)))
        or float(parameters.get(name, 0.0)) <= 0.0
        for name in positive
    ):
        raise ValueError("repeat-crawl parameters must be finite and positive")
    if float(parameters["dt_s"]) != float(
        raw["body_state_transduction"]["dt_s"]
    ) or float(parameters["dt_s"]) != float(
        raw["named_fiber_body_coupling"]["dt_s"]
    ):
        raise ValueError("repeat-crawl clocks must match in the Python oracle")
    if raw["body_state_transduction"].get("provenance") != "MODEL_FITTED":
        raise ValueError("repeat-crawl transduction must remain model-fitted")
    coupling = raw["named_fiber_body_coupling"]
    if (
        coupling.get("parameter_provenance") != "MODEL_FITTED"
        or coupling.get("force_unit") != "model_unit_not_newton"
        or coupling.get("force_projection_mode") != "local_tangent_axial"
        or coupling.get("force_projection_provenance") != "ANATOMY_DERIVED"
        or coupling.get("balance_mapped_fiber_side_coverage") is not True
        or coupling.get("coverage_balance_provenance") != "ANATOMY_DERIVED"
    ):
        raise ValueError("repeat-crawl mechanics boundary is invalid")
    decay_by_segment = parameters.get(
        "muscle_activation_decay_tau_s_by_segment", {}
    )
    shortening_by_segment = coupling.get(
        "maximum_shortening_fraction_by_segment", {}
    )
    if (
        set(decay_by_segment) != set(WAVE_SEGMENTS)
        or set(shortening_by_segment) != set(WAVE_SEGMENTS)
        or any(
            not isfinite(float(value)) or float(value) <= 0.0
            for value in decay_by_segment.values()
        )
        or any(
            not isfinite(float(value)) or not 0.0 < float(value) < 1.0
            for value in shortening_by_segment.values()
        )
        or not isfinite(float(coupling.get(
            "passive_planar_bending_stiffness_ratio", 0.0
        )))
        or float(coupling.get(
            "passive_planar_bending_stiffness_ratio", 0.0
        )) <= 0.0
        or not all(
            0.0 <= float(coupling[name]) <= 1.0
            for name in (
                "ground_negative_x_retention",
                "ground_positive_x_retention",
            )
        )
    ):
        raise ValueError("repeat-crawl fitted mechanics values are invalid")
    movement_gate = raw.get("directional_shape_gate", {})
    if (
        movement_gate.get("parameter_provenance") != "MODEL_FITTED"
        or float(
            movement_gate.get("minimum_forward_progress_efficiency", 0.0)
        ) > 1.0
        or any(
            not isfinite(float(movement_gate.get(name, 0.0)))
            or float(movement_gate.get(name, 0.0)) <= 0.0
            for name in (
                "minimum_forward_displacement_um",
                "maximum_absolute_lateral_displacement_um",
                "maximum_lateral_node_span_um",
                "maximum_planar_node_deviation_um",
                "minimum_forward_segment_alignment",
                "minimum_head_tail_chord_ratio",
                "maximum_backward_retrace_um",
                "minimum_forward_progress_efficiency",
            )
        )
    ):
        raise ValueError("repeat-crawl directional shape gate is invalid")
    calibration = raw.get("calibration", {})
    if (
        calibration.get("selection_used_held_out_values") is not False
        or calibration.get("parameter_provenance") != "MODEL_FITTED"
        or calibration.get("release_validated") is not False
        or calibration.get(
            "model_revision_after_prior_held_out_evaluation"
        ) is not True
        or calibration.get("independent_held_out_claim_available") is not False
    ):
        raise ValueError("repeat-crawl calibration boundary is invalid")
    return raw


@dataclass(frozen=True, slots=True)
class CausalMotorTrace:
    body_state_time_s: float
    sensor_node_id: str
    sensor_spike_time_s: float
    premotor_node_id: str
    premotor_spike_time_s: float
    motor_node_id: str
    motor_spike_time_s: float
    segment_id: str
    path_provenance: str = "ANATOMY_DERIVED"

    def force_mapping(self) -> dict[str, object]:
        return {
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
class RepeatCrawlResult:
    duration_s: float
    displacement_x_um: float
    displacement_y_um: float
    forward_displacement_um: float
    maximum_backward_retrace_um: float
    cumulative_backward_travel_um: float
    forward_progress_efficiency: float
    lateral_displacement_um: float
    maximum_lateral_span_um: float
    maximum_planar_deviation_um: float
    minimum_forward_segment_alignment: float
    minimum_head_tail_chord_ratio: float
    spike_counts: Mapping[str, int]
    first_spike_s: Mapping[str, float | None]
    premotor_spike_times_s: Mapping[str, tuple[float, ...]]
    motor_spike_times_s: Mapping[str, tuple[float, ...]]
    length_history_m: Mapping[str, tuple[float, ...]]
    center_x_history_m: tuple[float, ...]
    forward_position_history_m: tuple[float, ...]
    activation_history: Mapping[str, tuple[float, ...]]
    trajectory_samples: tuple[dict[str, Any], ...]
    feedback_force_frames: int
    all_active_forces_sensory_traced: bool
    maximum_pending_trace_count: int
    release_validated: bool = False

    def cycle_metrics(self, *, dt_s: float = 0.001) -> dict[str, Any]:
        """Measure neural cycles and causal physical responses, failing closed."""

        boundaries = tuple(self.premotor_spike_times_s.get("A6", ()))
        cycles: list[dict[str, Any]] = []
        physical_wave_speeds: list[float] = []
        for cycle_index, (start_s, end_s) in enumerate(
            zip(boundaries, boundaries[1:], strict=False)
        ):
            event_times: dict[str, float] = {}
            previous_event_s = start_s - dt_s
            for segment in WAVE_SEGMENTS:
                candidates = tuple(
                    value
                    for value in self.premotor_spike_times_s.get(segment, ())
                    if start_s <= value < end_s and value > previous_event_s
                )
                if candidates:
                    event_times[segment] = candidates[0]
                    previous_event_s = candidates[0]
            neural_ordered = len(event_times) == len(WAVE_SEGMENTS) and all(
                event_times[posterior] < event_times[anterior]
                for posterior, anterior in zip(
                    WAVE_SEGMENTS, WAVE_SEGMENTS[1:], strict=False
                )
            )
            if not neural_ordered:
                continue
            start = max(0, round(start_s / dt_s))
            end = min(len(self.forward_position_history_m), round(end_s / dt_s))
            if end - start < 3:
                continue
            physical_onsets: dict[str, float] = {}
            segment_metrics: dict[str, dict[str, float]] = {}
            missing_physical_response: list[str] = []
            for segment in WAVE_SEGMENTS:
                values = self.length_history_m[segment]
                event_index = max(start, round(event_times[segment] / dt_s))
                response_end = min(end, event_index + round(0.8 / dt_s))
                peak_end = min(response_end, event_index + round(0.05 / dt_s))
                if peak_end - event_index < 2:
                    missing_physical_response.append(segment)
                    continue
                peak_index = max(
                    range(event_index, peak_end), key=values.__getitem__
                )
                trough_index = min(
                    range(peak_index, response_end), key=values.__getitem__
                )
                peak = values[peak_index]
                trough = values[trough_index]
                amplitude = peak - trough
                if amplitude <= 0.0 or peak <= 0.0:
                    missing_physical_response.append(segment)
                    continue
                threshold = peak - 0.25 * amplitude
                onset_s: float | None = None
                for index in range(peak_index + 1, trough_index + 1):
                    before, after = values[index - 1], values[index]
                    if before > threshold >= after and before != after:
                        fraction = (before - threshold) / (before - after)
                        onset_s = (index - 1 + fraction) * dt_s
                        break
                if onset_s is None:
                    missing_physical_response.append(segment)
                    continue
                contraction_end_s: float | None = None
                for index in range(trough_index + 1, len(values)):
                    before, after = values[index - 1], values[index]
                    if before < threshold <= after and before != after:
                        fraction = (threshold - before) / (after - before)
                        contraction_end_s = (index - 1 + fraction) * dt_s
                        break
                if contraction_end_s is None:
                    missing_physical_response.append(segment)
                    continue
                physical_onsets[segment] = onset_s
                segment_metrics[segment] = {
                    "length_change_percent": 100.0 * amplitude / peak,
                    "duty_cycle_percent": (
                        100.0
                        * (contraction_end_s - onset_s)
                        / (end_s - start_s)
                    ),
                    "onset_s": onset_s,
                    "contraction_end_s": contraction_end_s,
                    "response_window_s": 0.8,
                }
            physical_ordered = (
                len(physical_onsets) == len(WAVE_SEGMENTS)
                and all(
                    physical_onsets[posterior] < physical_onsets[anterior]
                    for posterior, anterior in zip(
                        WAVE_SEGMENTS, WAVE_SEGMENTS[1:], strict=False
                    )
                )
            )
            physical_speed: float | None = None
            if physical_ordered:
                duration = physical_onsets["A1"] - physical_onsets["A6"]
                if duration > 0.0:
                    physical_speed = 5.0 / duration
                    physical_wave_speeds.append(physical_speed)
            cycles.append({
                "cycle_index": cycle_index,
                "status": (
                    "measured"
                    if physical_speed is not None
                    else "partial_physical_response"
                ),
                "start_s": start_s,
                "end_s": end_s,
                "period_s": end_s - start_s,
                "stride_um": (
                    self.forward_position_history_m[end - 1]
                    - self.forward_position_history_m[start]
                ) * 1e6,
                "neural_a1_a6_wave_speed_segments_s": (
                    5.0 / (event_times["A1"] - event_times["A6"])
                ),
                "a1_a6_wave_speed_segments_s": physical_speed,
                "segments": segment_metrics,
                "missing_physical_response": missing_physical_response,
                "physical_onset_order_valid": physical_ordered,
            })
        if not cycles:
            return {
                "status": "cycle_detection_failed",
                "complete_cycle_count": 0,
                "physical_wave_cycle_count": 0,
                "cycles": [],
                "median": None,
            }
        segment_medians: dict[str, dict[str, float] | None] = {}
        for segment in WAVE_SEGMENTS:
            available = [
                item["segments"][segment]
                for item in cycles
                if segment in item["segments"]
            ]
            segment_medians[segment] = (
                {
                    metric: median(item[metric] for item in available)
                    for metric in (
                        "length_change_percent",
                        "duty_cycle_percent",
                    )
                }
                if available
                else None
            )
        medians = {
            "period_s": median(item["period_s"] for item in cycles),
            "stride_um": median(item["stride_um"] for item in cycles),
            "neural_a1_a6_wave_speed_segments_s": median(
                item["neural_a1_a6_wave_speed_segments_s"] for item in cycles
            ),
            "a1_a6_wave_speed_segments_s": (
                median(physical_wave_speeds) if physical_wave_speeds else None
            ),
            "segments": segment_medians,
        }
        return {
            "status": (
                "measured"
                if len(physical_wave_speeds) == len(cycles)
                else "measured_with_failures"
            ),
            "complete_cycle_count": len(cycles),
            "physical_wave_cycle_count": len(physical_wave_speeds),
            "cycles": cycles,
            "median": medians,
        }

class RepeatCrawlProtocol:
    """Sparse sensory/premotor/MN path feeding the 146-fiber projection."""

    def __init__(
        self,
        config: Mapping[str, Any],
        projection: NeuralMuscleIdentityProjection,
        *,
        lesion_sensory_segment: str | None = None,
        lesion_premotor_segment: str | None = None,
        lesion_motor_node_ids: Iterable[str] = (),
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
            for segment in WAVE_SEGMENTS
        }
        if any(not values for values in self.source_nodes_by_segment.values()):
            raise ValueError("repeat crawl requires mapped source nodes in A1-A6")

        labels = ["environment_touch_receptor"]
        labels.extend(f"mechanosensory:shortening:{s}" for s in WAVE_SEGMENTS)
        labels.append("mechanosensory:recovery:A1")
        labels.extend(f"premotor_A27h_like:{s}" for s in WAVE_SEGMENTS)
        labels.extend(f"inhibitory_PMSI_like:{s}" for s in WAVE_SEGMENTS)
        labels.extend(sorted(projection.source_node_ids))
        if len(labels) != len(set(labels)):
            raise ValueError("repeat-crawl neural labels must be unique")
        self.labels = tuple(labels)
        self.index_by_id = {label: index for index, label in enumerate(labels)}

        dt = float(self.parameters["dt_s"])
        relay_steps = round(
            float(self.parameters["intersegmental_relay_delay_s"]) / dt
        )
        recovery_steps = round(
            float(self.parameters["a1_recovery_to_a6_delay_s"]) / dt
        )
        pmsi_steps = round(float(self.parameters["pmsi_delay_s"]) / dt)
        premotor_current = float(
            self.parameters["premotor_synaptic_current_a"]
        )
        motor_current = float(self.parameters["motor_synaptic_current_a"])
        inhibitory_current = float(
            self.parameters["pmsi_inhibitory_current_a"]
        )
        synapses = [
            Synapse(
                self.index_by_id["environment_touch_receptor"],
                self.index_by_id["premotor_A27h_like:A6"],
                premotor_current,
            )
        ]
        for posterior, anterior in zip(
            WAVE_SEGMENTS[:-1], WAVE_SEGMENTS[1:], strict=True
        ):
            synapses.append(
                Synapse(
                    self.index_by_id[f"mechanosensory:shortening:{posterior}"],
                    self.index_by_id[f"premotor_A27h_like:{anterior}"],
                    premotor_current,
                    delay_steps=relay_steps,
                )
            )
        synapses.append(
            Synapse(
                self.index_by_id["mechanosensory:recovery:A1"],
                self.index_by_id["premotor_A27h_like:A6"],
                premotor_current,
                delay_steps=recovery_steps,
            )
        )
        for segment in WAVE_SEGMENTS:
            premotor = self.index_by_id[f"premotor_A27h_like:{segment}"]
            inhibitory = self.index_by_id[f"inhibitory_PMSI_like:{segment}"]
            synapses.append(
                Synapse(
                    premotor,
                    inhibitory,
                    premotor_current,
                    delay_steps=pmsi_steps,
                )
            )
            synapses.append(
                Synapse(
                    inhibitory,
                    premotor,
                    inhibitory_current,
                    kind="inhibitory",
                )
            )
            for node_id in self.source_nodes_by_segment[segment]:
                motor = self.index_by_id[node_id]
                synapses.append(Synapse(premotor, motor, motor_current))
                synapses.append(
                    Synapse(
                        inhibitory,
                        motor,
                        inhibitory_current,
                        kind="inhibitory",
                    )
                )
        self.network = SparseLIFNetwork(len(labels), synapses)

        if lesion_sensory_segment is not None:
            if lesion_sensory_segment not in WAVE_SEGMENTS:
                raise ValueError("sensory lesion must be in A1-A6")
            sensory_id = (
                "mechanosensory:recovery:A1"
                if lesion_sensory_segment == "A1"
                else f"mechanosensory:shortening:{lesion_sensory_segment}"
            )
            self.network.lesion((self.index_by_id[sensory_id],))
        if lesion_premotor_segment is not None:
            if lesion_premotor_segment not in WAVE_SEGMENTS:
                raise ValueError("premotor lesion must be in A1-A6")
            self.network.lesion(
                (self.index_by_id[f"premotor_A27h_like:{lesion_premotor_segment}"],)
            )
        unknown_motor = set(lesion_motor_node_ids) - projection.source_node_ids
        if unknown_motor:
            raise ValueError(f"unknown motor lesion nodes: {sorted(unknown_motor)}")
        self.network.lesion(
            self.index_by_id[node_id] for node_id in lesion_motor_node_ids
        )
        projection.emit((), lesioned_fiber_ids=self.lesion_fiber_ids)

        self.activation_model = NeuralMuscleActivationModel(
            projection=projection,
            dt_s=dt,
            rise_tau_s=float(
                self.parameters["muscle_activation_rise_tau_s"]
            ),
            decay_tau_s=float(
                self.parameters["muscle_activation_decay_tau_s"]
            ),
            event_target=float(self.parameters["muscle_event_target"]),
            rise_tau_s_by_segment=self.parameters.get(
                "muscle_activation_rise_tau_s_by_segment"
            ),
            decay_tau_s_by_segment=self.parameters.get(
                "muscle_activation_decay_tau_s_by_segment"
            ),
        )
        self.adaptation = {
            f"mechanosensory:shortening:{segment}": 0.0
            for segment in WAVE_SEGMENTS
        }
        self.adaptation["mechanosensory:recovery:A1"] = 0.0
        self.raw_sensory_current = dict.fromkeys(self.adaptation, 0.0)
        self.peak_raw_sensory_current = dict.fromkeys(self.adaptation, 0.0)
        self.pending_origin_by_premotor: dict[
            str, list[dict[str, object]]
        ] = {segment: [] for segment in WAVE_SEGMENTS}
        self.last_premotor_origin: dict[str, dict[str, object]] = {}
        self.pending_motor_trace: dict[
            tuple[str, float], CausalMotorTrace
        ] = {}
        self.last_force_trace_by_source: dict[str, dict[str, object]] = {}
        self.spike_counts = dict.fromkeys(self.labels, 0)
        self.first_spike_s: dict[str, float | None] = dict.fromkeys(
            self.labels, None
        )
        self.premotor_spike_times = {segment: [] for segment in WAVE_SEGMENTS}
        self.motor_spike_times = {segment: [] for segment in WAVE_SEGMENTS}
        self.maximum_pending_trace_count = 0

    def _sensory_external(
        self,
        time_s: float,
        body_state: BodyStateSensoryFrame,
        stimulate: bool,
        local_tension_drive: Mapping[str, float],
    ) -> dict[int, float]:
        p = self.parameters
        dt = float(p["dt_s"])
        decay = exp(-dt / float(p["sensory_adaptation_tau_s"]))
        for sensor_id in self.adaptation:
            self.adaptation[sensor_id] *= decay
        external: dict[int, float] = {}
        if stimulate and time_s < float(p["posterior_touch_duration_s"]):
            external[self.index_by_id["environment_touch_receptor"]] = float(
                p["posterior_touch_current_a"]
            )
        maximum = float(p["sensory_maximum_current_a"])
        for segment in WAVE_SEGMENTS:
            sensor_id = f"mechanosensory:shortening:{segment}"
            drive = 0.5 * sum(
                body_state.contraction_channels[f"{segment}:{side}"].drive_0_1
                for side in ("left", "right")
            ) * min(
                1.0,
                max(0.0, float(local_tension_drive[segment]))
                * float(p["local_tension_gate_gain"]),
            )
            raw = drive * maximum
            self.raw_sensory_current[sensor_id] = raw
            self.peak_raw_sensory_current[sensor_id] = max(
                self.peak_raw_sensory_current[sensor_id], raw
            )
            adapted = max(0.0, raw - self.adaptation[sensor_id])
            if adapted > 0.0:
                external[self.index_by_id[sensor_id]] = adapted
        a1 = body_state.segments["A1"]
        recovery_drive = min(
            1.0,
            max(
                0.0,
                a1.strain_rate_s_1
                - float(p["recovery_rate_threshold_s_1"]),
            )
            * float(p["recovery_rate_gain_s"]),
        ) * min(
            1.0,
            max(0.0, float(local_tension_drive["A1"]))
            * float(p["local_tension_gate_gain"]),
        )
        recovery_id = "mechanosensory:recovery:A1"
        raw = recovery_drive * maximum
        self.raw_sensory_current[recovery_id] = raw
        self.peak_raw_sensory_current[recovery_id] = max(
            self.peak_raw_sensory_current[recovery_id], raw
        )
        adapted = max(0.0, raw - self.adaptation[recovery_id])
        if adapted > 0.0:
            external[self.index_by_id[recovery_id]] = adapted
        return external

    def _record_sensor_origin(
        self,
        sensor_id: str,
        time_s: float,
        body_state_time_s: float,
    ) -> None:
        if sensor_id == "environment_touch_receptor":
            target, delay = "A6", 0.0
            provenance = "MODEL_FITTED"
        elif sensor_id == "mechanosensory:recovery:A1":
            target = "A6"
            delay = float(self.parameters["a1_recovery_to_a6_delay_s"])
            provenance = "ANATOMY_DERIVED"
        else:
            segment = sensor_id.rsplit(":", 1)[-1]
            index = WAVE_SEGMENTS.index(segment)
            if index == len(WAVE_SEGMENTS) - 1:
                return
            target = WAVE_SEGMENTS[index + 1]
            delay = float(self.parameters["intersegmental_relay_delay_s"])
            provenance = "ANATOMY_DERIVED"
        self.pending_origin_by_premotor[target].append(
            {
                "body_state_time_s": body_state_time_s,
                "sensor_node_id": sensor_id,
                "sensor_spike_time_s": time_s,
                "available_time_s": time_s + delay,
                "path_provenance": provenance,
            }
        )

    def step(
        self,
        time_s: float,
        body_state: BodyStateSensoryFrame,
        *,
        stimulate: bool,
        local_tension_drive: Mapping[str, float],
    ) -> NeuralMuscleActivationFrame:
        expected = self.network.step_index * self.network.config.dt_s
        if abs(time_s - expected) > 1e-9:
            raise ValueError("repeat-crawl protocol must be stepped in time order")
        external = self._sensory_external(
            time_s, body_state, stimulate, local_tension_drive
        )
        spikes = self.network.step(external)
        spiked_labels = tuple(self.labels[index] for index in spikes)
        for label in spiked_labels:
            self.spike_counts[label] += 1
            if self.first_spike_s[label] is None:
                self.first_spike_s[label] = time_s

        sensor_ids = {"environment_touch_receptor"}
        sensor_ids.update(self.adaptation)
        for sensor_id in sensor_ids.intersection(spiked_labels):
            if sensor_id in self.adaptation:
                adaptation_fraction = float(
                    self.parameters[
                        "recovery_adaptation_fraction"
                        if sensor_id == "mechanosensory:recovery:A1"
                        else "sensory_adaptation_fraction"
                    ]
                )
                self.adaptation[sensor_id] = max(
                    self.adaptation[sensor_id],
                    float(self.parameters["sensory_maximum_current_a"])
                    * adaptation_fraction,
                )
            self._record_sensor_origin(sensor_id, time_s, body_state.time_s)

        window = float(self.parameters["trace_arrival_window_s"])
        for segment in WAVE_SEGMENTS:
            premotor_id = f"premotor_A27h_like:{segment}"
            if premotor_id not in spiked_labels:
                continue
            self.premotor_spike_times[segment].append(time_s)
            candidates = [
                item
                for item in self.pending_origin_by_premotor[segment]
                if float(item["available_time_s"]) <= time_s
                and time_s - float(item["available_time_s"]) <= window
            ]
            if candidates:
                origin = max(
                    candidates, key=lambda item: float(item["available_time_s"])
                )
                self.last_premotor_origin[segment] = {
                    **origin,
                    "premotor_node_id": premotor_id,
                    "premotor_spike_time_s": time_s,
                }
            self.pending_origin_by_premotor[segment] = [
                item
                for item in self.pending_origin_by_premotor[segment]
                if time_s - float(item["available_time_s"]) <= window
            ]

        source_segment = {
            node_id: segment
            for segment, nodes in self.source_nodes_by_segment.items()
            for node_id in nodes
        }
        motor_spikes = tuple(
            label for label in spiked_labels if label in source_segment
        )
        for node_id in motor_spikes:
            segment = source_segment[node_id]
            self.motor_spike_times[segment].append(time_s)
            origin = self.last_premotor_origin.get(segment)
            if origin is None:
                continue
            premotor_time = float(origin["premotor_spike_time_s"])
            if not premotor_time < time_s or time_s - premotor_time > window:
                continue
            self.pending_motor_trace[(node_id, time_s)] = CausalMotorTrace(
                body_state_time_s=float(origin["body_state_time_s"]),
                sensor_node_id=str(origin["sensor_node_id"]),
                sensor_spike_time_s=float(origin["sensor_spike_time_s"]),
                premotor_node_id=str(origin["premotor_node_id"]),
                premotor_spike_time_s=premotor_time,
                motor_node_id=node_id,
                motor_spike_time_s=time_s,
                segment_id=segment,
                path_provenance=str(origin["path_provenance"]),
            )

        events = self.projection.emit(
            motor_spikes, lesioned_fiber_ids=self.lesion_fiber_ids
        )
        activation = self.activation_model.step(time_s, events)
        for fiber_id in activation.applied_event_fibers:
            source = activation.applied_source_by_fiber[fiber_id]
            spike_time = activation.applied_spike_time_s_by_fiber[fiber_id]
            trace = self.pending_motor_trace.get((source, spike_time))
            if trace is None:
                self.last_force_trace_by_source.pop(source, None)
            else:
                self.last_force_trace_by_source[source] = trace.force_mapping()
        expired = time_s - max(
            window,
            float(self.parameters["a1_recovery_to_a6_delay_s"]) + window,
        )
        self.pending_motor_trace = {
            key: value
            for key, value in self.pending_motor_trace.items()
            if key[1] >= expired
        }
        self.maximum_pending_trace_count = max(
            self.maximum_pending_trace_count,
            len(self.pending_motor_trace)
            + sum(len(items) for items in self.pending_origin_by_premotor.values()),
        )
        return activation


class RepeatCrawlLarva:
    """Execute repeat-crawl neural output through attachment forces and physics."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        lesion_sensory_segment: str | None = None,
        lesion_premotor_segment: str | None = None,
        lesion_motor_node_ids: Iterable[str] = (),
        lesion_fiber_ids: Iterable[str] = (),
    ) -> None:
        self.config = config or load_repeat_crawl_config()
        self.projection = load_neural_muscle_identity_projection()
        self.protocol = RepeatCrawlProtocol(
            self.config,
            self.projection,
            lesion_sensory_segment=lesion_sensory_segment,
            lesion_premotor_segment=lesion_premotor_segment,
            lesion_motor_node_ids=lesion_motor_node_ids,
            lesion_fiber_ids=lesion_fiber_ids,
        )
        coupling = self.config["named_fiber_body_coupling"]
        self.body = ScientificBody3D(
            load_body_spec(),
            maximum_shortening_by_segment=coupling.get(
                "maximum_shortening_fraction_by_segment"
            ),
        )
        dt = float(coupling["dt_s"])
        for _ in range(50):
            self.body.step(
                dt,
                gravity=Vec3(0.0, 0.0, -9.81),
                ground_z=0.0,
                velocity_retention=float(coupling["body_velocity_retention"]),
                ground_velocity_retention_x=(
                    float(coupling["ground_negative_x_retention"]),
                    float(coupling["ground_positive_x_retention"]),
                ),
                use_local_tangent_friction=True,
            )
        for particle in self.body.particles:
            particle.previous_position = particle.position
        side_counts: dict[tuple[str, str], int] = {}
        for item in self.projection.mappings:
            key = (item.segment_id, item.side)
            side_counts[key] = side_counts.get(key, 0) + 1
        fiber_force_scale_by_id = None
        if coupling.get("balance_mapped_fiber_side_coverage", False):
            segment_totals = {
                segment: sum(
                    side_counts.get((segment, side), 0)
                    for side in ("left", "right")
                )
                for segment in WAVE_SEGMENTS
            }
            fiber_force_scale_by_id = {
                item.fiber_id: (
                    segment_totals[item.segment_id]
                    / 2.0
                    / side_counts[(item.segment_id, item.side)]
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

    @staticmethod
    def _center(body: ScientificBody3D) -> Vec3:
        count = len(body.particles)
        return Vec3(
            sum(item.position.x for item in body.particles) / count,
            sum(item.position.y for item in body.particles) / count,
            sum(item.position.z for item in body.particles) / count,
        )

    @classmethod
    def _center_x(cls, body: ScientificBody3D) -> float:
        return cls._center(body).x

    @staticmethod
    def _planar_deviation(body: ScientificBody3D) -> float:
        head = body.particles[0].position
        tail = body.particles[-1].position
        axis_x = tail.x - head.x
        axis_y = tail.y - head.y
        magnitude = (axis_x * axis_x + axis_y * axis_y) ** 0.5
        if magnitude == 0.0:
            return float("inf")
        return max(
            abs(
                (item.position.x - head.x) * axis_y
                - (item.position.y - head.y) * axis_x
            )
            / magnitude
            for item in body.particles
        )

    def _sample(
        self,
        time_s: float,
        activation_by_segment: Mapping[str, float],
        node_force_model_units: Mapping[int, Vec3] | None = None,
    ) -> dict[str, Any]:
        forces = node_force_model_units or {}
        return {
            "time_s": round(time_s, 9),
            "nodes_um": [
                [
                    round(item.position.x * 1e6, 9),
                    round(item.position.y * 1e6, 9),
                    round(item.position.z * 1e6, 9),
                ]
                for item in self.body.particles
            ],
            "segment_activation": {
                segment: round(activation_by_segment.get(segment, 0.0), 9)
                for segment in WAVE_SEGMENTS
            },
            "node_force_model_units": [
                [
                    round(forces.get(index, Vec3(0.0, 0.0, 0.0)).x, 12),
                    round(forces.get(index, Vec3(0.0, 0.0, 0.0)).y, 12),
                    round(forces.get(index, Vec3(0.0, 0.0, 0.0)).z, 12),
                ]
                for index in range(len(self.body.particles))
            ],
        }

    def run(
        self,
        *,
        stimulate: bool = True,
        duration_s: float | None = None,
        record_trajectory_interval_s: float | None = 0.03,
    ) -> RepeatCrawlResult:
        p = self.config["parameters"]
        coupling = self.config["named_fiber_body_coupling"]
        dt = float(p["dt_s"])
        duration = float(p["duration_s"] if duration_s is None else duration_s)
        steps = round(duration / dt)
        if steps <= 0:
            raise ValueError("repeat-crawl duration must span at least one step")
        stride = (
            None
            if record_trajectory_interval_s is None
            else max(1, round(record_trajectory_interval_s / dt))
        )
        initial_center = self._center(self.body)
        head = self.body.particles[0].position
        tail = self.body.particles[-1].position
        forward = Vec3(head.x - tail.x, head.y - tail.y, 0.0).normalized()
        lateral = Vec3(-forward.y, forward.x, 0.0)
        length_history = {segment: [] for segment in WAVE_SEGMENTS}
        center_x_history: list[float] = []
        forward_position_history: list[float] = []
        previous_forward_position = 0.0
        running_forward_peak = 0.0
        maximum_backward_retrace = 0.0
        cumulative_backward_travel = 0.0
        maximum_lateral_span = 0.0
        maximum_planar_deviation = 0.0
        minimum_forward_segment_alignment = 1.0
        minimum_head_tail_chord_ratio = 1.0
        posterior = forward * -1.0
        activation_history = {segment: [] for segment in WAVE_SEGMENTS}
        samples: list[dict[str, Any]] = []
        feedback_frames = 0
        all_traced = True
        local_tension_drive = dict.fromkeys(WAVE_SEGMENTS, 0.0)
        if stride is not None:
            samples.append(self._sample(0.0, {}))
        for step in range(steps):
            time_s = step * dt
            body_state = self.transducer.sample(time_s)
            activation = self.protocol.step(
                time_s,
                body_state,
                stimulate=stimulate,
                local_tension_drive=local_tension_drive,
            )
            force = self.coupling.step(
                activation,
                last_source_by_fiber=(
                    self.protocol.activation_model.last_applied_source
                ),
                last_spike_time_s_by_fiber=(
                    self.protocol.activation_model.last_applied_spike_s
                ),
                feedback_trace_by_source=(
                    self.protocol.last_force_trace_by_source
                ),
            )
            activation_by_segment = {}
            for segment in WAVE_SEGMENTS:
                values = [
                    activation.activations[item.fiber_id]
                    for item in self.projection.mappings
                    if item.segment_id == segment
                ]
                activation_by_segment[segment] = sum(values) / len(values)
            self.body.set_activations(activation_by_segment)
            if force.active_fiber_count > 0:
                feedback_frames += 1
                all_traced = all_traced and (
                    force.feedback_driven_fiber_count
                    == force.active_fiber_count
                    == force.feedback_traced_fiber_count
                )
            local_tension_drive = {}
            active_gain = float(coupling["active_tension_gain_model_units"])
            for segment in WAVE_SEGMENTS:
                values = [
                    force.fibers[item.fiber_id].active_tension_model_units
                    / active_gain
                    for item in self.projection.mappings
                    if item.segment_id == segment
                ]
                local_tension_drive[segment] = sum(values) / len(values)
            applied_node_forces = dict(force.node_forces_model_units)
            applied_accelerations = dict(force.node_accelerations_m_s2)
            if coupling.get("force_projection_mode") == "local_tangent_axial":
                applied_node_forces = {}
                applied_accelerations = {}
                acceleration_scale = float(
                    coupling["acceleration_scale_m_s2_per_model_force"]
                )
                for index, raw_force in force.node_forces_model_units.items():
                    tangent = self.body.node_tangent_xy(index)
                    axial_force = tangent * raw_force.dot(tangent)
                    applied_node_forces[index] = axial_force
                    applied_accelerations[index] = (
                        axial_force * acceleration_scale
                    )
            self.body.step(
                dt,
                gravity=Vec3(0.0, 0.0, -9.81),
                ground_z=0.0,
                external_accelerations_m_s2=applied_accelerations,
                velocity_retention=float(coupling["body_velocity_retention"]),
                ground_velocity_retention_x=(
                    float(coupling["ground_negative_x_retention"]),
                    float(coupling["ground_positive_x_retention"]),
                ),
                use_local_tangent_friction=True,
                directional_retention_includes_acceleration=True,
                passive_planar_bending_stiffness_ratio=float(
                    coupling.get("passive_planar_bending_stiffness_ratio", 1.0)
                ),
            )
            center = self._center(self.body)
            center_x_history.append(center.x)
            forward_position = (center - initial_center).dot(forward)
            forward_position_history.append(forward_position)
            forward_step = forward_position - previous_forward_position
            if forward_step < 0.0:
                cumulative_backward_travel -= forward_step
            running_forward_peak = max(running_forward_peak, forward_position)
            maximum_backward_retrace = max(
                maximum_backward_retrace,
                running_forward_peak - forward_position,
            )
            previous_forward_position = forward_position
            lateral_positions = [
                (item.position - initial_center).dot(lateral)
                for item in self.body.particles
            ]
            maximum_lateral_span = max(
                maximum_lateral_span,
                max(lateral_positions) - min(lateral_positions),
            )
            maximum_planar_deviation = max(
                maximum_planar_deviation, self._planar_deviation(self.body)
            )
            segment_vectors = [
                self.body.particles[index + 1].position
                - self.body.particles[index].position
                for index in range(len(self.body.particles) - 1)
            ]
            minimum_forward_segment_alignment = min(
                minimum_forward_segment_alignment,
                *(value.normalized().dot(posterior) for value in segment_vectors),
            )
            polyline_length = sum(value.norm() for value in segment_vectors)
            chord = (
                self.body.particles[-1].position
                - self.body.particles[0].position
            ).norm()
            minimum_head_tail_chord_ratio = min(
                minimum_head_tail_chord_ratio,
                chord / polyline_length if polyline_length else 0.0,
            )
            for segment in WAVE_SEGMENTS:
                activation_history[segment].append(
                    activation_by_segment[segment]
                )
                length_history[segment].append(
                    self.body.segment_length_m(self.body_index[segment])
                )
            if stride is not None and (
                (step + 1) % stride == 0 or step + 1 == steps
            ):
                samples.append(
                    self._sample(
                        (step + 1) * dt,
                        activation_by_segment,
                        applied_node_forces,
                    )
                )
        final_center = self._center(self.body)
        displacement = final_center - initial_center
        net_forward = displacement.dot(forward)
        progress_denominator = net_forward + cumulative_backward_travel
        forward_progress_efficiency = (
            net_forward / progress_denominator
            if progress_denominator > 0.0
            else 0.0
        )
        return RepeatCrawlResult(
            duration_s=steps * dt,
            displacement_x_um=displacement.x * 1e6,
            displacement_y_um=displacement.y * 1e6,
            forward_displacement_um=net_forward * 1e6,
            maximum_backward_retrace_um=maximum_backward_retrace * 1e6,
            cumulative_backward_travel_um=(
                cumulative_backward_travel * 1e6
            ),
            forward_progress_efficiency=forward_progress_efficiency,
            lateral_displacement_um=displacement.dot(lateral) * 1e6,
            maximum_lateral_span_um=maximum_lateral_span * 1e6,
            maximum_planar_deviation_um=maximum_planar_deviation * 1e6,
            minimum_forward_segment_alignment=minimum_forward_segment_alignment,
            minimum_head_tail_chord_ratio=minimum_head_tail_chord_ratio,
            spike_counts=dict(self.protocol.spike_counts),
            first_spike_s=dict(self.protocol.first_spike_s),
            premotor_spike_times_s={
                segment: tuple(values)
                for segment, values in self.protocol.premotor_spike_times.items()
            },
            motor_spike_times_s={
                segment: tuple(values)
                for segment, values in self.protocol.motor_spike_times.items()
            },
            length_history_m={
                segment: tuple(values)
                for segment, values in length_history.items()
            },
            center_x_history_m=tuple(center_x_history),
            forward_position_history_m=tuple(forward_position_history),
            activation_history={
                segment: tuple(values)
                for segment, values in activation_history.items()
            },
            trajectory_samples=tuple(samples),
            feedback_force_frames=feedback_frames,
            all_active_forces_sensory_traced=all_traced,
            maximum_pending_trace_count=(
                self.protocol.maximum_pending_trace_count
            ),
        )
