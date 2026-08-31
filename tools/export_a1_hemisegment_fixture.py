"""Export the checked isolated A1-left attachment/mechanics fixture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from oraclarva.artifacts import first_mismatch
from oraclarva.hemisegment import (
    IsolatedA1HemisegmentMechanics,
    load_a1_hemisegment_spec,
)
from oraclarva.muscles import (
    NeuralMuscleActivationModel,
    load_neural_muscle_identity_projection,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "data" / "trajectories" / "l1_a1_left_hemisegment_mechanics_v0.json"
)
DURATION_STEPS = 600
SAMPLE_EVERY_STEPS = 10
TARGET = "A1:left:M1:DA1"
SIBLING = "A1:left:M10:DO2"


def _rounded(value: float) -> float:
    return round(value, 9)


def _run(*, lesion_target: bool) -> dict[str, Any]:
    spec = load_a1_hemisegment_spec()
    projection = load_neural_muscle_identity_projection()
    mappings = {
        item.fiber_id: item
        for item in projection.mappings
        if item.fiber_id in {TARGET, SIBLING}
    }
    if set(mappings) != {TARGET, SIBLING}:
        raise ValueError("checked A1 targets must have observed neural mappings")
    activation = NeuralMuscleActivationModel(
        projection=projection,
        dt_s=spec.dt_s,
        rise_tau_s=0.020,
        decay_tau_s=0.080,
        event_target=1.0,
    )
    mechanics = IsolatedA1HemisegmentMechanics(spec)
    first_spike: dict[str, float | None] = {TARGET: None, SIBLING: None}
    first_activation: dict[str, float | None] = {TARGET: None, SIBLING: None}
    first_shortening: dict[str, float | None] = {TARGET: None, SIBLING: None}
    peak_activation = {TARGET: 0.0, SIBLING: 0.0}
    peak_shortening = {TARGET: 0.0, SIBLING: 0.0}
    samples = []
    trace_source = {
        fiber_id: mapping.source_node_id for fiber_id, mapping in mappings.items()
    }
    trace_provenance = {
        fiber_id: mapping.mapping_provenance for fiber_id, mapping in mappings.items()
    }

    for step in range(DURATION_STEPS):
        time_s = step * spec.dt_s
        spiked = []
        if 50 <= step < 200 and step % 5 == 0:
            spiked.append(mappings[TARGET].source_node_id)
            if first_spike[TARGET] is None:
                first_spike[TARGET] = time_s
        if 180 <= step < 330 and step % 7 == 0:
            spiked.append(mappings[SIBLING].source_node_id)
            if first_spike[SIBLING] is None:
                first_spike[SIBLING] = time_s
        events = projection.emit(spiked)
        activation_frame = activation.step(time_s, events)
        mechanics_frame = mechanics.step_activation_frame(
            activation_frame,
            lesioned_fiber_ids=(TARGET,) if lesion_target else (),
            source_by_fiber=trace_source,
            mapping_provenance_by_fiber=trace_provenance,
        )
        for fiber_id in (TARGET, SIBLING):
            activation_value = activation_frame.activations[fiber_id]
            shortening = mechanics_frame.fibers[fiber_id].shortening_body_units
            peak_activation[fiber_id] = max(peak_activation[fiber_id], activation_value)
            peak_shortening[fiber_id] = max(peak_shortening[fiber_id], shortening)
            if activation_value > 0.0 and first_activation[fiber_id] is None:
                first_activation[fiber_id] = time_s
            if shortening > 0.0 and first_shortening[fiber_id] is None:
                first_shortening[fiber_id] = time_s
        if step % SAMPLE_EVERY_STEPS == 0:
            samples.append(
                {
                    "time_s": _rounded(time_s),
                    "target_activation": _rounded(
                        activation_frame.activations[TARGET]
                    ),
                    "target_shortening_fraction": _rounded(
                        mechanics_frame.fibers[TARGET].shortening_fraction
                    ),
                    "sibling_activation": _rounded(
                        activation_frame.activations[SIBLING]
                    ),
                    "sibling_shortening_fraction": _rounded(
                        mechanics_frame.fibers[SIBLING].shortening_fraction
                    ),
                    "deformed_fiber_count": mechanics_frame.deformed_fiber_count,
                }
            )

    return {
        "scenario": "target_mechanics_lesion" if lesion_target else "control",
        "lesioned_fibers": [TARGET] if lesion_target else [],
        "upstream_sources": trace_source,
        "mapping_provenance": trace_provenance,
        "first_spike_s": {
            key: None if value is None else _rounded(value)
            for key, value in first_spike.items()
        },
        "first_activation_s": {
            key: None if value is None else _rounded(value)
            for key, value in first_activation.items()
        },
        "first_shortening_s": {
            key: None if value is None else _rounded(value)
            for key, value in first_shortening.items()
        },
        "peak_activation": {
            key: _rounded(value) for key, value in peak_activation.items()
        },
        "peak_shortening_body_units": {
            key: _rounded(value) for key, value in peak_shortening.items()
        },
        "frames": samples,
    }


def _zero_input_summary() -> dict[str, Any]:
    model = IsolatedA1HemisegmentMechanics(load_a1_hemisegment_spec())
    frame = None
    for step in range(DURATION_STEPS):
        frame = model.step(step * model.spec.dt_s, {})
    assert frame is not None
    return {
        "duration_s": _rounded((DURATION_STEPS - 1) * model.spec.dt_s),
        "deformed_fiber_count": frame.deformed_fiber_count,
        "maximum_shortening_fraction": frame.maximum_shortening_fraction,
        "exact_equilibrium": frame.deformed_fiber_count == 0,
    }


def build_artifact() -> dict[str, Any]:
    spec = load_a1_hemisegment_spec()
    model = IsolatedA1HemisegmentMechanics(spec)
    geometry = []
    for item in model.geometries:
        geometry.append(
            {
                "fiber_id": item.fiber_id,
                "muscle_number": item.muscle_number,
                "synonym": item.synonym,
                "spatial_group": item.spatial_group,
                "origin": {
                    "s": _rounded(item.origin.s),
                    "theta_rad": _rounded(item.origin.theta_rad),
                    "d": _rounded(item.origin.depth_fraction),
                },
                "insertion": {
                    "s": _rounded(item.insertion.s),
                    "theta_rad": _rounded(item.insertion.theta_rad),
                    "d": _rounded(item.insertion.depth_fraction),
                },
                "rest_length_body_units": _rounded(item.rest_length_body_units),
                "line_of_action": [_rounded(value) for value in item.line_of_action],
                "coordinate_provenance": item.coordinate_provenance,
                "rest_length_provenance": item.rest_length_provenance,
                "quantitative_image_coordinates_used": False,
                "individual_layer_claimed": False,
            }
        )
    control = _run(lesion_target=False)
    lesion = _run(lesion_target=True)
    target_first_spike = control["first_spike_s"][TARGET]
    target_first_activation = control["first_activation_s"][TARGET]
    target_first_shortening = control["first_shortening_s"][TARGET]
    if not (
        target_first_spike is not None
        and target_first_activation is not None
        and target_first_shortening is not None
        and target_first_spike < target_first_activation <= target_first_shortening
    ):
        raise ValueError("checked causal order is invalid")
    if lesion["peak_activation"][TARGET] != control["peak_activation"][TARGET]:
        raise ValueError("mechanics lesion must preserve upstream activation")
    if lesion["peak_shortening_body_units"][TARGET] != 0.0:
        raise ValueError("mechanics lesion must prevent target shortening")
    return {
        "schema_version": 1,
        "model_id": spec.model_id,
        "status": spec.status,
        "stage": "L1",
        "scope": "isolated_A1_left_hemisegment",
        "causal_contract": [
            "motor_identity_spike",
            "one_step_delayed_muscle_activation",
            "active_tension",
            "passive_elasticity_and_damping",
            "fiber_shortening",
        ],
        "claim_boundary": {
            "coordinate_unit": "normalized_body_unit",
            "force_unit": "model_unit_not_newton",
            "absolute_scale_claimed": False,
            "measured_attachment_claimed": False,
            "csa_claimed": False,
            "fmax_claimed": False,
            "full_body_motion_executed": False,
        },
        "parameter_provenance": {
            "attachments": "ANATOMY_DERIVED",
            "rest_length": "ANATOMY_DERIVED",
            "mechanics": "MODEL_FITTED",
            "observed_A1_neural_muscle_mapping": "MEASURED_PUBLISHED",
        },
        "dt_s": spec.dt_s,
        "sample_interval_s": spec.dt_s * SAMPLE_EVERY_STEPS,
        "fiber_count": len(geometry),
        "geometry": geometry,
        "zero_input": _zero_input_summary(),
        "scenarios": [control, lesion],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    artifact = build_artifact()
    if args.check:
        if not args.output.exists():
            print(f"missing checked artifact: {args.output}")
            return 1
        mismatch = first_mismatch(json.loads(args.output.read_text()), artifact)
        if mismatch:
            print(mismatch)
            return 1
        print(f"checked artifact is current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
