#!/usr/bin/env python3
"""Export oriented-section body mechanics v2 invariant evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from oraclarva.oriented_mechanics import (
    OrientedBodyMechanicsFixture,
    default_oriented_body_mechanics_path,
    load_oriented_body_mechanics_config,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data/validation/oriented_body_mechanics_v2.json"
FROZEN_V1 = ROOT / "data/trajectories/l1_named_fiber_steering_v1.json"
ATTACHMENT_SPEC = (
    ROOT / "data/muscles/l1_a1_left_hemisegment_mechanics_v0.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vector(value) -> list[float]:
    return [value.x, value.y, value.z]


def result_mapping(result) -> dict[str, Any]:
    return {
        "scenario": result.scenario,
        "duration_s": result.duration_s,
        "active_load_samples": result.active_load_samples,
        "traced_load_samples": result.traced_load_samples,
        "endpoint_application_samples": result.endpoint_application_samples,
        "maximum_net_force_model_units": (
            result.maximum_net_force_model_units
        ),
        "maximum_centerline_force_moment_model_units_m": (
            result.maximum_centerline_force_moment_model_units_m
        ),
        "maximum_net_generalized_torque_model_units_m": (
            result.maximum_net_generalized_torque_model_units_m
        ),
        "maximum_abs_section_twist_deg": (
            result.maximum_abs_section_twist_deg
        ),
        "maximum_abs_twist_gradient_deg": (
            result.maximum_abs_twist_gradient_deg
        ),
        "maximum_segment_extension_fraction": (
            result.maximum_segment_extension_fraction
        ),
        "final_center_m": vector(result.final_center_m),
        "final_nodes_m": [vector(value) for value in result.final_nodes_m],
        "final_twist_deg": result.final_twist_deg,
        "trace_examples": result.trace_examples,
        "trajectory_samples": result.trajectory_samples,
    }


def build_artifact() -> dict[str, Any]:
    config_path = default_oriented_body_mechanics_path()
    config = load_oriented_body_mechanics_config(config_path)
    fixtures = {
        name: OrientedBodyMechanicsFixture(config)
        for name in ("uniform", "left", "right")
    }
    results = {name: fixture.run(name) for name, fixture in fixtures.items()}
    target = str(config["parameters"]["fixture_fiber_pair"][0])
    lesion = OrientedBodyMechanicsFixture(
        config, lesioned_fiber_ids=(target,)
    ).run("left")
    left = results["left"]
    right = results["right"]
    mirror_node_error_um = max(
        (
            (left_node.x - right_node.x) ** 2
            + (left_node.y + right_node.y) ** 2
            + (left_node.z - right_node.z) ** 2
        )
        ** 0.5
        * 1e6
        for left_node, right_node in zip(
            left.final_nodes_m, right.final_nodes_m, strict=True
        )
    )
    mirror_twist_error_deg = max(
        abs(left_value + right_value)
        for left_value, right_value in zip(
            left.final_twist_deg, right.final_twist_deg, strict=True
        )
    )
    gates = config["validation"]["gates"]
    maximum_frame_orthogonality_error = 0.0
    for fixture in fixtures.values():
        for index in range(len(fixture.body.sections)):
            frame = fixture.body.material_frame(index)
            maximum_frame_orthogonality_error = max(
                maximum_frame_orthogonality_error,
                abs(frame.tangent.norm() - 1.0),
                abs(frame.lateral.norm() - 1.0),
                abs(frame.dorsal.norm() - 1.0),
                abs(frame.tangent.dot(frame.lateral)),
                abs(frame.tangent.dot(frame.dorsal)),
                abs(frame.lateral.dot(frame.dorsal)),
                (frame.tangent.cross(frame.lateral) - frame.dorsal).norm(),
            )
    comparisons = {
        "uniform_has_no_differential_load": (
            results["uniform"].active_load_samples == 0
            and results["uniform"].maximum_abs_section_twist_deg == 0.0
        ),
        "left_and_right_are_mirror_covariant": (
            mirror_node_error_um
            <= float(gates["mirror_position_tolerance_um"])
            and mirror_twist_error_deg
            <= float(gates["mirror_twist_tolerance_deg"])
        ),
        "left_lesion_removes_mechanics": (
            lesion.active_load_samples == 0
            and lesion.maximum_abs_section_twist_deg == 0.0
        ),
    }
    invariant_gates = {
        "all_active_loads_are_traced": all(
            result.active_load_samples == result.traced_load_samples
            for result in (left, right)
        ),
        "two_endpoints_per_active_fiber": all(
            result.endpoint_application_samples
            == 2 * result.active_load_samples
            for result in (left, right)
        ),
        "net_internal_force_is_zero": all(
            result.maximum_net_force_model_units
            <= float(gates["maximum_net_force_model_units"])
            for result in (left, right)
        ),
        "net_generalized_internal_torque_is_zero": all(
            result.maximum_net_generalized_torque_model_units_m
            <= float(
                gates["maximum_net_generalized_torque_model_units_m"]
            )
            for result in (left, right)
        ),
        "discarded_centerline_moment_is_observable": all(
            result.maximum_centerline_force_moment_model_units_m > 0.0
            for result in (left, right)
        ),
        "twist_is_bounded_and_nonzero": all(
            float(gates["minimum_abs_section_twist_deg"])
            <= result.maximum_abs_section_twist_deg
            <= float(gates["maximum_abs_section_twist_deg"])
            for result in (left, right)
        ),
        "material_frames_remain_orthonormal": (
            maximum_frame_orthogonality_error
            <= float(gates["maximum_frame_orthogonality_error"])
        ),
        "segment_extension_is_bounded": all(
            result.maximum_segment_extension_fraction
            <= float(gates["maximum_segment_extension_fraction"])
            for result in results.values()
        ),
    }
    passed = all((*comparisons.values(), *invariant_gates.values()))
    return {
        "schema": "oraclarva.oriented_body_mechanics.v2",
        "model_id": config["model_id"],
        "status": (
            "engineering_gates_passed"
            if passed
            else "engineering_gates_failed"
        ),
        "passed": passed,
        "release_validated": False,
        "independent_biological_validation": False,
        "scope": config["scope"],
        "generated_from": {
            "config": str(config_path.relative_to(ROOT)),
            "config_sha256": sha256(config_path),
            "attachment_spec": str(ATTACHMENT_SPEC.relative_to(ROOT)),
            "attachment_spec_sha256": sha256(ATTACHMENT_SPEC),
            "frozen_named_fiber_v1": str(FROZEN_V1.relative_to(ROOT)),
            "frozen_named_fiber_v1_sha256": sha256(FROZEN_V1),
        },
        "force_unit": "model_unit_not_newton",
        "torque_unit": "model_unit_m_not_newton_metre",
        "attachment_coordinate_provenance": "ANATOMY_DERIVED",
        "mechanics_parameter_provenance": "MODEL_FITTED",
        "mirror_node_error_um": mirror_node_error_um,
        "mirror_twist_error_deg": mirror_twist_error_deg,
        "maximum_frame_orthogonality_error": (
            maximum_frame_orthogonality_error
        ),
        "comparisons": comparisons,
        "invariant_gates": invariant_gates,
        "scenarios": {
            name: result_mapping(result)
            for name, result in results.items()
        },
        "lesion": {
            "fiber_id": target,
            "upstream_activation_preserved": True,
            "mechanics_removed": lesion.active_load_samples == 0,
            "result": result_mapping(lesion),
        },
        "limitations": config["limitations"],
        "claim_limit": config["validation"]["claim_limit"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = json.dumps(
        build_artifact(), indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            print(f"generated oriented-body validation is stale: {args.output}")
            return 1
        print("generated oriented-body validation is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
