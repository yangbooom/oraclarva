# L1EM calibration targets, sign sensitivity and cell-type fit v0

Follow-up to `docs/L1EM_BRAIN_PROBE_V0.md`. The probe found that no single
uniform `w_syn` gives a brain that is both bounded and responsive to reward.

## 1. Calibration targets

| target | value used | source and stage | status |
|---|---|---|---|
| bounded network | no spikes 100-300 ms after a 500 ms stimulus ends | generic physiological requirement | hard target |
| KC laterality | contralateral KC fraction <= 0.5 x ipsilateral + 0.01 | Zimmerman et al. 2026 Sci Adv, late L1 (2 d AEL) GCaMP imaging: KC odor responses "almost entirely ipsilateral" | `zimmerman_2026_l1_kc_laterality`, L1, calibration |
| KC sparseness | 3-15% of ipsilateral KCs respond to appetitive odor | no larval fraction found; adult imaging reports about 7% | weak prior, adult-derived |
| sugar -> pPAM DAN | >= 50% of DAN-i1/j1/k1 (MBE1c/1d/1b) above 1 Hz, mean >= 5 Hz | Weber et al. 2023 eLife: pooled pPAM (R58E02) Ca2+ rises with 500 mM fructose | `weber_2023_larval_dan_taste`; the L1 stage is not verified verbatim, so the record is reference-only and the target is qualitative |
| max rate | <= 300 Hz | sanity bound; larval ORNs reach about 150 Hz in strong responses | sanity |

We found no larval PN firing-rate data. Adult PN rates (16-48 Hz) are not used.

## 2. Which unknown-sign neurons decide stability

```text
.venv/bin/python tools/run_l1em_sign_sensitivity.py     # ~80 s
```

Setup: w_syn 0.8 mV and p_excitatory 0.7, which is the critical regime from the
probe. 60 sign seeds, with the 42 ORNs driven at 100 Hz for 0-500 ms. 57% of
seeds run away, and the median reverberating core (neurons still firing after
600 ms) has 555 neurons. Each unknown-sign neuron is scored by the excitatory
contacts it sends into the core, summed over the runaway runs.

Causal check: in 15 runaway runs, force the top-K scored unknown neurons
inhibitory, then compare with forcing K random unknown excitatory neurons.

| K | runs stopped (top-K) | runs stopped (random K) |
|---:|---:|---:|
| 10 | 8 / 15 | 1 / 15 |
| 30 | 14 / 15 | 1 / 15 |
| 100 | 15 / 15 | 3 / 15 |
| 300 | 15 / 15 | 9 / 15 |

About 30 unknown-sign neurons decide stability. The top of the list includes
the "Mickey Mouse" pair, MBE24a left/right, MBE26 and several CP/DPM-lineage
interneurons. These are the first candidates for literature sign checks or sign
fitting. A naive association (P(runaway | sampled excitatory) vs
P(runaway | sampled inhibitory)) is nearly flat for the same neurons, which
shows why the core-drive score plus intervention is needed. Ranking: local
`runs/sign_sensitivity_v0.json`.

This does not show that these neurons are inhibitory in the animal. It only
shows that their sign matters most for the model.

## 3. CMA-ES fit of cell-type scales

```text
.venv/bin/python tools/fit_l1em_celltype_scales.py --generations 60   # ~10 min, 6 workers
```

Parameters (14, log-space): one weight scale per presynaptic Winding class
(sensory, PN, KC, MBON, MBIN, MB FB/FF, LN, LHN, CN, RGN, dSEZ, dVNC, other)
plus a gain on neurons with a known inhibitory sign. Weight per contact is
0.275 mV x scale x gain. Unknown signs are sampled at p 0.7. The loss averages
the targets above over sign seeds and adds a weak L2 pull (0.02) toward the
uniform 0.6 mV start. `src/oraclarva/cmaes.py` is a minimal numpy CMA-ES,
tested on sphere and ill-conditioned problems.

Train: left appetitive ORNs (6) at 150 Hz plus sugar neurons (4) at 150 Hz,
sign seeds 0-7. Held out: the mirrored right-side odor and unseen sign seeds
100-109.

| | train (8 seeds) | held out (10 seeds) |
|---|---:|---:|
| all targets met | 8 / 8 | 6 / 10 |
| self-sustained (runaway) | 0 / 8 | 1 / 10 |
| ipsilateral KC fraction | 0.11-0.15 | 0.07-0.10 |
| contralateral KC fraction | 0.00 | 0.00 |
| pPAM mean rate | 10-23 Hz | 8-117 Hz |
| max rate | 114-133 Hz | 119-231 Hz |

The failures on held-out seeds are 3 runs with only 2 of 6 pPAM above 1 Hz and
1 runaway run. Before regularization, an earlier fit with 3 train seeds reached
zero train loss but ran away on 2 of 5 held-out seeds, with extreme scales (KC
x0.15, CN x18, inhibitory gain x11). Widening the sign seeds and regularizing
removed those extremes.

Fitted scales (x 0.275 mV per contact; `MODEL_FITTED`):

| class | scale | class | scale |
|---|---:|---|---:|
| sensory | 13.06 | LHN | 2.12 |
| PN | 2.36 | CN | 3.89 |
| KC | 1.62 | RGN | 3.37 |
| MBON | 2.47 | dSEZ | 2.42 |
| MBIN | 1.68 | dVNC | 2.04 |
| MB FB/FF | 5.94 | other | 2.14 |
| LN | 3.18 | known-inhibitory gain | 1.31 |

Interpretation and limits:

- Sensory synapses need about 3.6 mV per contact to drive PNs from a few
  receptor neurons. The rest of the brain sits at about 0.45-1.6 mV per contact.
  Only the sensory scale is far from uniform.
- Generalization to unseen sign samples is 60% all-targets and 90% bounded.
  The remaining sensitivity comes from the unknown signs, and section 2 names
  the neurons responsible.
- The targets are few and mostly qualitative. The fit shows the connectome
  *can* satisfy them; it does not identify unique biological weights. The scales
  are not identifiable from these targets alone.
- Results and fitted parameters stay local
  (`data/local/l1em_public_connectome/runs/celltype_fit_v0.json`). The
  3-seed fit is kept as `celltype_fit_v0_3seeds.json`.

## Next

1. Fit or look up the signs of the ~30 stability-deciding neurons, then refit.
2. Add quantitative L1 targets as they are found (KC response fraction,
   DAN rates) and odors beyond the appetitive set.
3. With a bounded, reward-responsive brain in place, add DAN-gated KC->MBON
   plasticity (c) and test odor + sugar conditioning through the MBON output.
