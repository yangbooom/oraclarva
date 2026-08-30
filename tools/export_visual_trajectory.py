"""Generate deterministic trajectories for the L1 visual-connectome loop."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from oraclarva.artifacts import NUMERIC_TOLERANCE, first_mismatch
from oraclarva.visual import (
    L1VisualClosedLoopLarva,
    PHOTORECEPTOR_CLASSES,
    load_visual_config,
    load_visual_connectome,
    validation_light_field,
    visual_node_ids_for_class,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "data" / "trajectories" / "l1_visual_closed_loop_v0.json"
)
SAMPLE_INTERVAL_S = 0.03
DT_S = 0.001
DURATION_S = 1.5
READOUT_CLASSES = ("VPLN", "nc-LaN", "5th-LaN", "PVL09", "pOLP")


def _earliest(values: list[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return None if not available else round(min(available), 9)


def _first_spike_trace(result, connectome) -> dict[str, float | None]:
    visual = result.visual_first_spike_s
    body = result.spatial_result.first_spike_s
    photoreceptors = sum(
        (
            visual_node_ids_for_class(connectome, neuron_class)
            for neuron_class in PHOTORECEPTOR_CLASSES
        ),
        (),
    )
    local_classes = ("cha-lOLP", "glu-lOLP", "extra-glu-lOLP")
    local = sum(
        (visual_node_ids_for_class(connectome, item) for item in local_classes),
        (),
    )
    readouts = sum(
        (visual_node_ids_for_class(connectome, item) for item in READOUT_CLASSES),
        (),
    )
    return {
        "photoreceptor": _earliest([visual[item] for item in photoreceptors]),
        "local_interneuron": _earliest([visual[item] for item in local]),
        "visual_projection_readout": _earliest(
            [visual[item] for item in readouts]
        ),
        "fitted_descending_bridge": _earliest(
            [
                value
                for label, value in body.items()
                if label.startswith("visual_descending_bridge")
            ]
        ),
        "a7_premotor": _earliest(
            [
                value
                for label, value in body.items()
                if label.startswith("premotor_A27h_like:A7")
            ]
        ),
        "a7_motor": _earliest(
            [
                value
                for label, value in body.items()
                if label.startswith("motor_pool:A7")
            ]
        ),
    }


def _visual_frame_index(trajectory_index: int) -> int:
    if trajectory_index == 0:
        return 0
    return round(trajectory_index * SAMPLE_INTERVAL_S / DT_S) - 1


def _window_spike_counts(protocol, frame_index: int) -> dict[str, int]:
    first = max(0, frame_index - round(SAMPLE_INTERVAL_S / DT_S) + 1)
    counts = {
        f"{side}:{group}": 0
        for side in ("left", "right")
        for group in ("Rh5-PR", "Rh6-PR", "local", "readout")
    }
    for frame in protocol.frames[first : frame_index + 1]:
        for node_id in frame.spiked_neurons:
            metadata = protocol.metadata_by_id[node_id]
            side = metadata["lon_side"]
            neuron_class = metadata["neuron_class"]
            if neuron_class in PHOTORECEPTOR_CLASSES:
                group = neuron_class
            elif neuron_class in {"cha-lOLP", "glu-lOLP", "extra-glu-lOLP"}:
                group = "local"
            elif neuron_class in READOUT_CLASSES:
                group = "readout"
            else:
                continue
            counts[f"{side}:{group}"] += 1
    return counts


def _sampled_visual(protocol, trajectory_index: int) -> dict[str, Any]:
    frame_index = _visual_frame_index(trajectory_index)
    frame = protocol.frames[frame_index]
    transduction = frame.transduction
    return {
        "sample_time_s": round(transduction.time_s, 9),
        "sample_positions_um": {
            side: [
                round(position.x * 1e6, 9),
                round(position.y * 1e6, 9),
                round(position.z * 1e6, 9),
            ]
            for side, position in transduction.sample_positions_m.items()
        },
        "irradiance_w_m2": {
            side: round(value, 9)
            for side, value in transduction.irradiance_w_m2.items()
        },
        "adapted_irradiance_w_m2": {
            side: round(value, 9)
            for side, value in transduction.adapted_irradiance_w_m2.items()
        },
        "receptor_drive": {
            neuron_class: {
                side: round(value, 9) for side, value in values.items()
            }
            for neuron_class, values in transduction.receptor_drive.items()
        },
        "spike_counts_in_window": _window_spike_counts(protocol, frame_index),
        "bridge_activity": {
            side: round(value, 9)
            for side, value in frame.bridge_activity.items()
        },
        "bridge_stimulus": [
            round(value, 9) for value in frame.bridge_stimulus.values()
        ],
    }


def _summary(result) -> dict[str, Any]:
    body = result.spatial_result
    stimuli = [frame.bridge_stimulus.values() for frame in result.visual_frames]
    return {
        "visual_neuron_compartments": result.visual_neuron_compartments,
        "published_connection_pairs": result.published_connection_pairs,
        "published_synaptic_contacts": result.published_synaptic_contacts,
        "executed_connection_pairs": result.executed_connection_pairs,
        "executed_synaptic_contacts": result.executed_synaptic_contacts,
        "downstream_spatial_neurons": body.neuron_count,
        "downstream_spatial_synapses": body.synapse_count,
        "visual_spikes": sum(result.visual_spike_counts.values()),
        "downstream_spikes": sum(body.spike_counts.values()),
        "bridge_stimulus_min": round(
            min(min(values) for values in stimuli), 9
        ),
        "bridge_stimulus_max": round(
            max(max(values) for values in stimuli), 9
        ),
        "displacement_x_um": round(body.displacement_x_um, 9),
        "displacement_y_um": round(body.displacement_y_um, 9),
        "displacement_z_um": round(body.displacement_z_um, 9),
        "yaw_change_deg": round(body.yaw_change_deg, 9),
        "head_pitch_change_deg": round(body.head_pitch_change_deg, 9),
    }


def render_trajectory() -> str:
    config = load_visual_config()
    connectome = load_visual_connectome()
    all_readouts = sum(
        (visual_node_ids_for_class(connectome, item) for item in READOUT_CLASSES),
        (),
    )
    scenario_specs = (
        ("brighter_right_intact", 1.0, ()),
        ("brighter_left_intact", -1.0, ()),
        ("brighter_right_readout_lesion", 1.0, all_readouts),
    )
    scenarios = []
    for scenario_id, lateral_sign, lesions in scenario_specs:
        organism = L1VisualClosedLoopLarva(
            field=validation_light_field(config, lateral_sign=lateral_sign),
            config=config,
            connectome=connectome,
            lesion_node_ids=lesions,
            ground_z_m=None,
            record_visual_frames=True,
        )
        result = organism.run(
            duration_s=DURATION_S,
            record_trajectory_interval_s=SAMPLE_INTERVAL_S,
        )
        frames = []
        for index, trajectory_frame in enumerate(
            result.spatial_result.trajectory_samples
        ):
            frame = dict(trajectory_frame)
            frame["visual_input"] = _sampled_visual(
                organism.protocol, index
            )
            frames.append(frame)
        scenarios.append(
            {
                "id": scenario_id,
                "lateral_gradient_sign": lateral_sign,
                "lesion_node_ids": list(lesions),
                "summary": _summary(result),
                "first_spike_trace_s": _first_spike_trace(
                    result, connectome
                ),
                "frames": frames,
            }
        )

    artifact = {
        "schema_version": 1,
        "model_id": config["model_id"],
        "status": config["status"],
        "stage": config["stage"],
        "release_validated": False,
        "sample_interval_s": SAMPLE_INTERVAL_S,
        "duration_s": DURATION_S,
        "node_count": 13,
        "source": connectome["source"],
        "published_connectome_summary": connectome["summary"],
        "phototransduction": config["phototransduction"],
        "lon_dynamics": config["lon_dynamics"],
        "descending_bridge": config["descending_bridge"],
        "validation_light_field": config["validation_light_field"],
        "scenarios": scenarios,
        "limitations": config["limitations"]
        + [
            "The diagnostic renderer reads these checked physical-node frames "
            "and never authors body motion.",
            "The intact left/right scenarios test causal sign reversal; their "
            "near balance is fitted and is not held-out behavioral validation.",
            "The readout lesion is a neural intervention, not a fallback action "
            "or scripted stop command.",
        ],
    }
    return json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic L1 visual-connectome trajectories"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_trajectory()
    if args.check:
        if not args.output.exists():
            print(f"generated visual trajectory is stale: {args.output}")
            return 1
        expected = json.loads(args.output.read_text(encoding="utf-8"))
        actual = json.loads(rendered)
        mismatch = first_mismatch(expected, actual)
        if mismatch:
            print(
                f"generated visual trajectory is stale: {args.output}: "
                f"{mismatch}"
            )
            return 1
        print(
            "generated visual trajectory is current "
            f"(numeric tolerance {NUMERIC_TOLERANCE:g})"
        )
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
