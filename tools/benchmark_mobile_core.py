#!/usr/bin/env python3
"""Measure the release-built mobile C ABI on the current host proxy."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "parity" / "repeat_crawl_native_v1.tsv"
INTEGRATION = ROOT / "data" / "mobile" / "mobile_core_integration_v1.json"
DEFAULT_OUTPUT = ROOT / "data" / "benchmarks" / "mobile_core_host_v1.json"
RUNS = 7


BUDGETS = {
    "initialize_ms_max": 250.0,
    "full_standard_run_median_ms_max": 1000.0,
    "simulated_seconds_per_wall_second_min": 10.0,
    "peak_process_rss_kib_max": 65536,
    "snapshot_struct_bytes_max": 4096,
    "snapshot_read_us_max": 2000.0,
    "render_mesh_read_us_max": 5000.0,
    "shared_library_bytes_max": 2_000_000,
    "static_library_bytes_max": 2_000_000,
    "host_harness_bytes_max": 2_000_000,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="oraclarva-mobile-benchmark-") as temp:
        build = Path(temp)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build_mobile_core.py"),
                "--output",
                str(build),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        host = build / "oraclarva-mobile-host"
        completed = subprocess.run(
            [
                str(host),
                str(FIXTURE),
                "--no-frame-output",
                "--benchmark-runs",
                str(RUNS),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        artifacts = {
            "static_library": build / "liboraclarva_mobile.a",
            "shared_library": build / "liboraclarva_mobile.so",
            "host_harness": host,
        }
        artifact_records = {
            name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for name, path in artifacts.items()
        }

    metadata: list[str] | None = None
    digest: str | None = None
    replay: list[str] | None = None
    benchmark: list[str] | None = None
    for line in completed.stdout.splitlines():
        fields = line.split("\t")
        if fields[0] == "metadata":
            metadata = fields[1:]
        elif fields[0] == "summary":
            digest = fields[2]
        elif fields[0] == "replay":
            replay = fields[1:]
        elif fields[0] == "benchmark":
            benchmark = fields[1:]
        else:
            raise RuntimeError(f"unexpected benchmark row {fields[0]}")
    if metadata is None or digest is None or replay is None or benchmark is None:
        raise RuntimeError("mobile benchmark output is incomplete")
    if replay != [digest, digest, "exact"]:
        raise RuntimeError("mobile benchmark reset replay mismatch")
    if metadata[4] != "release_validated=false":
        raise RuntimeError("mobile benchmark lost scientific status boundary")
    integration = json.loads(INTEGRATION.read_text())
    expected_digest = integration["result_summary"]["canonical_fnv1a64"]
    workload_steps = int(integration["fixed_step"]["steps"])
    workload_dt_s = float(integration["fixed_step"]["dt_s"])
    if digest != expected_digest:
        raise RuntimeError("benchmark workload digest differs from integration gate")

    measurements = {
        "initialize_ms": float(benchmark[0]),
        "full_standard_run_median_ms": float(benchmark[1]),
        "simulated_seconds_per_wall_second": float(benchmark[2]),
        "peak_process_rss_kib": int(benchmark[3]),
        "snapshot_struct_bytes": int(benchmark[4]),
        "snapshot_read_us": float(benchmark[5]),
        "render_mesh_read_us": float(benchmark[6]),
        "shared_library_bytes": artifact_records["shared_library"]["bytes"],
        "static_library_bytes": artifact_records["static_library"]["bytes"],
        "host_harness_bytes": artifact_records["host_harness"]["bytes"],
    }
    gates = {
        "initialize": measurements["initialize_ms"] <= BUDGETS["initialize_ms_max"],
        "full_run": measurements["full_standard_run_median_ms"]
        <= BUDGETS["full_standard_run_median_ms_max"],
        "throughput": measurements["simulated_seconds_per_wall_second"]
        >= BUDGETS["simulated_seconds_per_wall_second_min"],
        "rss": measurements["peak_process_rss_kib"]
        <= BUDGETS["peak_process_rss_kib_max"],
        "snapshot_size": measurements["snapshot_struct_bytes"]
        <= BUDGETS["snapshot_struct_bytes_max"],
        "snapshot_read": measurements["snapshot_read_us"]
        <= BUDGETS["snapshot_read_us_max"],
        "render_mesh_read": measurements["render_mesh_read_us"]
        <= BUDGETS["render_mesh_read_us_max"],
        "shared_size": measurements["shared_library_bytes"]
        <= BUDGETS["shared_library_bytes_max"],
        "static_size": measurements["static_library_bytes"]
        <= BUDGETS["static_library_bytes_max"],
        "host_size": measurements["host_harness_bytes"]
        <= BUDGETS["host_harness_bytes_max"],
    }
    compiler = subprocess.run(
        ["c++", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    return {
        "schema_version": 1,
        "schema": "mobile_core_host_benchmark_v1",
        "measurement_date_utc": datetime.now(timezone.utc).date().isoformat(),
        "target_class": "linux_host_proxy",
        "host_tested_only": True,
        "android_ios_device_tested": False,
        "device_performance_claim_allowed": False,
        "frozen_config_sha256": metadata[5],
        "canonical_workload_fnv1a64": digest,
        "build": {
            "compiler": compiler,
            "flags": [
                "-std=c++17",
                "-O3",
                "-DNDEBUG",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-fvisibility=hidden",
                "-fvisibility-inlines-hidden",
            ],
            "artifacts": artifact_records,
        },
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "workload": {
            "fixed_dt_s": float(metadata[6]),
            "steps": workload_steps,
            "simulated_duration_s": workload_steps * workload_dt_s,
            "posterior_touch_steps": 2,
            "posterior_touch_intensity": 1.0,
            "median_run_count": RUNS,
            "snapshot_samples": 100,
            "render_mesh_samples": 100,
            "render_vertices": int(metadata[10]),
            "render_triangles": int(metadata[11]),
        },
        "measurements": measurements,
        "budgets": BUDGETS,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
        "limitations": [
            "This is a process-level Linux host proxy, not Android or iOS device data.",
            "Peak RSS includes the executable, C++ runtime, fixture, and measurement process.",
            "Timing varies with host load and is an engineering budget, not a biological parameter.",
            "Passing this benchmark does not create an independent held-out behavioral validation claim.",
        ],
    }


def validate(report: dict[str, Any]) -> None:
    if report["schema"] != "mobile_core_host_benchmark_v1":
        raise RuntimeError("mobile benchmark schema mismatch")
    if report["host_tested_only"] is not True:
        raise RuntimeError("mobile benchmark is not marked host-only")
    if report["android_ios_device_tested"] is not False:
        raise RuntimeError("mobile benchmark overclaims device coverage")
    if report["device_performance_claim_allowed"] is not False:
        raise RuntimeError("mobile benchmark permits an unsupported device claim")
    if report["all_gates_pass"] is not True or not all(report["gates"].values()):
        raise RuntimeError("mobile host benchmark budget failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        if not args.output.exists():
            print(f"mobile benchmark artifact is missing: {args.output}")
            return 1
        checked = json.loads(args.output.read_text(encoding="utf-8"))
        validate(checked)
        current = measure()
        validate(current)
        if current["canonical_workload_fnv1a64"] != checked["canonical_workload_fnv1a64"]:
            print("mobile benchmark workload digest drifted")
            return 1
        print("mobile host benchmark passes current budgets")
        return 0
    report = measure()
    validate(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
