"""Export the evidence-bounded bidirectional axial-locomotion diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from oraclarva.axial import (
    AxialLocomotionLarva,
    default_axial_locomotion_path,
    load_axial_locomotion_config,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "data" / "trajectories" / "l1_axial_locomotion_v1.json"
)
SAMPLE_INTERVAL_S = 0.005


def result_mapping(result) -> dict[str, Any]:
    return {
        "duration_s": result.duration_s,
        "displacement_x_um": result.displacement_x_um,
        "anatomical_forward_displacement_um": (
            result.anatomical_forward_displacement_um
        ),
        "stimulus": dict(result.stimulus),
        "spike_counts": dict(result.spike_counts),
        "first_spike_s": dict(result.first_spike_s),
        "premotor_spike_times_s": result.premotor_spike_times_s,
        "relaxation_spike_times_s": result.relaxation_spike_times_s,
        "motor_spike_times_s": result.motor_spike_times_s,
        "contact_retention_range": result.contact_retention_range,
        "contact_direction_input": result.contact_direction_input,
        "feedback_force_frames": result.feedback_force_frames,
        "all_active_forces_sensory_traced": (
            result.all_active_forces_sensory_traced
        ),
        "causal_trace_examples": result.causal_trace_examples,
        "t3_contact_proxy_peak_activation": (
            result.t3_contact_proxy_peak_activation
        ),
        "t3_contact_proxy_neural_traced": (
            result.t3_contact_proxy_neural_traced
        ),
        "trajectory_samples": result.trajectory_samples,
        "release_validated": result.release_validated,
    }


def build_artifact() -> dict[str, Any]:
    config_path = default_axial_locomotion_path()
    config = load_axial_locomotion_config(config_path)
    forward_larva = AxialLocomotionLarva(config)
    backward_larva = AxialLocomotionLarva(config)
    forward = forward_larva.run(
        posterior_touch=True,
        record_trajectory_interval_s=SAMPLE_INTERVAL_S,
    )
    backward = backward_larva.run(
        anterior_touch=True,
        record_trajectory_interval_s=SAMPLE_INTERVAL_S,
    )
    return {
        "schema": "oraclarva.axial_locomotion.v1",
        "model_id": config["model_id"],
        "status": config["status"],
        "stage": config["stage"],
        "release_validated": False,
        "causal_contract": config["causal_contract"],
        "generated_from": {
            "config": str(config_path.relative_to(ROOT)),
            "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        },
        "action_command": False,
        "behavior_fsm": False,
        "external_policy": False,
        "shared_mapped_fiber_count": len(forward_larva.projection.mappings),
        "sample_interval_s": SAMPLE_INTERVAL_S,
        "body_segment_ids": [
            item.id for item in forward_larva.body.geometry
        ],
        "continuous_ground_contact": {
            "model_id": config["continuous_ground_contact"]["model_id"],
            "provenance": config["continuous_ground_contact"]["provenance"],
            "movement_direction_input": False,
            "equation": config["continuous_ground_contact"]["equation"],
            "t3_backward_contact_proxy": config["continuous_ground_contact"][
                "t3_backward_contact_proxy"
            ],
        },
        "forward": result_mapping(forward),
        "backward": result_mapping(backward),
        "claim_limit": config["validation"]["claim_limit"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = json.dumps(
        build_artifact(),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            print(f"generated axial trajectory is stale: {args.output}")
            return 1
        print("generated axial trajectory is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
