#!/usr/bin/env python3
"""Export the frozen repeat-crawl Python reference trajectory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from oraclarva.artifacts import first_mismatch
from oraclarva.repeat_crawl import RepeatCrawlLarva, load_repeat_crawl_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "organism" / "l1_repeat_crawl_v0.json"
DEFAULT_OUTPUT = ROOT / "data" / "trajectories" / "l1_repeat_crawl_v0.json"
SAMPLE_INTERVAL_S = 0.03


def render_trajectory() -> str:
    config = load_repeat_crawl_config(CONFIG)
    config_sha256 = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    larva = RepeatCrawlLarva(config)
    result = larva.run(record_trajectory_interval_s=SAMPLE_INTERVAL_S)
    metrics = result.cycle_metrics(dt_s=float(config["parameters"]["dt_s"]))
    trace_examples = {}
    for trace in larva.protocol.last_force_trace_by_source.values():
        trace_examples.setdefault(str(trace["segment_id"]), trace)
    if set(trace_examples) != set(config["supported_wave_segments_posterior_to_anterior"]):
        raise RuntimeError("repeat-crawl artifact lacks an A1-A6 force trace")
    if (
        metrics["complete_cycle_count"] < 3
        or not result.all_active_forces_sensory_traced
        or result.release_validated is not False
    ):
        raise RuntimeError("repeat-crawl trajectory fails its causal export gate")
    artifact = {
        "schema_version": 1,
        "model_id": config["model_id"],
        "stage": "L1",
        "status": "research_approximation",
        "release_validated": False,
        "generated_from": {
            "config": str(CONFIG.relative_to(ROOT)),
            "config_sha256": config_sha256,
            "parameter_fit_status": config["calibration"]["fit_status"],
            "selection_used_held_out_values": config["calibration"][
                "selection_used_held_out_values"
            ],
        },
        "causal_contract": config["causal_contract"],
        "periodic_stimulus": False,
        "action_command": False,
        "supported_wave_segments_posterior_to_anterior": list(
            config["supported_wave_segments_posterior_to_anterior"]
        ),
        "node_count": 13,
        "causal_trace_examples": {
            segment: trace_examples[segment]
            for segment in config["supported_wave_segments_posterior_to_anterior"]
        },
        "duration_s": result.duration_s,
        "sample_interval_s": SAMPLE_INTERVAL_S,
        "frames": list(result.trajectory_samples),
        "result_summary": {
            "displacement_x_um": round(result.displacement_x_um, 9),
            "feedback_force_frames": result.feedback_force_frames,
            "all_active_forces_sensory_traced": (
                result.all_active_forces_sensory_traced
            ),
            "maximum_pending_trace_count": (
                result.maximum_pending_trace_count
            ),
            "premotor_spike_times_s": {
                key: list(values)
                for key, values in result.premotor_spike_times_s.items()
            },
            "motor_spike_times_s": {
                key: list(values)
                for key, values in result.motor_spike_times_s.items()
            },
            "cycle_metrics": metrics,
        },
    }
    return json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_trajectory()
    if args.check:
        if not args.output.exists():
            print(f"repeat-crawl trajectory is missing: {args.output}")
            return 1
        expected = json.loads(args.output.read_text(encoding="utf-8"))
        actual = json.loads(rendered)
        mismatch = first_mismatch(expected, actual)
        if mismatch:
            print(f"repeat-crawl trajectory is stale: {mismatch}")
            return 1
        print("repeat-crawl trajectory is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
