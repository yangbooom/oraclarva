# Fit specificity, strict KC laterality, and GVLI gating of brain A6 drive (v0)

Follows `L1_SCORECARD_AND_CONNECTOME_SPECIFICITY_V0.md` and does its three "Next" steps:

1. Make the shuffle test part of every fit.
2. Tighten the fit targets so they separate intact from shuffled wiring.
3. Reduce the brain's extra A6 drive, then the body period.

Parameters were selected on train seeds 0-3. Reported numbers come from held-out sign seeds 100-109.

## 1. Shuffle control for every fit

`tools/run_shuffle_control.py` gives the intact network and the block shuffles (default 1-3) the same treatment:

1. The same fit, each network starting from its own fit. An existing fit can be used instead.
2. Learning parameters (DA threshold, eta) chosen on train seeds by paired minus unpaired LI, then run on held-out seeds.
3. The forward bridge current chosen on train seeds by mean displacement, then held-out spontaneous crawling and PDM-DN activation.

The tool writes `summary.json` under `data/local/.../runs/control/<tag>/`. For each criterion the summary records three things: whether intact passes, which shuffles pass, and `connectome_specific`. `connectome_specific` means intact passes and no shuffle does. A stage whose output already exists is skipped, so an interrupted run picks up where it stopped.

`tools/build_l1_scorecard.py --control <tag>` now builds both the model column and the shuffle column from one such run. It also computes the specificity column from the data instead of hard-coding it.

## 2. Strict KC laterality separates measured from shuffled wiring

L1 KC odor responses are "almost entirely ipsilateral" (Zimmerman 2026). The previous target allowed a contralateral fraction up to 0.5 × ipsilateral + 0.01. `--strict-laterality` tightens this to 0.2 × ipsilateral, with 10 times the weight. A seed passes if its contralateral KC fraction is at most 0.2 × its ipsilateral fraction.

The v4 fits were not trained on the strict target. On held-out seeds, intact passes it 10/10 and the shuffles pass 0/10.

An adversarial test refit each network under the v2 protocol with the strict target, so the shuffles were explicitly pushed to meet it:

| network | train loss | held-out loss | held-out seeds passing | ipsilateral KC fraction (median) | self-sustained |
|---|---:|---:|---:|---:|---:|
| intact | 0.05 | 0.05 | **10/10** | 0.088 (contra 0) | 0/10 |
| shuffle 1 | 1.00 | 1.75 | 4/10 | 0.009 (KCs nearly silent) | 1/10 |
| shuffle 2 | 0.70 | 19.63 | 0/10 | 0.035 (contra/ipsi 1.02) | 6/10 |
| shuffle 3 | 0.12 | 3.46 | 0/10 | 0.018 (contra/ipsi 0.83) | 1/10 |

The shuffles can fit the four train seeds but do not generalise to new seeds. The intact network does both. The KC laterality target is therefore the first physiological target that needs the measured wiring.

## 3. Brain A6 drive: GVLI gating fixes it; the body period does not move

### Diagnosis

The brain sends extra spikes to A27h:A6 while a wave is still travelling. Each extra spike restarts the wave, which shortens strides. A body-only replay put one extra A6 volley at phases 1.0-4.5 s after a clean start. A clean start reaches A1 twice in 12 s and moves 279.6 µm. Extra volleys cut this to 237.7 µm on average and 217.6 µm at worst.

GVLI interneurons (Itakura 2015) inhibit a segment's motor neurons while the wave is 2-3 segments anterior. With GVLI the replay keeps both waves and nearly all the displacement:

| GVLI current | gate tau | clean | with an extra volley (mean / min) |
|---|---:|---:|---:|
| 0 | - | 279.6 | 237.7 / 217.6 |
| 1e-9 A | 1.0 s | 279.4 | 276.0 / 259.0 |
| 2e-9 A | 1.0 s | 279.5 | 278.2 / 264.9 |
| 1e-9 A | 2.5 s | 144.0 | 142.3 / 126.2 (only one wave) |
| 4e-9 A | 1.0 s | -70.6 | -72.2 / -88.4 (breaks) |

A gate that is too long or too strong also suppresses the next real wave.

### Selection with the brain

The GVLI current, gate tau and forward current were swept on train seeds with the v4 brain. Forward 1e-10 A with GVLI 1e-9 A and tau 1.0-1.2 s was best (about 690 µm, 26.8 µm/s per cycle, no untraced frames). A larger forward current lost displacement and produced untraced frames.

The selected values are forward 1e-10 A, GVLI 1e-9 A and tau 1.2 s. These are the held-out v4 results:

| metric | v4 | v4 + GVLI | L1 (p10-p90) |
|---|---:|---:|---|
| cycle speed | 21.5 µm/s | **26.8 µm/s** | 25.7-38.2 |
| stride | 108.5 µm | **143.5 µm** | 129.8-159.7 |
| period | 5.09 s | 5.37 s | 4.10-5.38 |
| displacement (30 s) | 484 µm | 603 µm | |
| PDM-DN stop | 0 waves | 0 waves | stops |
| head touch backs up | 0/10 | 0/10 | backs up |

GVLI is a body pathway (VNC interneurons driven by the wave itself). It is a `run_brain_body_crawl.py` option (`--gvli-current-a`, `--gvli-tau-s`), not a body-config default. The frozen axial calibration and its tests are unchanged.

### Body period: negative result

With GVLI the cycle speed sits at the body ceiling. The remaining gap to the L1 median is the period, which is about 5.4 s against 4.8-5.0 s. The body's restart loop waits `forward_recovery_delay_s` (0.6 s) before the A1 recovery signal restarts A6. Shortening that delay breaks the Greaney calibration:

| recovery delay | calibration comparisons passed | shape gates |
|---:|---:|---|
| 0.6 s (current) | 29/29 | pass |
| 0.5 s | 28/29 | pass |
| 0.4 s | 26/29 | pass |
| 0.3 s and below | 24/29 | pass |
| 0.1 s | 24/29 | fail |

The failures are in stride and duty cycle. Calibration-cycle speed barely changes (26.4 to 26.8 µm/s). A shorter period needs a different mechanism, for example a faster intersegmental handoff or a shorter muscle phase, which would have to be re-checked against wave speed. The body config was left unchanged.

## 4. v5: v4 protocol + strict laterality + GVLI bridge, with the shuffle control

`run_shuffle_control.py --tag joint_v5_strict` ran this protocol:

- the v4 protocol (frozen sensory, PN, KC, MBON, MBIN and MB_FB_FF classes; frozen init signs; reward contrast; background input);
- `--strict-laterality`;
- each network starting from its strict v2-protocol fit above;
- the GVLI bridge (MDN 1.5e-10, SEZ-DN1 9e-10, GVLI 1e-9, tau 1.2 s).

Each network had its learning parameters and its forward current reselected on train seeds. The intact network's best train-seed paired-minus-unpaired LI was +1.33; the shuffles reached at most +0.12.

| network | held-out fit loss | KC ipsilateral (seeds) | touch->MDN median | paired LI | unpaired LI | fictive punishment LI | spontaneous forward runs | cycle speed | stride | period | PDM-DN stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **intact v5** | **7.43** | **10/10** | 1.9 Hz | **+1.15 (10/10)** | +0.16 | **-1.84** | 10/10 | 26.7 µm/s | 143.4 µm | 5.37 s | 0 waves |
| shuffle 1 | 25.61 | 3/10 | 12.2 Hz | -0.05 (3/10) | +0.01 | -0.14 | 10/10 | 26.8 µm/s | 135.2 µm | 5.05 s | 0 waves |
| shuffle 2 | 12.45 | 2/10 | 21.9 Hz | +0.05 (8/10) | +0.06 | +0.05 | 10/10 | 26.2 µm/s | 132.6 µm | 5.06 s | 0 waves |
| shuffle 3 | 11.97 | 0/10 | 10.0 Hz | -0.01 (6/10) | -0.01 | -0.01 | 10/10 | 26.7 µm/s | 135.7 µm | 5.04 s | 0 waves |

The forward currents were 2e-10 A for intact, 4e-10 A for shuffles 1 and 3, and 3e-10 A for shuffle 2. Shuffle 3 had up to 287 untraced frames.

Verdicts from `summary.json` and the scorecard:

| behaviour | intact | shuffles passing | connectome-specific |
|---|---|---|---|
| KC odor responses stay ipsilateral | pass | none | **yes** |
| odor-sugar conditioning | pass | none | **yes** |
| fictive punishment memory | pass | none | **yes** |
| spontaneous forward crawl | pass | all | no |
| crawl speed, stride, period | pass | all | no |
| PDM-DN stop | pass | all | no |

What changed compared with v4:

- **The fit now separates the networks.** Under v4, two shuffles reached a lower held-out loss than intact. Under v5, intact has the lowest loss (7.43 against 12.0-25.6), and every shuffle fails strict laterality on held-out seeds.
- **Learning stays connectome-specific, and more cleanly so.** Under v4, shuffle 2 learned a memory without valence (+0.80 after punishment). Under v5, no shuffle learns either memory.
- **The intact brain now crawls within the L1 range on all three cycle metrics.** The cycle metrics are not connectome-specific. With GVLI the body sets them, and any brain that supplies a forward drive reaches them.
- **Still failing: head touch backup (0/10).** The shuffles have a 5-11 times stronger touch->MDN response, but the intact fit reaches only 1.9 Hz against the 15 Hz target. This target remains the largest term in the intact loss. It is the next thing to fix.

## Scorecard

`tools/build_l1_scorecard.py --control joint_v5_strict` gives 10 pass, 3 fail and 2 not built (v4: 7, 5, 2). Three rows are connectome-specific: KC laterality, conditioning and punishment memory. The three failures are head touch backup, the PDM-DN odor-offset response and odor-gradient turning. The last two still use older brains (v4 and v3b) and have not been rerun.

## Next

- Strengthen the touch->MDN path in the intact fit without giving up the specific rows. The shuffles meet this target easily, so it does not need the measured wiring.
- Rerun odor-offset and navigation with the v5 brain, using the shuffle control.
- Look for a body mechanism that shortens the period without breaking the Greaney calibration.

## Commands

```text
R=data/local/l1em_public_connectome/runs
# v2-protocol strict-laterality fits (intact and block shuffles k = 1, 2, 3)
.venv/bin/python tools/fit_l1em_celltype_scales.py [v2 options] --strict-laterality \
  [--shuffle block:$k] --out $R/control/strict_lat/fit_v2strict_{intact,block_$k}.json
# v5 protocol with the shuffle control
.venv/bin/python tools/run_shuffle_control.py --tag joint_v5_strict \
  --fit-args "--generations 60 --free-signs 30 --free-mdn-input-signs 20 --free-touch-path-signs 20 \
    --motor-targets --freeze-classes sensory,PN,KC,MBON,MBIN,MB_FB_FF --freeze-init-signs \
    --reward-contrast --bg-hz 100 --bg-mv 6 --strict-laterality --workers 2" \
  --init $R/control/strict_lat/fit_v2strict_intact.json \
  --shuffle-init "$R/control/strict_lat/fit_v2strict_block_{k}.json" \
  --bridge-args "--mdn-current-a 1.5e-10 --sez-current-a 9e-10 --gvli-current-a 1e-9 --gvli-tau-s 1.2" \
  --workers 2
# reflex conditions for the intact network
.venv/bin/python tools/run_brain_body_crawl.py --fit $R/control/joint_v5_strict/fit_intact.json \
  --seeds 100 ... 109 --conditions head_touch forward_cut --forward-current-a 2e-10 \
  --mdn-current-a 1.5e-10 --sez-current-a 9e-10 --gvli-current-a 1e-9 --gvli-tau-s 1.2 \
  --out $R/control/joint_v5_strict/crawl_intact_reflex.json
.venv/bin/python tools/build_l1_scorecard.py --control joint_v5_strict
```
