"""Verify that native physics frames satisfy the checked viewer artifact contract."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "parity" / "closed_loop_native_v1.tsv"
VIEWER_ARTIFACT = ROOT / "data" / "trajectories" / "l1_closed_loop_v0.json"


def build_binary(output: Path) -> None:
    compiler = shutil.which("c++")
    if compiler is None:
        raise RuntimeError("C++ compiler is unavailable")
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(ROOT / "native" / "lif_core.cpp"),
            str(ROOT / "native" / "organism_core.cpp"),
            str(ROOT / "native" / "organism_main.cpp"),
            "-o",
            str(output),
        ],
        check=True,
    )


def native_frames(binary: Path) -> tuple[tuple[str, ...], list[dict[str, object]]]:
    output = subprocess.run(
        [str(binary), str(FIXTURE)],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    metadata: tuple[str, ...] | None = None
    frames: list[dict[str, object]] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if fields[0] == "metadata":
            metadata = tuple(fields[1:])
        elif fields[0] == "frame":
            frames.append({
                "time_s": round(float(fields[2]), 9),
                "nodes_um": [
                    [round(float(value), 9) for value in node.split(",")]
                    for node in fields[3].split(";")
                ],
                "segment_activation": [
                    round(float(value), 9) for value in fields[4].split(",")
                ],
            })
    if metadata is None:
        raise RuntimeError("native output omitted metadata")
    return metadata, frames


def check(binary: Path) -> None:
    metadata, frames = native_frames(binary)
    artifact = json.loads(VIEWER_ARTIFACT.read_text())
    expected_metadata = (
        "closed_loop_native_v1",
        artifact["model_id"],
        artifact["status"],
        "release_validated=false",
    )
    if metadata != expected_metadata:
        raise RuntimeError(
            f"native/viewer metadata mismatch: {metadata} != {expected_metadata}"
        )
    if artifact["schema_version"] != 1 or artifact["release_validated"] is not False:
        raise RuntimeError("viewer artifact claim boundary is invalid")
    expected_frames = artifact["frames"]
    if len(frames) != len(expected_frames):
        raise RuntimeError("native/viewer frame counts differ")
    maximum_node_error_um = 0.0
    maximum_activation_error = 0.0
    for native_frame, viewer_frame in zip(frames, expected_frames, strict=True):
        if native_frame["time_s"] != viewer_frame["time_s"]:
            raise RuntimeError("native/viewer sample times differ")
        native_nodes = native_frame["nodes_um"]
        viewer_nodes = viewer_frame["nodes_um"]
        if len(native_nodes) != len(viewer_nodes):
            raise RuntimeError("native/viewer node counts differ")
        for native_node, viewer_node in zip(native_nodes, viewer_nodes, strict=True):
            maximum_node_error_um = max(
                maximum_node_error_um,
                *(abs(left - right) for left, right in zip(
                    native_node, viewer_node, strict=True
                )),
            )
        native_activation = native_frame["segment_activation"]
        viewer_activation = viewer_frame["segment_activation"]
        if len(native_activation) != len(viewer_activation):
            raise RuntimeError("native/viewer activation channel counts differ")
        maximum_activation_error = max(
            maximum_activation_error,
            *(abs(left - right) for left, right in zip(
                native_activation, viewer_activation, strict=True
            )),
        )
    if maximum_node_error_um > 2e-9:
        raise RuntimeError(
            f"native/viewer node error exceeds 2e-9 um: {maximum_node_error_um}"
        )
    if maximum_activation_error > 5.1e-10:
        raise RuntimeError(
            "native/viewer activation error exceeds 5.1e-10: "
            f"{maximum_activation_error}"
        )
    print(
        "native closed-loop trajectory matches viewer artifact: "
        f"{len(frames)} frames, {artifact['node_count']} nodes, "
        f"max node error {maximum_node_error_um:.3g} um, "
        f"max activation error {maximum_activation_error:.3g}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare native closed-loop output with the viewer artifact"
    )
    parser.add_argument("--binary", type=Path)
    args = parser.parse_args(argv)
    if args.binary is not None:
        check(args.binary)
        return 0
    with tempfile.TemporaryDirectory(prefix="oraclarva-native-viewer-") as directory:
        binary = Path(directory) / "oraclarva-native-organism"
        build_binary(binary)
        check(binary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
