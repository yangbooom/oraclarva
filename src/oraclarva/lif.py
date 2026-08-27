"""Small, dependency-free LIF reference simulator using SI units.

This module favors auditability over speed. A future native mobile core must match
its outputs on shared fixtures before it is accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class LIFConfig:
    dt_s: float = 0.001
    tau_m_s: float = 0.020
    tau_exc_s: float = 0.005
    tau_inh_s: float = 0.010
    resistance_ohm: float = 100e6
    v_rest_v: float = -0.065
    v_reset_v: float = -0.065
    v_threshold_v: float = -0.050
    refractory_s: float = 0.002

    def __post_init__(self) -> None:
        positive = (
            self.dt_s,
            self.tau_m_s,
            self.tau_exc_s,
            self.tau_inh_s,
            self.resistance_ohm,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("time constants, dt, and resistance must be positive")
        if self.refractory_s < 0:
            raise ValueError("refractory_s must be non-negative")
        if self.v_threshold_v <= self.v_reset_v:
            raise ValueError("threshold must be above reset")


@dataclass(frozen=True, slots=True)
class Synapse:
    pre: int
    post: int
    current_a: float
    kind: str = "excitatory"

    def __post_init__(self) -> None:
        if self.pre < 0 or self.post < 0:
            raise ValueError("neuron indices must be non-negative")
        if self.current_a <= 0:
            raise ValueError("current_a is an unsigned magnitude and must be positive")
        if self.kind not in {"excitatory", "inhibitory"}:
            raise ValueError("kind must be excitatory or inhibitory")


class SparseLIFNetwork:
    """Event-driven sparse synapses around a fixed-step LIF membrane model."""

    def __init__(
        self,
        neuron_count: int,
        synapses: Iterable[Synapse] = (),
        config: LIFConfig | None = None,
    ) -> None:
        if neuron_count <= 0:
            raise ValueError("neuron_count must be positive")
        self.neuron_count = neuron_count
        self.config = config or LIFConfig()
        self.voltage_v = [self.config.v_rest_v] * neuron_count
        self.excitatory_current_a = [0.0] * neuron_count
        self.inhibitory_current_a = [0.0] * neuron_count
        self.refractory_steps = [0] * neuron_count
        self.lesioned: set[int] = set()
        self.step_index = 0
        self.outgoing: list[list[Synapse]] = [[] for _ in range(neuron_count)]
        for synapse in synapses:
            if synapse.pre >= neuron_count or synapse.post >= neuron_count:
                raise ValueError("synapse endpoint is outside the network")
            self.outgoing[synapse.pre].append(synapse)

    def lesion(self, neuron_ids: Iterable[int]) -> None:
        for neuron_id in neuron_ids:
            self._check_neuron(neuron_id)
            self.lesioned.add(neuron_id)
            self.voltage_v[neuron_id] = self.config.v_reset_v
            self.excitatory_current_a[neuron_id] = 0.0
            self.inhibitory_current_a[neuron_id] = 0.0

    def step(self, external_current_a: Mapping[int, float] | None = None) -> tuple[int, ...]:
        cfg = self.config
        external = external_current_a or {}
        for neuron_id in external:
            self._check_neuron(neuron_id)

        exc_decay = exp(-cfg.dt_s / cfg.tau_exc_s)
        inh_decay = exp(-cfg.dt_s / cfg.tau_inh_s)
        spikes: list[int] = []

        for neuron_id in range(self.neuron_count):
            self.excitatory_current_a[neuron_id] *= exc_decay
            self.inhibitory_current_a[neuron_id] *= inh_decay
            if neuron_id in self.lesioned:
                continue
            if self.refractory_steps[neuron_id] > 0:
                self.refractory_steps[neuron_id] -= 1
                self.voltage_v[neuron_id] = cfg.v_reset_v
                continue

            total_current = (
                self.excitatory_current_a[neuron_id]
                - self.inhibitory_current_a[neuron_id]
                + external.get(neuron_id, 0.0)
            )
            dv = cfg.dt_s * (
                (cfg.v_rest_v - self.voltage_v[neuron_id])
                + cfg.resistance_ohm * total_current
            ) / cfg.tau_m_s
            self.voltage_v[neuron_id] += dv
            if self.voltage_v[neuron_id] >= cfg.v_threshold_v:
                spikes.append(neuron_id)

        refractory_steps = round(cfg.refractory_s / cfg.dt_s)
        for neuron_id in spikes:
            self.voltage_v[neuron_id] = cfg.v_reset_v
            self.refractory_steps[neuron_id] = refractory_steps
            for synapse in self.outgoing[neuron_id]:
                if synapse.post in self.lesioned:
                    continue
                if synapse.kind == "excitatory":
                    self.excitatory_current_a[synapse.post] += synapse.current_a
                else:
                    self.inhibitory_current_a[synapse.post] += synapse.current_a

        self.step_index += 1
        return tuple(spikes)

    def run(
        self,
        steps: int,
        stimulus: Mapping[int, Mapping[int, float]] | None = None,
    ) -> list[tuple[int, ...]]:
        if steps < 0:
            raise ValueError("steps must be non-negative")
        schedule = stimulus or {}
        return [self.step(schedule.get(i)) for i in range(steps)]

    def _check_neuron(self, neuron_id: int) -> None:
        if not 0 <= neuron_id < self.neuron_count:
            raise IndexError(f"neuron {neuron_id} is outside the network")
