# Head-touch backup is limited by the brain volume; odor rerun under the shuffle control (v0)

Follows `L1_FIT_SPECIFICITY_AND_A6_GATING_V0.md`. Its next steps were:

1. Strengthen touch->MDN.
2. Rerun the odor rows with the v5 brain under the shuffle control.
3. Shorten the body period.

Parameters were selected on train seeds 0-3. Reported numbers come from held-out sign seeds 100-109.

## 1. Head touch -> MDN

### Why the fit stays weak

The brain gets "head touch" through 34 first-order sensory neurons that feed the Winding mechano-II/III second-order neurons.

- **No short path.** No touch neuron synapses directly onto an MDN. The MDNs are 2-3 hops away.
- **Inputs of unknown sign.** 98.6% of MDN input contacts come from neurons whose transmitter sign is unknown. Neurons within 2 hops of touch supply 34.5% of MDN input, and neurons within 3 hops supply 93%.
- **Weak, variable response.** Each sign seed draws the unknown signs again, and the fit had freed only 20 touch-path signs and 20 MDN-input signs. In v5 the touch response therefore varied from -1.2 to 9.4 Hz across held-out seeds, with a median of 1.6 Hz.
- **The body MDN never fires.** In the head-touch crawl the brain MDNs fire about 250 spikes over 30 s, but the body's `descending:MDN` node never fires. The backup score is 0/10.

### More free signs on the path (v6)

The v6 protocol is v5 with more free signs: `--free-mdn-input-signs 40` and `--free-touch-path-signs 80`, 121 free signs in total. Each network starts from its v5 fit, and v5's signs stay frozen.

The fit tool now matches the start fit's signs to neurons by skid rather than by position. Before this change, enlarging the free set would have frozen old signs onto the wrong neurons.

| network | held-out fit loss | KC ipsilateral (seeds) | touch->MDN median | paired LI | unpaired LI | fictive punishment LI | stride | period |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **intact v6** | **5.68** | **10/10** | 4.1 Hz | **+1.45 (9/10)** | +0.12 | **-2.62** | 143.6 µm | 5.37 s |
| shuffle 1 | 38.36 | 3/10 | 15.5 Hz | +0.02 | -0.06 | -0.06 | 141.9 µm | 5.31 s |
| shuffle 2 | 13.72 | 0/10 | 16.4 Hz | -0.03 | +0.01 | -0.12 | 135.1 µm | 5.07 s |
| shuffle 3 | 11.43 | 0/10 | 8.6 Hz | -0.05 | -0.01 | -0.02 | 134.5 µm | 5.06 s |

Shuffle 2 had up to 362 untraced frames and shuffle 3 up to 5004.

What changed from v5:

- Intact touch->MDN rose from 1.6 to 4.1 Hz.
- The intact held-out loss fell from 7.43 to 5.68.
- Learning became stronger.
- Head-touch backup is still 0/10, and the body MDN still never fires.

### How much MDN drive the body needs

A body-only test added extra MDN spikes during a touch window on top of a 10 Hz summed baseline:

| summed extra MDN rate (4 MDNs) | bridge 1.5e-10 A, 0.5 s | bridge 3e-10 A, 0.5 s | bridge 3e-10 A, 2 s |
|---:|---:|---:|---:|
| 16 Hz (the v6 intact response) | 0 backward | 0 | 0 |
| 60 Hz (15 Hz per MDN, the fit target) | 0 | 3 | 9 |
| 120 Hz | 1 | 14 | 45 |
| 240 Hz | 13 | 44 | 183 |

The cells count backward-wave A1 spikes.

The body needs about the fit target, 15 Hz per MDN, at a 3e-10 A bridge. The intact brain gives about a quarter of that.

### Why: the touch route runs through the nerve cord

In larvae, gentle touch acts through class III da neurons in the body wall. MDNs are needed for the backward response, but the ascending AMB neurons upstream of MDN are not (Omamiuda-Ishikawa et al. 2020, PLoS Genet 16:e1009120). The brain EM volume contains almost none of this nerve-cord pathway. Ascending neurons annotated in it give 4 of 1183 MDN input contacts, and all 4 come from nociceptive A1 ascending neurons.

The block shuffles reach 9-16 Hz because shuffling spreads the touch input over many more targets. That response does not come from wiring that the larva has.

So **head-touch backup is a limit of the brain-only connectome, not of the fit**. Fixing it needs the missing nerve-cord route as modeled neurons with fitted weights, as the SEZ-DN1 relay already is. That is a separate step, and the row stays failing until then.

## 2. Odor rows under the shuffle control

`tools/run_shuffle_control.py` now has a fourth stage, so every protocol is tested on odor too:

1. the odor-offset probe (does an odor decrease raise PDM-DN?) on held-out seeds;
2. odor-gradient navigation, with the steering current chosen per network on train seeds 0-3 by the mean mirror-pair difference (grid 2e-10, 4e-10, 8e-10 A).

The tool's summary and the scorecard now include two new criteria: `toward_odor_runs` (at least 8 of 10) and `odor_offset_pdm_seeds` (at least 5 of 10).

### v5

| network | steering current | runs toward odor | Wilcoxon p | odor decrease raises PDM-DN (seeds) |
|---|---:|---:|---:|---:|
| **intact v5** | 2e-10 | **8/10** | 0.020 | 1/10 |
| shuffle 1 | 2e-10 | 4/10 | 0.28 | 1/10 |
| shuffle 2 | 2e-10 | 2/10 | 0.16 | 2/10 |
| shuffle 3 | 4e-10 | 6/10 | 0.70 | 1/10 |

- **Turning toward an odor gradient now passes, and it is connectome-specific.** The v3b brain had given 5/10.
- **The PDM-DN odor-offset response still fails on every network.** Model ORNs fire about 0.36 Hz at rest, so an odor decrease cannot push them lower. The fix belongs in the ORN model, not in the brain fit.

### v6

| network | steering current | runs toward odor | Wilcoxon p | odor decrease raises PDM-DN (seeds) |
|---|---:|---:|---:|---:|
| **intact v6** | 4e-10 | **8/10** | 0.084 | 0/10 |
| shuffle 1 | 2e-10 | 6/10 | 0.56 | 2/10 |
| shuffle 2 | 2e-10 | 6/10 | 0.56 | 1/10 |
| shuffle 3 | 4e-10 | 4/10 | 1.00 | 2/10 |

V6 also passes the navigation criterion, and no shuffle does. Its effect is weaker than v5's (p = 0.084 against 0.020). Navigation is the least robust connectome-specific row.

## 3. Body period

Not changed. The period, 5.37 s, is inside the L1 range (4.10-5.38 s) but at its edge. The recovery-delay sweep in the previous note shows that the period cannot be shortened through that loop without breaking the Greaney calibration.

## Scorecard

v6 is the new model of record. It has the lowest train loss (4.29 against 5.43 for v5) and the lowest held-out fit loss, and its protocol contains v5's.

`tools/build_l1_scorecard.py` now defaults to `--control joint_v6_touch` and gives 11 pass, 2 fail and 2 not built (previous note: 10, 3, 2).

- **Connectome-specific (4):** KC laterality, turning toward an odor gradient, conditioning, punishment memory.
- **Failing (2):** head-touch backup (limited by the brain volume) and the PDM-DN odor-offset response (limited by the ORN model).
- **Not built (2):** head casts, M4.

## Next

- Model the nerve-cord touch route to MDN: C3da to MDN through the nerve cord, as modeled neurons with fitted weights.
- Give model ORNs a measured spontaneous rate, so that an odor decrease can produce an OFF signal.
- Learned preference changing navigation (M4): the v5/v6 brains now pass both conditioning and navigation.

## Commands

```text
R=data/local/l1em_public_connectome/runs/control
.venv/bin/python tools/run_shuffle_control.py --tag joint_v6_touch \
  --fit-args "--generations 80 --free-signs 30 --free-mdn-input-signs 40 --free-touch-path-signs 80 \
    --motor-targets --freeze-classes sensory,PN,KC,MBON,MBIN,MB_FB_FF --freeze-init-signs \
    --reward-contrast --bg-hz 100 --bg-mv 6 --strict-laterality --workers 3" \
  --init $R/joint_v5_strict/fit_intact.json --shuffle-init "$R/joint_v5_strict/fit_{k}.json" \
  --bridge-args "--mdn-current-a 1.5e-10 --sez-current-a 9e-10 --gvli-current-a 1e-9 --gvli-tau-s 1.2" \
  --workers 2
# reflex conditions for the intact network (forward current as selected by the control run)
.venv/bin/python tools/run_brain_body_crawl.py --fit $R/joint_v6_touch/fit_intact.json --seeds 100 ... 109 \
  --conditions head_touch forward_cut --forward-current-a 1.4e-10 --mdn-current-a 1.5e-10 \
  --sez-current-a 9e-10 --gvli-current-a 1e-9 --gvli-tau-s 1.2 --out $R/joint_v6_touch/crawl_intact_reflex.json
.venv/bin/python tools/build_l1_scorecard.py --control joint_v6_touch
```
