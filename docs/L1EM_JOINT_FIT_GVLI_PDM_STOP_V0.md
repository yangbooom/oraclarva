# Joint motor + learning fit, GVLI, and the PDM-DN stop pathway (v0)

Follows `L1EM_DESCENDING_TARGETS_AND_SPONTANEOUS_CRAWL_V0.md` ("Next" items 1-3).
All numbers are on held-out sign seeds 100-109 unless marked "train".
Every body parameter was chosen on train seeds 0-3 only. Data, fits and run
outputs stay in git-ignored `data/local/`.

## 1. Joint fit v4: freeze the learning block, fit the descending side

### Why v3b lost learning

The motor-only refit v3b moved the learning block far from v2:
- MBIN (DAN) scale fell from 1.06 to 0.06;
- KC scale fell from 0.97 to 0.44.

So the fit met the motor targets by silencing the dopaminergic teaching signal.

### What v4 changes

v4 starts from v2 and freezes two things:
- the class scales of sensory, PN, KC, MBON, MBIN and MB_FB_FF;
- the 30 v2 free signs.

It fits everything else: the LN, LHN, CN, RGN, dSEZ, dVNC and "other" scales, the inhibitory gain, and the 40 new MDN-input and touch-path signs. The targets are the same as v3c (motor targets plus the MBON odor readout). Run with 60 generations (`--freeze-classes`, `--freeze-init-signs`).

### Conditioning results

Paired / unpaired / fictive-punishment learning index (LI):

| fit | paired | unpaired | fictive punishment |
|---|---|---|---|
| v2 | +0.86 | — | -1.26 |
| v3b | -0.01 | 0.00 | -0.08 |
| v3c | +0.02 (5/10) | -0.11 | -0.70 (10/10) |
| **v4** | **+1.30 (10/10 positive)** | +0.01 | -0.62 (7/10 negative) |

### Brain targets

| measure | v4 train | v4 held out |
|---|---|---|
| touch -> MDN evoked | median 5.5 Hz | median 2.8 Hz (5/10 >= 4 Hz; 4/10 <= 1 Hz) |
| MBON odor evoked | 2.2-7.2 Hz | 1.4-4.5 Hz |
| self-sustained activity | 0/8 | 2/10 |

**v4 restores sugar learning, but touch -> MDN generalizes worse than v3b.** v3b's held-out median was 5.2 Hz.

## 2. Stride length: the cause was the bridge calibration, not refractoriness

### What actually shortened the strides

The v4 brain's forward-initiation DNs fire about twice as fast as v3b's. At the forward bridge current chosen for v3b (2e-10 A per spike):
- A27h:A6 fired 56-102 times per 30 s;
- only 6 waves completed;
- the repeated A6 contraction held the tail and shortened every stride.

The fix was to re-select the forward current on train seeds:

| forward current (train, v4) | speed µm/s | waves / 30 s | untraced frames |
|---|---|---|---|
| 2e-10 | 11.5 | 6.0 | up to 670 |
| 1.4e-10 | 12.5 | 6.0 | up to 1251 |
| **1e-10** | **17.7** | 5.5 | **0** |
| 7e-11 | 0 (no wave starts) | 0 | 0 |

### GVLI implementation

GVLI is implemented, but it is off by default.

The source is Itakura et al. 2015 (PLoS One, L3 imaging):
- GVLIs "are activated when the front of a forward motor wave reaches the second or third anterior segment";
- they "most likely ... directly inhibit motoneurons in the same neuromere";
- optogenetic activation "ceased ongoing peristalsis".

In this model:
- `inhibitory:GVLI:{A6..A3}` receives A27h from the segments 2 and 3 anterior. That input identity is a MODEL_HYPOTHESIS.
- It inhibits its own segment's motor neurons through a decaying gate. The gate time constant is fitted, not measured.
- With the model's tonic current, inhibition must stay at or below about 3e-10 A. At 4e-9 A, a gate that has decayed to 0.17 still blocks the next legitimate wave.

### GVLI results

- With forward 2e-10, GVLI made crawling worse: speed fell from 11.5 to 8.7 µm/s at 2e-10 A, τ = 1 s.
- With forward 1e-10, GVLI changed nothing, because there were no extra starts left to block.

It is kept as an identified-circuit option and not used below.

## 3. Odor decrease -> PDM-DN -> stop

### What the literature says

Tastekin et al. 2018 (eLife, behaviour in L3; EM in the L1 CNS) report:
- **Upstream (EM):** "PDM-DN receives input from the Or42a and Or42b projection neurons (PNs) via two local interneurons located in the lateral horn (LH-LN1 and LH-LN2), which form a feedforward motif". They add: "The signs of the interactions of the feedforward motif are unknown."
- **Downstream:** "PDM-DN blocks forward peristalsis by activating an inhibitory descending neuron in the SEZ, SEZ-DN1". SEZ-DN1 (GABA) connects to A27h, and these connections "are restricted to the posterior segments". Both neurons stop crawling "by inhibiting the initiation of new peristaltic waves at the posterior segments".
- **Stimulation:** activation stops crawling for about 3 s, then a head cast follows.
- **Not measured:** PDM-DN's own odor response was not imaged. "Odor decrease -> PDM-DN" is inferred from behaviour: silencing PDM-DN reduces turns on negative gradients.

Schulze et al. 2015 (eLife, L3 ORN recordings) add:
- larval ORNs are differentiators;
- "At the end of the falling phase, OSN activity decreased below baseline".

### 3a. Brain side: no OFF response (negative)

**ORN model.** `OrnTransducer` (in `brain_body.py`) is a sensory transduction model, not a brain or motor rule:
- an adapting drive d = F - β·A, with dA/dt = (F - A)/τ;
- extra Poisson input while d > 0;
- while d < 0, ORN background input is scaled down, which produces offset inhibition;
- τ, β and the inhibition scale are MODEL_ASSUMPTION values.

**Probe.** `tools/probe_brain_odor_offset.py` drives both sides' appetitive ORNs from 3 to 6 s, then drops the odor to 0. Each result is the change after the drop, corrected against a no-odor run.

| fit | PDM-DN onset | PDM-DN after drop | seeds with rise > 1 Hz |
|---|---|---|---|
| v4, plain stimulus | +4.75 Hz | -2.75 Hz | 0/10 |
| v4, ORN transducer | +3.25 | -0.5 | 1/10 |
| v5, transducer | +0.25 | 0.0 | 1/10 |

**v5 fit.** v5 adds a PDM-DN target and 20 free signs on ORN -> PDM-DN paths:
- The target: appetitive odor lowers PDM-DN by at least 1 Hz. This is a functional requirement, not a measured response.
- The top path neurons include LH-LN2 left/right and "LH bilateral axon 3" (likely LH-LN1).
- Result: v5 removed the wrong-signed ON response of v4, but **there is still no OFF response**.

**Root cause, from the probe.** The model's appetitive ORNs fire 0.36 Hz at rest, so offset inhibition (0.36 -> 0.12 Hz) carries almost no signal. Larval ORNs do fire spontaneously, but I have not verified a rate to use. Until that is sourced, the OFF signal cannot reach PDM-DN.

### 3b. Body side: the PDM-DN -> SEZ-DN1 relay stops crawling

**Relay.** `descending:SEZ-DN1` is a reduced relay:
- it receives brain PDM-DN spikes, excitatory, because PDM-DN is cholinergic;
- it inhibits `premotor:A27h:A6` and `premotor:A27h:A5`. Treating these as "the posterior segments" is an assumption.
- SEZ-DN1 is not part of the Winding brain neuron set, so it lives in the reduced VNC circuit.

**Relay current.** The PDM-DN -> relay current is 9e-10 A, so two coincident PDM-DN spikes are needed. It was chosen on train seeds: 1.8e-9 A (one spike) also fired on resting PDM-DN activity and cut spontaneous speed from 17.7 to 11.6 µm/s.

**Test condition.** The test is the analogue of Tastekin's CsChrimson activation: Poisson input to the two brain PDM-DNs at 100 Hz for 5 s from t = 15 s. There is no odor and no body rule.

Held out, v4, forward 1e-10, MDN 1.5e-10, SEZ relay 9e-10, 30 s per run:

| condition | net forward | speed µm/s (median) | period s | backward waves | untraced frames |
|---|---|---|---|---|---|
| spontaneous | **10/10** | **16.5** | 5.09 | 0 | 0 |
| PDM-DN activation 15-20 s | 10/10 | 12.9 | 5.10 | 0 | 0 |
| forward bridge cut | 0/10 | 0 | — | 0 | 0 |
| head touch (via brain) | 10/10 | 16.2 | 5.08 | 0 | 0 |
| L1 reference (Greaney, held out) | — | 25.7-38.2 | 4.10-5.38 | — | — |

**Stop readout.** This counts forward waves that reached A5 during the 5 s window:

| | runs with >= 1 wave in the window | mean waves |
|---|---|---|
| spontaneous | 9/10 | 0.9 |
| PDM-DN activation | **0/10** | **0.0** |

- The difference holds in 9/9 discordant seed pairs (exact sign test, two-sided p = 0.004).
- Whether crawling resumes after the stimulus ends was not measured.

**v4 compared with the previous release (v3b, forward 2e-10).**
- Spontaneous forward crawling: 8/10 -> 10/10.
- Speed: 12.3 -> 16.5 µm/s. This is still below the L1 range.
- Wave period: stays inside the L1 range.
- Untraced frames: up to 5 -> 0.
- **Head touch still never produces backing up (0/10).** v4's held-out MDN response is too weak.

## Status against the plan

1. Joint fit: **learning restored** (v4). The cost is weaker held-out touch -> MDN.
2. Stride: held-out speed 12.3 -> 16.5 µm/s and 10/10 forward, from re-calibrating the bridge on train seeds. Still below L1 (25.7-38.2). Identified GVLI inhibition is implemented but did not help.
3. Temporal odor coding: **the brain does not produce the OFF response** (negative, with root cause). The downstream PDM-DN -> SEZ-DN1 -> posterior A27h stop works. Head casts are not built yet, so M4 is still not attempted.

## Next

- Source larval ORN spontaneous rates and the Schulze IFF parameters, then re-run the OFF probe.
- Head-cast mechanics. PDM-DN activation produced "a delayed increase in the average head-angle speed peaking at ~3 s".
- A joint fit that keeps v3b-level touch -> MDN without unfreezing the learning block. For example, free the sensory scale only for mechanosensory classes.

## Commands

```text
R=data/local/l1em_public_connectome/runs
.venv/bin/python tools/fit_l1em_celltype_scales.py --generations 60 --free-signs 30 \
  --free-mdn-input-signs 20 --free-touch-path-signs 20 --motor-targets \
  --init $R/celltype_sign_fit_v2.json --freeze-classes sensory,PN,KC,MBON,MBIN,MB_FB_FF \
  --freeze-init-signs --reward-contrast --bg-hz 100 --bg-mv 6 --out $R/celltype_joint_fit_v4.json
.venv/bin/python tools/run_l1em_conditioning.py --fit $R/celltype_joint_fit_v4.json --out $R/conditioning_v4.json
.venv/bin/python tools/probe_brain_odor_offset.py --fit $R/celltype_joint_fit_v4.json --transducer \
  --out $R/odor_offset_probe_v4_transducer.json
.venv/bin/python tools/run_brain_body_crawl.py --fit $R/celltype_joint_fit_v4.json --seeds 100 ... 109 \
  --conditions spontaneous pdm_activation forward_cut head_touch --forward-current-a 1e-10 \
  --mdn-current-a 1.5e-10 --sez-current-a 9e-10 --out $R/brain_body_crawl_v1.json
```

Follow-up: `L1_SCORECARD_AND_CONNECTOME_SPECIFICITY_V0.md` (shuffle test of v4, speed-gap breakdown, scorecard).
