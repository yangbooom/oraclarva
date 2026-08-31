# Native numerical reference

This directory starts the mobile-core port with a dependency-free C++17 LIF
integrator. It consumes the same versioned TSV fixture as the Python oracle and
emits every step's spikes, membrane voltage, excitatory current, and inhibitory
current for parity checking.

The checked LIF fixture is synthetic and may only be used for numerical
regression. The second gate compiles the current provenance-aware research
configuration to `data/parity/closed_loop_native_v1.tsv`. The native executable
directly runs all 91 LIF neurons, 90 sparse synapses, continuous segment
activation, the 358-fiber aggregate identity proxy, 13-node XPBD body,
asymmetric ground contact, and shortening-sensitive proprioceptive feedback.
It matches Python in the normal, no-stimulus, A4 premotor-lesion, A4
muscle-lesion, and A1 motor-identity-lesion conditions.

The bilateral fixture adds a separate 126-neuron, 130-synapse C++17 path with
side-resolved sensory, premotor, inhibitory, motor, muscle, active-curvature,
local-tangent contact, and proprioceptive rail state. Symmetric, left, right,
zero-input, and three side-specific lesion cases match Python on every spike and
all 151 frames. The topology and all unmeasured gains remain research-only.

The repeat-crawl fixture executes the frozen Stage 6 approximation rather than
replaying its trajectory. It covers 164 LIF neurons, 307 delayed synapses,
sensory adaptation, body-shortening and recovery feedback, 144 mapped motor
sources, 146 named-fiber forces, the 13-node body, causal traces, and physical
cycle detection. Its 16 s normal run and five zero/lesion cases match exact
spikes and strict sampled-state tolerances. The checked report intentionally
retains `release_validated=false` and the held-out amplitude/duty failures.

Stage 8 adds `mobile_core.h/.cpp`: a C11-compatible, hidden-symbol lifecycle
around the same repeat state. It exposes environment-intensity advance,
deterministic reset, copied snapshot/trace/cycle state, and a separate read-only
watertight render mesh. `mobile_main.cpp` is a host acceptance and benchmark
harness. It does not expose a behavior command.

Passing these gates establishes numerical parity and a host-tested mobile
source boundary for the current research approximations. It does not establish
biological fidelity, held-out validation, measured individual muscle
mechanics, a complete L1 brain/VNC, an Android/iOS build, or device performance.

```bash
c++ -std=c++17 -O2 -Wall -Wextra -Werror \
  native/lif_core.cpp native/parity_main.cpp \
  -o /tmp/oraclarva-native-parity
/tmp/oraclarva-native-parity data/parity/lif_smoke_v0.tsv

c++ -std=c++17 -O2 -Wall -Wextra -Werror \
  native/lif_core.cpp native/organism_core.cpp native/organism_main.cpp \
  -o /tmp/oraclarva-native-organism
/tmp/oraclarva-native-organism data/parity/closed_loop_native_v1.tsv

c++ -std=c++17 -O2 -Wall -Wextra -Werror \
  native/lif_core.cpp native/bilateral_core.cpp native/bilateral_main.cpp \
  -o /tmp/oraclarva-native-bilateral
/tmp/oraclarva-native-bilateral data/parity/bilateral_native_v1.tsv \
  --left 1 --right 0

python tools/export_native_repeat_fixture.py --check
python tools/export_native_repeat_parity.py --check
c++ -std=c++17 -O2 -Wall -Wextra -Werror \
  native/lif_core.cpp native/repeat_core.cpp native/repeat_main.cpp \
  -o /tmp/oraclarva-native-repeat
/tmp/oraclarva-native-repeat data/parity/repeat_crawl_native_v1.tsv

python tools/build_mobile_core.py --output /tmp/oraclarva-mobile-build
/tmp/oraclarva-mobile-build/oraclarva-mobile-host \n  data/parity/repeat_crawl_native_v1.tsv
python tools/export_mobile_core_integration.py --check
python tools/benchmark_mobile_core.py --check
```
