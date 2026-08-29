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
from .lif import SparseLIFNetwork, Synapse


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
    lesion: str | None

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
            "lesion": self.lesion,
            "claim_boundary": "reduced embodied neural research model; not a complete L1 brain emulation",
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
    expected = ["environment", "sensory_transduction", "neural_dynamics", "motor_neurons", "muscle_activation", "body_physics", "environment"]
    if raw.get("causal_contract") != expected:
        raise ValueError("closed-loop causal contract is incomplete or reordered")
    return raw


class ClosedLoopLarva:
    """Reduced embodied circuit with no crawl, turn, FSM, or animation commands."""

    def __init__(self, config: dict[str, Any] | None = None, *, lesion_premotor_segment: str | None = None) -> None:
        self.config = config or load_closed_loop_config()
        self.params = self.config["parameters"]
        self.segments = tuple(self.config["wave_segments_posterior_to_anterior"])
        self.body = ScientificBody3D(load_body_spec())
        self.body_indices = {segment.id: index for index, segment in enumerate(self.body.geometry)}
        if any(segment not in self.body_indices for segment in self.segments):
            raise ValueError("closed-loop circuit references an unknown body segment")
        if lesion_premotor_segment is not None and lesion_premotor_segment not in self.segments:
            raise ValueError("lesion must name a modeled wave segment")
        self.lesion = lesion_premotor_segment
        count = len(self.segments)
        self.touch = 0
        self.proprioceptor_offset = 1
        self.premotor_offset = 1 + count
        self.motor_offset = 1 + 2 * count
        current = float(self.params["synaptic_current_a"])
        synapses = [Synapse(self.touch, self.premotor_offset, current)]
        synapses.extend(Synapse(self.premotor_offset + i, self.motor_offset + i, current) for i in range(count))
        synapses.extend(Synapse(self.proprioceptor_offset + i, self.premotor_offset + i + 1, current) for i in range(count - 1))
        self.network = SparseLIFNetwork(1 + 3 * count, synapses)
        if self.lesion is not None:
            self.network.lesion([self.premotor_offset + self.segments.index(self.lesion)])

    def run(self, *, stimulate: bool = True) -> ClosedLoopResult:
        p = self.params
        dt = float(p["dt_s"])
        steps = round(float(p["duration_s"]) / dt)
        activation = [0.0] * len(self.segments)
        adaptation = [0.0] * len(self.segments)
        previous_length = [self.body.segment_length_m(self.body_indices[s]) for s in self.segments]
        peak_activation = [0.0] * len(self.segments)
        peak_shortening = [0.0] * len(self.segments)
        labels = self._labels()
        spike_counts = {label: 0 for label in labels}
        first_spike = {label: None for label in labels}
        initial_center = self._center_x()

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
            for i in range(len(self.segments)):
                activation[i] *= exp(-dt / float(p["muscle_activation_tau_s"]))
                if self.motor_offset + i in spikes:
                    activation[i] = min(1.0, activation[i] + float(p["activation_per_motor_spike"]))
                peak_activation[i] = max(peak_activation[i], activation[i])
            self.body.set_activations(dict(zip(self.segments, activation, strict=True)))
            self.body.step(
                dt,
                gravity=Vec3(0.0, 0.0, -9.81),
                ground_z=0.0,
                velocity_retention=float(p["body_velocity_retention"]),
                ground_velocity_retention_x=(float(p["ground_negative_x_retention"]), float(p["ground_positive_x_retention"])),
            )

        return ClosedLoopResult(
            model_id=str(self.config["model_id"]), status=str(self.config["status"]), duration_s=steps * dt,
            displacement_um=(self._center_x() - initial_center) * 1e6, forward_axis="negative_x (posterior-to-anterior body coordinate)",
            spike_counts=spike_counts, first_spike_s=first_spike,
            peak_activation=dict(zip(self.segments, peak_activation, strict=True)),
            peak_shortening_fraction=dict(zip(self.segments, peak_shortening, strict=True)),
            causal_contract=tuple(self.config["causal_contract"]), lesion=self.lesion,
        )

    def _labels(self) -> list[str]:
        labels = ["environment_touch_receptor"]
        labels.extend(f"proprioceptor:{segment}" for segment in self.segments)
        labels.extend(f"premotor_A27h_like:{segment}" for segment in self.segments)
        labels.extend(f"motor_pool:{segment}" for segment in self.segments)
        return labels

    def _center_x(self) -> float:
        return sum(p.position.x for p in self.body.particles) / len(self.body.particles)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the research-mode embodied L1 closed-loop reference")
    parser.add_argument("--lesion-premotor", choices=load_closed_loop_config()["wave_segments_posterior_to_anterior"])
    parser.add_argument("--config", default=None)
    parser.add_argument("--no-touch", action="store_true", help="run the unstimulated control")
    args = parser.parse_args(argv)
    result = ClosedLoopLarva(load_closed_loop_config(args.config), lesion_premotor_segment=args.lesion_premotor).run(stimulate=not args.no_touch)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
