"""Synthetic causal smoke circuit; this is not biological data."""

from __future__ import annotations

import json

from .lif import SparseLIFNetwork, Synapse


SENSORY, INTERNEURON, MOTOR = 0, 1, 2


def run_smoke(*, lesion_interneuron: bool = False) -> dict[str, int]:
    network = SparseLIFNetwork(
        3,
        [
            Synapse(SENSORY, INTERNEURON, 1.25e-9),
            Synapse(INTERNEURON, MOTOR, 1.25e-9),
        ],
    )
    if lesion_interneuron:
        network.lesion([INTERNEURON])
    stimulus = {step: {SENSORY: 4e-9} for step in range(0, 40, 4)}
    events = network.run(50, stimulus)
    counts = {"sensory": 0, "interneuron": 0, "motor": 0}
    labels = ("sensory", "interneuron", "motor")
    for spikes in events:
        for neuron_id in spikes:
            counts[labels[neuron_id]] += 1
    return counts


def main() -> int:
    normal = run_smoke()
    lesioned = run_smoke(lesion_interneuron=True)
    print(json.dumps({"normal": normal, "interneuron_lesion": lesioned}, indent=2))
    return 0 if normal["motor"] > 0 and lesioned["motor"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
