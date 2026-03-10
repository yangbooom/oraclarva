# Drosophila Larva Whole-Brain Emulation Project

## Implementation Plan & Technical Reference

**From Connectome to Embodied Simulation: 3,016 Neurons | 548,000 Synapses | Complete CNS**

March 2026 | Based on FlyWire, Winding et al. (Science 2023), Shiu et al. (Nature 2024), and Eon Systems research

-----

## 1. Executive Summary

This document presents a detailed implementation plan for building a **connectome-driven whole-brain emulation of the *Drosophila melanogaster* first-instar (L1) larva**, coupled with a physics-based body simulation to create a closed sensorimotor loop.

The project draws directly on the approach demonstrated by Eon Systems PBC for the adult fly brain (March 2025), but targets the dramatically smaller and more tractable larval nervous system. The larval CNS contains only **3,016 neurons and 548,000 synapses** (compared to ~139,000 neurons and 50 million synapses in the adult), yet supports rich behaviors including crawling, turning, feeding, chemotaxis, and associative learning.

Critically, the larval connectome includes the **complete CNS (brain + ventral nerve cord)**, providing a full sensory-to-motor pathway — something the adult brain connectome alone lacks. This makes the larva an ideal first target for full sensorimotor emulation.

The project is structured in **four phases spanning approximately 8–12 weeks**, requiring only standard computing hardware (a laptop with 16GB RAM) and freely available open-source tools.

-----

## 2. Rationale: Why the Larva?

### 2.1 Comparison: Adult vs. Larva

|Parameter          |Adult (Eon Systems)       |Larva (L1)                     |
|-------------------|--------------------------|-------------------------------|
|Neurons            |~139,000                  |3,016 (46× smaller)            |
|Synapses           |~50,000,000               |548,000 (91× smaller)          |
|CNS Coverage       |Brain only                |**Brain + VNC (complete)**     |
|Motor Output       |Incomplete (no VNC–muscle)|**Full sensory→motor path**    |
|Connectivity Matrix|~19.3 billion entries     |~9.1 million entries           |
|Hardware Required  |GPU recommended           |Any laptop (CPU only)          |
|Behaviors          |Walk, fly, groom, feed    |Crawl, turn, feed, learn       |
|Simulation speed   |Near real-time (GPU)      |**Faster than real-time (CPU)**|

### 2.2 Key Advantages

- **Complete sensorimotor pathway:** The connectome spans from sensory neurons through interneurons to motor neurons, enabling simulation of full stimulus–response transformations without gaps.
- **Manageable scale:** The 3,016-neuron connectivity matrix fits entirely in RAM on any modern computer, enabling rapid iteration and debugging.
- **Rich behavioral validation data:** Extensive optogenetic, calcium imaging, and behavioral studies on larval circuits provide ground truth for model validation.
- **Learning circuits included:** The mushroom body (223 Kenyon cells), a well-characterized associative learning center, is fully reconstructed and annotated.
- **Soft-body locomotion:** Larval crawling (peristaltic waves) is mechanistically simpler than adult legged locomotion, making body physics easier to model.

-----

## 3. Data Sources & Resources

### 3.1 Core Connectome Data

|Resource                 |Description                                                                                |Access                                                            |
|-------------------------|-------------------------------------------------------------------------------------------|------------------------------------------------------------------|
|**Winding et al. (2023)**|Complete L1 larva brain connectome. 3,016 neurons, 548,000 synapses. Science 379, eadd9330.|[DOI](https://doi.org/10.1126/science.add9330)                    |
|**CATMAID L1 Dataset**   |Original EM volume with neuron skeletons, synapses, and annotations. Browsable online.     |[catmaid.virtualflybrain.org](https://catmaid.virtualflybrain.org)|
|**Virtual Fly Brain**    |Integrated atlas with 3D visualization for larval and adult data.                          |[virtualflybrain.org](https://virtualflybrain.org)                |
|**FlyBrainLab Datasets** |Larva L1EM database for OrientDB. Pre-packaged graph database.                             |[GitHub](https://github.com/FlyBrainLab/datasets)                 |
|**Supplementary Data**   |Adjacency matrices, neuron annotations, cell type classifications.                         |Science SI tables                                                 |
|**Eichler et al. (2017)**|Complete mushroom body connectome of L1 larva. 223 Kenyon cells. Nature 548, 175–182.      |[DOI](https://doi.org/10.1038/nature23455)                        |
|**Ohyama et al. (2015)** |Multilevel multimodal circuit for action selection in larva. Nature 520, 633–639.          |[DOI](https://doi.org/10.1038/nature14297)                        |

### 3.2 Brain Simulation Reference Code

|Resource                 |Description                                                                                      |Access                                                      |
|-------------------------|-------------------------------------------------------------------------------------------------|------------------------------------------------------------|
|**Shiu et al. LIF Model**|Original leaky integrate-and-fire model of adult Drosophila brain. Brian2 framework. Nature 2024.|[GitHub](https://github.com/philshiu/Drosophila_brain_model)|
|**Eon Systems fly-brain**|Extended version: Brian2, Brian2CUDA, PyTorch, NEST GPU backends. Benchmark suite.               |[GitHub](https://github.com/eonsystemspbc/fly-brain)        |
|**Eon NEURD-sandbox**    |Scripts for wrangling NEURD package and proofreading data transforms.                            |[GitHub](https://github.com/eonsystemspbc/NEURD-sandbox)    |
|**NEURD**                |Neural Decomposition: automated proofreading and feature extraction. Celii et al. Nature 2025.   |[DOI](https://doi.org/10.1038/s41586-025-08660-5)           |
|**FlyWire Codex (FAFB)** |Connectome Data Explorer for adult fly brain. Reference for data access patterns.                |[codex.flywire.ai](https://codex.flywire.ai/?dataset=fafb)  |

### 3.3 Body Simulation & Embodiment

|Resource                      |Description                                                                                                         |Access                                                      |
|------------------------------|--------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------|
|**Larvaworld**                |Python package for simulating Drosophila larva locomotion and foraging. Validated against real larvae.              |[PyPI](https://pypi.org/project/larvaworld/)                |
|**Neuromech Larva Model**     |Neuromechanical crawling model with measured biomechanical parameters. Sun et al. BMC Biology 2022.                 |[DOI](https://doi.org/10.1186/s12915-022-01336-w)           |
|**NeuroMechFly v2**           |Adult fly simulation framework (reference architecture for our larval adaptation). MuJoCo + Gymnasium.              |[neuromechfly.org](https://neuromechfly.org)                |
|**MuJoCo**                    |Open-source physics engine by DeepMind. Supports soft-body, contact dynamics.                                       |[mujoco.org](https://mujoco.org)                            |
|**flybody (Janelia/DeepMind)**|Anatomically detailed adult fly model in MuJoCo. Reference for body modeling pipeline. Vaxenburg et al. Nature 2025.|[GitHub](https://github.com/TuragaLab/flybody)              |
|**Larva behavior data**       |Sakagiannis et al. eLife 2025 — behavioral architecture for realistic larva simulations.                            |[eLife](https://elifesciences.org/reviewed-preprints/104262)|

### 3.4 Additional Analysis & Visualization Tools

|Resource                 |Description                                                                                            |Access                                                                    |
|-------------------------|-------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
|**FlyBrainLab**          |Interactive computing platform for Drosophila brain studies. Multi-dataset support.                    |[GitHub](https://github.com/FlyBrainLab)                                  |
|**navis**                |Python package for neuron analysis, visualization, and comparative connectomics.                       |[navis-org.github.io](https://navis-org.github.io/navis/)                 |
|**natverse / coconatfly**|R packages for cross-connectome analysis.                                                              |[natverse.org](https://natverse.org)                                      |
|**Brian2**               |Spiking neural network simulator. Core engine for Shiu LIF model.                                      |[brian2.readthedocs.io](https://brian2.readthedocs.io)                    |
|**BPU (Vogelstein Lab)** |Biological Processing Unit: larval connectome as a fixed recurrent network for ML tasks. Johns Hopkins.|[Springer](https://link.springer.com/chapter/10.1007/978-3-032-00800-8_32)|

-----

## 4. System Architecture

The emulation system consists of three coupled modules that form a closed sensorimotor loop:

```
┌─────────────────────────────────────────────────────────────┐
│                      ENVIRONMENT                             │
│  (odor gradients, substrate, temperature, obstacles)         │
└──────────┬──────────────────────────────────┬───────────────┘
           │ sensory stimuli                  ▲ body movement
           ▼                                  │
┌──────────────────────┐           ┌──────────────────────────┐
│  MODULE C:           │           │  MODULE B:               │
│  Sensory Interface   │           │  Body Physics            │
│                      │           │                          │
│  • Proprioception    │           │  • 12-segment soft body  │
│  • Chemosensation    │           │  • Muscle actuators      │
│  • Gustation         │           │  • Substrate friction    │
│  • Nociception       │           │  • Contact dynamics      │
│  • Thermosensation   │           │                          │
└──────────┬───────────┘           └──────────▲───────────────┘
           │ sensory neuron                   │ muscle activation
           │ activations                      │ commands
           ▼                                  │
┌─────────────────────────────────────────────┴───────────────┐
│                    MODULE A:                                 │
│                    Brain Emulation                           │
│                                                             │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐ │
│  │  Sensory    │──▶│ Interneurons │──▶│  Motor neurons   │ │
│  │  neurons    │   │ (brain +     │   │  (VNC segments)  │ │
│  │  (~390)     │   │  VNC core)   │   │  (~74)           │ │
│  └─────────────┘   │ (~2,552)     │   └──────────────────┘ │
│                    │              │                          │
│                    │  ┌────────┐  │                          │
│                    │  │Mushroom│  │                          │
│                    │  │ Body   │  │                          │
│                    │  │(223 KC)│  │                          │
│                    │  └────────┘  │                          │
│                    └──────────────┘                          │
│                                                             │
│  LIF Network: 3,016 neurons, 548,000 synapses              │
│  Engine: Brian2 / PyTorch                                   │
│  Timestep: 0.1 ms                                           │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

1. **Environment** provides sensory stimuli (odor concentrations, mechanical contact, etc.)
2. **Module C** converts physical stimuli into sensory neuron activation patterns
3. **Module A** propagates neural activity through the complete connectome via LIF dynamics
4. **Motor neurons** in Module A output firing rates
5. **Module B** converts motor neuron firing rates to muscle forces, simulates body physics
6. **Body movement** changes the larva’s position in the environment, altering sensory input
7. **Loop repeats** at each simulation timestep

-----

## 5. Implementation Phases

### 5.1 Phase 1: Brain Model (Weeks 1–2)

**Goal:** Build a functioning LIF simulation of the larval CNS that can predict motor neuron responses to sensory stimulation.

#### Step 1: Data Acquisition & Preprocessing

1. Download Winding et al. supplementary data (adjacency matrix, neuron annotations, cell types) from the Science paper supplementary materials
2. Parse the connectivity matrix into a sparse format (`scipy.sparse` CSR matrix)
3. Extract neuron metadata: cell type, hemisphere, sensory/motor/interneuron class
4. Map neurotransmitter identity to excitatory (+1) or inhibitory (−1) weights — the larval dataset includes neurotransmitter predictions (acetylcholine, GABA, glutamate) for most neurons
5. Identify key neuron populations:
- **Sensory neurons** (~390): olfactory (dorsal organ, ~21 ORNs), gustatory, mechanosensory (chordotonal, multidendritic), nociceptive (class IV md), photoreceptor (Bolwig’s organ, 12 neurons)
- **Motor neurons** (~74): mapped to specific body wall muscle groups per segment
- **Descending neurons**: brain → VNC commands
- **Ascending neurons**: VNC → brain feedback
- **Kenyon cells** (223): mushroom body learning circuit

**Key code reference:** Shiu’s `model.py` loads connectivity from a Parquet file; we replace this with the larval adjacency matrix in the same format.

```python
# Pseudocode for data loading
import pandas as pd
import scipy.sparse as sp

# Load adjacency matrix from Winding et al. supplementary
adj = pd.read_csv('larva_adjacency.csv', index_col=0)
neuron_meta = pd.read_csv('larva_annotations.csv')

# Build sparse weight matrix
# Weight = synapse_count × sign(neurotransmitter) × w_0
W = sp.csr_matrix(adj.values) * w_0
# Set inhibitory weights negative
inhib_mask = neuron_meta['nt_type'].isin(['GABA', 'glutamate'])
W[inhib_mask, :] *= -1
```

#### Step 2: LIF Model Implementation

Adapt Shiu et al.’s Brian2 code to the larval connectome. Core model equations:

```
τ_m × dV/dt = -(V - V_rest) + I_syn
I_syn = Σ_j w_ij × s_j(t)
τ_s × ds/dt = -s + Σ(δ(t - t_spike))
```

Model parameters:

|Parameter                   |Value                           |Source                      |
|----------------------------|--------------------------------|----------------------------|
|Resting potential (V_rest)  |−52 mV                          |Drosophila neuron recordings|
|Threshold (V_th)            |−20 mV                          |Shiu et al. 2024            |
|Reset potential (V_reset)   |−52 mV                          |Shiu et al. 2024            |
|Membrane time constant (τ_m)|10 ms                           |Shiu et al. 2024            |
|Synaptic time constant (τ_s)|5 ms (exc), 10 ms (inh)         |Shiu et al. 2024            |
|Simulation timestep (dt)    |0.1 ms                          |Standard for Brian2         |
|Weight scaling (w_0)        |Tunable (start: 0.01 nA/synapse)|Optimize for stable activity|
|Refractory period           |2 ms                            |Drosophila literature       |

**Implementation (Brian2):**

```python
from brian2 import *

N = 3016  # total neurons
# Load sparse weight matrix W (N×N)

eqs = '''
dv/dt = (-(v - V_rest) + I_syn) / tau_m : volt
dI_syn/dt = -I_syn / tau_s : amp
'''

G = NeuronGroup(N, eqs, threshold='v > V_th',
                reset='v = V_reset', refractory=2*ms)
G.v = V_rest

# Create synapses from sparse matrix
sources, targets = W.nonzero()
S = Synapses(G, G, 'w : amp', on_pre='I_syn_post += w')
S.connect(i=sources, j=targets)
S.w = W[sources, targets] * nA

# Sensory input (Poisson spiking)
sensory_input = PoissonGroup(N_sensory, rates=0*Hz)
# Connect to sensory neuron indices...

# Monitors
spike_mon = SpikeMonitor(G)
rate_mon = PopulationRateMonitor(G)

run(1*second)
```

#### Step 3: Validation

- Stimulate sugar-sensing gustatory neurons → verify motor neuron activation for feeding (proboscis extension equivalent: pharyngeal motor neurons)
- Stimulate mechanosensory neurons (chordotonal organs) → verify escape/turning responses
- Verify mushroom body circuit: KC activation patterns upon olfactory stimulation
- Compare against known results:
  - Ohyama et al. (2015): multilevel action selection circuit
  - Seeds et al. (2014): grooming suppression hierarchy
  - Eichler et al. (2017): mushroom body connectivity predictions

**Estimated compute:** 1-second biological time simulation takes approximately **5–10 seconds on a laptop CPU** for 3,016 neurons. Real-time or faster simulation is feasible with PyTorch GPU backend.

-----

### 5.2 Phase 2: Body Model (Weeks 3–5)

**Goal:** Create a physics-based soft-body model of the L1 larva capable of peristaltic crawling in MuJoCo.

#### Step 1: Morphological Model

1. Define **12 body segments** as linked soft-body elements (3 thoracic + 8 abdominal + tail)
2. Set segment dimensions from L1 larva measurements (~0.5 mm total body length, ~0.15 mm diameter)
3. Implement **longitudinal muscles** (dorsal/ventral) per segment for contraction/extension
4. Implement **lateral muscles** for turning/bending
5. Add mouth hooks (cephalic segment) for feeding behavior simulation
6. Model denticle belts on ventral surface (anisotropic friction)

**MuJoCo XML structure:**

```xml
<mujoco model="drosophila_larva_L1">
  <option timestep="0.001" gravity="0 0 -9.81"/>
  
  <worldbody>
    <body name="segment_0" pos="0 0 0.001">  <!-- head -->
      <joint name="seg0_slide" type="slide" axis="1 0 0"/>
      <joint name="seg0_bend" type="hinge" axis="0 0 1"/>
      <geom type="capsule" size="0.00007 0.00004"
            friction="0.3 0.1 0.05"/>  <!-- anisotropic -->
      <!-- Muscle actuators -->
      <actuator name="seg0_dorsal" joint="seg0_slide" gear="1"/>
      <actuator name="seg0_ventral" joint="seg0_slide" gear="-1"/>
      <actuator name="seg0_lateral" joint="seg0_bend" gear="1"/>
      
      <body name="segment_1" pos="0.00008 0 0">  <!-- T2 -->
        <!-- ... recursive segment chain ... -->
      </body>
    </body>
  </worldbody>
</mujoco>
```

#### Step 2: Biomechanical Parameters

Incorporate measured parameters from Sun et al. (BMC Biology 2022):

|Parameter               |Value                          |Source               |
|------------------------|-------------------------------|---------------------|
|Body length (L1)        |~0.5 mm                        |Measured             |
|Segment width           |~0.15 mm                       |Measured             |
|Elastic modulus         |1.17 kPa (SLS model)           |Sun et al. 2022      |
|Viscosity               |0.42 kPa·s                     |Sun et al. 2022      |
|Muscle contraction force|~1.5 µN per muscle             |Sun et al. 2022      |
|Crawling frequency      |~1.4 Hz (L3), ~0.8 Hz (L1 est.)|Heckscher et al. 2012|
|Crawling speed          |~1 mm/s (L3), scale for L1     |Measured             |
|Friction (forward)      |0.1 (low, denticles assist)    |Estimated            |
|Friction (backward)     |0.4 (high, denticles resist)   |Estimated            |

#### Step 3: Locomotion Validation (Without Brain)

Before connecting the brain, validate body physics with manually programmed motor patterns:

1. Drive segment contractions in a **posterior-to-anterior wave** → verify forward peristaltic crawling
2. Measure simulated crawling speed against experimental data
3. Verify turning behavior with asymmetric lateral muscle activation
4. Compare stride length, body curvature, and frequency with Larvaworld behavioral statistics

-----

### 5.3 Phase 3: Brain–Body Coupling (Weeks 6–8)

**Goal:** Connect the LIF brain model to the body simulation through a sensorimotor interface, creating a closed loop.

#### Step 1: Motor Output Mapping

Map identified motor neurons from the connectome to body segment actuators:

|VNC Segment|Motor Neurons |Target Muscles   |Function            |
|-----------|--------------|-----------------|--------------------|
|T1–T3      |~6 per segment|Thoracic muscles |Head/thorax movement|
|A1–A8      |~6 per segment|Body wall muscles|Peristaltic crawling|
|A8–A9      |~4 total      |Tail muscles     |Posterior anchor    |

**Motor neuron → muscle activation transfer function:**

```python
def motor_to_muscle(firing_rate, tau_nmj=20):
    """Convert motor neuron firing rate to muscle activation.
    
    Args:
        firing_rate: Hz, instantaneous firing rate of motor neuron
        tau_nmj: ms, neuromuscular junction time constant
    Returns:
        activation: 0-1, normalized muscle activation level
    """
    # Sigmoid transfer function
    activation = 1.0 / (1.0 + np.exp(-(firing_rate - 30) / 10))
    # Temporal filtering (exponential smoothing)
    activation_filtered = alpha * activation + (1 - alpha) * prev_activation
    return activation_filtered
```

#### Step 2: Sensory Input Mapping

|Sensory Modality                    |Neuron Count|Input Source                   |Mapping                       |
|------------------------------------|------------|-------------------------------|------------------------------|
|**Proprioception** (chordotonal, md)|~240        |Segment deformation            |Stretch → firing rate (linear)|
|**Olfaction** (dorsal organ)        |~21 ORNs    |Odor concentration at head     |Concentration → Poisson rate  |
|**Gustation** (terminal organ)      |~30 GRNs    |Food patch contact             |Binary + concentration        |
|**Nociception** (class IV md)       |~24         |Extreme deformation / collision|Threshold activation          |
|**Photoreception** (Bolwig’s organ) |12          |Light intensity at head        |Intensity → firing rate       |
|**Thermosensation**                 |~6          |Temperature gradient           |ΔT → firing rate              |

#### Step 3: Closed-Loop Integration

```python
# Main simulation loop
dt_brain = 0.0001  # 0.1 ms
dt_body = 0.001    # 1 ms
brain_steps_per_body = int(dt_body / dt_brain)  # 10

for t in range(total_body_steps):
    # 1. Read body state
    body_state = mujoco_sim.get_state()
    
    # 2. Compute sensory activations
    sensory_rates = compute_sensory_input(body_state, environment)
    brain_model.set_sensory_input(sensory_rates)
    
    # 3. Run brain for 10 timesteps (1 ms of biological time)
    for _ in range(brain_steps_per_body):
        brain_model.step(dt_brain)
    
    # 4. Extract motor neuron firing rates
    motor_rates = brain_model.get_motor_output()
    
    # 5. Convert to muscle activations
    muscle_commands = motor_to_muscle(motor_rates)
    
    # 6. Apply to body actuators and step physics
    mujoco_sim.set_actuators(muscle_commands)
    mujoco_sim.step(dt_body)
    
    # 7. Update environment
    environment.update(mujoco_sim.get_position())
```

**Key success criterion:** The simulated larva produces **forward peristaltic waves without explicit crawling pattern programming** — the behavior should emerge from connectome-driven neural dynamics interacting with body physics.

**Tuning strategy if locomotion does not emerge spontaneously:**

1. Adjust global weight scaling parameter (w_0): start at 0.001 and sweep logarithmically to 0.1
2. Adjust sensory gain (proprioceptive feedback strength)
3. Add tonic (background) excitation to motor neuron pools — this is biologically plausible as neuromodulatory input
4. If needed, use the CPG (central pattern generator) interneurons identified in the VNC connectome as additional constraints

-----

### 5.4 Phase 4: Behavioral Validation & Extensions (Weeks 9–12)

**Goal:** Validate the model against known larval behaviors and explore novel predictions.

#### Experiment 1: Chemotaxis

- Place simulated larva in an odor gradient (e.g., ethyl acetate)
- Activate dorsal organ neurons proportional to local odor concentration
- **Expected:** larva navigates toward odor source using biased random walk and/or weathervaning
- **Validate against:** Gomez-Marin et al. (2011) chemotaxis trajectories, Gershow et al. (2012) navigation strategies

#### Experiment 2: Associative Learning

- Pair odor stimulus with reward (dopaminergic neuron activation in mushroom body)
- Implement simple spike-timing-dependent plasticity (STDP) at KC→MBON synapses
- Test whether learned synaptic changes alter subsequent odor preference
- **Validate against:** Eichler et al. (2017) mushroom body circuit predictions, Gerber & Stocker (2007) larval conditioning experiments

#### Experiment 3: Optogenetic Silencing Predictions

- Silence specific interneuron populations identified as **hub neurons** by Winding et al.
- Predict behavioral consequences (e.g., loss of specific turning patterns)
- Generate experimentally testable hypotheses for wet-lab validation
- Focus on the 73% of in-out hubs that are postsynaptic to the learning center

#### Experiment 4: Virtual Lesion Studies

- Systematically remove individual neuron types and measure behavioral impact
- Identify minimal circuits sufficient for each behavior
- Compare with descending neuron function studies
- **Novel prediction:** Which neurons are essential vs. redundant for peristaltic crawling?

#### Experiment 5: Multi-Sensory Integration

- Present conflicting stimuli (attractive odor near aversive stimulus)
- Observe decision-making dynamics in the brain network
- Compare with known larval conflict resolution behaviors
- Analyze information flow through the recurrent circuit architecture identified by Winding et al.

-----

## 6. Technical Stack & Environment Setup

### 6.1 Software Dependencies

|Component          |Package                |Version|Purpose                         |
|-------------------|-----------------------|-------|--------------------------------|
|Language           |Python                 |3.10+  |Primary language                |
|Neural simulation  |Brian2                 |2.5+   |LIF network simulation          |
|GPU alternative    |PyTorch                |2.0+   |GPU-accelerated simulation      |
|Physics engine     |MuJoCo                 |3.0+   |Body simulation                 |
|RL interface       |Gymnasium              |0.29+  |Standard environment API        |
|Data handling      |pandas, scipy, numpy   |Latest |Connectivity matrix ops         |
|Visualization      |matplotlib, plotly     |Latest |Neural activity / behavior plots|
|3D visualization   |MuJoCo viewer / meshcat|Latest |Body simulation rendering       |
|Neuron analysis    |navis                  |1.0+   |Neuron morphology tools         |
|Behavior simulation|larvaworld             |Latest |Reference behavior data         |

### 6.2 Environment Setup

```bash
# Create conda environment
conda create -n larva-brain python=3.10
conda activate larva-brain

# Core neural simulation
pip install brian2
pip install torch torchvision  # GPU alternative

# Body simulation
pip install mujoco
pip install gymnasium

# Data and visualization
pip install pandas scipy numpy matplotlib plotly
pip install navis
pip install larvaworld

# Neuroscience tools
pip install flybrainlab
pip install cloudvolume  # for accessing EM data

# Jupyter for interactive exploration
pip install jupyterlab ipywidgets
```

### 6.3 Hardware Requirements

|Configuration  |Specs                            |Performance        |
|---------------|---------------------------------|-------------------|
|**Minimum**    |Laptop, 8GB RAM, any CPU         |1s bio-time in ~30s|
|**Recommended**|16GB RAM, modern CPU (8+ cores)  |1s bio-time in ~5s |
|**Optimal**    |16GB RAM + NVIDIA GPU (RTX 3060+)|Real-time or faster|

-----

## 7. Connectome Data Deep Dive

### 7.1 Neuron Classification (Winding et al.)

The 3,016 neurons in the larval brain cluster into **93 cell types** based on connectivity alone:

- **Sensory neurons:** ~390 (olfactory, gustatory, mechanosensory, nociceptive, photoreceptor)
- **Interneurons:** ~2,552 (local and projection interneurons, Kenyon cells)
- **Motor neurons:** ~74 (body wall muscle innervation, per-segment)
- **Neuromodulatory:** Dopaminergic (DANs), octopaminergic (OANs), serotonergic

### 7.2 Circuit Motifs

Key architectural features discovered in the larval connectome that are relevant for simulation:

- **Multilayer shortcuts:** Direct connections that bypass intermediate layers, similar to skip connections in deep neural networks
- **Nested recurrent loops:** The most recurrent circuits are in the mushroom body (learning center), with KC→MBON→DAN→KC feedback
- **Cross-hemisphere integration:** 93% of neurons have contralateral homologs, with strong bilateral connectivity
- **Hub neurons:** A small set of highly connected neurons (rich-club organization) that integrate information across circuits
- **Feedforward/feedback pathways:** Descending neurons (brain→VNC) coexist with abundant ascending feedback (VNC→brain)

### 7.3 Neurotransmitter Assignments

|Neurotransmitter   |Effect     |Prevalence     |Notes                        |
|-------------------|-----------|---------------|-----------------------------|
|Acetylcholine (ACh)|Excitatory |~60% of neurons|Most excitatory interneurons |
|GABA               |Inhibitory |~25% of neurons|Local inhibition             |
|Glutamate          |Inhibitory*|~10% of neurons|*Inhibitory in Drosophila CNS|
|Dopamine           |Modulatory |~20 DANs       |Reward/punishment signals    |
|Octopamine         |Modulatory |~10 OANs       |Arousal / state modulation   |
|Serotonin          |Modulatory |~8 neurons     |Mood / feeding regulation    |

*Note: In Drosophila, glutamatergic neurons in the CNS are typically inhibitory (via GluCl receptors), unlike in vertebrates. This is critical for correct model parameterization.

-----

## 8. Risk Assessment & Mitigation

|Risk                               |Likelihood      |Impact|Mitigation                                                              |
|-----------------------------------|----------------|------|------------------------------------------------------------------------|
|**Locomotion doesn’t emerge**      |Medium          |High  |Tune w_0, add tonic drive, use CPG interneurons as constraints          |
|**Epileptic-like runaway activity**|High (initially)|Medium|Implement balanced E/I ratio, normalize weights, add adaptation currents|
|**Poor body-brain timing sync**    |Medium          |Medium|Adjust dt ratio, add synaptic delays, tune NMJ time constants           |
|**Missing neurotransmitter data**  |Low             |Medium|~90% neurons have NT predictions; assign remaining by cell type         |
|**Incomplete motor neuron mapping**|Low             |Medium|Use Landgraf et al. muscle innervation maps for L1                      |
|**Computational bottleneck**       |Very Low        |Low   |3,016 neurons is trivially small for modern hardware                    |

-----

## 9. Success Metrics

### Primary Metrics

1. **Emergent locomotion:** Peristaltic wave propagation without explicit programming (posterior→anterior, ~0.5–1.5 Hz)
2. **Sensory-motor prediction accuracy:** >80% agreement with known optogenetic activation results
3. **Chemotaxis performance:** Simulated larva reaches odor source within 2× the time of real larvae in equivalent gradient

### Secondary Metrics

1. **Mushroom body dynamics:** KC ensemble responses match known odor coding properties
2. **Turning behavior:** Asymmetric sensory input produces appropriate head sweeps
3. **Speed modulation:** Motor neuron firing rate correlates with crawling speed
4. **Circuit hub predictions:** Silencing predicted hub neurons produces measurable behavioral deficits

### Stretch Goals

1. **Associative learning:** KC→MBON plasticity produces conditioned odor preference
2. **Multi-behavior repertoire:** Model produces crawling, turning, stopping, AND feeding without switching controllers
3. **Novel predictions:** Identify at least 3 experimentally testable predictions about larval circuit function

-----

## 10. Timeline Summary

|Week|Phase  |Milestone                              |Deliverable                                        |
|----|-------|---------------------------------------|---------------------------------------------------|
|1   |Phase 1|Data loaded, connectivity matrix parsed|Sparse weight matrix + neuron annotations          |
|2   |Phase 1|LIF model running, basic validation    |Working brain simulation, response to sensory input|
|3   |Phase 2|Soft-body model in MuJoCo              |Larva body that deforms under applied forces       |
|4   |Phase 2|Biomechanical parameters tuned         |Body that crawls with manual motor patterns        |
|5   |Phase 2|Locomotion validated against data      |Crawling speed/frequency match experiments         |
|6   |Phase 3|Motor mapping implemented              |Brain output drives body muscles                   |
|7   |Phase 3|Sensory feedback connected             |Closed sensorimotor loop                           |
|8   |Phase 3|**Emergent locomotion achieved**       |**Larva crawls from brain dynamics alone**         |
|9   |Phase 4|Chemotaxis experiments                 |Navigation performance quantified                  |
|10  |Phase 4|Learning experiments                   |Mushroom body plasticity tested                    |
|11  |Phase 4|Virtual lesion studies                 |Hub neuron predictions generated                   |
|12  |Phase 4|Documentation & release                |Complete codebase + paper draft                    |

-----

## 11. References

### Primary Papers

1. Winding, M. et al. “The connectome of an insect brain.” *Science* 379, eadd9330 (2023). [DOI](https://doi.org/10.1126/science.add9330)
2. Shiu, P.K. et al. “A Drosophila computational brain model reveals sensorimotor processing.” *Nature* 634, 210–219 (2024). [DOI](https://doi.org/10.1038/s41586-024-07763-9)
3. Celii, B. et al. “NEURD offers automated proofreading and feature extraction for connectomics.” *Nature* 640, 487–496 (2025). [DOI](https://doi.org/10.1038/s41586-025-08660-5)
4. Dorkenwald, S. et al. “Neuronal wiring diagram of an adult brain.” *Nature* 634, 124–138 (2024). [DOI](https://doi.org/10.1038/s41586-024-07558-y)

### Mushroom Body & Learning

1. Eichler, K. et al. “The complete connectome of a learning and memory centre in an insect brain.” *Nature* 548, 175–182 (2017). [DOI](https://doi.org/10.1038/nature23455)
2. Ohyama, T. et al. “A multilevel multimodal circuit enhances action selection in Drosophila.” *Nature* 520, 633–639 (2015). [DOI](https://doi.org/10.1038/nature14297)

### Body Simulation

1. Sun, X. et al. “A neuromechanical model for Drosophila larval crawling based on physical measurements.” *BMC Biology* 20, 130 (2022). [DOI](https://doi.org/10.1186/s12915-022-01336-w)
2. Wang-Chen, S. et al. “NeuroMechFly v2: simulating embodied sensorimotor control in adult Drosophila.” *Nature Methods* 21, 2353–2362 (2024). [DOI](https://doi.org/10.1038/s41592-024-02497-y)
3. Vaxenburg, R. et al. “Whole-body physics simulation of fruit fly locomotion.” *Nature* 643, 1312–1320 (2025). [DOI](https://doi.org/10.1038/s41586-025-09029-4)
4. Sakagiannis, P. et al. “A behavioral architecture for realistic simulations of Drosophila larva locomotion and foraging.” *eLife* (2025). [Link](https://elifesciences.org/reviewed-preprints/104262)

### Connectome Analysis

1. Schlegel, P. et al. “Whole-brain annotation and multi-connectome cell typing of Drosophila.” *Nature* 634, 139–152 (2024). [DOI](https://doi.org/10.1038/s41586-024-07686-5)
2. Yu, S. et al. “Biological Processing Units: Leveraging an Insect Connectome to Pioneer Biofidelic Neural Architectures.” *Springer* (2025). [Link](https://link.springer.com/chapter/10.1007/978-3-032-00800-8_32)

### Embodied Emulation

1. Wissner-Gross, A.D. “The First Multi-Behavior Brain Upload.” *The Innermost Loop* (March 7, 2026). [Substack](https://theinnermostloop.substack.com/p/the-first-multi-behavior-brain-upload)
2. Eon Systems PBC. Fly-brain repository (Brian2, PyTorch, NEST GPU backends). [GitHub](https://github.com/eonsystemspbc/fly-brain)

### Tools & Platforms

1. FlyWire Codex — Connectome Data Explorer. [codex.flywire.ai](https://codex.flywire.ai)
2. Virtual Fly Brain. [virtualflybrain.org](https://virtualflybrain.org)
3. FlyBrainLab. [GitHub](https://github.com/FlyBrainLab)
4. MuJoCo physics engine. [mujoco.org](https://mujoco.org)
5. Brian2 neural simulator. [brian2.readthedocs.io](https://brian2.readthedocs.io)

-----

## Appendix A: Quick-Start Checklist

- [ ] Clone Shiu’s LIF model: `git clone https://github.com/philshiu/Drosophila_brain_model`
- [ ] Clone Eon’s extended framework: `git clone https://github.com/eonsystemspbc/fly-brain`
- [ ] Download Winding et al. supplementary data from Science
- [ ] Access CATMAID L1 dataset via Virtual Fly Brain
- [ ] Install conda environment with all dependencies (Section 6.2)
- [ ] Parse larval adjacency matrix into sparse format
- [ ] Run first LIF simulation with olfactory neuron stimulation
- [ ] Install MuJoCo and verify basic soft-body simulation
- [ ] Build 12-segment larval body model
- [ ] Connect brain output to body actuators
- [ ] Achieve emergent peristaltic crawling
- [ ] Run chemotaxis experiment
- [ ] Celebrate 🎉

-----

*This document is a living reference. As the project progresses, implementation details, parameter values, and validation results should be updated accordingly.*