#!/usr/bin/env python3
"""Render the frozen repeat-crawl trajectory as an honest animated GIF."""

from __future__ import annotations

import argparse
import json
from math import hypot
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY = ROOT / "data" / "trajectories" / "l1_repeat_crawl_v0.json"
BODY = ROOT / "data" / "body" / "l1_body_v0.json"
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "oraclarva_repeat_crawl.gif"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
WIDTH, HEIGHT, SS = 1080, 720, 2
FRAME_COUNT = 51
FRAME_DURATION_MS = 80
WORLD_X = (-80.0, 1520.0)
WORLD_Y = (-260.0, 260.0)
BODY_RECT = (54.0, 105.0, 1026.0, 435.0)
WAVE_SEGMENTS = ("A6", "A5", "A4", "A3", "A2", "A1")


def font(path: Path, size: int):
    return ImageFont.truetype(str(path), size * SS) if path.exists() else ImageFont.load_default()


def scaled(point):
    return tuple(round(value * SS) for value in point)


def mix(left, right, amount):
    amount = min(1.0, max(0.0, amount))
    return tuple(round(a * (1.0 - amount) + b * amount) for a, b in zip(left, right, strict=True))


def label(draw, xy, value, fill, face, anchor=None):
    draw.text(scaled(xy), value, fill=fill, font=face, anchor=anchor)


def world_to_screen(node):
    left, top, right, bottom = BODY_RECT
    x = left + (node[0] - WORLD_X[0]) / (WORLD_X[1] - WORLD_X[0]) * (right - left)
    y = (top + bottom) / 2 - node[1] / (WORLD_Y[1] - WORLD_Y[0]) * (bottom - top)
    return x, y


def node_profile(values):
    return [
        values[0] * 0.55,
        *[(values[i - 1] + values[i]) / 2 for i in range(1, len(values))],
        values[-1] * 0.45,
    ]


def node_normals(nodes):
    normals = []
    for i in range(len(nodes)):
        if i == 0:
            dx, dy = nodes[1][0] - nodes[0][0], nodes[1][1] - nodes[0][1]
        elif i == len(nodes) - 1:
            dx, dy = nodes[-1][0] - nodes[-2][0], nodes[-1][1] - nodes[-2][1]
        else:
            dx, dy = nodes[i + 1][0] - nodes[i - 1][0], nodes[i + 1][1] - nodes[i - 1][1]
        magnitude = max(1e-9, hypot(dx, dy))
        normals.append((-dy / magnitude, dx / magnitude))
    return normals


def smooth_profile(profile, iterations=3):
    values = list(profile)
    for _ in range(iterations):
        refined = [values[0]]
        for left, right in zip(values, values[1:], strict=False):
            refined.append(tuple(0.75 * a + 0.25 * b for a, b in zip(left, right, strict=True)))
            refined.append(tuple(0.25 * a + 0.75 * b for a, b in zip(left, right, strict=True)))
        refined.append(values[-1])
        values = refined
    return values


def draw_body(draw, frame, body):
    nodes = [world_to_screen(node) for node in frame["nodes_um"]]
    maximum_width_um = body["global_geometry"]["maximum_width_m"]["nominal"] * 1e6
    widths = [item["width_scale"] * maximum_width_um for item in body["segments"]]
    pixels_per_um_y = (BODY_RECT[3] - BODY_RECT[1]) / (WORLD_Y[1] - WORLD_Y[0])
    radii = [value * pixels_per_um_y / 2 for value in node_profile(widths)]
    segment_activation = [
        float(frame["segment_activation"].get(item["id"], 0.0))
        for item in body["segments"]
    ]
    node_activation = [
        segment_activation[0],
        *[
            0.5 * (segment_activation[i - 1] + segment_activation[i])
            for i in range(1, len(segment_activation))
        ],
        segment_activation[-1],
    ]
    profile = smooth_profile(
        [
            (point[0], point[1], radius, activation)
            for point, radius, activation in zip(
                nodes, radii, node_activation, strict=True
            )
        ]
    )
    centers = [(item[0], item[1]) for item in profile]
    smooth_radii = [item[2] for item in profile]
    activations = [item[3] for item in profile]
    outline = (101, 57, 64)
    skin = (218, 167, 103)
    for color, padding in ((outline, 5.0), (skin, 0.0)):
        for index in range(len(centers) - 1):
            radius = 0.5 * (smooth_radii[index] + smooth_radii[index + 1])
            draw.line(
                [scaled(centers[index]), scaled(centers[index + 1])],
                fill=color,
                width=max(2 * SS, round((2.0 * radius + padding) * SS)),
            )
        for center, radius in zip(centers, smooth_radii, strict=True):
            expanded = radius + padding / 2.0
            draw.ellipse(
                (
                    *scaled((center[0] - expanded, center[1] - expanded)),
                    *scaled((center[0] + expanded, center[1] + expanded)),
                ),
                fill=color,
            )
    for index in range(len(centers) - 1):
        activation = 0.5 * (activations[index] + activations[index + 1])
        if activation <= 0.01:
            continue
        radius = 0.5 * (smooth_radii[index] + smooth_radii[index + 1])
        color = mix(skin, (243, 68, 104), activation * 0.95)
        draw.line(
            [scaled(centers[index]), scaled(centers[index + 1])],
            fill=color,
            width=max(2 * SS, round(1.25 * radius * SS)),
        )
    draw.line(
        [scaled(center) for center in centers],
        fill=(244, 195, 132),
        width=SS,
        joint="curve",
    )
    head = centers[0]
    radius = smooth_radii[0] * 0.30
    draw.ellipse(
        (
            *scaled((head[0] - radius, head[1] - radius)),
            *scaled((head[0] + radius, head[1] + radius)),
        ),
        fill=(82, 35, 47),
    )

def draw_wave_panel(draw, trajectory, frame_index):
    frames = trajectory["frames"]
    left, top, right = 74.0, 492.0, 790.0
    row_height = 25.0
    small = font(FONT_MONO, 9)
    for row, segment in enumerate(WAVE_SEGMENTS):
        y0 = top + row * row_height
        label(draw, (54, y0 + 10), segment, (203, 184, 199), small, anchor="rm")
        draw.rounded_rectangle(
            (*scaled((left, y0)), *scaled((right, y0 + 18))),
            radius=4 * SS,
            fill=(22, 16, 29),
        )
        for i, source in enumerate(frames):
            x0 = left + i / len(frames) * (right - left)
            x1 = left + (i + 1) / len(frames) * (right - left)
            value = float(source["segment_activation"].get(segment, 0.0))
            color = mix((33, 24, 40), (243, 68, 104), value)
            draw.rectangle((*scaled((x0, y0 + 1)), *scaled((x1 + 1, y0 + 17))), fill=color)
    cursor = left + frame_index / (len(frames) - 1) * (right - left)
    draw.line((*scaled((cursor, top - 5)), *scaled((cursor, top + 6 * row_height - 5))), fill=(255, 235, 195), width=2 * SS)


def render_frame(trajectory, body, index):
    frame = trajectory["frames"][index]
    canvas = Image.new("RGB", (WIDTH * SS, HEIGHT * SS), "#0d0912")
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        color = mix((13, 9, 18), (29, 18, 35), y / HEIGHT)
        draw.line((0, y * SS, WIDTH * SS, y * SS), fill=color, width=SS)
    title, mono, small = font(FONT_BOLD, 25), font(FONT_MONO, 10), font(FONT_MONO, 8)
    label(draw, (42, 25), "ORACLARVA / REPEAT CRAWL", (245, 231, 211), title)
    label(draw, (43, 62), "ONE POSTERIOR TOUCH → SENSORY → LIF → MN → 146 FIBERS → 13-NODE BODY → SENSORY", (168, 145, 169), mono)
    draw.rounded_rectangle((*scaled((36, 92)), *scaled((1044, 450))), radius=18 * SS, fill=(17, 12, 23), outline=(58, 41, 64), width=SS)
    for tick in range(0, 1501, 250):
        x, _ = world_to_screen((tick, 0, 0))
        draw.line((*scaled((x, 115)), *scaled((x, 422))), fill=(34, 25, 41), width=SS)
        label(draw, (x, 430), f"{tick} µm", (96, 80, 102), small, anchor="ms")
    draw.line((*scaled((BODY_RECT[0], 270)), *scaled((BODY_RECT[2], 270))), fill=(48, 36, 51), width=SS)
    draw_body(draw, frame, body)
    time_s = float(frame["time_s"])
    summary = trajectory["result_summary"]
    label(draw, (54, 112), f"t = {time_s:05.2f} s", (238, 216, 193), mono)
    label(draw, (1024, 112), f"checked displacement = {summary['displacement_x_um']:.1f} µm", (238, 216, 193), mono, anchor="ra")
    label(draw, (42, 470), "A6 → A1 named-fiber activation", (224, 205, 187), mono)
    draw_wave_panel(draw, trajectory, index)
    metrics = summary["cycle_metrics"]["median"]
    x = 827
    label(draw, (x, 492), "FROZEN RESULT", (224, 205, 187), mono)
    label(draw, (x, 520), f"cycles       3", (185, 164, 183), small)
    label(draw, (x, 540), f"period       {metrics['period_s']:.3f} s   PASS", (116, 215, 167), small)
    label(draw, (x, 560), f"stride       {metrics['stride_um']:.1f} µm  PASS", (116, 215, 167), small)
    label(draw, (x, 580), f"wave speed   {metrics['a1_a6_wave_speed_segments_s']:.3f} seg/s PASS", (116, 215, 167), small)
    label(draw, (x, 604), "amplitude    FAIL", (244, 116, 133), small)
    label(draw, (x, 624), "duty         FAIL", (244, 116, 133), small)
    label(draw, (42, 680), "release_validated = false", (150, 126, 149), small)
    label(draw, (1038, 680), "NO GAIT COMMAND / NO FSM / NO AUTHORED MOTION", (150, 126, 149), small, anchor="rs")
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(output: Path) -> None:
    trajectory = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    body = json.loads(BODY.read_text(encoding="utf-8"))
    metrics = trajectory["result_summary"]["cycle_metrics"]
    if (
        trajectory["release_validated"] is not False
        or trajectory["action_command"] is not False
        or trajectory["periodic_stimulus"] is not False
        or trajectory["node_count"] != 13
        or metrics["complete_cycle_count"] < 3
    ):
        raise RuntimeError("repeat-crawl GIF source contract is invalid")
    count = len(trajectory["frames"])
    indices = [round(i * (count - 1) / (FRAME_COUNT - 1)) for i in range(FRAME_COUNT)]
    frames = [render_frame(trajectory, body, index) for index in indices]
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
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
