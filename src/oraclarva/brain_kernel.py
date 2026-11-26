"""Compiled (numba) inner loop for ``brain_sim.simulate``.

Same dynamics as the numpy reference loop: Shiu LIF, g frozen while
refractory, delay ring buffer, Poisson inputs, background input and the
dopamine-gated KC->MBON rule.  Only the random-number stream differs, so runs
are statistically, not bitwise, equivalent to the reference engine.
"""

from __future__ import annotations

import numpy as np
from numba import njit


@njit(cache=True)
def init_state(n, delay, v0, n_kc, n_dan, bg_prob, seed):
    """Fresh state; seeds the (process-global) numba RNG."""
    np.random.seed(seed)
    # Background Bernoulli(p) input per step is generated exactly via
    # geometric inter-event gaps, so no random draw is needed on quiet steps.
    bg_next = np.full(n, np.iinfo(np.int64).max, dtype=np.int64)
    for i in range(n):
        if bg_prob[i] > 0.0:
            bg_next[i] = np.random.geometric(min(bg_prob[i], 1.0)) - 1
    return (
        np.full(n, v0), np.zeros(n), np.zeros(n, dtype=np.int32), np.zeros((delay, n)), bg_next,
        np.zeros(n_kc), np.zeros(n_dan),
    )


@njit(cache=True)
def run_kernel(
    step0, step1, delay, refractory, decay_g, k_mbr, v0, v_th,
    indptr, indices, data,
    stim_neuron, stim_prob, stim_weight, stim_start, stim_stop,
    bg_prob, bg_weight,
    late_step, bin_steps,
    plastic, kc_local, dan_local, mbon_idx, km, modulation,
    eta_dt, da_threshold, kc_decay, dan_decay, learn,
    v, g, ref, ring, bg_next, kc_tr, dan_tr, counts, late, per_bin,
):
    """Advance the state (modified in place) from absolute step0 to step1."""
    n = indptr.size - 1
    n_kc = km.shape[0]
    n_mb = km.shape[1]
    n_dan = modulation.shape[0]
    fired = np.empty(n, dtype=np.int64)

    for step in range(step0, step1):
        slot = step % delay
        for s in range(stim_neuron.size):
            if stim_start[s] <= step < stim_stop[s]:
                if np.random.random() < stim_prob[s]:
                    g[stim_neuron[s]] += stim_weight[s]
        nf = 0
        for i in range(n):
            g[i] += ring[slot, i]
            ring[slot, i] = 0.0
            if bg_next[i] <= step:
                g[i] += bg_weight
                bg_next[i] = step + np.random.geometric(min(bg_prob[i], 1.0))
            if ref[i] == 0:
                v[i] += k_mbr * (v0 - v[i] + g[i])
                g[i] *= decay_g
                if v[i] >= v_th:
                    v[i] = v0
                    g[i] = 0.0
                    ref[i] = refractory
                    fired[nf] = i
                    nf += 1
            else:
                ref[i] -= 1
        if nf:
            if per_bin.size:
                per_bin[min(step // bin_steps, per_bin.size - 1)] += nf
            for f in range(nf):
                j = fired[f]
                counts[j] += 1
                if step >= late_step:
                    late[j] += 1
                for k in range(indptr[j], indptr[j + 1]):
                    ring[slot, indices[k]] += data[k]
                if plastic:
                    kc = kc_local[j]
                    if kc >= 0:
                        for m in range(n_mb):
                            ring[slot, mbon_idx[m]] += km[kc, m]
                        kc_tr[kc] += 1.0
                    d = dan_local[j]
                    if d >= 0:
                        dan_tr[d] += 1.0
        if plastic:
            if learn:
                any_da = False
                for d in range(n_dan):
                    if dan_tr[d] > da_threshold:
                        any_da = True
                        break
                if any_da:
                    da = np.zeros(n_mb)
                    for d in range(n_dan):
                        e = dan_tr[d] - da_threshold
                        if e > 0.0:
                            for m in range(n_mb):
                                da[m] += e * modulation[d, m]
                    for kc in range(n_kc):
                        if kc_tr[kc] > 1e-12:
                            for m in range(n_mb):
                                f = 1.0 - eta_dt * kc_tr[kc] * da[m]
                                if f < 0.0:
                                    f = 0.0
                                km[kc, m] *= f
            for kc in range(n_kc):
                kc_tr[kc] *= kc_decay
            for d in range(n_dan):
                dan_tr[d] *= dan_decay
