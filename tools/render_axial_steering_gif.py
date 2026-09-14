#!/usr/bin/env python3
"""Render mirrored axial-v1 field steering from the checked trajectory."""

from __future__ import annotations

import argparse
import json
from math import hypot
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY = ROOT / "data/trajectories/l1_axial_steering_v1.json"
BODY = ROOT / "data/body/l1_body_v0.json"
DEFAULT_OUTPUT = ROOT / "docs/assets/oraclarva_axial_steering_v1.gif"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
WIDTH, HEIGHT, SS = 1280, 720, 2
FRAME_COUNT = 61
FRAME_DURATION_MS = 70
WORLD_X = (-330.0, 980.0)
WORLD_Y = (-190.0, 190.0)
PANELS = ((40, 125, 620, 560), (660, 125, 1240, 560))


def font(path: Path, size: int):
    if path.exists():
        return ImageFont.truetype(str(path), size * SS)
    return ImageFont.load_default()


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


def world_to_screen(x_um, y_um, panel):
    x = panel[0] + (x_um - WORLD_X[0]) / (WORLD_X[1] - WORLD_X[0]) * (
        panel[2] - panel[0]
    )
    y = panel[3] - (y_um - WORLD_Y[0]) / (WORLD_Y[1] - WORLD_Y[0]) * (
        panel[3] - panel[1]
    )
    return x, y


def node_widths_um(body):
    maximum = body["global_geometry"]["maximum_width_m"]["nominal"] * 1e6
    segments = [item["width_scale"] * maximum for item in body["segments"]]
    return [
        segments[0] * 0.55,
        *[
            0.5 * (segments[index - 1] + segments[index])
            for index in range(1, len(segments))
        ],
        segments[-1] * 0.45,
    ]


def field_intensity(y_um, gradient):
    return min(1.0, max(0.0, 0.5 + gradient * y_um * 1e-6))


def draw_field(draw, panel, gradient):
    top, bottom = panel[1], panel[3]
    for row in range(round(top), round(bottom)):
        world_y = WORLD_Y[1] - (row - top) / (bottom - top) * (
            WORLD_Y[1] - WORLD_Y[0]
        )
        intensity = field_intensity(world_y, gradient)
        color = mix((18, 23, 31), (39, 112, 105), intensity)
        draw.line(
            (*scaled((panel[0], row)), *scaled((panel[2], row))),
            fill=color,
            width=SS,
        )
    for x_um in range(-200, 1001, 200):
        x, _ = world_to_screen(x_um, 0.0, panel)
        draw.line(
            (*scaled((x, panel[1])), *scaled((x, panel[3]))),
            fill=(53, 68, 72),
            width=SS,
        )
    for y_um in (-100, 0, 100):
        _, y = world_to_screen(0.0, y_um, panel)
        draw.line(
            (*scaled((panel[0], y)), *scaled((panel[2], y))),
            fill=(53, 68, 72),
            width=SS,
        )


def surface_polygon(points, widths_px):
    left = []
    right = []
    for index, point in enumerate(points):
        before = points[max(0, index - 1)]
        after = points[min(len(points) - 1, index + 1)]
        dx = after[0] - before[0]
        dy = after[1] - before[1]
        length = hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        radius = widths_px[index] * 0.5
        left.append((point[0] + nx * radius, point[1] + ny * radius))
        right.append((point[0] - nx * radius, point[1] - ny * radius))
    return left + list(reversed(right)), left, right


def draw_body(draw, frame, body, panel):
    points = [
        world_to_screen(float(node[0]), float(node[1]), panel)
        for node in frame["nodes_um"]
    ]
    widths_um = node_widths_um(body)
    pixels_per_um = min(
        (panel[2] - panel[0]) / (WORLD_X[1] - WORLD_X[0]),
        (panel[3] - panel[1]) / (WORLD_Y[1] - WORLD_Y[0]),
    )
    widths_px = [value * pixels_per_um for value in widths_um]
    polygon, left_surface, right_surface = surface_polygon(points, widths_px)
    outline = [(x * SS, y * SS) for x, y in polygon]
    draw.polygon(outline, fill=(178, 174, 142), outline=(235, 220, 178))

    left_values = frame["segment_activation_left"]
    right_values = frame["segment_activation_right"]
    segments = [item["id"] for item in body["segments"]]
    for index in range(len(points) - 1):
        segment = segments[index]
        left_activation = float(left_values.get(segment, 0.0))
        right_activation = float(right_values.get(segment, 0.0))
        for surface, activation, active_color in (
            (left_surface, left_activation, (240, 79, 105)),
            (right_surface, right_activation, (77, 211, 195)),
        ):
            if activation <= 0.015:
                continue
            draw.line(
                [scaled(surface[index]), scaled(surface[index + 1])],
                fill=mix((126, 119, 105), active_color, activation),
                width=max(2 * SS, round(4 * SS * activation)),
            )

    head = points[0]
    next_point = points[1]
    dx, dy = head[0] - next_point[0], head[1] - next_point[1]
    length = hypot(dx, dy) or 1.0
    tip = (head[0] + dx / length * 22, head[1] + dy / length * 22)
    draw.line(
        [scaled(head), scaled(tip)], fill=(245, 226, 179), width=2 * SS
    )
    label(
        draw,
        (tip[0], tip[1] - 8),
        "ANTERIOR",
        (242, 222, 184),
        font(FONT_MONO, 7),
        anchor="ms",
    )

    # External brackets show sampled sides without adding eye-like body dots.
    left_field = float(frame["field_left"])
    right_field = float(frame["field_right"])
    label(
        draw,
        (panel[0] + 13, panel[3] - 33),
        f"L HEAD FIELD {left_field:.3f}",
        mix((121, 118, 130), (240, 79, 105), left_field),
        font(FONT_MONO, 8),
    )
    label(
        draw,
        (panel[2] - 13, panel[3] - 33),
        f"R HEAD FIELD {right_field:.3f}",
        mix((121, 118, 130), (77, 211, 195), right_field),
        font(FONT_MONO, 8),
        anchor="ra",
    )


def render_frame(artifact, body, frame_index):
    canvas = Image.new("RGB", (WIDTH * SS, HEIGHT * SS), "#090c11")
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        draw.line(
            (0, y * SS, WIDTH * SS, y * SS),
            fill=mix((9, 12, 17), (19, 18, 27), y / HEIGHT),
            width=SS,
        )
    label(
        draw,
        (40, 22),
        "ORACLARVA / AXIAL-v1 + BILATERAL FIELD STEERING",
        (241, 231, 213),
        font(FONT_BOLD, 24),
    )
    label(
        draw,
        (41, 60),
        "WORLD FIELD -> L/R HEAD SENSORS -> LIF -> A1-A3 MNs -> NAMED FIBERS -> 3D BODY + CONTACT",
        (151, 174, 172),
        font(FONT_MONO, 9),
    )

    cases = (
        ("positive_y_gradient", "+Y FIELD GRADIENT", 5000.0),
        ("negative_y_gradient", "-Y FIELD GRADIENT", -5000.0),
    )
    for panel, (key, title, gradient) in zip(PANELS, cases, strict=True):
        scenario = artifact["scenarios"][key]
        frames = scenario["trajectory_samples"]
        index = round(frame_index * (len(frames) - 1) / (FRAME_COUNT - 1))
        frame = frames[index]
        draw.rounded_rectangle(
            (*scaled((panel[0] - 2, panel[1] - 35)), *scaled((panel[2] + 2, panel[3] + 2))),
            radius=14 * SS,
            fill=(16, 19, 25),
            outline=(66, 73, 78),
            width=SS,
        )
        draw_field(draw, panel, gradient)
        draw_body(draw, frame, body, panel)
        label(
            draw,
            (panel[0] + 10, panel[1] - 26),
            title,
            (229, 211, 185),
            font(FONT_BOLD, 10),
        )
        label(
            draw,
            (panel[2] - 10, panel[1] - 26),
            f"yaw {float(frame['heading_change_deg']):+.2f} deg",
            (154, 205, 193),
            font(FONT_MONO, 9),
            anchor="ra",
        )

    time_s = frame_index / (FRAME_COUNT - 1) * artifact["duration_s"]
    positive = artifact["scenarios"]["positive_y_gradient"]
    negative = artifact["scenarios"]["negative_y_gradient"]
    label(draw, (40, 590), f"t = {time_s:04.2f} s", (230, 213, 190), font(FONT_MONO, 10))
    label(
        draw,
        (640, 590),
        "DISTRIBUTED PIVOT T3-A3 / L2 RELATIVE SUPPORT ONLY",
        (154, 205, 193),
        font(FONT_MONO, 9),
        anchor="ma",
    )
    label(
        draw,
        (40, 623),
        f"final mirrored yaw  {positive['heading_change_deg']:+.2f} / {negative['heading_change_deg']:+.2f} deg",
        (226, 187, 128),
        font(FONT_BOLD, 12),
    )
    label(
        draw,
        (40, 655),
        "LEFT/RIGHT COLORS ARE MUSCLE ACTIVATION RAILS, NOT EYES",
        (145, 132, 151),
        font(FONT_MONO, 8),
    )
    label(
        draw,
        (1240, 623),
        "NO TURN COMMAND / NO TARGET HEADING / NO AUTHORED TRANSLATION",
        (145, 132, 151),
        font(FONT_MONO, 8),
        anchor="ra",
    )
    label(
        draw,
        (1240, 655),
        "RESEARCH APPROXIMATION / release_validated=false",
        (145, 132, 151),
        font(FONT_MONO, 8),
        anchor="ra",
    )
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(output: Path) -> None:
    artifact = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    body = json.loads(BODY.read_text(encoding="utf-8"))
    positive = artifact["scenarios"]["positive_y_gradient"]
    negative = artifact["scenarios"]["negative_y_gradient"]
    if (
        artifact["release_validated"] is not False
        or artifact["action_command"] is not False
        or artifact["target_heading_input"] is not False
        or artifact["yaw_input_to_body"] is not False
        or artifact["anterior_pivot"]["mechanical_joint_support"]
        != ["T3-A1", "A1-A2", "A2-A3", "A3-A4"]
        or artifact["anterior_pivot"]["published_stage"] != "L2"
        or positive["heading_change_deg"] >= 0.0
        or negative["heading_change_deg"] <= 0.0
        or positive["all_active_forces_sensory_traced"] is not True
        or negative["all_active_forces_sensory_traced"] is not True
    ):
        raise RuntimeError("axial-steering GIF source contract is invalid")
    frames = [render_frame(artifact, body, index) for index in range(FRAME_COUNT)]
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
