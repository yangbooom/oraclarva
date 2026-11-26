"""Vectorized whole-brain LIF simulator for the compiled L1EM connectome.

Requires the optional ``data`` extra (numpy, scipy).  The dependency-free
``oraclarva.lif`` reference stays untouched; this engine targets thousands of
neurons.

Neuron model follows Shiu et al. 2024 (canonical values, see project memory):

    dv/dt = (v0 - v + g) / t_mbr          (not while refractory)
    dg/dt = -g / tau
    v >= v_th  ->  spike, v <- v0, g <- 0, refractory t_rfc
    each spike adds W[pre, post] (mV) to g[post] after t_dly

    W[pre, post] = contacts(pre, post) * fast_sign(pre) * w_syn

Unknown signs are resolved by an explicit ``SignPolicy`` so every run states
its assumption.  Modulatory transmitters (DA/OA/5-HT) get no fast weight by
default (project decision 2026-11-25); they are a separate channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy import sparse


@dataclass(frozen=True, slots=True)
class BrainParams:
    dt_ms: float = 0.1
    v0_mv: float = -52.0
    v_th_mv: float = -45.0
    t_mbr_ms: float = 20.0
    tau_ms: float = 5.0
    t_rfc_ms: float = 2.2
    t_dly_ms: float = 1.8
    w_syn_mv: float = 0.275
    poisson_weight_mv: float = 0.275 * 250  # Shiu w_syn * f_poi


@dataclass(frozen=True, slots=True)
class SignPolicy:
    """How to sign presynaptic neurons whose transmitter is unknown.

    mode:
      "excitatory"  unknown -> +1 (Shiu-style default)
      "silent"      unknown -> 0 (only neurons with known sign transmit)
      "sample"      unknown -> +1 with probability p_excitatory, else -1
    modulatory_fast_sign: fast sign given to modulatory-only neurons (default 0).
    """

    mode: str = "sample"
    p_excitatory: float = 0.7
    seed: int = 0
    modulatory_fast_sign: int = 0

    def __post_init__(self) -> None:
        if self.mode not in {"excitatory", "silent", "sample"}:
            raise ValueError(f"unknown sign mode {self.mode}")
        if not 0.0 <= self.p_excitatory <= 1.0:
            raise ValueError("p_excitatory must be in [0, 1]")


def resolve_signs(neurons: Sequence[Mapping[str, Any]], policy: SignPolicy) -> np.ndarray:
    rng = np.random.default_rng(policy.seed)
    draws = rng.random(len(neurons))
    signs = np.zeros(len(neurons), dtype=np.int8)
    for i, neuron in enumerate(neurons):
        known = neuron.get("fast_sign")
        if known in (1, -1):
            signs[i] = known
        elif neuron.get("modulatory"):
            signs[i] = policy.modulatory_fast_sign
        elif neuron.get("conflict"):
            signs[i] = 0
        elif policy.mode == "excitatory":
            signs[i] = 1
        elif policy.mode == "silent":
            signs[i] = 0
        else:
            signs[i] = 1 if draws[i] < policy.p_excitatory else -1
    return signs


@dataclass
class BrainNetwork:
    skids: list[str]
    signs: np.ndarray
    weights: sparse.csr_matrix  # rows = pre, cols = post, values in mV
    contacts: sparse.csr_matrix | None = None  # unsigned contact counts, rows = pre
    index: dict[str, int] = field(init=False)

    def __post_init__(self) -> None:
        self.index = {skid: i for i, skid in enumerate(self.skids)}

    def ids(self, skids: Iterable[str]) -> np.ndarray:
        return np.array([self.index[s] for s in skids if s in self.index], dtype=np.int64)

    def reweighted(
        self,
        signs: np.ndarray | None = None,
        row_scale: np.ndarray | None = None,
        w_syn_mv: float = BrainParams().w_syn_mv,
    ) -> "BrainNetwork":
        """Same graph, new signs and/or per-presynaptic-neuron scale (mV per contact = w_syn * scale)."""
        if self.contacts is None:
            raise ValueError("network was built without contacts")
        signs = self.signs if signs is None else np.asarray(signs, dtype=np.int8)
        scale = np.ones(len(self.skids)) if row_scale is None else np.asarray(row_scale, dtype=float)
        factor = sparse.diags(signs.astype(float) * scale * w_syn_mv)
        return BrainNetwork(
            skids=self.skids, signs=signs, weights=(factor @ self.contacts).tocsr(), contacts=self.contacts
        )


def build_network(
    compiled: Mapping[str, Any],
    policy: SignPolicy,
    params: BrainParams = BrainParams(),
    include: Iterable[str] | None = None,
) -> BrainNetwork:
    """Build W from a compiled connectome; ``include`` limits the neuron set."""
    keep = set(include) if include is not None else None
    neurons = [n for n in compiled["neurons"] if keep is None or n["skid"] in keep]
    skids = [n["skid"] for n in neurons]
    index = {s: i for i, s in enumerate(skids)}
    signs = resolve_signs(neurons, policy)
    rows, cols, vals = [], [], []
    for edge in compiled["edges"]:
        pre, post = index.get(edge["pre"]), index.get(edge["post"])
        if pre is None or post is None:
            continue
        rows.append(pre)
        cols.append(post)
        vals.append(float(sum(edge["contacts_by_confidence"])))
    n = len(skids)
    contacts = sparse.csr_matrix((vals, (rows, cols)), shape=(n, n), dtype=np.float64)
    weights = (sparse.diags(signs.astype(float) * params.w_syn_mv) @ contacts).tocsr()
    weights.eliminate_zeros()
    return BrainNetwork(skids=skids, signs=signs, weights=weights, contacts=contacts)


@dataclass
class RunResult:
    duration_ms: float
    spike_counts: np.ndarray
    spikes_per_bin: np.ndarray  # population spikes per bin_ms
    bin_ms: float
    late_counts: np.ndarray | None = None  # per-neuron spikes at t >= late_from_ms

    def rates_hz(self) -> np.ndarray:
        return self.spike_counts / (self.duration_ms / 1000.0)


def simulate(
    network: BrainNetwork,
    duration_ms: float,
    poisson_inputs: Mapping[int, float] | None = None,
    stim_window_ms: tuple[float, float] | None = None,
    params: BrainParams = BrainParams(),
    seed: int = 0,
    bin_ms: float = 10.0,
    late_from_ms: float | None = None,
) -> RunResult:
    """Run the network; ``poisson_inputs`` maps neuron index -> rate (Hz)."""
    n = len(network.skids)
    steps = int(round(duration_ms / params.dt_ms))
    delay = max(1, int(round(params.t_dly_ms / params.dt_ms)))
    refractory = int(round(params.t_rfc_ms / params.dt_ms))
    decay_g = np.exp(-params.dt_ms / params.tau_ms)
    k_mbr = params.dt_ms / params.t_mbr_ms
    rng = np.random.default_rng(seed)

    v = np.full(n, params.v0_mv)
    g = np.zeros(n)
    ref = np.zeros(n, dtype=np.int32)
    ring = np.zeros((delay, n))
    counts = np.zeros(n, dtype=np.int64)
    late = np.zeros(n, dtype=np.int64) if late_from_ms is not None else None
    late_step = int(round(late_from_ms / params.dt_ms)) if late_from_ms is not None else steps
    bin_steps = max(1, int(round(bin_ms / params.dt_ms)))
    per_bin = np.zeros(int(np.ceil(steps / bin_steps)), dtype=np.int64)

    stim_idx = np.array(sorted(poisson_inputs or {}), dtype=np.int64)
    stim_p = np.array([poisson_inputs[i] for i in stim_idx]) * params.dt_ms / 1000.0 if stim_idx.size else None
    start, stop = stim_window_ms if stim_window_ms else (0.0, duration_ms)
    weights = network.weights

    for step in range(steps):
        slot = step % delay
        g += ring[slot]
        ring[slot] = 0.0
        t = step * params.dt_ms
        if stim_idx.size and start <= t < stop:
            hits = stim_idx[rng.random(stim_idx.size) < stim_p]
            g[hits] += params.poisson_weight_mv

        active = ref == 0
        v[active] += k_mbr * (params.v0_mv - v[active] + g[active])
        g[active] *= decay_g  # Shiu: g frozen while refractory
        ref[~active] -= 1

        fired = np.flatnonzero(active & (v >= params.v_th_mv))
        if fired.size:
            v[fired] = params.v0_mv
            g[fired] = 0.0
            ref[fired] = refractory
            counts[fired] += 1
            if late is not None and step >= late_step:
                late[fired] += 1
            per_bin[step // bin_steps] += fired.size
            ring[(step + delay) % delay] += np.asarray(weights[fired].sum(axis=0)).ravel()
    return RunResult(
        duration_ms=duration_ms, spike_counts=counts, spikes_per_bin=per_bin, bin_ms=bin_ms, late_counts=late
    )
