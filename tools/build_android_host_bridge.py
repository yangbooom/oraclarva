#!/usr/bin/env python3
"""Build and execute the Android JNI boundary on the current host JVM."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
BRIDGE = ROOT / "android" / "app" / "src" / "main" / "cpp" / "android_bridge.cpp"
JAVA_SOURCES = ROOT / "tools" / "android_host_bridge"
REPEAT_FIXTURE = ROOT / "data" / "parity" / "repeat_crawl_native_v1.tsv"
SPATIAL_FIXTURE = ROOT / "data" / "parity" / "spatial_environment_native_v1.tsv"


def required(name: str) -> str:
    value = shutil.which(name)
    if value is None:
        raise RuntimeError(f"{name} is required")
    return value


def build(output: Path) -> Path:
    compiler = required("c++")
    javac = Path(required("javac")).resolve()
    jdk = javac.parents[1]
    library = output / "liboraclarva_android.so"
    sources = (
        NATIVE / "lif_core.cpp",
        NATIVE / "spatial_controller.cpp",
        NATIVE / "repeat_core.cpp",
        NATIVE / "mobile_core.cpp",
        BRIDGE,
    )
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O3",
            "-DNDEBUG",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fPIC",
            "-shared",
            "-DORACLARVA_MOBILE_BUILD",
            "-I",
            str(NATIVE),
            "-I",
            str(jdk / "include"),
            "-I",
            str(jdk / "include" / "linux"),
            *(str(source) for source in sources),
            "-o",
            str(library),
        ],
        check=True,
    )
    classes = output / "classes"
    classes.mkdir()
    java_files = sorted(JAVA_SOURCES.rglob("*.java"))
    subprocess.run(
        [str(javac), "-d", str(classes), *(str(path) for path in java_files)],
        check=True,
    )
    return classes


def execute(output: Path, classes: Path) -> str:
    completed = subprocess.run(
        [
            required("java"),
            f"-Djava.library.path={output}",
            "-cp",
            str(classes),
            "org.oraclarva.mobile.AndroidHostHarness",
            str(REPEAT_FIXTURE),
            str(SPATIAL_FIXTURE),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Android JNI harness failed")
    return completed.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
        print(execute(args.output, build(args.output)), end="")
        return 0
    with tempfile.TemporaryDirectory(prefix="oraclarva-android-jni-") as temp:
        output = Path(temp)
        print(execute(output, build(output)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
