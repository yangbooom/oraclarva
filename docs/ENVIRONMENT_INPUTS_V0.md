# Multimodal environment inputs v0

This research extension turns local light, temperature, and odor fields into
auditable neural input. It does not add a target selector, action command,
finite-state machine, behavior tree, policy network, or renderer-authored
motion.

The executed chain is:

```text
analytic scalar field at physical position and time
  -> left/right/dorsal/ventral head-surface samples
  -> spatial contrast + adapted temporal contrast
  -> four bounded receptor currents
  -> 168 sparse LIF neurons / 188 synapses
  -> opposed motor pools and aggregate muscle identities
  -> yaw/pitch XPBD body physics
  -> next physical sample position
```

Every checked trajectory frame stores the raw field samples, the adaptation
state used for that step, each modality's signed drive, the four final receptor
currents, and the resulting 13 physical body nodes.

## Evidence and stage boundary

- Larderet et al. reconstructed the bilateral visual input circuit from a
  first-instar CNS ssTEM volume. The two photoreceptor classes form pathways
  capable of carrying ambient and temporal light information
  ([DOI 10.7554/eLife.28387](https://doi.org/10.7554/eLife.28387)).
- Berck et al. reconstructed the complete first-instar larval antennal lobe and
  identified canonical and multiglomerular paths with gain-control structure
  ([DOI 10.7554/eLife.14859](https://doi.org/10.7554/eLife.14859)).
- Luo et al. tracked first-instar larvae on 0.5 degC/cm linear thermal
  gradients and found navigation depends on temporal changes in temperature
  ([DOI 10.1523/JNEUROSCI.4090-09.2010](https://doi.org/10.1523/JNEUROSCI.4090-09.2010)).
- Kane et al. support temporal light comparison and directional context from
  the Bolwig organ, but their behavior experiments used L2. No absolute light
  response is copied into this L1 model
  ([DOI 10.1073/pnas.1215295110](https://doi.org/10.1073/pnas.1215295110)).
- Gershow et al. found L2 odor navigation relies on temporal concentration
  changes rather than direct bilateral gradient measurement. This is a
  response-structure prior only
  ([DOI 10.1038/nmeth.1853](https://doi.org/10.1038/nmeth.1853)).

The L1 visual and olfactory sources support sensory topology, not the numeric
transducer below. The L2 sources cannot supply L1 stimulus-response constants.

## Analytic fields

The current field primitive is linear in space and time:

```text
q(x, t) = clamp(q0 + gradient dot (x - x0) + temporal_rate * t)
```

`q` retains its declared unit: `W_m-2`, `degC`, or
`normalized_concentration`. Sampling a field never produces a heading or body
command.

The validation fixtures are:

| modality | origin value | gradient | polarity |
|---|---:|---:|---|
| light | 4 W/m2 | (0, 6000, 6000) W/m3 | increasing excites |
| temperature | 18 degC | (50, 0, 0) degC/m | decreasing excites |
| odor | 0.5 normalized | (500, 0, 0) /m | decreasing excites |

The thermal gradient magnitude is the 0.5 degC/cm L1 assay context. Its virtual
orientation, origin temperature, field bounds, and every light/odor fixture
value remain `MODEL_FITTED` diagnostics.

## Adaptive transduction

For modality `m`, receptor channel `i`, and the four-sample spatial mean
`mean(q_m)`, the unbounded drive is:

```text
d_mi = weight_m * polarity_m * (
    spatial_gain_m * (q_mi - mean(q_m)) / response_scale_m
  + temporal_gain_m * (q_mi - adapted_mi) / response_scale_m
)
```

The adaptation state is a first-order low-pass value:

```text
adapted(t + dt) = adapted(t)
  + (q(t) - adapted(t)) * (1 - exp(-dt / tau))
```

Modal drives sum before a single bounded receptor output:

```text
I_i = clamp(baseline + sum_m(d_mi), 0, 1)
```

The current baseline is 0.5. Response scales are 4 W/m2, 0.02 degC, and 0.2
normalized concentration. All baselines, polarities, gains, scales, weights,
and adaptation time constants are `MODEL_FITTED`; none is claimed as a
measured L1 receptor constant.

Only light currently uses a spatial-contrast term, reflecting the directional
context of the Bolwig organ. Temperature and odor set spatial gain to zero and
use temporal contrast only. They therefore do not acquire an invented direct
bilateral gradient sense; modality-specific run-turn and head-sweep circuits
remain future work.

## Checked regression scenarios

The checked artifact contains 151 frames at 30 ms for each 4.5-second field
fixture. Receptor currents remain analog rather than saturating at 0 or 1.
The regeneration gate requires exact JSON schema, keys, strings, booleans, and
integers; floating-point values use a 1e-8 absolute tolerance to accommodate
the final decimal differences between supported Python runtimes.

| field | current range | dx (um) | dy (um) | dz (um) | yaw | pitch |
|---|---:|---:|---:|---:|---:|---:|
| light | 0.416–0.628 | +2.151 | +2.754 | +18.824 | -0.553 deg | -5.993 deg |
| temperature | 0.406–0.587 | +4.663 | 0.000 | +21.306 | 0.000 deg | -4.762 deg |
| odor | 0.376–0.579 | +4.772 | 0.000 | +19.749 | 0.000 deg | -5.251 deg |

A separate two-second symmetry test reverses a pure lateral light gradient.
The two runs produce equal x/z displacement, pitch, and total spike count while
y displacement and yaw reverse exactly within 1e-9 tolerance. Thus field
coordinates enter through receptor samples rather than a hidden screen-space
turn instruction.

![Light, temperature, and odor field input](assets/oraclarva_environment_inputs.gif)

## Reproduce

```bash
oraclarva-environment-input --modality light --free
oraclarva-environment-input --modality temperature --free
oraclarva-environment-input --modality odor --free
python tools/export_environment_input_trajectory.py --check
python tools/render_environment_input_gif.py
pytest tests/test_environment_inputs.py tests/test_sources.py
```

## Claim boundary and next scientific step

This is a provenance-aware multimodal input front end, not validated natural
L1 phototaxis, thermotaxis, or chemotaxis. The four probes are virtual surface
samples rather than measured sensory-organ coordinates. The reduced downstream
network does not yet contain modality-specific receptor populations, complete
sensory-to-descending paths, stochastic run-turn transitions, or a measured
head-sweep acceptance circuit.

The identified-neuron step is now implemented for light in
`L1_VISUAL_CONNECTOME_LOOP_V0.md`: bilateral Rh5/Rh6 and published L1 LON
contacts replace the four anonymous light probes. The published visual source
still ends before an identified VNC-premotor route, so that successor model
keeps a declared fitted bridge. Temperature and odor remain at the shared input
stage described here. These trajectories validate causal integration, units,
adaptation, provenance, and symmetry—not biological taxis performance.
