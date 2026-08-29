"""Generate the deterministic bilateral steering trajectory consumed by the viewer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from oraclarva.bilateral import BilateralClosedLoopLarva, BilateralStimulus


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "trajectories"
    / "l1_bilateral_steering_v0.json"
)


def render_trajectory() -> str:
    result = BilateralClosedLoopLarva().run(
        BilateralStimulus(1.0, 0.0),
        record_trajectory_interval_s=0.03,
    )
    artifact = result.trajectory_artifact()
    artifact["stimulus"] = {
        "left_touch_intensity": 1.0,
        "right_touch_intensity": 0.0,
    }
    artifact["result_summary"] = {
        # Match the trajectory coordinate quantization so libm tail bits do not
        # make the checked artifact platform-dependent.
        "displacement_x_um": round(result.displacement_x_um, 9),
        "displacement_y_um": round(result.displacement_y_um, 9),
        "heading_change_deg": round(result.heading_change_deg, 9),
        "maximum_abs_lateral_um": round(
            result.maximum_abs_lateral_um, 9
        ),
    }
    return json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the viewer trajectory from the bilateral Python loop"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_trajectory()
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            print(f"generated bilateral trajectory is stale: {args.output}")
            return 1
        print("generated bilateral trajectory is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
