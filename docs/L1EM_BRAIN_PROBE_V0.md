# L1EM whole-brain probe v0

First runs of the 3,066 Winding 2023 brain neurons as one spiking network.

```text
.venv/bin/python -m pip install -e ".[data]"        # numpy + scipy (optional extra)
.venv/bin/python tools/run_l1em_brain_probe.py       # ~3 min, outputs under data/local/
```

## Engine

`src/oraclarva/brain_sim.py` uses the Shiu et al. 2024 LIF with canonical
values: v0 -52 mV, threshold -45 mV, t_mbr 20 ms, tau 5 ms, refractory 2.2 ms,
delay 1.8 ms, dt 0.1 ms, Poisson input 68.75 mV. Weights are
`W = contacts x fast_sign(pre) x w_syn`. The dependency-free `oraclarva.lif`
reference is unchanged. One simulated second of the whole brain takes about
0.5 s on a laptop.

The 78% of neurons with unknown transmitter need an explicit `SignPolicy`:
`excitatory` (Shiu-style default), `silent` (only neurons with a known sign
transmit), or `sample` (+1 with probability p, seeded). Modulatory neurons
(DA/OA/5-HT) have no fast weight.

## Structural readiness for odor + sugar conditioning (edges >= 2 contacts)

| path | reached / targets | min hops | median hops |
|---|---:|---:|---:|
| ORN -> KC | 181 / 222 | 2 | 2 |
| sugar sensory -> DAN | 14 / 14 | 1 | 2 |
| KC -> MBON | 48 / 48 | 1 | 1 |
| MBON -> dVNC | 182 / 182 | 1 | 2 |

The full conditioning loop (odor -> KC -> MBON -> descending, sugar -> DAN)
exists in the measured graph. The only direct sugar-to-DAN contacts are 10
contacts onto the MBE1d pair. Each DAN receives about 250-680 input contacts,
so the 4 annotated sugar neurons are a tiny fraction of DAN drive.

## Functional probe: 42 ORNs at 100 Hz for 500 ms, 1 s run

Across 11 sign policies (excitatory, silent, sample p = 0.6 / 0.7 / 0.85 with
3 seeds each), with one uniform `w_syn`:

| w_syn (mV) | regime |
|---|---|
| 0.275 (adult Shiu value) | activity stays in about 120 neurons near the ORNs; 0 KCs, 0 DANs |
| 0.5 - 0.7 | bounded in almost all policies; 3-15 of 222 KCs respond to appetitive odor; DANs barely respond to sugar |
| 0.7 - 0.9 | **transition**: runaway or bounded depends on the sampled unknown signs (seed) |
| >= 1.0 | runaway in every policy, including `silent`: activity continues after stimulus offset and rates saturate near the refractory limit (~430 Hz) |

## Conclusions

1. A single adult-calibrated `w_syn` does not transfer. The brain only
   propagates sensory input past the first layers near a sharp critical point,
   and that point depends on the unknown signs.
2. Even with the unknown neurons silenced, the network becomes self-sustaining
   at w_syn >= 0.9. The 103 annotated inhibitory neurons are not enough to
   balance it. Inhibition is likely under-annotated.
3. No uniform-weight setting yields stable propagation *and* a sugar -> DAN
   response. Reward-pathway function needs either the per-cell-type weight
   fitting planned in (a), or more reward inputs than the 4 annotated sugar
   neurons, or both.
4. In the bounded regime, appetitive odor activates about 3-7% of KCs. That
   sparse KC code is a plausible starting point for mushroom-body learning (c).

## Next

- Calibration targets from L1 literature (KC sparseness, DAN responses to
  sugar, PN rates) to replace the uniform `w_syn` with fitted cell-type scales.
- Per-edge-type (a-d / a-a / d-d / d-a) weights; this needs synapse-level data.
- Ensemble statistics near the transition to rank which unknown-sign neurons
  decide stability. Those are the first candidates for sign fitting.
