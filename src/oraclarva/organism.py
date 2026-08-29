"""Research-mode closed-loop nervous-system-to-body L1 reference organism."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from math import exp
from pathlib import Path
from typing import Any

from .body import load_body_spec
from .body3d import ScientificBody3D, Vec3
from .kinematics import load_kinematic_targets
from .lif import SparseLIFNetwork, Synapse
from .muscles import AggregateMuscleIdentityProjection, load_muscle_atlas
from .neuromuscular import load_neuromuscular_map


@dataclass(frozen=True, slots=True)
class ClosedLoopResult:
    model_id: str
    status: str
    duration_s: float
    displacement_um: float
    forward_axis: str
    spike_counts: dict[str, int]
    first_spike_s: dict[str, float | None]
    peak_activation: dict[str, float]
    peak_shortening_fraction: dict[str, float]
    causal_contract: tuple[str, ...]
    phase_fit: dict[str, dict[str, float | bool]]
    phase_fit_passed: bool
    contraction_kinematics: dict[str, dict[str, float | None]]
    contraction_fit: dict[str, dict[str, dict[str, float | bool | None]]]
    contraction_fit_passed: bool
    muscle_identity_summary: dict[str, Any]
    motor_identity_summary: dict[str, Any]
    trajectory_samples: tuple[dict[str, Any], ...]
    trajectory_sample_interval_s: float | None
    lesion: str | None
    muscle_lesion: str | None
    motor_identity_lesion: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "status": self.status,
            "duration_s": self.duration_s,
            "displacement_um": self.displacement_um,
            "forward_axis": self.forward_axis,
            "spike_counts": self.spike_counts,
            "first_spike_s": self.first_spike_s,
            "peak_activation": self.peak_activation,
            "peak_shortening_fraction": self.peak_shortening_fraction,
            "causal_contract": list(self.causal_contract),
            "phase_fit": self.phase_fit,
            "phase_fit_passed": self.phase_fit_passed,
            "contraction_kinematics": self.contraction_kinematics,
            "contraction_fit": self.contraction_fit,
            "contraction_fit_passed": self.contraction_fit_passed,
            "release_validated": False,
            "calibration_scope": (
                "in-sample Greaney 2026 L1 plausibility fit; no held-out cohort"
            ),
            "muscle_identity_summary": self.muscle_identity_summary,
            "motor_identity_summary": self.motor_identity_summary,
            "trajectory_frames": len(self.trajectory_samples),
            "trajectory_sample_interval_s": self.trajectory_sample_interval_s,
            "lesion": self.lesion,
            "muscle_lesion": self.muscle_lesion,
            "motor_identity_lesion": self.motor_identity_lesion,
            "claim_boundary": "reduced embodied neural research model; not a complete L1 brain emulation",
        }

    def trajectory_artifact(self) -> dict[str, Any]:
        if not self.trajectory_samples or self.trajectory_sample_interval_s is None:
            raise ValueError("run must record trajectory samples first")
        return {
            "schema_version": 1,
            "model_id": self.model_id,
            "status": self.status,
            "release_validated": False,
            "causal_contract": list(self.causal_contract),
            "units": {"time": "second", "position": "micrometre"},
            "sample_interval_s": self.trajectory_sample_interval_s,
            "body_segment_ids": [
                "PSC", "T1", "T2", "T3", "A1", "A2",
                "A3", "A4", "A5", "A6", "A7", "A8",
            ],
            "node_count": 13,
            "frames": list(self.trajectory_samples),
            "limitations": [
                "Generated from the research approximation, not measured motion capture.",
                "Physics nodes are internal; the viewer renders a separate continuous skin.",
                "All fitted and geometry claim boundaries remain in the source configs.",
            ],
        }



def default_closed_loop_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "organism" / "l1_closed_loop_v0.json"


def load_closed_loop_config(path: str | Path | None = None) -> dict[str, Any]:
    raw = json.loads((Path(path) if path else default_closed_loop_path()).read_text(encoding="utf-8"))
    if raw.get("status") != "research_approximation":
        raise ValueError("closed-loop v0 must remain explicitly research-only")
    if raw.get("topology", {}).get("provenance") != "ANATOMY_DERIVED":
        raise ValueError("reduced circuit topology must be anatomy-derived")
    if raw.get("parameter_provenance", {}).get("provenance") != "MODEL_FITTED":
        raise ValueError("unmeasured closed-loop parameters must be model-fitted")
    motor_identity_projection = raw.get("motor_identity_projection", {})
    if motor_identity_projection.get("mapping_provenance") != "MEASURED_PUBLISHED":
        raise ValueError("motor identity names and targets must remain source-backed")
    if motor_identity_projection.get("gain_provenance") != "MODEL_FITTED":
        raise ValueError("motor identity pooling gains must remain model-fitted")
    if int(motor_identity_projection.get("resolved_identities", 0)) != 58:
        raise ValueError("motor identity proxy must preserve 58 resolved skeletons")
    if motor_identity_projection.get("causal_proxy_segments") != ["A1"]:
        raise ValueError("only A1 has causal identity proxy coverage in v0")
    if motor_identity_projection.get("release_ready") is not False:
        raise ValueError("partial motor identity projection cannot be release-ready")
    identity_projection = raw.get("muscle_identity_projection", {})
    if identity_projection.get("provenance") != "MODEL_FITTED":
        raise ValueError("equal muscle-identity recruitment must remain model-fitted")
    if identity_projection.get("individual_geometry_executed") is not False:
        raise ValueError("identity proxy must not claim individual muscle geometry")
    if int(identity_projection.get("supported_fibers", 0)) != 358:
        raise ValueError("identity proxy must preserve the audited 358-fiber scope")
    expected = ["environment", "sensory_transduction", "neural_dynamics", "motor_neurons", "muscle_activation", "body_physics", "environment"]
    if raw.get("causal_contract") != expected:
        raise ValueError("closed-loop causal contract is incomplete or reordered")
    parameters = raw.get("parameters", {})
    if float(parameters.get("pmsi_recruitment_delay_s", -1.0)) < 0:
        raise ValueError("PMSI recruitment delay must be non-negative")
    if float(parameters.get("pmsi_inhibitory_current_a", 0.0)) <= 0:
        raise ValueError("PMSI inhibitory current must be positive")
    positive_parameters = (
        "motor_excitation_tau_s",
        "excitation_per_motor_spike",
        "muscle_activation_excitation_threshold",
        "motor_identity_synaptic_current_a",
    )
    if any(float(parameters.get(name, 0.0)) <= 0 for name in positive_parameters):
        raise ValueError("motor-excitation and activation parameters must be positive")
    if float(parameters["muscle_activation_excitation_threshold"]) >= float(
        parameters["excitation_per_motor_spike"]
    ):
        raise ValueError(
            "activation threshold must be below one motor-spike excitation"
        )
    modeled_segments = set(raw.get("wave_segments_posterior_to_anterior", ()))
    for map_name in (
        "maximum_shortening_fraction_by_segment",
        "muscle_activation_rise_tau_s_by_segment",
        "muscle_activation_fall_tau_s_by_segment",
    ):
        values = parameters.get(map_name, {})
        if set(values) != modeled_segments:
            raise ValueError(f"{map_name} must cover every modeled segment")
        if any(float(value) <= 0 for value in values.values()):
            raise ValueError(f"{map_name} values must be positive")
    shortening_upper = load_body_spec().maximum_shortening_fraction.upper
    if any(
        float(value) > shortening_upper
        for value in parameters[
            "maximum_shortening_fraction_by_segment"
        ].values()
    ):
        raise ValueError(
            "segment shortening capacity exceeds the body-model upper bound"
        )
    return raw


class ClosedLoopLarva:
    """Reduced embodied circuit with no crawl, turn, FSM, or animation commands."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        lesion_premotor_segment: str | None = None,
        lesion_muscle_segment: str | None = None,
        lesion_motor_identity_segment: str | None = None,
    ) -> None:
        self.config = config or load_closed_loop_config()
        self.params = self.config["parameters"]
        self.segments = tuple(self.config["wave_segments_posterior_to_anterior"])
        self.body = ScientificBody3D(
            load_body_spec(),
            maximum_shortening_by_segment=self.params[
                "maximum_shortening_fraction_by_segment"
            ],
        )
        self.body_indices = {segment.id: index for index, segment in enumerate(self.body.geometry)}
        self.neuromuscular_map = load_neuromuscular_map(self.body.spec)
        self.motor_identities = self.neuromuscular_map.projections
        self.motor_identities_by_segment = {
            segment: tuple(
                projection
                for projection in self.motor_identities
                if projection.channel.segment_id == segment
            )
            for segment in ("A1", "A2")
        }
        self.muscle_atlas = load_muscle_atlas()
        self.muscle_identity_projection = AggregateMuscleIdentityProjection(
            self.muscle_atlas
        )
        if any(segment not in self.body_indices for segment in self.segments):
            raise ValueError("closed-loop circuit references an unknown body segment")
        if lesion_premotor_segment is not None and lesion_premotor_segment not in self.segments:
            raise ValueError("lesion must name a modeled wave segment")
        if (
            lesion_muscle_segment is not None
            and lesion_muscle_segment not in self.muscle_atlas.supported_segments
        ):
            raise ValueError("muscle lesion must name an A1-A6 atlas segment")
        if (
            lesion_motor_identity_segment is not None
            and lesion_motor_identity_segment != "A1"
        ):
            raise ValueError(
                "only A1 has causal motor-identity proxy coverage in v0"
            )
        self.lesion = lesion_premotor_segment
        self.muscle_lesion = lesion_muscle_segment
        self.motor_identity_lesion = lesion_motor_identity_segment
        count = len(self.segments)
        self.touch = 0
        self.proprioceptor_offset = 1
        self.premotor_offset = 1 + count
        self.inhibitory_offset = 1 + 2 * count
        self.motor_offset = 1 + 3 * count
        self.motor_identity_offset = 1 + 4 * count
        self.motor_identity_indices = {
            projection.neuron_id: self.motor_identity_offset + index
            for index, projection in enumerate(self.motor_identities)
        }
        current = float(self.params["synaptic_current_a"])
        synapses = [Synapse(self.touch, self.premotor_offset, current)]
        synapses.extend(
            Synapse(self.premotor_offset + i, self.motor_offset + i, current)
            for i in range(count)
        )
        inhibitory_delay_steps = round(
            float(self.params["pmsi_recruitment_delay_s"])
            / float(self.params["dt_s"])
        )
        synapses.extend(
            Synapse(
                self.premotor_offset + i,
                self.inhibitory_offset + i,
                current,
                delay_steps=inhibitory_delay_steps,
            )
            for i in range(count)
        )
        synapses.extend(
            Synapse(
                self.inhibitory_offset + i,
                self.motor_offset + i,
                float(self.params["pmsi_inhibitory_current_a"]),
                kind="inhibitory",
            )
            for i in range(count)
        )
        identity_current = float(
            self.params["motor_identity_synaptic_current_a"]
        )
        synapses.extend(
            Synapse(
                self.motor_offset + self.segments.index(
                    projection.channel.segment_id
                ),
                self.motor_identity_indices[projection.neuron_id],
                identity_current,
            )
            for projection in self.motor_identities
        )
        relay_delays = self.params["intersegmental_relay_delay_s"]
        expected_relays = set(self.segments[:-1])
        if set(relay_delays) != expected_relays:
            raise ValueError("relay delays must cover every modeled intersegmental edge")
        dt = float(self.params["dt_s"])
        synapses.extend(
            Synapse(
                self.proprioceptor_offset + i,
                self.premotor_offset + i + 1,
                current,
                delay_steps=round(float(relay_delays[segment]) / dt),
            )
            for i, segment in enumerate(self.segments[:-1])
        )
        self.network = SparseLIFNetwork(
            self.motor_identity_offset + len(self.motor_identities),
            synapses,
        )
        if self.lesion is not None:
            self.network.lesion([self.premotor_offset + self.segments.index(self.lesion)])
        if self.motor_identity_lesion is not None:
            self.network.lesion(
                self.motor_identity_indices[projection.neuron_id]
                for projection in self.motor_identities_by_segment[
                    self.motor_identity_lesion
                ]
            )

    def run(
        self,
        *,
        stimulate: bool = True,
        record_trajectory_interval_s: float | None = None,
    ) -> ClosedLoopResult:
        p = self.params
        dt = float(p["dt_s"])
        steps = round(float(p["duration_s"]) / dt)
        if (
            record_trajectory_interval_s is not None
            and record_trajectory_interval_s <= 0
        ):
            raise ValueError("trajectory sample interval must be positive")
        trajectory_stride = (
            None
            if record_trajectory_interval_s is None
            else max(1, round(record_trajectory_interval_s / dt))
        )
        actual_trajectory_interval = (
            None if trajectory_stride is None else trajectory_stride * dt
        )
        excitation = [0.0] * len(self.segments)
        activation = [0.0] * len(self.segments)
        adaptation = [0.0] * len(self.segments)
        previous_length = [self.body.segment_length_m(self.body_indices[s]) for s in self.segments]
        length_history = [[length] for length in previous_length]
        peak_activation = [0.0] * len(self.segments)
        peak_shortening = [0.0] * len(self.segments)
        peak_recruited_fibers = 0
        active_motor_identity_ids: set[str] = set()
        labels = self._labels()
        spike_counts = {label: 0 for label in labels}
        first_spike = {label: None for label in labels}
        initial_center = self._center_x()
        trajectory_samples: list[dict[str, Any]] = []
        if trajectory_stride is not None:
            trajectory_samples.append(
                self._trajectory_sample(0.0, [0.0] * len(self.segments))
            )

        for step in range(steps):
            time_s = step * dt
            external: dict[int, float] = {}
            if stimulate and time_s < float(p["posterior_touch_duration_s"]):
                external[self.touch] = float(p["posterior_touch_current_a"])
            for i, segment in enumerate(self.segments):
                body_index = self.body_indices[segment]
                length = self.body.segment_length_m(body_index)
                rest = self.body.geometry[body_index].rest_length_m
                strain = max(0.0, 1.0 - length / rest)
                shortening_rate = max(0.0, (previous_length[i] - length) / dt)
                previous_length[i] = length
                adaptation[i] *= exp(-dt / float(p["sensory_adaptation_tau_s"]))
                drive = 0.0
                if strain >= float(p["proprioceptor_min_strain"]):
                    excess_rate = max(0.0, shortening_rate - float(p["proprioceptor_min_shortening_rate_m_s"]))
                    drive = min(float(p["proprioceptor_max_current_a"]), excess_rate * float(p["proprioceptor_current_gain_a_s_m"]))
                adapted_drive = max(0.0, drive - adaptation[i])
                if adapted_drive:
                    external[self.proprioceptor_offset + i] = adapted_drive
                    adaptation[i] += drive * float(p["sensory_adaptation_fraction"])
                peak_shortening[i] = max(peak_shortening[i], strain)

            spikes = self.network.step(external)
            for neuron in spikes:
                label = labels[neuron]
                spike_counts[label] += 1
                if first_spike[label] is None:
                    first_spike[label] = time_s
                if neuron >= self.motor_identity_offset:
                    active_motor_identity_ids.add(
                        self.motor_identities[
                            neuron - self.motor_identity_offset
                        ].neuron_id
                    )
            excitation_decay = exp(
                -dt / float(p["motor_excitation_tau_s"])
            )
            excitation_threshold = float(
                p["muscle_activation_excitation_threshold"]
            )
            for i, segment in enumerate(self.segments):
                excitation[i] *= excitation_decay
                if segment == "A1":
                    a1_identities = self.motor_identities_by_segment["A1"]
                    identity_spike_fraction = sum(
                        self.motor_identity_indices[projection.neuron_id]
                        in spikes
                        for projection in a1_identities
                    ) / len(a1_identities)
                    excitation[i] += (
                        float(p["excitation_per_motor_spike"])
                        * identity_spike_fraction
                    )
                elif self.motor_offset + i in spikes:
                    excitation[i] += float(p["excitation_per_motor_spike"])
                activation_target = (
                    1.0 if excitation[i] >= excitation_threshold else 0.0
                )
                tau_map_key = (
                    "muscle_activation_rise_tau_s_by_segment"
                    if activation_target > activation[i]
                    else "muscle_activation_fall_tau_s_by_segment"
                )
                coupling = 1.0 - exp(
                    -dt / float(p[tau_map_key][self.segments[i]])
                )
                activation[i] += (
                    activation_target - activation[i]
                ) * coupling
                activation[i] = min(1.0, max(0.0, activation[i]))
                peak_activation[i] = max(peak_activation[i], activation[i])
            segment_activation = dict(
                zip(self.segments, activation, strict=True)
            )
            identity_frame = self.muscle_identity_projection.project(
                segment_activation,
                lesioned_segments=(
                    () if self.muscle_lesion is None else (self.muscle_lesion,)
                ),
            )
            peak_recruited_fibers = max(
                peak_recruited_fibers, identity_frame.active_fiber_count
            )
            applied_activation = self.muscle_identity_projection.axial_proxy(
                identity_frame, segment_activation
            )
            self.body.set_activations(applied_activation)
            self.body.step(
                dt,
                gravity=Vec3(0.0, 0.0, -9.81),
                ground_z=0.0,
                velocity_retention=float(p["body_velocity_retention"]),
                ground_velocity_retention_x=(float(p["ground_negative_x_retention"]), float(p["ground_positive_x_retention"])),
            )
            for i, segment in enumerate(self.segments):
                length_history[i].append(
                    self.body.segment_length_m(self.body_indices[segment])
                )
            if trajectory_stride is not None and (
                (step + 1) % trajectory_stride == 0 or step + 1 == steps
            ):
                trajectory_samples.append(
                    self._trajectory_sample((step + 1) * dt, applied_activation)
                )

        phase_fit = self._phase_fit(first_spike)
        contraction_kinematics = {
            segment: self._contraction_kinematics(length_history[i], dt)
            for i, segment in enumerate(self.segments)
        }
        contraction_fit = self._contraction_fit(contraction_kinematics)
        return ClosedLoopResult(
            model_id=str(self.config["model_id"]), status=str(self.config["status"]), duration_s=steps * dt,
            displacement_um=(self._center_x() - initial_center) * 1e6, forward_axis="negative_x (posterior-to-anterior body coordinate)",
            spike_counts=spike_counts, first_spike_s=first_spike,
            peak_activation=dict(zip(self.segments, peak_activation, strict=True)),
            peak_shortening_fraction=dict(zip(self.segments, peak_shortening, strict=True)),
            causal_contract=tuple(self.config["causal_contract"]),
            phase_fit=phase_fit,
            phase_fit_passed=(
                len(phase_fit) == len(self.segments) - 1
                and all(
                    bool(item["inside_observed_p10_p90"])
                    for item in phase_fit.values()
                )
            ),
            contraction_kinematics=contraction_kinematics,
            contraction_fit=contraction_fit,
            contraction_fit_passed=(
                len(contraction_fit) == len(self.segments)
                and all(
                    bool(metric["inside_observed_p10_p90"])
                    for segment in contraction_fit.values()
                    for metric in segment.values()
                )
            ),
            motor_identity_summary={
                "map_model_id": self.neuromuscular_map.model_id,
                "dataset_id": self.neuromuscular_map.dataset_id,
                "mapping_provenance": "MEASURED_PUBLISHED",
                "gain_provenance": "MODEL_FITTED",
                "network_neurons": self.network.neuron_count,
                "reduced_core_neurons": self.motor_identity_offset,
                "resolved_identities": len(self.motor_identities),
                "active_identities": len(active_motor_identity_ids),
                "a1_causal_proxy_identities": len(
                    self.motor_identities_by_segment["A1"]
                ),
                "a2_diagnostic_only_identities": len(
                    self.motor_identities_by_segment["A2"]
                ),
                "unresolved_neuron_ids": list(
                    self.neuromuscular_map.unresolved_neuron_ids
                ),
                "release_ready": False,
            },
            muscle_identity_summary={
                "atlas_model_id": self.muscle_atlas.model_id,
                "projection_provenance": "MODEL_FITTED",
                "supported_segments": list(self.muscle_atlas.supported_segments),
                "supported_fibers": len(self.muscle_atlas.all_supported_fibers),
                "peak_recruited_fibers": peak_recruited_fibers,
                "individual_geometry_executed": False,
                "aggregation": "equal recruitment -> mean axial segment proxy",
            },
            trajectory_samples=tuple(trajectory_samples),
            trajectory_sample_interval_s=actual_trajectory_interval,
            lesion=self.lesion,
            muscle_lesion=self.muscle_lesion,
            motor_identity_lesion=self.motor_identity_lesion,
        )

    def _trajectory_sample(
        self,
        time_s: float,
        segment_activation: list[float] | dict[str, float],
    ) -> dict[str, Any]:
        if isinstance(segment_activation, dict):
            activations = [
                round(float(segment_activation.get(segment.id, 0.0)), 9)
                for segment in self.body.geometry
            ]
        else:
            by_segment = dict(
                zip(self.segments, segment_activation, strict=True)
            )
            activations = [
                round(float(by_segment.get(segment.id, 0.0)), 9)
                for segment in self.body.geometry
            ]
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
            "segment_activation": activations,
        }

    @staticmethod
    def _contraction_kinematics(
        length_history_m: list[float], dt_s: float
    ) -> dict[str, float | None]:
        """Extract one contraction using Greaney's 75%-amplitude crossings.

        This is a simulation-side implementation of the source paper's
        segment-length definition. It is not a neural or behavioral command.
        """
        minimum_index = min(range(len(length_history_m)), key=length_history_m.__getitem__)
        pre_peak_index = max(
            range(minimum_index + 1), key=length_history_m.__getitem__
        )
        rest_before = length_history_m[pre_peak_index]
        minimum = length_history_m[minimum_index]
        amplitude = rest_before - minimum
        max_shortening_rate = max(
            (left - right) / dt_s
            for left, right in zip(length_history_m[:-1], length_history_m[1:], strict=True)
        )
        if amplitude <= 0:
            return {
                "contraction_amplitude_percent": 0.0,
                "shortening_rate_um_s": max(0.0, max_shortening_rate * 1e6),
                "contraction_duration_s": None,
            }

        onset_threshold = rest_before - 0.75 * amplitude
        onset_time_s = None
        for index in range(pre_peak_index + 1, minimum_index + 1):
            before = length_history_m[index - 1]
            after = length_history_m[index]
            if before > onset_threshold >= after:
                fraction = (before - onset_threshold) / (before - after)
                onset_time_s = (index - 1 + fraction) * dt_s
                break

        post_rest = max(length_history_m[minimum_index:])
        offset_threshold = minimum + 0.75 * (post_rest - minimum)
        offset_time_s = None
        for index in range(minimum_index + 1, len(length_history_m)):
            before = length_history_m[index - 1]
            after = length_history_m[index]
            if before < offset_threshold <= after:
                fraction = (offset_threshold - before) / (after - before)
                offset_time_s = (index - 1 + fraction) * dt_s
                break
        duration = (
            None
            if onset_time_s is None or offset_time_s is None
            else offset_time_s - onset_time_s
        )
        return {
            "contraction_amplitude_percent": 100.0 * amplitude / rest_before,
            "shortening_rate_um_s": max(0.0, max_shortening_rate * 1e6),
            "contraction_duration_s": duration,
        }

    def _contraction_fit(
        self,
        simulated: dict[str, dict[str, float | None]],
    ) -> dict[str, dict[str, dict[str, float | bool | None]]]:
        targets = load_kinematic_targets()
        metrics = (
            "contraction_amplitude_percent",
            "shortening_rate_um_s",
            "contraction_duration_s",
        )
        result: dict[str, dict[str, dict[str, float | bool | None]]] = {}
        for segment in self.segments:
            result[segment] = {}
            for metric in metrics:
                band = targets.targets[segment][metric]
                if band is None:
                    continue
                value = simulated[segment][metric]
                result[segment][metric] = {
                    "simulated": value,
                    "observed_p10": band.p10,
                    "observed_median": band.median,
                    "observed_p90": band.p90,
                    "inside_observed_p10_p90": (
                        value is not None and band.contains(value)
                    ),
                }
        return result

    def _phase_fit(
        self, first_spike: dict[str, float | None]
    ) -> dict[str, dict[str, float | bool]]:
        targets = load_kinematic_targets()
        cycle_period = float(self.params["fitted_cycle_period_s"])
        result: dict[str, dict[str, float | bool]] = {}
        for posterior, anterior in zip(self.segments[:-1], self.segments[1:], strict=True):
            posterior_onset = first_spike[f"motor_pool:{posterior}"]
            anterior_onset = first_spike[f"motor_pool:{anterior}"]
            if posterior_onset is None or anterior_onset is None:
                continue
            band = targets.targets[posterior]["adjacent_onset_delay_cycle_fraction"]
            if band is None:
                continue
            simulated = (anterior_onset - posterior_onset) / cycle_period
            result[posterior] = {
                "simulated": simulated,
                "observed_p10": band.p10,
                "observed_median": band.median,
                "observed_p90": band.p90,
                "inside_observed_p10_p90": band.contains(simulated),
            }
        return result

    def _labels(self) -> list[str]:
        labels = ["environment_touch_receptor"]
        labels.extend(f"proprioceptor:{segment}" for segment in self.segments)
        labels.extend(f"premotor_A27h_like:{segment}" for segment in self.segments)
        labels.extend(f"inhibitory_PMSI_like:{segment}" for segment in self.segments)
        labels.extend(f"motor_pool:{segment}" for segment in self.segments)
        labels.extend(
            f"motor_identity:{projection.neuron_id}"
            for projection in self.motor_identities
        )
        return labels

    def _center_x(self) -> float:
        return sum(p.position.x for p in self.body.particles) / len(self.body.particles)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the research-mode embodied L1 closed-loop reference")
    parser.add_argument("--lesion-premotor", choices=load_closed_loop_config()["wave_segments_posterior_to_anterior"])
    parser.add_argument("--config", default=None)
    parser.add_argument(
        "--lesion-muscle-segment",
        choices=load_muscle_atlas().supported_segments,
        help="zero all named muscle-identity proxies in one A1-A6 segment",
    )
    parser.add_argument(
        "--lesion-motor-identity-segment",
        choices=("A1",),
        help="lesion all resolved causal motor-identity neurons in A1",
    )
    parser.add_argument("--no-touch", action="store_true", help="run the unstimulated control")
    args = parser.parse_args(argv)
    result = ClosedLoopLarva(
        load_closed_loop_config(args.config),
        lesion_premotor_segment=args.lesion_premotor,
        lesion_muscle_segment=args.lesion_muscle_segment,
        lesion_motor_identity_segment=args.lesion_motor_identity_segment,
    ).run(stimulate=not args.no_touch)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
