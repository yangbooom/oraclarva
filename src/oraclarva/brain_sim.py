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


def shuffle_targets(
    contacts: sparse.csr_matrix, seed: int, groups: np.ndarray | None = None
) -> sparse.csr_matrix:
    """Null-model rewiring: permute postsynaptic targets among edges.

    Every edge keeps its presynaptic neuron and contact count, so each neuron's
    out-degree, total output contacts and in-degree (edge count) are preserved.
    With ``groups`` (one label per neuron) targets are permuted only inside each
    (pre group, post group) block, which also preserves the group-to-group
    contact matrix: only *which* member of a group is wired to which changes.
    Self-loops are re-drawn inside their block; duplicate edges are merged.
    """
    rng = np.random.default_rng(seed)
    coo = contacts.tocoo()
    rows, cols, data = coo.row.copy(), coo.col.copy(), coo.data.copy()
    key = np.zeros(rows.size, dtype=np.int64) if groups is None else groups[rows] * (int(groups.max()) + 1) + groups[cols]
    order = np.argsort(key, kind="stable")
    bounds = np.flatnonzero(np.diff(key[order])) + 1
    for block in np.split(order, bounds):
        cols[block] = cols[block][rng.permutation(block.size)]
        for _ in range(20):
            loops = block[rows[block] == cols[block]]
            if loops.size == 0 or block.size < 2:
                break
            partners = rng.choice(block, size=loops.size)
            cols[loops], cols[partners] = cols[partners], cols[loops].copy()
    keep = rows != cols
    out = sparse.csr_matrix((data[keep], (rows[keep], cols[keep])), shape=contacts.shape)
    out.sum_duplicates()
    return out


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
class Plasticity:
    """Dopamine-gated KC->MBON depression (three-factor, synapse-local rule).

    dw_ij/dt = -eta * kc_trace_i(t) * da_j(t) * w_ij      (w_ij >= 0)
    da_j     = sum_d modulation[d, j] * max(0, dan_trace_d(t) - da_threshold)

``da_threshold`` (spikes in the DAN trace) stands in for the supralinear
cAMP coincidence detection downstream of dopamine: weak, odor-evoked DAN
activity does not teach, strong reinforcer-evoked activity does.

    ``modulation`` (n_dan x n_mbon) is the compartment proxy; here it comes
    from measured DAN->MBON contacts, row-normalized (ANATOMY_DERIVED).  KC->MBON
    weights are taken out of the sparse matrix and held densely in ``km`` so
    they can change; they persist across ``simulate`` calls (train, then test).
    """

    kc_idx: np.ndarray
    mbon_idx: np.ndarray
    dan_idx: np.ndarray
    modulation: np.ndarray
    eta: float = 2e-6  # per ms per (trace unit)^2
    tau_kc_ms: float = 500.0
    tau_dan_ms: float = 300.0
    da_threshold: float = 0.0
    learn: bool = True
    km: np.ndarray | None = None
    km_initial: np.ndarray | None = None

    def attach(self, network: "BrainNetwork") -> "BrainNetwork":
        """Move KC->MBON weights from ``network`` into ``km``; return the network without them."""
        w = network.weights.tolil(copy=True)
        sub = network.weights[self.kc_idx][:, self.mbon_idx].toarray()
        for i in self.kc_idx:
            for j in self.mbon_idx:
                if w[i, j] != 0:
                    w[i, j] = 0.0
        self.km = sub.copy()
        self.km_initial = sub.copy()
        stripped = w.tocsr()
        stripped.eliminate_zeros()
        return BrainNetwork(skids=network.skids, signs=network.signs, weights=stripped, contacts=network.contacts)


@dataclass
class RunResult:
    duration_ms: float
    spike_counts: np.ndarray
    spikes_per_bin: np.ndarray  # population spikes per bin_ms
    bin_ms: float
    late_counts: np.ndarray | None = None  # per-neuron spikes at t >= late_from_ms

    def rates_hz(self) -> np.ndarray:
        return self.spike_counts / (self.duration_ms / 1000.0)


try:  # optional compiled engine
    from oraclarva.brain_kernel import init_state as _init_state
    from oraclarva.brain_kernel import run_kernel as _run_kernel

    _HAVE_NUMBA = True
except ImportError:  # pragma: no cover - numba not installed
    _HAVE_NUMBA = False


def _simulate_numba(
    network, duration_ms, steps, delay, refractory, decay_g, k_mbr, params, seed,
    stim_idx, stim_p, start, stop, extras, bg_prob, bg_weight, late_step, bin_steps, bin_ms, want_late, plasticity,
):
    dt = params.dt_ms
    neurons, probs, weights, starts, stops = [], [], [], [], []

    def add(idx, prob, window):
        neurons.append(np.asarray(idx, dtype=np.int64))
        probs.append(np.asarray(prob, dtype=float))
        weights.append(np.full(len(idx), params.poisson_weight_mv))
        # step t is active when window[0] <= step*dt < window[1]
        starts.append(np.full(len(idx), int(np.ceil(window[0] / dt - 1e-9)), dtype=np.int64))
        stops.append(np.full(len(idx), int(np.ceil(window[1] / dt - 1e-9)), dtype=np.int64))

    if stim_idx.size:
        add(stim_idx, stim_p, (start, stop))
    for idx, prob, window in extras:
        add(idx, prob, window)
    cat = lambda xs, dtype: np.concatenate(xs).astype(dtype) if xs else np.zeros(0, dtype=dtype)  # noqa: E731
    w = network.weights.tocsr()
    n = len(network.skids)
    if plasticity is not None:
        kc_local = np.full(n, -1, dtype=np.int64)
        kc_local[plasticity.kc_idx] = np.arange(plasticity.kc_idx.size)
        dan_local = np.full(n, -1, dtype=np.int64)
        dan_local[plasticity.dan_idx] = np.arange(plasticity.dan_idx.size)
        km = np.ascontiguousarray(plasticity.km, dtype=float)
        args = (
            True, kc_local, dan_local, np.asarray(plasticity.mbon_idx, dtype=np.int64), km,
            np.ascontiguousarray(plasticity.modulation, dtype=float), plasticity.eta * dt, float(plasticity.da_threshold),
            float(np.exp(-dt / plasticity.tau_kc_ms)), float(np.exp(-dt / plasticity.tau_dan_ms)), bool(plasticity.learn),
        )
    else:
        empty_i = np.full(n, -1, dtype=np.int64)
        args = (False, empty_i, empty_i, np.zeros(0, dtype=np.int64), np.zeros((0, 0)), np.zeros((0, 0)), 0.0, 0.0, 1.0, 1.0, False)
    n_kc = km.shape[0] if plasticity is not None else 0
    n_dan = plasticity.dan_idx.size if plasticity is not None else 0
    bgp = np.ascontiguousarray(bg_prob, dtype=float) if bg_weight else np.zeros(n)
    state = _init_state(n, delay, params.v0_mv, n_kc, n_dan, bgp, int(seed) % (2**32))
    counts = np.zeros(n, dtype=np.int64)
    late = np.zeros(n, dtype=np.int64)
    per_bin = np.zeros((steps + bin_steps - 1) // bin_steps, dtype=np.int64)
    _run_kernel(
        0, steps, delay, refractory, decay_g, k_mbr, params.v0_mv, params.v_th_mv,
        w.indptr.astype(np.int64), w.indices.astype(np.int64), w.data.astype(float),
        cat(neurons, np.int64), cat(probs, float), cat(weights, float), cat(starts, np.int64), cat(stops, np.int64),
        bgp, float(bg_weight), late_step, bin_steps, *args, *state, counts, late, per_bin,
    )
    if plasticity is not None:
        plasticity.km[...] = km
    return RunResult(
        duration_ms=duration_ms, spike_counts=counts, spikes_per_bin=per_bin, bin_ms=bin_ms,
        late_counts=late if want_late else None,
    )


def simulate(
    network: BrainNetwork,
    duration_ms: float,
    poisson_inputs: Mapping[int, float] | None = None,
    stim_window_ms: tuple[float, float] | None = None,
    params: BrainParams = BrainParams(),
    seed: int = 0,
    bin_ms: float = 10.0,
    late_from_ms: float | None = None,
    plasticity: Plasticity | None = None,
    extra_inputs: Sequence[tuple[Mapping[int, float], tuple[float, float]]] = (),
    background_hz: float | np.ndarray = 0.0,
    background_weight_mv: float = 0.0,
    engine: str = "auto",
) -> RunResult:
    """Run the network.

    ``poisson_inputs`` maps neuron index -> rate (Hz) inside ``stim_window_ms``;
    ``extra_inputs`` adds more (rates, window) stimuli.  ``background_hz`` gives
    every neuron an independent Poisson input of ``background_weight_mv``
    (spontaneous synaptic noise; without it silent neurons cannot show
    decreases, the known Shiu-model limitation).  It may be a per-neuron array.

    ``engine``: "numba" (compiled kernel), "numpy" (reference loop) or "auto"
    (numba when installed).  Engines differ only in their random streams.
    """
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
    extras = [
        (
            np.array(sorted(rates), dtype=np.int64),
            np.array([rates[i] for i in sorted(rates)]) * params.dt_ms / 1000.0,
            window,
        )
        for rates, window in extra_inputs
    ]
    bg_prob = np.broadcast_to(np.asarray(background_hz, dtype=float), (n,)) * params.dt_ms / 1000.0
    bg_on = bool(np.any(bg_prob > 0.0)) and background_weight_mv != 0.0
    if plasticity is not None:
        if plasticity.km is None:
            raise ValueError("call plasticity.attach(network) first")
        kc_local = np.full(n, -1, dtype=np.int64)
        kc_local[plasticity.kc_idx] = np.arange(plasticity.kc_idx.size)
        dan_local = np.full(n, -1, dtype=np.int64)
        dan_local[plasticity.dan_idx] = np.arange(plasticity.dan_idx.size)
        kc_tr = np.zeros(plasticity.kc_idx.size)
        dan_tr = np.zeros(plasticity.dan_idx.size)
        kc_decay = np.exp(-params.dt_ms / plasticity.tau_kc_ms)
        dan_decay = np.exp(-params.dt_ms / plasticity.tau_dan_ms)

    if engine == "auto":
        engine = "numba" if _HAVE_NUMBA else "numpy"
    if engine == "numba":
        return _simulate_numba(
            network, duration_ms, steps, delay, refractory, decay_g, k_mbr, params, seed,
            stim_idx, stim_p, start, stop, extras, bg_prob, background_weight_mv if bg_on else 0.0,
            late_step, bin_steps, bin_ms, late is not None, plasticity,
        )
    if engine != "numpy":
        raise ValueError(f"unknown engine {engine!r}")

    for step in range(steps):
        slot = step % delay
        g += ring[slot]
        ring[slot] = 0.0
        t = step * params.dt_ms
        if stim_idx.size and start <= t < stop:
            hits = stim_idx[rng.random(stim_idx.size) < stim_p]
            g[hits] += params.poisson_weight_mv
        if bg_on:
            g[rng.random(n) < bg_prob] += background_weight_mv
        for idx, prob, (e_start, e_stop) in extras:
            if e_start <= t < e_stop:
                g[idx[rng.random(idx.size) < prob]] += params.poisson_weight_mv

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
            if plasticity is not None:
                kc_fired = kc_local[fired]
                kc_fired = kc_fired[kc_fired >= 0]
                if kc_fired.size:
                    ring[(step + delay) % delay][plasticity.mbon_idx] += plasticity.km[kc_fired].sum(axis=0)
                    kc_tr[kc_fired] += 1.0
                dan_fired = dan_local[fired]
                dan_tr[dan_fired[dan_fired >= 0]] += 1.0
        if plasticity is not None:
            if plasticity.learn and kc_tr.any() and dan_tr.max() > plasticity.da_threshold:
                da = np.maximum(dan_tr - plasticity.da_threshold, 0.0) @ plasticity.modulation
                plasticity.km *= np.clip(1.0 - plasticity.eta * params.dt_ms * np.outer(kc_tr, da), 0.0, 1.0)
            kc_tr *= kc_decay
            dan_tr *= dan_decay
    return RunResult(
        duration_ms=duration_ms, spike_counts=counts, spikes_per_bin=per_bin, bin_ms=bin_ms, late_counts=late
    )


class BrainStepper:
    """Advance the brain in chunks, with inputs that may change between chunks.

    For closed-loop co-simulation with a body: each ``advance`` runs
    ``duration_ms`` with the given Poisson rates (Hz per neuron index) and
    returns the spike counts of that chunk.  State (membranes, conductances,
    delay buffer, background schedule, plastic weights) carries over.
    Requires the numba engine.
    """

    def __init__(
        self,
        network: BrainNetwork,
        params: BrainParams = BrainParams(),
        seed: int = 0,
        background_hz: float | np.ndarray = 0.0,
        background_weight_mv: float = 0.0,
        plasticity: Plasticity | None = None,
    ) -> None:
        if not _HAVE_NUMBA:
            raise RuntimeError("BrainStepper requires numba")
        self.network, self.params, self.plasticity = network, params, plasticity
        n = self.n = len(network.skids)
        self.delay = max(1, int(round(params.t_dly_ms / params.dt_ms)))
        self.refractory = int(round(params.t_rfc_ms / params.dt_ms))
        self.decay_g = float(np.exp(-params.dt_ms / params.tau_ms))
        self.k_mbr = params.dt_ms / params.t_mbr_ms
        w = network.weights.tocsr()
        self.csr = (w.indptr.astype(np.int64), w.indices.astype(np.int64), w.data.astype(float))
        bg = np.broadcast_to(np.asarray(background_hz, dtype=float), (n,)) * params.dt_ms / 1000.0
        self.bg_weight = float(background_weight_mv) if np.any(bg > 0) and background_weight_mv else 0.0
        self.bg_prob = np.ascontiguousarray(bg) if self.bg_weight else np.zeros(n)
        if plasticity is not None:
            if plasticity.km is None:
                raise ValueError("call plasticity.attach(network) first")
            kc_local = np.full(n, -1, dtype=np.int64)
            kc_local[plasticity.kc_idx] = np.arange(plasticity.kc_idx.size)
            dan_local = np.full(n, -1, dtype=np.int64)
            dan_local[plasticity.dan_idx] = np.arange(plasticity.dan_idx.size)
            self.km = np.ascontiguousarray(plasticity.km, dtype=float)
            dt = params.dt_ms
            self._plastic_static = (
                True, kc_local, dan_local, np.asarray(plasticity.mbon_idx, dtype=np.int64), self.km,
                np.ascontiguousarray(plasticity.modulation, dtype=float), plasticity.eta * dt,
                float(plasticity.da_threshold), float(np.exp(-dt / plasticity.tau_kc_ms)),
                float(np.exp(-dt / plasticity.tau_dan_ms)),
            )
            n_kc, n_dan = self.km.shape[0], plasticity.dan_idx.size
        else:
            empty = np.full(n, -1, dtype=np.int64)
            self.km = np.zeros((0, 0))
            self._plastic_static = (False, empty, empty, np.zeros(0, dtype=np.int64), self.km, np.zeros((0, 0)), 0.0, 0.0, 1.0, 1.0)
            n_kc = n_dan = 0
        self.state = _init_state(n, self.delay, params.v0_mv, n_kc, n_dan, self.bg_prob, int(seed) % (2**32))
        self.step = 0
        self.total_counts = np.zeros(n, dtype=np.int64)

    def advance(self, duration_ms: float, rates_hz: Mapping[int, float] | None = None) -> np.ndarray:
        steps = int(round(duration_ms / self.params.dt_ms))
        idx = np.array(sorted(rates_hz or {}), dtype=np.int64)
        prob = np.array([rates_hz[i] for i in idx], dtype=float) * self.params.dt_ms / 1000.0 if idx.size else np.zeros(0)
        start = np.full(idx.size, self.step, dtype=np.int64)
        stop = np.full(idx.size, self.step + steps, dtype=np.int64)
        weight = np.full(idx.size, self.params.poisson_weight_mv)
        counts = np.zeros(self.n, dtype=np.int64)
        late = np.zeros(self.n, dtype=np.int64)
        per_bin = np.zeros(0, dtype=np.int64)
        learn = bool(self.plasticity.learn) if self.plasticity is not None else False
        _run_kernel(
            self.step, self.step + steps, self.delay, self.refractory, self.decay_g, self.k_mbr,
            self.params.v0_mv, self.params.v_th_mv, *self.csr, idx, prob, weight, start, stop,
            self.bg_prob, self.bg_weight, np.iinfo(np.int64).max, 1, *self._plastic_static, learn,
            *self.state, counts, late, per_bin,
        )
        self.step += steps
        self.total_counts += counts
        if self.plasticity is not None:
            self.plasticity.km[...] = self.km
        return counts
