#!/usr/bin/env python3
"""Build the host-tested mobile C ABI as static/shared libraries and a harness."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/oraclarva-mobile-build")
    )
    parser.add_argument("--compiler", default=shutil.which("c++"))
    parser.add_argument("--archiver", default=shutil.which("ar"))
    args = parser.parse_args(argv)
    if not args.compiler or not args.archiver:
        raise RuntimeError("a C++17 compiler and ar are required")
    args.output.mkdir(parents=True, exist_ok=True)
    common = [
        args.compiler,
        "-std=c++17",
        "-O3",
        "-DNDEBUG",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-DORACLARVA_MOBILE_BUILD",
        "-fvisibility=hidden",
        "-fvisibility-inlines-hidden",
        "-I",
        str(NATIVE),
    ]
    objects: list[Path] = []
    for source in (
        "lif_core.cpp",
        "spatial_controller.cpp",
        "repeat_core.cpp",
        "mobile_core.cpp",
    ):
        output = args.output / f"{Path(source).stem}.o"
        run([*common, "-fPIC", "-c", str(NATIVE / source), "-o", str(output)])
        objects.append(output)
    static = args.output / "liboraclarva_mobile.a"
    run([args.archiver, "rcs", str(static), *(str(item) for item in objects)])
    shared = args.output / "liboraclarva_mobile.so"
    shared_command = [
        args.compiler,
        "-shared",
        *(str(item) for item in objects),
        "-o",
        str(shared),
    ]
    if sys.platform.startswith("linux"):
        export_map = args.output / "mobile.exports"
        export_map.write_text(
            "{\n  global: oraclarva_mobile_*;\n  local: *;\n};\n",
            encoding="utf-8",
        )
        shared_command.append(f"-Wl,--version-script={export_map}")
    run(shared_command)
    host = args.output / "oraclarva-mobile-host"
    run(
        [
            *common,
            str(NATIVE / "mobile_main.cpp"),
            *(str(item) for item in objects),
            "-o",
            str(host),
        ]
    )
    for artifact in (static, shared, host):
        print(f"{artifact}\t{artifact.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
