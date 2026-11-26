# L1EM unknown-sign fitting, reward-contrast refit and odor-sugar conditioning v0

Follow-up to `docs/L1EM_CELLTYPE_FIT_V0.md`. This note covers three steps:

1. Fit the signs of the stability-deciding unknown neurons, then refit.
2. Add L1 targets.
3. Add dopamine-gated KC->MBON plasticity and test odor + sugar conditioning.

All runs, fitted parameters and plasticity outputs stay in git-ignored
`data/local/l1em_public_connectome/runs/`. Only methods and aggregate numbers
are committed.

## 1. Signs of the stability-deciding neurons

The sign-sensitivity ranking was rerun with the fitted v0 scales, using all 42
ORNs at 150 Hz and 80 sign seeds:

```text
.venv/bin/python tools/run_l1em_sign_sensitivity.py \
  --fit data/local/l1em_public_connectome/runs/celltype_fit_v0.json --orn-rate 150 --seeds 80 \
  --out data/local/l1em_public_connectome/runs/sign_sensitivity_fitted_v0.json
```

16% of seeds ran away. The median reverberating core was 152 neurons. In all
13/13 runaway runs, making the top 10 unknown neurons inhibitory stopped the
runaway. Making 10 random unknown neurons inhibitory stopped only 4/13.

Literature and annotation check. None of the top 30 neurons has a transmitter
annotation in the public L1EM project. We found no published sign for them in
this pass. MBON valence and sign annotations (`mw MBON inhib/excit Appet/Avers`)
exist only for MBONs whose sign is already known, so they add nothing new.

Fit. The signs of the top 30 neurons became free CMA-ES parameters, thresholded
at 0, alongside the 14 scale parameters. The loss also gained a new hard target:
the network must stay bounded when all ORNs are driven at 150 Hz.

```text
.venv/bin/python tools/fit_l1em_celltype_scales.py --generations 60 --free-signs 30 \
  --init data/local/l1em_public_connectome/runs/celltype_fit_v0.json \
  --out data/local/l1em_public_connectome/runs/celltype_sign_fit_v1.json
```

| | v0 (scales only) | v1 (scales + 30 signs) |
|---|---:|---:|
| held out, all targets met | 4 / 10 | 6 / 10 |
| held out, runaway (any stimulus) | 3 / 10 | 0 / 10 |

Both rows use the v1 loss, which includes the all-ORN test.

The fitted signs are **not** a biological identification. Several left/right
homolog pairs received opposite signs, for example Mickey Mouse left - / right +,
BQ1 DPMl12, and AT DPMpm2. Homologous pairs normally share a transmitter, so the
targets do not identify these signs. A pair-tied refit is listed under next
steps.

## 2. Targets

No quantitative first-instar value was found in this pass for any of these:
the KC response fraction, DAN or PN firing rates, or an odor-sugar performance
index. Larval odor-taste learning protocols report third-instar scores. The
manifest gained `eschbach_2020_larval_dan_teaching`, which is reference-only and
stage-unverified. It supports a qualitative finding: pairing an odor with
DAN-d1, f1 or g1 activation teaches aversion, and DAN-c1 does not. That finding
selects the fictive-punishment DAN set below.

Step 3 exposed a functional requirement, which was added to the fit as
**reward contrast**. With spontaneous activity present, odor alone drove pPAM
DANs about as strongly as sugar did. Odor-only trials then depressed KC->MBON
synapses as much as paired trials, so paired and unpaired training gave the
same result. The v2 fit therefore runs with the same spontaneous input that the
conditioning test uses. All targets are measured relative to a no-stimulus run:

- runaway is late activity in excess of baseline, with a 2% tolerance;
- pPAM responses are evoked rates;
- odor-evoked pPAM rate must be <= 0.5 x the sugar-evoked rate (functional
  requirement, not a measured value);
- baseline pPAM rate must be <= 15 Hz (sanity bound).

```text
.venv/bin/python tools/fit_l1em_celltype_scales.py --generations 35 --free-signs 30 \
  --init data/local/l1em_public_connectome/runs/celltype_sign_fit_v1.json \
  --reward-contrast --bg-hz 100 --bg-mv 6 \
  --out data/local/l1em_public_connectome/runs/celltype_sign_fit_v2.json   # ~30 min, 6 workers
```

| v2 (spontaneous input 100 Hz x 6 mV, non-KC) | train (8) | held out (10) |
|---|---:|---:|
| all targets met | 7 / 8 | 7 / 10 (2 more within loss 0.05) |
| runaway | 0 / 8 | 1 / 10 |
| ipsilateral KC fraction | 0.12-0.16 | 0.08-0.13 |
| contralateral KC fraction | <= 0.02 | <= 0.02 |
| pPAM evoked, sugar | 5.6-13.3 Hz | 4.0-13.8 Hz |
| pPAM evoked, odor | 0.4-1.7 Hz | -0.2-1.5 Hz |
| pPAM baseline | 0.2-1.5 Hz | 0.2-1.5 Hz |
| max rate | 83-89 Hz | 84-96 Hz |

The v2 scales sit closer to uniform than v0: sensory x4.9 (v0 x13.1), the other
classes x0.9-3.7, and inhibitory gain x1.05. Spontaneous input does part of the
work that large sensory gains did before.

## 3. Dopamine-gated KC->MBON plasticity and conditioning

`oraclarva.brain_sim.Plasticity` implements a synapse-local three-factor rule
for KC->MBON weights:

```text
dw_ij/dt = -eta * kc_trace_i * da_j * w_ij
da_j     = sum_d M[d, j] * max(0, dan_trace_d - theta)
```

- Traces are spike traces with tau of 500 ms (KC) and 300 ms (DAN).
- `M` is the measured DAN->MBON contact matrix, row-normalized: a DAN modulates
  the MBONs it contacts, which is the anatomical compartment proxy.
- Dopamine is a modulatory channel only. DANs still have no fast weight.
- The KC->MBON weights are moved out of the sparse matrix into a dense plastic
  block, and they persist across `simulate` calls.
- `theta` stands in for supralinear cAMP coincidence detection.

The reward is never a code-injected scalar. Sugar enters as Poisson input to
the 4 sugar sensory neurons. Its effect reaches the synapses only through the
connectome, via sugar sensory -> ... -> DANs.

Protocol (`tools/run_l1em_conditioning.py`), a reciprocal design as in larval
odor-taste learning:

- Odors: odor A (ORN 42a/42b/24a) and odor B (74a/85c/22c).
- Training: 3 cycles of rewarded odor + sugar for 2 s, then the other odor
  alone. Group A+/B- and group A-/B+.
- Test: plasticity off, each odor 3 x 2 s.
- Readout: approach drive = mean appetitive MBON rate - mean aversive MBON rate,
  using the Eschbach/Winding MBON valence annotations.
- Learning index: LI = (pref_A[A+] - pref_A[B+]) / 2, where pref_A = drive(A) -
  drive(B).

Controls:

- unpaired: sugar 1.5 s after odor offset;
- learning off;
- fictive punishment: odor paired with stimulation of DAN-d1/f1/g1
  (MBE4h/4a/4f), like an optogenetic experiment.

`theta` = 4 and `eta` = 2e-3 were chosen on train sign seeds 0-3. They were then
evaluated once on held-out sign seeds 100-109:

```text
.venv/bin/python tools/run_l1em_conditioning.py        # ~6 min, 6 workers
```

| condition (held out, n = 10) | LI mean +/- SD | LI > 0 | Wilcoxon p |
|---|---:|---:|---:|
| odor + sugar, paired | +0.94 +/- 0.50 | 10 / 10 | 0.002 |
| unpaired | +0.02 +/- 0.22 | 6 / 10 | 0.63 |
| learning off | 0.00 | 0 / 10 | - |
| fictive punishment (DAN-d1/f1/g1) | -1.29 +/- 0.26 | 0 / 10 | 0.002 |

Paired LI was greater than unpaired LI in 10/10 networks (p = 0.002). An
ablation with no threshold (`--da-threshold 0 --eta 1e-4`) still gives paired
+0.30 +/- 0.20 (9/10 > 0, p = 0.006) against unpaired -0.03 (p = 0.42). The
threshold sharpens the effect but does not create it.

Mechanism:

- After sugar pairing, depression falls on aversive-MBON inputs (1.7% mean) and
  not on appetitive ones (0.0%). This matches the anatomy: sugar-responsive
  pPAM DANs (MBE1b/1c) contact aversive MBONs MBE5a/5b. Weakening an aversive
  MBON shifts the drive toward approach.
- Fictive DL1 punishment depresses appetitive-MBON inputs more, matching
  DL1->MBE15/MBE6/MBE34 contacts. That gives the expected negative LI.

Limits:

- The readout is MBON population drive and has not been taken to descending
  neurons or the body.
- The valence readout uses published MBON valence annotations; it is not a
  behavioral choice.
- One synthetic odor pair was tested.
- Unknown signs remain sampled (p 0.7) apart from the 30 fitted ones.
- Spontaneous input is a uniform Poisson drive. It is not measured L1 baseline
  activity.

## Next

1. Refit the free signs tied across left/right homologs, and add more odors.
2. Read the learned change out through descending neurons into the body
   (odor preference as navigation), which closes (c) end to end.
3. Add sugar memory extinction and reversal (Eschbach 2020 protocols) as a
   qualitative test of the MBON->DAN feedback loops.
