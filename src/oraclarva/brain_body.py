"""Fitted L1EM whole brain coupled to the axial VNC/body model.

The brain (``BrainStepper``, 0.1 ms steps) and the axial body (1 ms steps)
advance together. Each 1 ms, spikes of two identified L1EM groups are summed
and delivered as excitatory synaptic current to reduced-circuit nodes:

- the four MDNs (MDNa/b left/right) -> ``descending:MDN`` (backward);
- the brain neurons annotated as descending to A8/A9 (``lv dVNC to A8+A9``,
  MDNs excluded) -> ``premotor:A27h:A6``, the posterior start of the forward
  wave (forward-initiation hypothesis).

Environmental events reach the brain only as Poisson input to sensory
neurons (``schedule``). Nothing sends a direction, gait or target to the body.
Requires the git-ignored L1EM snapshot in ``data/local`` and numba.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np

from .brain_sim import BrainStepper

ROOT = Path(__file__).resolve().parents[2]
FORWARD_GROUP_ANNOTATION = "lv dVNC to A8+A9"


def _fit_module():
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import fit_l1em_celltype_scales as fit  # noqa: PLC0415

    return fit


@dataclass
class Stimulus:
    """Poisson input to ``neurons`` at ``rate_hz`` during [start_s, stop_s)."""

    neurons: np.ndarray
    rate_hz: float
    start_s: float
    stop_s: float


@dataclass
class BrainContext:
    """Shared, seed-independent state: fitted scales, groups, sensory sets."""

    fit: object
    state: dict
    scale: np.ndarray
    free_signs: np.ndarray
    names: list[str]
    groups: dict[str, np.ndarray]
    background_hz: np.ndarray
    background_mv: float
    fitted: dict = field(default_factory=dict)

    @classmethod
    def load(cls, fit_path: str | Path, bg_hz: float = 100.0, bg_mv: float = 6.0) -> "BrainContext":
        fit = _fit_module()
        fitted = json.loads(Path(fit_path).read_text(encoding="utf-8"))
        state = fit.setup(tuple(fitted.get("fitted_free_signs", {})), fitted.get("shuffle"))
        base = state["base"]
        names = {n["skid"]: n["name"] for n in json.loads(fit.COMPILED.read_text(encoding="utf-8"))["neurons"]}
        listed = [names[s] for s in base.skids]
        x = np.array(fitted["best_x"], dtype=float)
        n_scale = len(fit.CLASSES) + 1
        groups = dict(state.get("groups", {}))
        groups.update(fit.motor_groups(state))
        return cls(
            fit=fit,
            state=state,
            scale=fit.row_scale(x[:n_scale], state),
            free_signs=np.where(x[n_scale:] >= 0, 1, -1).astype(np.int8),
            names=listed,
            groups=groups,
            background_hz=fit.background_rates(state, bg_hz),
            background_mv=bg_mv,
            fitted=fitted,
        )

    def network(self, seed: int):
        signs = self.state["signs"][seed].copy()
        signs[self.state["free_idx"]] = self.free_signs
        return self.state["base"].reweighted(signs=signs, row_scale=self.scale, w_syn_mv=self.fit.W_BASE)

    def stepper(self, seed: int, plasticity=None) -> BrainStepper:
        return BrainStepper(
            self.network(seed),
            seed=seed,
            background_hz=self.background_hz,
            background_weight_mv=self.background_mv,
            plasticity=plasticity,
        )


class BrainSpikeSource:
    """``descending_spike_source`` for ``AxialLocomotionLarva.run``.

    ``dynamic_rates(time_s) -> {neuron index: Hz}`` adds closed-loop sensory
    input (e.g. odor sampled at the current head position)."""

    def __init__(
        self,
        brain: BrainStepper,
        groups: Mapping[str, np.ndarray],
        bridges: Mapping[str, str],
        schedule: Sequence[Stimulus] = (),
        dynamic_rates: Callable[[float], Mapping[int, float]] | None = None,
        record: Sequence[str] = (),
    ) -> None:
        self.brain = brain
        self.groups = groups
        self.bridges = dict(bridges)  # axial node -> brain group name
        self.schedule = list(schedule)
        self.dynamic_rates = dynamic_rates
        self.counts = {name: 0 for name in set(self.bridges.values()) | set(record)}
        self.record = tuple(set(self.bridges.values()) | set(record))
        self.per_ms: dict[str, list[int]] = {name: [] for name in self.record}
        self.pending: dict[str, int] = {}

    def __call__(self, time_s: float, dt_s: float) -> dict[str, int]:
        rates: dict[int, float] = {}
        for stim in self.schedule:
            if stim.start_s <= time_s < stim.stop_s:
                for i in stim.neurons:
                    rates[int(i)] = rates.get(int(i), 0.0) + stim.rate_hz
        if self.dynamic_rates is not None:
            for i, r in self.dynamic_rates(time_s).items():
                rates[int(i)] = rates.get(int(i), 0.0) + float(r)
        # Return the spikes of the previous brain step [t - dt, t), then advance
        # the brain over [t, t + dt): delivered spikes always precede their effect.
        out = self.pending
        counts = self.brain.advance(dt_s * 1000.0, rates or None)
        for name in self.record:
            k = int(counts[self.groups[name]].sum())
            self.counts[name] += k
            self.per_ms[name].append(k)
        self.pending = {node: int(counts[self.groups[g]].sum()) for node, g in self.bridges.items()}
        return out
