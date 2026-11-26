# L1EM null-model control, robustness, fast engine and first brain-body bridge v0

Follow-up to `docs/L1EM_CONDITIONING_V0.md`. North star: a connectome-driven
L1 model that **moves naturally**. Brain-only results are intermediate. They
count once body behavior matches L1 data.

All data, fitted parameters and run outputs stay in git-ignored
`data/local/l1em_public_connectome/runs/` (subfolders `null/` and
`sensitivity/`). Only methods and aggregate numbers are committed.

## 1. Fast engine (numba)

`brain_sim.simulate(..., engine="auto")` now uses a compiled kernel
(`src/oraclarva/brain_kernel.py`) when numba is installed. It is part of the
optional `.[data]` extra. The numpy loop stays as the reference.

| 3,066-neuron brain, 1 s, odor + spontaneous input | wall time |
|---|---:|
| numpy reference | 0.65 s |
| numba | 0.057 s (11x) |

The dynamics are the same: Shiu LIF, g frozen while refractory, 1.8 ms delay
ring, Poisson input, and the dopamine-gated KC->MBON rule. The background
Bernoulli input is drawn exactly through geometric inter-event gaps. Only the
random stream differs, so runs are statistically equivalent, not bitwise
identical:

- per-neuron rates correlate at r = 0.998;
- total spikes do not differ (stimulus only: p = 0.55; background only:
  p = 0.31; 20-60 runs each);
- the v2 conditioning result reproduces under numba: paired LI +0.86 (10/10),
  where the numpy run gave +0.94.

`BrainStepper` advances the same state in chunks, for closed-loop
co-simulation with a body.

## 2. Null model: is it the connectome?

`brain_sim.shuffle_targets` permutes postsynaptic targets among edges. Every
neuron keeps its out-degree, its total output contacts and its in-degree.

- **Block** shuffle: permutation only inside (presynaptic class, postsynaptic
  class) blocks, using the 13 Winding classes of the fit. This also preserves
  the class-to-class contact matrix: ORN->PN, PN->KC, DAN->MBON and so on keep
  their totals, and only *which* member is wired to which changes. This is the
  strict test of the claim.
- **Full** shuffle: degree-preserving only.

Every network, intact included, was fitted with the same protocol:

- start from v2;
- 35 CMA-ES generations with the same loss;
- the same 30 free signs.

Conditioning then used the default parameters, plus a train-seed (0-3)
reselection grid.

| network | held-out fit: all targets met | paired LI (>0) | paired vs unpaired p | fictive punishment LI (<0) |
|---|---:|---:|---:|---:|
| intact (refit) | **8 / 10** | +0.26 (6/10) | 0.19 | **-0.60 (10/10), p 0.002** |
| block shuffle 1 | 2 / 10 | -0.09 (4/10) | 0.70 | -0.01 (5/10) |
| block shuffle 2 | 0 / 10 | -0.15 (2/10) | 0.06 | +0.12 (2/10) |
| block shuffle 3 | 0 / 10 | -0.05 (2/10) | 0.08 | -0.08 (9/10) |
| full shuffle | 0 / 10 | +0.00 (6/10) | 0.38 | +0.02 (2/10) |

Best paired-minus-unpaired LI on the train-seed selection grid: intact +0.45;
shuffles <= +0.07.

What this shows:

- With class-to-class totals preserved, the shuffled wiring can no longer meet
  the physiological targets. Typically KCs stop responding ipsilaterally.
- The DAN-specific memory of fictive DL1 punishment needs the measured wiring.
- Appetitive memory also vanishes in every shuffle.

What it does not show:

- The appetitive effect is **not fixed by the fit targets**. The intact refit
  fits better than v2 (held out 8/10 against 7/10) but learns weakly (+0.26,
  not significant against unpaired), while v2 gives +0.86. Equally good fits
  can differ in learning strength. Three shuffles is a small null sample.

## 3. Robustness of the v2 result

Each row changes one assumption. Held-out sign seeds 100-109, n = 10.

| change | paired LI (>0) | paired vs unpaired p | fictive punishment (<0) |
|---|---:|---:|---:|
| none (v2, numba) | +0.86 (10/10) | 0.004 | -1.26 (10/10) |
| eta 5e-4 (4x lower) | +0.63 (10/10) | 0.004 | -1.23 (10/10) |
| p_excitatory 0.5 | +0.37 (10/10) | 0.004 | -0.98 (10/10) |
| p_excitatory 0.9 | +0.13 (7/10) | 0.70 | -0.47 (9/10) |
| odor pair 1a/45a/49a vs 59a/83a/30a | +0.14 (9/10) | 0.012 | -0.61 (10/10) |
| odor pair 13a/33a/35a vs 47a/63a/82a | +0.12 (8/10) | 0.027 | -0.73 (10/10) |
| spontaneous input 150 Hz | +0.26 (8/10) | 0.027 | -0.03 (6/10) |
| spontaneous input 50 Hz | +0.01 (5/10) | 1.0 | -0.18 (10/10) |

- Direction and significance hold for learning rate, a lower excitatory
  fraction and two new odor pairs. The effect is 6-7x smaller on the new odors.
- The result breaks when spontaneous input moves away from the fitted 100 Hz:
  at 50 Hz there is no appetitive learning, and at 150 Hz the punishment memory
  is lost. It also breaks with mostly excitatory unknown signs (0.9).
- Spontaneous input is therefore a load-bearing assumption, not a detail. It
  should become measured or body-generated input; see section 5.

## 4. First brain -> body bridge (M1 groundwork)

`tools/run_brain_body_bridge.py` co-simulates the fitted 3,066-neuron brain
(0.1 ms steps) with the existing axial locomotion body (1 ms steps;
`docs/AXIAL_LOCOMOTION_V1.md`).

- **Identity mapping:** the spikes of the four identified L1EM MDNs (MDNa/b
  left/right) arrive as excitatory synaptic current on the reduced circuit's
  `descending:MDN` node. This is the only bridge node (`BRAIN_BRIDGE_NODES`).
- **What the body receives:** no touch is applied, and no direction or target
  is sent to the body. Movement comes from MDN -> Pair1/A18b -> motor neurons ->
  fibers -> contact physics.
- **Bridge current:** 0.2 nA per brain MDN spike (`MODEL_FITTED`). It was
  chosen so that baseline MDN firing (about 1-2 Hz per neuron) does not trigger
  backward crawling. At 1 nA the resting brain made the body crawl backward.

5.5 s runs on 5 held-out sign seeds:

| condition | brain MDN spikes | axial MDN spikes | displacement | backward runs |
|---|---:|---:|---:|---:|
| spontaneous brain only | 23 | 0 | 0 um | 0 / 5 |
| top-8 MDN presynaptic neurons at 150 Hz, 1 s | 362 | 61 | **-175 um** | 5 / 5 |
| fictive MDN (positive control) | 467 | 82 | -176 um | 5 / 5 |
| upstream stimulus, bridge cut | 362 | 0 | 0 um | 0 / 5 |

Provenance audit: under sustained brain MDN drive, the reduced circuit's
causal-trace bookkeeping loses some origins. `untraced_active_force_frames` is
now reported, not hidden:

- upstream condition: at most 38 of 5,500 frames;
- fictive MDN: up to 4,933 frames.

The forces are still produced by motor-neuron spikes. It is the
origin-matching window, built for single touch events, that breaks.

Key findings for the north star:

- In the fitted brain, MDNs barely respond to any natural sensory class. The
  best gain was about +8 Hz, from mouthpart/maxillary (MN) sensory input in one
  seed; descending neurons as a whole changed by about +1 Hz.
- No fit target has constrained descending output so far, and all MDN inputs
  have unknown signs. So the bridge works, but the brain does not yet *decide*
  to move.

## 5. Next (toward natural movement)

1. **Descending-output targets.** Add L1-supported qualitative motor targets
   to the brain fit, with sources checked:
   - anterior touch -> MDN -> backward;
   - noxious input -> escape-related descending neurons;
   - odor -> turning-related descending neurons.

   Without them the brain cannot drive behavior.
2. **Spontaneous forward crawling from neurons.** Forward waves currently need
   a posterior touch. Generate them from VNC neurons plus proprioceptive
   feedback; the public A1 VNC has 62 MNs plus premotor and proprioceptive
   neurons. Replace the uniform spontaneous input with body-generated sensory
   input where possible. Section 3 shows this assumption matters.
3. Then M3 (odor navigation) and M4 (learned odor preference as navigation),
   with the shuffled networks as standing controls.

## Commands

```text
.venv/bin/python tools/fit_l1em_celltype_scales.py --generations 35 --free-signs 30 \
  --init data/local/l1em_public_connectome/runs/celltype_sign_fit_v2.json \
  --reward-contrast --bg-hz 100 --bg-mv 6 [--shuffle block:1] --out ...      # ~3 min
.venv/bin/python tools/run_l1em_conditioning.py --fit ... [--p-exc 0.5] [--odor-a ...] [--bg-hz 50]  # ~1 min
.venv/bin/python tools/run_brain_body_bridge.py --fit data/local/l1em_public_connectome/runs/celltype_sign_fit_v2.json  # ~2 min
```
