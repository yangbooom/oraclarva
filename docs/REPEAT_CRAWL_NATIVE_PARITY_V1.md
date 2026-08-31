# Repeat-crawl native parity v1

## Result

Stage 7 ports the frozen Stage 6 repeat-crawl path to a dependency-free C++17
core. The native program computes the trajectory; it does not replay the
checked Python frames. Python and C++ consume the same generated fixture with
the frozen configuration SHA-256:

    5cbaec6a716cf2b8dd2d8e053b00469f5e9f09389fa74645c17a148143b936e3

Both implementations execute the same causal order:

    environment -> sensory transduction -> sparse LIF dynamics
      -> mapped motor neurons -> one-step muscle activation
      -> 146 named-fiber forces -> 13-node body physics -> environment

The 16 s normal run matches on all 164 neuron spike counts and first-spike
times, 535 sampled body frames, six segment activations, 13 node-force vectors,
three complete cycles, three physical waves, and causal ancestry for every
active-force frame. Exact spike matching and all declared numerical tolerances
pass.

This is numerical parity for a `research_approximation`. It is not biological
validation, native performance evidence, or a complete L1 brain/VNC. The same
frozen result still fails all six held-out segment-amplitude rows and all six
held-out duty rows, so `release_validated` remains `false`.

## Shared fixture and executed state

`data/parity/repeat_crawl_native_v1.tsv` is generated from the Python model and
contains:

- 164 LIF neurons and 307 sparse delayed synapses;
- 144 mapped motor sources and 146 named fibers;
- sensory adaptation, shortening relays, and A1 recovery feedback;
- activation, attachment, passive, damping, body, contact, and cycle-detector
  parameters;
- 13 body nodes, 12 mechanical segments, and the six A6-A1 wave segments.

The C++ core refuses a fixture whose schema, model ID, scientific status, or
frozen configuration hash differs. Its output declares
`release_validated=false` and includes every neuron's count/first spike, sampled
nodes, activation, node forces, premotor events, cycle metrics, and ordered
body-state-to-sensory-to-premotor-to-MN trace examples.

## Numerical acceptance

The checked report is
`data/parity/repeat_crawl_native_parity_v1.json`. Its ceilings and observed
maximum errors are:

| Quantity | Absolute tolerance | Observed maximum error |
|---|---:|---:|
| sample time (s) | 3e-15 | within tolerance |
| sampled node coordinate (um) | 5e-8 | 4.054254532093182e-8 |
| segment activation | 5.1e-10 | 4.993568614164445e-10 |
| node force (model units) | 2e-7 | 1.4525656721886548e-7 |
| summary scalar | 1e-8 | 1.988837539101951e-9 displacement |
| spike count | exact | exact for all 164 neurons |
| first-spike time (s) | 1e-15 | within tolerance |

The remaining summary errors are 0 s for median period,
1.091962076316122e-10 um for median stride, and
1.4788170688007085e-13 segment/s for physical wave speed. Tolerances are
absolute numerical-regression limits; they do not represent experimental
uncertainty.

## Lesion gates

The native and Python paths run the same five failure/causal cases in addition
to the normal 16 s trajectory:

| Case | Required result |
|---|---|
| no initial touch | no spikes, force, cycles, or displacement |
| A6 shortening-sensory lesion | initial A6 remains; A5 and later are absent |
| A4 premotor lesion | A6/A5 remain; A4 and later are absent |
| all mapped A6 MN lesion | A6 premotor remains; mapped MN force disappears |
| all A6 fiber lesion | premotor and MN spikes remain; A6 force disappears |

Invalid sensory, premotor, MN-segment, and fiber-segment lesion arguments fail
closed. All nonzero normal-run forces retain an ordered earlier sensory origin,
premotor spike, and mapped-MN spike.

## Reproduction

```bash
python tools/export_repeat_crawl_trajectory.py --check
python tools/evaluate_repeat_crawl.py --check
python tools/export_native_repeat_fixture.py --check
python tools/export_native_repeat_parity.py --check
python tools/render_native_repeat_parity_gif.py
pytest -q tests/test_native_repeat_parity.py
```

For direct execution:

```bash
c++ -std=c++17 -O2 -Wall -Wextra -Werror \
  native/lif_core.cpp native/repeat_core.cpp native/repeat_main.cpp \
  -o /tmp/oraclarva-native-repeat
/tmp/oraclarva-native-repeat data/parity/repeat_crawl_native_v1.tsv
```

The comparison GIF uses only the 51 paired body frames retained in the checked
parity report. It applies the same continuous render-skin construction to each
implementation and never changes their positions:

![Python and C++ repeat-crawl parity](assets/oraclarva_repeat_native_parity.gif)

GitHub Actions remains manual-only through `workflow_dispatch`; this gate is
verified locally and does not trigger CI.

## Stage 8 integration

Stage 8 now exposes this verified implementation through a stateful C11
lifecycle. The full stepped run exactly matches this one-shot gate, deterministic
reset replay passes, and a read-only watertight render projection remains
separate from the 13 physics nodes. See
`docs/MOBILE_CORE_INTEGRATION_V1.md`.

This does not change the native parity tolerances, frozen configuration, or
held-out failure. Android/iOS target builds and device measurements remain
future product work, and no app API may introduce `crawl`, `turn`, or other
direct behavior commands.
