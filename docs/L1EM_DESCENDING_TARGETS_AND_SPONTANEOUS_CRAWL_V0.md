# L1EM descending-output targets, brain-driven crawling and odor navigation v0

Follow-up to `docs/L1EM_NULL_MODEL_AND_BRAIN_BODY_BRIDGE_V0.md`, section 5,
items 1-3. North star: a connectome model that **moves naturally**.

All fits, runs and per-seed outputs stay in git-ignored
`data/local/l1em_public_connectome/runs/`. Only methods and aggregate numbers
are committed. Sign seeds 0-7 are train seeds and 100-109 are held out.
Every bridge current below was chosen on train seeds only.

## 1. Descending-output targets in the brain fit

### Which descending neurons have a known behavior

Winding et al. 2023 (Science; bioRxiv 10.1101/2022.11.28.516756) name two
brain-to-VNC descending types with a published phenotype:

- **MDN**: acute activation makes larvae back up;
- **PDM-DN**: acute activation makes larvae stop, followed by head casts
  (Tastekin et al. 2018).

The paper notes that stop then back-up is a common larval sequence. It states
that the behavioral roles of most DNs-VNC are unknown. The public L1EM project
annotates 14 neurons as `mw dVNC with phenotypes`; the extra names in that set
(DNs-17, DALd LAL output 1, DPMl_ant_ven 3, CM4 bc 2) have no phenotype in the
paper text we read, so they are not used as targets.

### Targets (qualitative, functional)

| target | value | why |
|---|---|---|
| head touch -> MDN, evoked | >= 15 Hz | larvae back up on anterior touch; MDN drives backing up |
| appetitive odor -> MDN, evoked | <= 2 Hz | attractive odor should not trigger backing up |
| sugar -> MDN, evoked | <= 2 Hz | same |
| MDN baseline | <= 3 Hz | a resting brain should not back up |

None of these is a measured L1 rate. They are hinge losses.

"Head touch" is a new stimulus set built from annotations: the 34 first-order
sensory inputs with >= 2 contacts onto Winding `mw mechano-II/III 2nd_order`
neurons. These are mostly antennal-nerve external sensory neurons, plus v'td
and pCC (class II/III touch). Before this fit, in v2, head touch did not drive
MDN: evoked -0.4 Hz.

### Free signs

All 20 strongest MDN inputs have unknown signs. So, beyond the 30 earlier free
signs, the fit also frees:

- the top 20 unknown-sign MDN inputs;
- 16 more unknown-sign neurons that both receive head-touch signal within 3
  hops and reach MDN within 2 hops (score = product of input fractions).

Fit: CMA-ES, starting from v2, same loss plus the motor terms, spontaneous
input 100 Hz x 6 mV.

| fit | held-out head touch -> MDN, evoked (Hz) | held-out odor / sugar -> MDN | held-out runaway |
|---|---|---|---:|
| v2 (no motor target) | -0.4 (mean, 5 seeds) | ~0 | 1/10 |
| v3 (+ 20 MDN-input signs, 50 gen) | median 3.4; 1/10 >= 15 | odor <= 2.8 Hz in 9/10; sugar 13.4 Hz in 1/10 | 1/10 |
| **v3b** (+ 16 touch-path signs, 60 gen) | median 5.2; 4/10 >= 9; range -1.9 to 19.7 | odor <= 3.1, sugar <= 4.7 Hz | 0/10 |
| v3c (v3b + MBON readout target) | median 2.3; 2/10 >= 10 | odor <= 2.2, sugar <= 2.5 Hz | 0/10 |

The touch response stays seed-dependent: it depends on the remaining sampled
unknown signs.

### Cost: the motor fit broke appetitive learning

Conditioning (protocol of `docs/L1EM_CONDITIONING_V0.md`, held out, n = 10):

| fit | paired LI (>0) | unpaired LI | fictive punishment LI (<0) |
|---|---:|---:|---:|
| v2 | +0.86 (10/10) | ~0 | -1.26 (10/10) |
| v3b | -0.01 (3/10) | 0.00 | -0.08 (10/10) |
| v3c | +0.02 (5/10) | -0.11 | **-0.70 (10/10)** |

Re-selecting theta/eta on train seeds (8 settings) did not restore v3b: best
paired LI +0.04.

The cause is visible. In v3b, odor-evoked MBON firing collapsed: +0.46 Hz
against +4.3 Hz in v2, with KC rates 0.24 against 0.87 Hz. KC->MBON plasticity
then has nothing to read out.

v3c adds a functional requirement: odor-evoked MBON firing >= 3 Hz, and >= 30%
of MBONs evoked. This recovers MBON drive (held-out mean +2.4 Hz) and the
punishment memory, but not the sugar memory. At the same time it weakens the
touch -> MDN response.

**Motor output and appetitive learning are not yet satisfied by one parameter
set.** v3b is used for the body experiments below because its motor output is
strongest.

## 2. Brain-driven crawling (no touch)

### Bridges (`src/oraclarva/brain_body.py`)

| brain group (L1EM) | n | axial node | current per spike |
|---|---:|---|---:|
| MDNa/b left/right | 4 | `descending:MDN` | 0.15 nA |
| `lv dVNC to A8+A9`, MDNs excluded | 29 | `premotor:A27h:A6` (posterior start of the forward wave) | 0.2 nA |

The forward bridge is a hypothesis. Larval forward waves start in posterior
segments, and these brain neurons project there (L1EM annotation). It is not a
published phenotype.

Causality contract: the brain step [t - dt, t) is delivered at t. Every brain
spike therefore strictly precedes its effect, and it enters the axial
causal-trace bookkeeping as origin `brain_l1em:*`.

The currents were chosen on train seeds 0-3 from a 3 x 2 grid. The criterion
was runs with net forward and no backward wave at rest, plus clean
touch-evoked backing up.

| forward bridge current, v2 brain, seed 100, 20 s | result |
|---|---|
| 0.2 nA | no wave starts |
| 0.3 nA | first wave at 3.7 s, then clean waves every 5.35 s, about 140 um stride |
| 0.4 nA | extra A6 starts in mid-wave, shorter strides |

Once a wave has started, the existing proprioceptive recovery loop (A1
recovery -> A27h:A6) repeats it. The brain decides *whether* the animal
crawls, and the VNC loop sets the rhythm. There is still no CPG, FSM or
periodic stimulus.

### Held out (seeds 100-109, v3b, 30 s each)

| condition | net forward | clean (no backward wave) | wave period (median) | speed (median) | untraced frames (max) |
|---|---:|---:|---:|---:|---:|
| spontaneous brain | 8/10 | 7/10 | **5.05 s** | 12.3 um/s | 5 / 30,000 |
| forward bridge cut | 0/10 | - | - | 0 | 0 |
| both bridges cut | 0/10 (no motion) | - | - | 0 | 0 |

Compared with the L1 held-out reference (Greaney 2026):

- the period sits inside the reference interval (median 4.84 s, p10-p90
  4.10-5.38 s);
- the speed does not: 12 um/s against 25.7-38.2 um/s. Strides are short,
  because brain spikes keep re-starting A6 during an ongoing wave.

2 of 10 seeds back up at rest; MDN baseline crosses the bridge threshold.

### Head touch through the brain: negative

With the axial model's own anterior-touch path unused, the head-touch set was
driven at 150 Hz for 0.5 s at 15 s.

- Only 2/10 runs backed up within 3 s, and both were seeds that already back
  up at rest. Clean touch-evoked backing up: **0/8**.
- The evoked MDN response (v3b held-out median about 5 Hz x 4 neurons x 0.5 s)
  stays below the bridge threshold. Lowering the threshold makes resting
  brains back up (train-seed grid: MDN 0.2 nA gives 1/4 clean spontaneous
  runs).

The descending target must be much stronger, and less seed-dependent, before
the body can express it.

### Null control: block-shuffled connectome with the same motor fit

One block shuffle (`--shuffle block:1`; class-to-class contact totals
preserved) was fitted with the identical v3b protocol. It was then run in the
body with the identical bridges.

| | intact v3b | block shuffle 1 |
|---|---:|---:|
| held-out fit: all targets met / runaway | 1/10 / 0/10 | 0/10 / 2/10 |
| held-out head touch -> MDN, evoked (median) | 5.2 Hz | **18.5 Hz** |
| spontaneous: net forward crawl (30 s) | **8/10** | 3/10 |
| head touch: backing up within 3 s | 2/10 (0/8 clean) | 0/10 (touch triggers forward crawling, 10/10) |

- The head-touch -> MDN target is **not connectome-specific**. Random wiring
  within the same class blocks meets it more easily, and it does so at the
  cost of the other targets. The target is too weak a constraint on its own.
- Spontaneous forward crawling is more frequent with the measured wiring
  (8/10 against 3/10), although forward-DN baseline rates are similar (about
  1 Hz). This is one shuffle only, so it is suggestive, not established.
- Even about 18 Hz of evoked MDN firing for 0.5 s does not move the body
  backward at 0.15 nA per spike. The direct upstream stimulation in the
  previous note needed about 360 MDN spikes.

## 3. M3 v0: odor gradient navigation through the brain

`tools/run_brain_odor_navigation.py`. The closed loop runs every 1 ms:

1. The odor field is sampled at the current left/right head surface.
2. Left/right appetitive ORNs fire at 150 Hz x F.
3. The fitted brain runs.
4. MDN and forward groups drive crawling as in section 2.
5. Left/right soma-side brain DNs annotated `lv dVNC to T3+A1` (46 per side;
   MDN and forward groups excluded) feed the existing side-resolved steering
   relay (`docs/AXIAL_STEERING_V1.md`), then A1-A3 premotor, shared MNs,
   fibers, body.

The only placement choice is ipsilateral: left-soma DNs drive the left relay.
It was fixed a priori and not fitted. Whether the larva turns toward or away
from the odor is therefore decided by the brain's lateralization.

In the brain alone, a one-sided odor raises the ipsilateral T3+A1 DNs more
than the contralateral ones, about +0.8 Hz on average, in the same direction
in all 3 seeds tested.

Field: the steering-v1 fixture, F = 0.5 + g*y with g = +/-5000 /m. This is a
strong lateral gradient and not a measured odor plume.

The steering current, 0.2 nA per DN spike, was chosen on train seeds 0-3
from 0.2, 0.4 and 0.8 nA. At 0.2 nA all 4 train seeds moved up-gradient,
though not significantly (Wilcoxon p 0.125).

Held out (seeds 100-109, 20 s; paired by seed, +y run minus -y run):

| quantity | +y gradient | -y gradient | uniform |
|---|---:|---:|---:|
| steering DN spikes, left minus right (20 s) | -57.8 | +47.8 | +4.2 |
| y displacement (um, mean) | -0.5 | -17.4 | +0.4 |
| forward displacement (um, mean) | 721 | 785 | 737 |

- The brain does sense the side of the odor. The left/right DN difference
  flips with the gradient, in the ipsilateral direction.
- The body does not follow. Only 5/10 seeds moved toward the odor; Wilcoxon
  p = 0.85. **M3 v0 is negative.**
- The lateral signal is about 2.5 spikes/s, out of about 46 Hz of
  spontaneous DN firing per side. That is too small against the relay
  threshold and against wave-to-wave yaw noise.
- Forward speed in the steering body (about 36-39 um/s) is higher than in the
  axial body. The added A1-A3 relay drive also adds propulsion; this is a
  known coupling of the steering-v1 reduced mechanics.

## 4. What this means for "moves naturally"

- **Achieved:**
  - a resting connectome brain starts forward crawling by itself;
  - the rhythm comes out at the L1 period;
  - cutting the brain->body link stops the body.
- **Not yet:**
  - L1 speed: about 12 against about 31 um/s;
  - touch-evoked backing up through the brain;
  - a brain that keeps sugar learning while also driving descending
    behavior.
- **Navigation:** negative in v0. The brain lateralizes the odor, but the
  signal is too small to steer the body. Real larval chemotaxis relies on
  head casts and temporal comparison (odor decrease -> PDM-DN -> stop), which
  this body cannot do yet. M4 is therefore not attempted.

## Next

1. A joint fit with motor targets *and* a learning target. For example,
   train-seed conditioning LI as part of the loss, or keep v2's KC/MBON block
   fixed while fitting only the descending circuitry.
2. Make wave starts refractory during an ongoing wave through identified VNC
   inhibition, not a rule, so that brain spikes stop shortening strides.
3. Temporal odor coding: odor decrease -> PDM-DN -> stop and head cast. This
   is the actual L1 chemotaxis strategy, and it needs head-cast mechanics in
   the body.
4. Then M4: learned odor preference expressed in navigation.

## Commands

```text
.venv/bin/python tools/fit_l1em_celltype_scales.py --generations 60 --free-signs 30 \
  --free-mdn-input-signs 20 --free-touch-path-signs 20 --motor-targets \
  --init data/local/l1em_public_connectome/runs/celltype_motor_fit_v3.json \
  --reward-contrast --bg-hz 100 --bg-mv 6 --out .../celltype_motor_fit_v3b.json   # ~12 min
.venv/bin/python tools/run_brain_body_crawl.py --fit .../celltype_motor_fit_v3b.json \
  --seeds 100 ... 109 --forward-current-a 2e-10 --mdn-current-a 1.5e-10            # ~10 min
.venv/bin/python tools/run_brain_odor_navigation.py --fit .../celltype_motor_fit_v3b.json \
  --seeds 100 ... 109 --steering-current-a 2e-10 --forward-current-a 2e-10 --mdn-current-a 1.5e-10
```
- Follow-up (joint fit v4, bridge re-calibration, GVLI, PDM-DN -> SEZ-DN1 stop): `L1EM_JOINT_FIT_GVLI_PDM_STOP_V0.md`.
