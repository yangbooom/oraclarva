#!/usr/bin/env python3
"""Cross-build and execute Stage 9 parity with Android NDK Bionic ABIs."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
MAIN = ROOT / "tools" / "android_ndk_parity_main.cpp"
REPEAT_FIXTURE = ROOT / "data" / "parity" / "repeat_crawl_native_v1.tsv"
SPATIAL_FIXTURE = ROOT / "data" / "parity" / "spatial_environment_native_v1.tsv"
TARGETS = {
    "arm64-v8a": "aarch64-linux-android26-clang++",
    "x86_64": "x86_64-linux-android26-clang++",
}


def toolchain(ndk: Path) -> Path:
    result = ndk / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64" / "bin"
    if not result.is_dir():
        raise RuntimeError(f"Android NDK Linux toolchain not found: {result}")
    return result


def build(ndk: Path, output: Path, abi: str, compiler_name: str) -> Path:
    compiler = toolchain(ndk) / compiler_name
    if not compiler.is_file():
        raise RuntimeError(f"Android NDK compiler not found: {compiler}")
    executable = output / f"oraclarva-android-ndk-parity-{abi}"
    subprocess.run(
        [
            str(compiler),
            "-static",
            "-std=c++17",
            "-O3",
            "-DNDEBUG",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-DORACLARVA_MOBILE_BUILD",
            "-ffunction-sections",
            "-fdata-sections",
            "-I",
            str(NATIVE),
            str(NATIVE / "lif_core.cpp"),
            str(NATIVE / "spatial_controller.cpp"),
            str(NATIVE / "repeat_core.cpp"),
            str(NATIVE / "mobile_core.cpp"),
            str(MAIN),
            "-Wl,--gc-sections",
            "-o",
            str(executable),
        ],
        check=True,
    )
    return executable


def execute(executable: Path) -> tuple[dict[str, tuple[str, ...]], float]:
    started = time.perf_counter()
    completed = subprocess.run(
        [str(executable), str(REPEAT_FIXTURE), str(SPATIAL_FIXTURE)],
        text=True,
        capture_output=True,
        check=False,
    )
    wall_s = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Android NDK parity failed")
    rows = {
        fields[0]: tuple(fields[1:])
        for line in completed.stdout.splitlines()
        if (fields := line.split("\t"))
    }
    return rows, wall_s


def run_all(ndk: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, tuple[str, ...]]] = {}
    for abi, compiler in TARGETS.items():
        executable = build(ndk, output, abi, compiler)
        rows, wall_s = execute(executable)
        if rows.get("abi") != (abi,):
            raise RuntimeError(f"Android NDK ABI identity drifted for {abi}")
        results[abi] = rows
        print(f"abi\t{abi}\tstatic_bionic\t{executable.stat().st_size}\t{wall_s:.6f}")
        for name in ("uniform", "lateral", "render", "replay", "release_validated"):
            print("\t".join((abi, name, *rows[name])))
    first, second = (results[abi] for abi in TARGETS)
    for row in ("render", "replay", "release_validated"):
        if first[row] != second[row]:
            raise RuntimeError(f"Android NDK structural state differs at {row}")
    if first["uniform"][3] != second["uniform"][3]:
        raise RuntimeError("Android NDK spike totals differ")
    numeric_pairs = (
        *zip(first["uniform"][:3], second["uniform"][:3], strict=True),
        *zip(first["lateral"], second["lateral"], strict=True),
    )
    maximum_delta = max(
        abs(float(first_value) - float(second_value))
        for first_value, second_value in numeric_pairs
    )
    tolerance = 1e-8
    if maximum_delta > tolerance:
        raise RuntimeError("arm64-v8a and x86_64 Android NDK states exceed tolerance")
    print(
        f"android_abi_parity\twithin_tolerance\t{maximum_delta:.12g}\t{tolerance:.12g}"
    )
    print("device_performance_claim\tfalse")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ndk",
        type=Path,
        default=Path(os.environ["ANDROID_NDK_HOME"])
        if "ANDROID_NDK_HOME" in os.environ
        else None,
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.ndk is None:
        raise RuntimeError("--ndk or ANDROID_NDK_HOME is required")
    if args.output is not None:
        run_all(args.ndk, args.output)
        return 0
    with tempfile.TemporaryDirectory(prefix="oraclarva-android-ndk-") as temporary:
        run_all(args.ndk, Path(temporary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
