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

Passing these gates establishes numerical parity for the current research
approximation. It does not establish biological fidelity, held-out validation,
individual muscle mechanics, a complete L1 brain/VNC, or mobile performance.

```bash
c++ -std=c++17 -O2 -Wall -Wextra -Werror \
  native/lif_core.cpp native/parity_main.cpp \
  -o /tmp/oraclarva-native-parity
/tmp/oraclarva-native-parity data/parity/lif_smoke_v0.tsv

c++ -std=c++17 -O2 -Wall -Wextra -Werror \
  native/lif_core.cpp native/organism_core.cpp native/organism_main.cpp \
  -o /tmp/oraclarva-native-organism
/tmp/oraclarva-native-organism data/parity/closed_loop_native_v1.tsv
```
