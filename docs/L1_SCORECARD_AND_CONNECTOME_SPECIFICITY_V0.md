# L1 scorecard, connectome specificity of v4, and the crawl-speed gap (v0)

Follows `L1EM_JOINT_FIT_GVLI_PDM_STOP_V0.md`. Three questions:

1. Does a shuffled connectome do what v4 does?
2. Is the speed gap (16.5 vs 25.7-38.2 µm/s) caused by the brain or the body?
3. Where does the model stand against L1 data overall?

All numbers come from held-out sign seeds 100-109. Parameters were selected on train seeds 0-3.

## 1. Block-shuffled connectomes under the v4 protocol

Three block shuffles (seeds 1-3) went through the full v4 protocol:

- start from their own v2-protocol fits;
- the same frozen classes and the same loss;
- the same conditioning and crawl tests.

Learning parameters (DA threshold, eta) were reselected for every network on train seeds. The intact network's best train-seed paired-minus-unpaired LI was +1.64; the shuffles reached at most +0.17. The brain-body forward current was also reselected per network, and the grid was extended to 4e-10 when a shuffle chose its top value.

| network | held-out loss | touch->MDN median | paired LI | unpaired LI | fictive punishment LI | spontaneous forward runs | cycle speed | PDM-DN stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| intact v4 | 9.52 | 2.8 Hz | **+1.30 (10/10)** | +0.01 | **-0.62** | 10/10 | 21.5 µm/s | 0 waves |
| shuffle 1 | 12.28 | 7.8 Hz | -0.11 (4/10) | -0.11 | -0.05 | 6/10 | 26.5 µm/s | 0 waves |
| shuffle 2 | 5.36 | 11.4 Hz | +0.27 (10/10) | -0.02 | **+0.80** | 10/10 | 14.6 µm/s | 0 waves |
| shuffle 3 | 5.64 | 11.6 Hz | -0.04 (3/10) | -0.04 | +0.04 | 10/10 | 16.7 µm/s | 0 waves |

The forward currents were 1e-10 for intact, 2e-10 for shuffle 1, and 3e-10 for shuffles 2 and 3. Shuffle 2 had up to 335 untraced frames.

What this shows:

- **Learning with the right valence needs the measured wiring.** No shuffle learns both the appetitive memory and the aversive one. Shuffle 2 learns a nonspecific memory: it approaches the paired odor after sugar and also after fictive punishment.
- **The physiological fit targets do not separate the networks under the v4 protocol.** Two shuffles reach a lower loss than intact, with a stronger touch->MDN response. This revises the earlier v2-protocol result, where shuffles could not meet the targets. The v4 freeze-and-refit protocol is loose enough for shuffled wiring to satisfy the targets.
- **Crawling, its period and the PDM-DN stop are not connectome-specific.** Given a reselected bridge current, the shuffles crawl as well as intact. The stop relay lives in the body (SEZ-DN1), so it tests the bridge, not brain wiring.

## 2. Where the speed gap comes from

The gap between the L1 median (31.2 µm/s) and the reported 16.5 µm/s splits into three parts.

| step | speed |
|---|---:|
| reported (window average, includes time before the first wave) | 16.5 µm/s |
| per-cycle median (metric fix, now `cycle_speed_um_s_median`) | 21.5 µm/s |
| replay of clean starts only (no extra brain A6 spikes) | 27 µm/s |
| body ceiling (clean body wave) | 26.8 µm/s |
| L1 median | 31.2 µm/s |

- About +5 µm/s is a metric artifact.
- About +5 µm/s is lost to extra brain spikes onto A6, which restart the wave and shorten strides (held-out stride 108.5 µm against a clean 143.7 µm).
- The remaining +4.4 µm/s is the body. Its stride (143.7 µm) and A1-A6 wave speed (1.69 segments/s) are within L1 ranges. Its period (about 5.36 s against 4.84 s) is long.

So fixing the brain's forward drive is worth more than tuning the body.

## 3. Scorecard

`tools/build_l1_scorecard.py` builds the scorecard from local run outputs. It writes aggregate rows to `data/local/.../runs/scorecard_v0.json`.

Of 14 behaviours, 7 pass, 5 fail and 2 are not built. Only the two learning rows pass and also fail on the shuffles.

| area | behaviour | L1 | model | status |
|---|---|---|---:|---|
| Crawling | crawl speed per cycle | 25.7-38.2 µm/s | 21.5 | fail |
| Crawling | stride per cycle | 129.8-159.7 µm | 108.5 | fail |
| Crawling | cycle period | 4.10-5.38 s | 5.09 | pass |
| Crawling | A1-A6 wave speed | 1.58-2.35 seg/s | 1.69 | pass (body parameter) |
| Crawling | spontaneous forward crawl | crawls | 10/10 | pass |
| Crawling | forward cut stops crawl | control | 0/10 | pass |
| Reflexes | head touch -> back up | backs up | 0/10 | fail |
| Reflexes | PDM-DN activation stops crawl | stops | 0 waves | pass |
| Odor | odor decrease raises PDM-DN | inferred | 1/10 | fail |
| Odor | turns toward odor gradient | climbs | 5/10 (v3b) | fail |
| Odor | head casts | casts | — | not built |
| Learning | odor-sugar conditioning | LI > 0 | +1.30 | pass, connectome-specific |
| Learning | fictive punishment memory | LI < 0 | -0.62 | pass, connectome-specific |
| Learning | learned preference changes navigation (M4) | goal | — | not built |

## Next

- Make the shuffle test part of every future fit. A result only counts toward the north star if the shuffled networks fail it.
- Tighten the fit targets so that they separate intact from shuffled wiring.
- Reduce the brain's extra A6 drive, then the body period.

All three are done in `L1_FIT_SPECIFICITY_AND_A6_GATING_V0.md`.

## Commands

```text
R=data/local/l1em_public_connectome/runs
# v4 protocol on block shuffle k (k = 1, 2, 3)
.venv/bin/python tools/fit_l1em_celltype_scales.py --shuffle block:$k --init $R/null/fit_block_$k.json \
  [v4 options as in L1EM_JOINT_FIT_GVLI_PDM_STOP_V0.md] --out $R/null/fit_joint_v4_block_$k.json
.venv/bin/python tools/run_l1em_conditioning.py --fit $R/null/fit_joint_v4_block_$k.json \
  --da-threshold TH --eta ETA --out $R/null/cond_joint_v4_block_$k.json
.venv/bin/python tools/run_brain_body_crawl.py --fit $R/null/fit_joint_v4_block_$k.json --seeds 100 ... 109 \
  --conditions spontaneous pdm_activation --forward-current-a F --mdn-current-a 1.5e-10 --sez-current-a 9e-10 \
  --out $R/null/crawl_joint_v4_block_$k.json
.venv/bin/python tools/build_l1_scorecard.py
```
