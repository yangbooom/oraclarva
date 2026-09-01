#!/usr/bin/env python3
"""Render the checked mobile lifecycle and read-only mesh projection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "data" / "mobile" / "mobile_core_integration_v1.json"
BENCHMARK = ROOT / "data" / "benchmarks" / "mobile_core_host_v1.json"
FIXTURE = ROOT / "data" / "parity" / "repeat_crawl_native_v1.tsv"
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "oraclarva_mobile_core_integration.gif"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
WIDTH, HEIGHT, SS = 1080, 720, 2
WORLD_X = (-450.0, 1100.0)
RINGS, RADIAL = 25, 12


def font(path: Path, size: int):
    return (
        ImageFont.truetype(str(path), size * SS)
        if path.exists()
        else ImageFont.load_default()
    )


def scaled(point):
    return tuple(round(value * SS) for value in point)


def mix(left, right, amount):
    amount = min(1.0, max(0.0, amount))
    return tuple(
        round(a * (1.0 - amount) + b * amount)
        for a, b in zip(left, right, strict=True)
    )


def label(draw, xy, value, fill, face, anchor=None):
    draw.text(scaled(xy), value, fill=fill, font=face, anchor=anchor)


def world_to_panel(point, rect):
    left, top, right, bottom = rect
    pixels_per_um = (right - left) / (WORLD_X[1] - WORLD_X[0])
    ground_y = bottom - 45.0
    return (
        left
        + (point[0] - WORLD_X[0])
        / (WORLD_X[1] - WORLD_X[0])
        * (right - left),
        ground_y - point[2] * pixels_per_um,
    )


def wave_body_indices():
    result = {}
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if fields[0] == "wave_segment":
            result[int(fields[3])] = fields[2]
    if len(result) != 6:
        raise RuntimeError("mobile GIF cannot map wave body segments")
    return result


def panel(draw, rect, heading, subheading, mono, small):
    draw.rounded_rectangle(
        (*scaled((rect[0], rect[1] - 18)), *scaled((rect[2], rect[3] + 22))),
        radius=16 * SS,
        fill=(17, 13, 24),
        outline=(57, 45, 66),
        width=SS,
    )
    label(draw, (rect[0] + 16, rect[1] - 5), heading, (230, 213, 195), mono)
    label(draw, (rect[0] + 16, rect[1] + 13), subheading, (139, 124, 147), small)
    ground_y = world_to_panel((0.0, 0.0, 0.0), rect)[1]
    draw.line(
        (*scaled((rect[0] + 8, ground_y)), *scaled((rect[2] - 8, ground_y))),
        fill=(53, 43, 57),
        width=SS,
    )


def draw_internal(draw, frame, rect, body_map):
    nodes = frame["physics_nodes_um"]
    points = [world_to_panel(node, rect) for node in nodes]
    activation = frame["segment_activation"]
    for index, (left, right) in enumerate(
        zip(points[:-1], points[1:], strict=True)
    ):
        segment = body_map.get(index)
        active = float(activation.get(segment, 0.0)) if segment else 0.0
        color = mix((83, 113, 126), (245, 82, 126), active)
        draw.line(
            [scaled(left), scaled(right)],
            fill=color,
            width=max(2 * SS, round((4.0 + 5.0 * active) * SS)),
        )
    for point in points:
        radius = 4.0
        draw.ellipse(
            (
                *scaled((point[0] - radius, point[1] - radius)),
                *scaled((point[0] + radius, point[1] + radius)),
            ),
            fill=(225, 213, 199),
            outline=(41, 33, 47),
            width=SS,
        )


def draw_surface(draw, frame, rect):
    vertices = frame["render_vertices_um_activation"]
    rings = [
        vertices[index * RADIAL : (index + 1) * RADIAL]
        for index in range(RINGS)
    ]
    upper = []
    lower = []
    activation = []
    for ring in rings:
        points = [world_to_panel(vertex[:3], rect) for vertex in ring]
        upper.append(min(points, key=lambda point: point[1]))
        lower.append(max(points, key=lambda point: point[1]))
        activation.append(sum(vertex[3] for vertex in ring) / RADIAL)
    for index in range(RINGS - 1):
        active = 0.5 * (activation[index] + activation[index + 1])
        color = mix((103, 190, 184), (246, 80, 125), active)
        draw.polygon(
            [
                scaled(upper[index]),
                scaled(upper[index + 1]),
                scaled(lower[index + 1]),
                scaled(lower[index]),
            ],
            fill=color,
        )
    start_cap = world_to_panel(vertices[-2][:3], rect)
    end_cap = world_to_panel(vertices[-1][:3], rect)
    draw.polygon(
        [scaled(start_cap), scaled(upper[0]), scaled(lower[0])],
        fill=(103, 190, 184),
    )
    draw.polygon(
        [scaled(end_cap), scaled(lower[-1]), scaled(upper[-1])],
        fill=(103, 190, 184),
    )
    outline = [start_cap, *upper, end_cap, *reversed(lower), start_cap]
    draw.line(
        [scaled(point) for point in outline],
        fill=(52, 73, 79),
        width=2 * SS,
        joint="curve",
    )


def plot_timeline(draw, frames, index, rect, mono, small):
    left, top, right, bottom = rect
    draw.rounded_rectangle(
        (*scaled((left - 16, top - 28)), *scaled((right + 16, bottom + 22))),
        radius=14 * SS,
        fill=(17, 13, 24),
        outline=(57, 45, 66),
        width=SS,
    )
    label(draw, (left, top - 18), "CLOSED-LOOP STATE HISTORY", (221, 204, 189), mono)
    activations = [max(frame["segment_activation"].values()) for frame in frames]
    initial_x = sum(node[0] for node in frames[0]["physics_nodes_um"]) / 13
    displacements = [
        (initial_x - sum(node[0] for node in frame["physics_nodes_um"]) / 13)
        / 400.0
        for frame in frames
    ]
    for level in (0.0, 0.5, 1.0):
        y = bottom - level * (bottom - top)
        draw.line(
            (*scaled((left, y)), *scaled((right, y))),
            fill=(40, 32, 46),
            width=SS,
        )
    for values, color in (
        (activations, (245, 91, 128)),
        (displacements, (95, 204, 193)),
    ):
        points = [
            (
                left + i / (len(values) - 1) * (right - left),
                bottom - min(1.0, max(0.0, value)) * (bottom - top),
            )
            for i, value in enumerate(values)
        ]
        draw.line([scaled(point) for point in points], fill=color, width=2 * SS)
    cursor = left + index / (len(frames) - 1) * (right - left)
    draw.line(
        (*scaled((cursor, top)), *scaled((cursor, bottom))),
        fill=(244, 228, 201),
        width=2 * SS,
    )
    label(draw, (left, bottom + 10), "activation", (245, 91, 128), small)
    label(draw, (left + 90, bottom + 10), "anatomical forward", (95, 204, 193), small)
    label(
        draw,
        (right, bottom + 10),
        f"{frames[-1]['time_s']:.1f} s",
        (137, 121, 144),
        small,
        anchor="ra",
    )


def render_frame(index, artifact, benchmark, body_map):
    frames = artifact["frames"]
    frame = frames[index]
    canvas = Image.new("RGB", (WIDTH * SS, HEIGHT * SS), "#0d0a12")
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        draw.line(
            (0, y * SS, WIDTH * SS, y * SS),
            fill=mix((13, 10, 18), (24, 19, 31), y / HEIGHT),
            width=SS,
        )
    title = font(FONT_BOLD, 24)
    mono = font(FONT_MONO, 10)
    small = font(FONT_MONO, 8)
    label(draw, (40, 24), "ORACLARVA / MOBILE CORE LIFECYCLE", (246, 232, 211), title)
    label(
        draw,
        (41, 60),
        "ENVIRONMENT → SENSORY → 164 LIF → 146 FIBERS → 13-NODE PHYSICS → ENVIRONMENT",
        (163, 145, 168),
        mono,
    )
    left = (36, 111, 524, 388)
    right = (556, 111, 1044, 388)
    panel(draw, left, "INTERNAL PHYSICS STATE", "13 double-precision nodes · writable only by core", mono, small)
    panel(draw, right, "READ-ONLY RENDER PROJECTION", "302 vertices · 600 triangles · watertight", mono, small)
    draw_internal(draw, frame, left, body_map)
    draw_surface(draw, frame, right)
    label(
        draw,
        (52, 92),
        "← ANATOMICAL FORWARD · ANTERIOR IS LEFT · NO EYE MARKER",
        (151, 207, 193),
        small,
    )
    label(draw, (52, 420), f"t = {frame['time_s']:05.2f} s", (226, 208, 190), mono)
    if index == 0:
        label(draw, (1030, 420), "POSTERIOR TOUCH 1.0 / FIRST 2 ms", (244, 173, 103), mono, anchor="ra")
    else:
        label(draw, (1030, 420), "NO PERIODIC STIMULUS · BODY FEEDBACK CONTINUES", (136, 194, 181), mono, anchor="ra")

    plot_timeline(draw, frames, index, (52, 486, 738, 611), mono, small)
    measurements = benchmark["measurements"]
    label(draw, (790, 468), "HOST PROXY GATE", (116, 218, 168), mono)
    label(draw, (790, 499), "step/reset     exact", (184, 167, 184), small)
    label(draw, (790, 521), "one-shot      exact", (184, 167, 184), small)
    label(draw, (790, 543), "render state  read-only", (184, 167, 184), small)
    label(
        draw,
        (790, 565),
        f"throughput    {measurements['simulated_seconds_per_wall_second']:.1f}× realtime",
        (184, 167, 184),
        small,
    )
    label(
        draw,
        (790, 587),
        f"peak process  {measurements['peak_process_rss_kib'] / 1024:.1f} MiB",
        (184, 167, 184),
        small,
    )
    label(draw, (790, 609), "Android/iOS    NOT TESTED", (244, 174, 103), small)
    label(draw, (40, 678), "release_validated = false · held-out A5/A6 duty FAIL · NON-INDEPENDENT", (244, 113, 133), small)
    label(draw, (1040, 678), "HOST ENGINEERING GATE ≠ DEVICE OR BIOLOGICAL VALIDATION", (151, 132, 153), small, anchor="rs")
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(output):
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    if (
        artifact["schema"] != "mobile_core_integration_v1"
        or artifact["release_validated"] is not False
        or artifact["reset_replay"]["status"] != "exact"
        or len(artifact["frames"]) < 2
        or artifact["frames"][-1]["time_s"]
        != artifact["fixed_step"]["steps"]
        * artifact["fixed_step"]["dt_s"]
        or benchmark["all_gates_pass"] is not True
        or benchmark["android_ios_device_tested"] is not False
    ):
        raise RuntimeError("mobile GIF source contract is invalid")
    body_map = wave_body_indices()
    frames = [
        render_frame(index, artifact, benchmark, body_map)
        for index in range(len(artifact["frames"]))
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=80,
        loop=0,
        disposal=2,
        optimize=True,
    )
    print(f"wrote {output.relative_to(ROOT)}: {len(frames)} frames")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    render(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
