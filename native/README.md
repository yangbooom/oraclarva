# Native numerical reference

This directory starts the mobile-core port with a dependency-free C++17 LIF
integrator. It consumes the same versioned TSV fixture as the Python oracle and
emits every step's spikes, membrane voltage, excitatory current, and inhibitory
current for parity checking.

The checked fixture is synthetic and may only be used for numerical regression.
Passing it does not validate the 91-neuron research approximation, muscles,
XPBD body, mobile performance, or biological fidelity. Those require additional
fixtures before this code can replace the Python reference.

```bash
c++ -std=c++17 -O2 -Wall -Wextra -Werror \
  native/lif_core.cpp native/parity_main.cpp \
  -o /tmp/oraclarva-native-parity
/tmp/oraclarva-native-parity data/parity/lif_smoke_v0.tsv
```
