#!/usr/bin/env python3
"""Render the checked Stage 9 C++ environment/body trajectories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT / "data" / "trajectories" / "l1_native_environment_closed_loop_v1.json"
)
DEFAULT_OUTPUT = (
    ROOT / "docs" / "assets" / "oraclarva_native_environment_closed_loop.gif"
)
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
WIDTH, HEIGHT, SS = 1080, 720, 2
ANATOMICAL_X = (-960.0, 220.0)
TOP_Y = (-180.0, 180.0)
SIDE_Z = (-20.0, 300.0)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return (
        ImageFont.truetype(str(path), size * SS)
        if path.exists()
        else ImageFont.load_default()
    )


def scaled(point: tuple[float, float]) -> tuple[int, int]:
    return tuple(round(value * SS) for value in point)


def label(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    value: str,
    fill: tuple[int, int, int],
    face: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    anchor: str | None = None,
) -> None:
    draw.text(scaled(xy), value, fill=fill, font=face, anchor=anchor)


def panel(
    draw: ImageDraw.ImageDraw,
    rect: tuple[float, float, float, float],
    title: str,
    subtitle: str,
    mono: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    small: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    draw.rounded_rectangle(
        (*scaled((rect[0], rect[1] - 28)), *scaled((rect[2], rect[3]))),
        radius=14 * SS,
        fill=(18, 15, 26),
        outline=(62, 53, 74),
        width=SS,
    )
    label(draw, (rect[0] + 14, rect[1] - 17), title, (238, 225, 207), mono)
    label(draw, (rect[0] + 14, rect[1] + 2), subtitle, (145, 132, 155), small)


def map_world(
    node: list[float],
    rect: tuple[float, float, float, float],
    vertical_range: tuple[float, float],
    vertical_index: int,
) -> tuple[float, float]:
    x = -node[0]
    vertical = node[vertical_index]
    left, top, right, bottom = rect
    pixels_per_um = (right - left) / (ANATOMICAL_X[1] - ANATOMICAL_X[0])
    zero_y = (top + bottom) * 0.5 if vertical_index == 1 else bottom - 28.0
    return (
        left + (x - ANATOMICAL_X[0]) / (ANATOMICAL_X[1] - ANATOMICAL_X[0]) * (right - left),
        zero_y - vertical * pixels_per_um,
    )


def selected_frame(run: dict[str, Any], index: int, count: int) -> dict[str, Any]:
    frames = run["frames"]
    source = round(index * (len(frames) - 1) / (count - 1))
    return frames[source]


def center(frame: dict[str, Any]) -> list[float]:
    nodes = frame["physics_nodes_um"]
    return [sum(node[axis] for node in nodes) / len(nodes) for axis in range(3)]


def draw_grid(
    draw: ImageDraw.ImageDraw,
    rect: tuple[float, float, float, float],
    vertical_range: tuple[float, float],
    vertical_index: int,
) -> None:
    for x in (-800.0, -400.0, 0.0):
        a = map_world([-x, 0.0, 0.0], rect, vertical_range, vertical_index)
        draw.line(
            (*scaled((a[0], rect[1] + 22)), *scaled((a[0], rect[3] - 8))),
            fill=(42, 36, 50),
            width=SS,
        )
    zero = [0.0, 0.0, 0.0]
    axis = map_world(zero, rect, vertical_range, vertical_index)[1]
    draw.line(
        (*scaled((rect[0] + 8, axis)), *scaled((rect[2] - 8, axis))),
        fill=(54, 47, 62),
        width=SS,
    )


def draw_body(
    draw: ImageDraw.ImageDraw,
    frame: dict[str, Any],
    rect: tuple[float, float, float, float],
    vertical_range: tuple[float, float],
    vertical_index: int,
    color: tuple[int, int, int],
) -> None:
    points = [
        map_world(node, rect, vertical_range, vertical_index)
        for node in frame["physics_nodes_um"]
    ]
    draw.line(
        [scaled(point) for point in points],
        fill=(7, 7, 11),
        width=13 * SS,
        joint="curve",
    )
    draw.line(
        [scaled(point) for point in points],
        fill=color,
        width=9 * SS,
        joint="curve",
    )
    for point in points:
        radius = 2.2
        draw.ellipse(
            (
                *scaled((point[0] - radius, point[1] - radius)),
                *scaled((point[0] + radius, point[1] + radius)),
            ),
            fill=(237, 227, 211),
        )
    head = points[0]
    draw.ellipse(
        (
            *scaled((head[0] - 6, head[1] - 6)),
            *scaled((head[0] + 6, head[1] + 6)),
        ),
        outline=(247, 236, 217),
        width=2 * SS,
    )


def draw_trail(
    draw: ImageDraw.ImageDraw,
    run: dict[str, Any],
    index: int,
    count: int,
    rect: tuple[float, float, float, float],
    vertical_range: tuple[float, float],
    vertical_index: int,
    color: tuple[int, int, int],
) -> None:
    stop = round(index * (len(run["frames"]) - 1) / (count - 1)) + 1
    points = [
        map_world(center(frame), rect, vertical_range, vertical_index)
        for frame in run["frames"][:stop]
    ]
    if len(points) > 1:
        draw.line(
            [scaled(point) for point in points],
            fill=tuple(value // 2 for value in color),
            width=2 * SS,
        )


def bar(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    value: float,
    color: tuple[int, int, int],
    name: str,
    small: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    width = 88.0
    label(draw, (x, y), name, (155, 143, 164), small)
    draw.rounded_rectangle(
        (*scaled((x + 22, y + 1)), *scaled((x + 22 + width, y + 10))),
        radius=4 * SS,
        fill=(42, 36, 50),
    )
    normalized = min(1.0, max(0.0, value / 0.9))
    draw.rounded_rectangle(
        (
            *scaled((x + 22, y + 1)),
            *scaled((x + 22 + width * normalized, y + 10)),
        ),
        radius=4 * SS,
        fill=color,
    )


def render_frame(index: int, artifact: dict[str, Any], count: int) -> Image.Image:
    canvas = Image.new("RGB", (WIDTH * SS, HEIGHT * SS), (12, 10, 17))
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        shade = round(12 + 10 * y / HEIGHT)
        draw.line((0, y * SS, WIDTH * SS, y * SS), fill=(shade, shade - 2, shade + 5), width=SS)
    title = font(FONT_BOLD, 24)
    mono = font(FONT_MONO, 10)
    small = font(FONT_MONO, 8)
    label(draw, (34, 22), "ORACLARVA / STAGE 9 NATIVE ENVIRONMENT LOOP", (246, 234, 215), title)
    label(
        draw,
        (35, 59),
        "LIGHT FIELD → 4 SURFACE SAMPLES → 168 LIF → MN → MUSCLE → SAME 13-NODE BODY → LIGHT FIELD",
        (164, 148, 174),
        mono,
    )
    left_rect = (32.0, 122.0, 532.0, 462.0)
    right_rect = (556.0, 122.0, 1048.0, 462.0)
    panel(draw, left_rect, "LATERAL GRADIENT / TOP VIEW", "mirrored physical fields + right-sensor lesion", mono, small)
    panel(draw, right_rect, "DORSAL–VENTRAL / SIDE VIEW", "upward response; downward response limited by ground", mono, small)
    draw_grid(draw, left_rect, TOP_Y, 1)
    draw_grid(draw, right_rect, SIDE_Z, 2)
    scenarios = artifact["scenarios"]
    lateral = (
        ("positive_y_gradient", (78, 218, 210)),
        ("negative_y_gradient", (240, 93, 150)),
        ("positive_y_right_sensor_lesion", (138, 131, 151)),
    )
    vertical = (
        ("positive_z_gradient", (244, 184, 80)),
        ("negative_z_gradient", (142, 111, 226)),
    )
    for name, color in lateral:
        run = scenarios[name]
        frame = selected_frame(run, index, count)
        draw_trail(draw, run, index, count, left_rect, TOP_Y, 1, color)
        draw_body(draw, frame, left_rect, TOP_Y, 1, color)
    for name, color in vertical:
        run = scenarios[name]
        frame = selected_frame(run, index, count)
        draw_trail(draw, run, index, count, right_rect, SIDE_Z, 2, color)
        draw_body(draw, frame, right_rect, SIDE_Z, 2, color)
    label(draw, (48, 439), "cyan +Y · pink −Y · gray sensor lesion", (176, 164, 184), small)
    label(draw, (571, 439), "gold +Z · violet −Z / ground", (176, 164, 184), small)
    label(draw, (35, 82), "ANTERIOR = RING MARKER · NO EYE · 1:1 WORLD SCALE · ALL MOTION FROM C++ PHYSICS", (143, 203, 191), small)

    left_frame = selected_frame(scenarios["positive_y_gradient"], index, count)
    dorsal_frame = selected_frame(scenarios["positive_z_gradient"], index, count)
    t = left_frame["time_s"]
    label(draw, (34, 500), f"t = {t:04.2f} s", (236, 221, 201), mono)
    label(draw, (180, 500), "SPATIAL MOTOR ACTIVATION", (184, 167, 193), mono)
    names = ("L", "R", "D", "V")
    colors = ((78, 218, 210), (240, 93, 150), (244, 184, 80), (142, 111, 226))
    for offset, (name, color, value) in enumerate(
        zip(names, colors, left_frame["channel_activation"], strict=True)
    ):
        bar(draw, 180 + (offset % 2) * 148, 526 + (offset // 2) * 28, value, color, name, small)
    for offset, (name, color, value) in enumerate(
        zip(names, colors, dorsal_frame["channel_activation"], strict=True)
    ):
        bar(draw, 494 + (offset % 2) * 148, 526 + (offset // 2) * 28, value, color, name, small)

    summaries = scenarios
    left_summary = summaries["positive_y_gradient"]["result_summary"]
    right_summary = summaries["negative_y_gradient"]["result_summary"]
    dorsal_summary = summaries["positive_z_gradient"]["result_summary"]
    lesion_summary = summaries["positive_y_right_sensor_lesion"]["result_summary"]
    label(draw, (34, 605), "CHECKED FINAL GATES", (111, 222, 168), mono)
    label(draw, (34, 630), f"mirror yaw   {left_summary['heading_change_deg']:+.3f}° / {right_summary['heading_change_deg']:+.3f}°", (195, 181, 201), small)
    label(draw, (34, 651), f"dorsal lift  {dorsal_summary['displacement_um'][2]:.2f} µm / pitch {dorsal_summary['head_pitch_change_deg']:.2f}°", (195, 181, 201), small)
    label(draw, (390, 630), f"sensor lesion yaw {lesion_summary['heading_change_deg']:+.3f}°", (195, 181, 201), small)
    label(draw, (390, 651), "uniform crawl = Stage 8 exact · no action command API", (195, 181, 201), small)
    label(draw, (1045, 684), "HOST DIAGNOSTIC · MODEL_FITTED · release_validated=false", (242, 171, 102), small, anchor="rs")
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(output: Path) -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if (
        artifact["schema"] != "l1_native_environment_closed_loop_v1"
        or artifact["release_validated"] is not False
        or artifact["direct_behavior_command"] is not False
        or not all(artifact["acceptance_gates"].values())
    ):
        raise RuntimeError("Stage 9 GIF source contract is invalid")
    count = 51
    frames = [render_frame(index, artifact, count) for index in range(count)]
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
        disposal=2,
        optimize=True,
    )
    print(f"wrote {output.relative_to(ROOT)}: {len(frames)} frames")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    render(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
