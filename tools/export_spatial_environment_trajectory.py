"""Generate deterministic free, slope, and obstacle spatial trajectories."""

from __future__ import annotations

import argparse
import json
from math import atan, degrees
from pathlib import Path
from typing import Any

from oraclarva.body3d import Vec3
from oraclarva.environment import (
    RhythmicObstacleTransduction,
    load_environment_config,
)
from oraclarva.spatial import SpatialClosedLoopLarva, SpatialStimulus
from oraclarva.terrain import ContactWorld, PlaneCollider, SphereCollider


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "data" / "trajectories" / "l1_spatial_environment_v0.json"
)


def summary(result) -> dict[str, float | int]:
    return {
        "neuron_count": result.neuron_count,
        "synapse_count": result.synapse_count,
        "displacement_x_um": round(result.displacement_x_um, 9),
        "displacement_y_um": round(result.displacement_y_um, 9),
        "displacement_z_um": round(result.displacement_z_um, 9),
        "yaw_change_deg": round(result.yaw_change_deg, 9),
        "head_pitch_change_deg": round(result.head_pitch_change_deg, 9),
        "minimum_head_pitch_deg": round(result.minimum_head_pitch_deg, 9),
        "maximum_head_pitch_deg": round(result.maximum_head_pitch_deg, 9),
    }


def render_trajectory() -> str:
    free = SpatialClosedLoopLarva(ground_z_m=None).run(
        SpatialStimulus(1.0, 0.0, 1.0, 0.0),
        record_trajectory_interval_s=0.03,
    )

    environment = load_environment_config()
    slope = float(
        environment["validation_fixtures"]["uphill_plane_slope_x"]
    )
    slope_plane = PlaneCollider.from_slopes(slope, 0.0)
    slope_world = ContactWorld((slope_plane,))
    uphill_larva = SpatialClosedLoopLarva(
        initial_pitch_deg=degrees(atan(-slope)),
        ground_z_m=None,
        contact_surface=slope_world,
    )
    uphill = uphill_larva.run(
        SpatialStimulus(1.0, 1.0, 1.0, 1.0),
        record_trajectory_interval_s=0.03,
    )

    obstacle_center = environment["validation_fixtures"]["obstacle_center_m"]
    obstacle_radius = float(
        environment["validation_fixtures"]["obstacle_radius_m"]
    )
    sphere = SphereCollider(Vec3(*obstacle_center), obstacle_radius)
    obstacle_world = ContactWorld((
        PlaneCollider.from_slopes(0.0, 0.0),
        sphere,
    ))
    obstacle_larva = SpatialClosedLoopLarva(
        ground_z_m=None,
        contact_surface=obstacle_world,
    )
    obstacle = obstacle_larva.run(
        stimulus_protocol=RhythmicObstacleTransduction.from_config(
            obstacle_world
        ),
        record_trajectory_interval_s=0.03,
    )

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "model_id": "dmel_l1_spatial_environment_demo_v0",
        "status": "research_approximation",
        "release_validated": False,
        "units": {
            "time": "second",
            "position": "micrometre",
        },
        "sample_interval_s": 0.03,
        "node_count": 13,
        "channels": ["left", "right", "dorsal", "ventral"],
        "scenarios": [
            {
                "id": "free_combined_yaw_pitch",
                "environment": {"type": "none"},
                "stimulus": {
                    "left": 1.0,
                    "right": 0.0,
                    "dorsal": 1.0,
                    "ventral": 0.0,
                },
                "summary": summary(free),
                "frames": list(free.trajectory_samples),
            },
            {
                "id": "uphill_twenty_percent",
                "environment": {
                    "type": "plane",
                    "slope_x": slope,
                    "contact_friction_coefficient": environment[
                        "parameters"
                    ]["contact_friction_coefficient"],
                },
                "stimulus": {
                    "left": 1.0,
                    "right": 1.0,
                    "dorsal": 1.0,
                    "ventral": 1.0,
                },
                "summary": summary(uphill),
                "frames": list(uphill.trajectory_samples),
            },
            {
                "id": "offset_sphere_receptor_avoidance",
                "environment": {
                    "type": "plane_plus_sphere",
                    "sphere_center_um": [
                        round(value * 1e6, 9) for value in obstacle_center
                    ],
                    "sphere_radius_um": round(obstacle_radius * 1e6, 9),
                    "transduction": environment["parameters"],
                },
                "summary": summary(obstacle),
                "frames": list(obstacle.trajectory_samples),
            },
        ],
        "limitations": environment["limitations"] + [
            "The diagnostic renderer interpolates only these physical nodes.",
            "The three scenarios are fitted regression fixtures, not held-out L1 validation.",
        ],
    }
    return json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic spatial-environment trajectories"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_trajectory()
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            print(f"generated spatial trajectory is stale: {args.output}")
            return 1
        print("generated spatial trajectory is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
