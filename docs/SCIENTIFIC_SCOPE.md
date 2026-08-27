# Scientific scope and evidence gates

## Claim boundary

Oraclarva aims to become a connectome-driven embodied neural simulation. It does not currently reproduce a larva's mind, consciousness, or validated full behavior repertoire.

The Winding et al. dataset commonly summarized as 3,016 neurons and roughly 548,000 synapses is a larval brain connectome reconstructed within the available CNS EM volume. Before describing a model as a complete sensor-to-muscle animal, the project must verify coverage and identity across sensory neurons, descending pathways, VNC circuitry, motor neurons, neuromuscular junctions, and muscles.

## Provenance labels

Every imported node, edge, parameter, and mapping must carry one of these labels:

- `observed`: directly supported by a cited dataset;
- `derived`: mechanically transformed from observed data;
- `fit`: estimated against a named experimental measurement;
- `hypothesis`: biologically plausible but not directly established;
- `synthetic`: test-only material with no biological claim.

Unknown sign, neurotransmitter, laterality, endpoint, or mapping must remain explicit. Missing data must not silently become a behavioral rule.

## Required data audit

The initial interchange format is intentionally small:

- neurons CSV: required column `neuron_id`;
- synapses CSV: `pre,post,weight,kind`;
- `kind`: `excitatory`, `inhibitory`, or `unknown`;
- `weight`: positive anatomical or modeled magnitude; its biological meaning must be declared in dataset metadata.

`oraclarva-audit` rejects missing endpoints, non-positive weights, duplicate neuron IDs, and invalid signs. Duplicate edges and self-loops are reported for review rather than automatically deleted.

## Validation gates

1. **Identity:** stable IDs and reproducible source-to-model mappings.
2. **Numerics:** unit checks, deterministic fixtures, convergence tests, and Python/native parity.
3. **Neural:** firing statistics and stimulus responses compared with held-out recordings where available.
4. **Causal:** lesions or stimulation change downstream activity in predicted ways.
5. **Embodied:** motor output drives physics without direct action commands.
6. **Behavioral:** trajectories and response distributions match experimental data, including failures.

The synthetic three-neuron smoke circuit satisfies only a software causal-path test. It is not evidence of larval behavior.
