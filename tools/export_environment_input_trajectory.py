"""Generate deterministic light, temperature, and odor input trajectories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from oraclarva.artifacts import NUMERIC_TOLERANCE, first_mismatch
from oraclarva.environment_inputs import (
    MODALITIES,
    MultimodalFieldTransduction,
    load_environment_input_config,
    validation_fields,
)
from oraclarva.spatial import SpatialClosedLoopLarva


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "data" / "trajectories" / "l1_environment_inputs_v0.json"
)
SAMPLE_INTERVAL_S = 0.03
DT_S = 0.001
def summary(result, protocol) -> dict[str, float | int]:
    stimuli = [frame.stimulus.values() for frame in protocol.frames]
    return {
        "neuron_count": result.neuron_count,
        "synapse_count": result.synapse_count,
        "displacement_x_um": round(result.displacement_x_um, 9),
        "displacement_y_um": round(result.displacement_y_um, 9),
        "displacement_z_um": round(result.displacement_z_um, 9),
        "yaw_change_deg": round(result.yaw_change_deg, 9),
        "head_pitch_change_deg": round(result.head_pitch_change_deg, 9),
        "total_spikes": sum(result.spike_counts.values()),
        "stimulus_min": round(min(min(value) for value in stimuli), 9),
        "stimulus_max": round(max(max(value) for value in stimuli), 9),
    }


def sampled_input(protocol, trajectory_index: int) -> dict[str, Any]:
    protocol_index = (
        0
        if trajectory_index == 0
        else round(trajectory_index * SAMPLE_INTERVAL_S / DT_S) - 1
    )
    frame = protocol.frames[protocol_index]
    return {
        "sample_time_s": round(frame.time_s, 9),
        "raw_values": {
            key: [round(value, 9) for value in values]
            for key, values in frame.raw_values.items()
        },
        "adapted_values": {
            key: [round(value, 9) for value in values]
            for key, values in frame.adapted_values.items()
        },
        "drive_values": {
            key: [round(value, 9) for value in values]
            for key, values in frame.drive_values.items()
        },
        "stimulus": [round(value, 9) for value in frame.stimulus.values()],
    }


def render_trajectory() -> str:
    config = load_environment_input_config()
    scenarios = []
    for modality in MODALITIES:
        fields = validation_fields(modalities=(modality,))
        protocol = MultimodalFieldTransduction.from_config(
            fields,
            enabled_modalities=(modality,),
            record_frames=True,
        )
        result = SpatialClosedLoopLarva(ground_z_m=None).run(
            stimulus_protocol=protocol,
            record_trajectory_interval_s=SAMPLE_INTERVAL_S,
        )
        frames = []
        for index, trajectory_frame in enumerate(result.trajectory_samples):
            frame = dict(trajectory_frame)
            frame["environment_input"] = sampled_input(protocol, index)
            frames.append(frame)
        scenarios.append({
            "id": f"{modality}_linear_field",
            "modality": modality,
            "field": config["validation_fields"][modality],
            "transduction": config["transduction"][modality],
            "summary": summary(result, protocol),
            "frames": frames,
        })

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "model_id": config["model_id"],
        "status": config["status"],
        "release_validated": False,
        "units": {
            "time": "second",
            "position": "micrometre",
        },
        "sample_interval_s": SAMPLE_INTERVAL_S,
        "node_count": 13,
        "channels": ["left", "right", "dorsal", "ventral"],
        "scenarios": scenarios,
        "limitations": config["limitations"] + [
            "The diagnostic renderer reads checked physical-node frames and "
            "does not author motion.",
            "These three deterministic fixtures test integration and symmetry; "
            "they are not held-out natural-taxis validation.",
        ],
    }
    return json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic multimodal environment trajectories"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_trajectory()
    if args.check:
        if not args.output.exists():
            print(f"generated environment input trajectory is stale: {args.output}")
            return 1
        expected = json.loads(args.output.read_text())
        actual = json.loads(rendered)
        mismatch = first_mismatch(expected, actual)
        if mismatch:
            print(
                f"generated environment input trajectory is stale: "
                f"{args.output}: {mismatch}"
            )
            return 1
        print(
            "generated environment input trajectory is current "
            f"(numeric tolerance {NUMERIC_TOLERANCE:g})"
        )
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
