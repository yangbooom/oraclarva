#!/usr/bin/env python3
"""Render checked Python/C++ repeat-crawl parity frames as an animated GIF."""

from __future__ import annotations

import argparse
import json
from math import hypot
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "parity" / "repeat_crawl_native_parity_v1.json"
BODY = ROOT / "data" / "body" / "l1_body_v0.json"
DEFAULT_OUTPUT = (
    ROOT / "docs" / "assets" / "oraclarva_repeat_native_parity.gif"
)
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
WIDTH, HEIGHT, SS = 1080, 720, 2
DURATION_MS = 80
WORLD_X = (-600.0, 1000.0)
WORLD_Y = (-260.0, 260.0)


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
    draw.text(
        scaled(xy), value, fill=fill, font=face, anchor=anchor
    )


def node_profile(values):
    return [
        values[0] * 0.55,
        *[
            (values[index - 1] + values[index]) / 2.0
            for index in range(1, len(values))
        ],
        values[-1] * 0.45,
    ]


def smooth_profile(profile, iterations=3):
    values = list(profile)
    for _ in range(iterations):
        refined = [values[0]]
        for left, right in zip(values, values[1:], strict=False):
            refined.append(
                tuple(
                    0.75 * a + 0.25 * b
                    for a, b in zip(left, right, strict=True)
                )
            )
            refined.append(
                tuple(
                    0.25 * a + 0.75 * b
                    for a, b in zip(left, right, strict=True)
                )
            )
        refined.append(values[-1])
        values = refined
    return values


def world_to_panel(node, rect):
    left, top, right, bottom = rect
    return (
        left
        + (node[0] - WORLD_X[0])
        / (WORLD_X[1] - WORLD_X[0])
        * (right - left),
        (top + bottom) / 2
        - node[1]
        / (WORLD_Y[1] - WORLD_Y[0])
        * (bottom - top),
    )


def draw_body(draw, nodes_um, activation, body, rect, native):
    nodes = [world_to_panel(node, rect) for node in nodes_um]
    maximum_width_um = (
        body["global_geometry"]["maximum_width_m"]["nominal"] * 1e6
    )
    widths = [
        segment["width_scale"] * maximum_width_um
        for segment in body["segments"]
    ]
    pixels_per_um = (rect[3] - rect[1]) / (
        WORLD_Y[1] - WORLD_Y[0]
    )
    radii = [
        value * pixels_per_um / 2.0 for value in node_profile(widths)
    ]
    segment_activation = [
        float(activation.get(item["id"], 0.0))
        for item in body["segments"]
    ]
    node_activation = [
        segment_activation[0],
        *[
            0.5
            * (segment_activation[index - 1] + segment_activation[index])
            for index in range(1, len(segment_activation))
        ],
        segment_activation[-1],
    ]
    profile = smooth_profile(
        [
            (point[0], point[1], radius, active)
            for point, radius, active in zip(
                nodes, radii, node_activation, strict=True
            )
        ]
    )
    centers = [(item[0], item[1]) for item in profile]
    smooth_radii = [item[2] for item in profile]
    active_values = [item[3] for item in profile]
    outline = (74, 94, 104) if native else (101, 57, 64)
    skin = (112, 190, 184) if native else (218, 167, 103)
    for color, padding in ((outline, 4.0), (skin, 0.0)):
        for index in range(len(centers) - 1):
            radius = 0.5 * (
                smooth_radii[index] + smooth_radii[index + 1]
            )
            draw.line(
                [scaled(centers[index]), scaled(centers[index + 1])],
                fill=color,
                width=max(
                    2 * SS, round((2.0 * radius + padding) * SS)
                ),
            )
        for center, radius in zip(
            centers, smooth_radii, strict=True
        ):
            expanded = radius + padding / 2.0
            draw.ellipse(
                (
                    *scaled(
                        (center[0] - expanded, center[1] - expanded)
                    ),
                    *scaled(
                        (center[0] + expanded, center[1] + expanded)
                    ),
                ),
                fill=color,
            )
    for index in range(len(centers) - 1):
        active = 0.5 * (
            active_values[index] + active_values[index + 1]
        )
        if active <= 0.01:
            continue
        radius = 0.5 * (
            smooth_radii[index] + smooth_radii[index + 1]
        )
        draw.line(
            [scaled(centers[index]), scaled(centers[index + 1])],
            fill=mix(skin, (244, 71, 111), active * 0.95),
            width=max(2 * SS, round(1.15 * radius * SS)),
        )


def render_frame(index, report, body):
    frame = report["paired_frames"][index]
    canvas = Image.new(
        "RGB", (WIDTH * SS, HEIGHT * SS), "#0d0912"
    )
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        draw.line(
            (0, y * SS, WIDTH * SS, y * SS),
            fill=mix((13, 9, 18), (25, 19, 34), y / HEIGHT),
            width=SS,
        )
    title = font(FONT_BOLD, 25)
    mono = font(FONT_MONO, 10)
    small = font(FONT_MONO, 8)
    label(
        draw,
        (42, 25),
        "ORACLARVA / PYTHON ↔ C++17 REPEAT PARITY",
        (245, 231, 211),
        title,
    )
    label(
        draw,
        (43, 62),
        "SAME CHECKED FIXTURE · 164 LIF · 307 SYNAPSES · 146 FIBERS · 13 BODY NODES",
        (166, 145, 169),
        mono,
    )
    panels = ((38, 105, 526, 410), (554, 105, 1042, 410))
    for rect, heading in zip(
        panels, ("PYTHON SCIENTIFIC ORACLE", "C++17 NATIVE CORE"), strict=True
    ):
        draw.rounded_rectangle(
            (*scaled((rect[0], rect[1] - 15)), *scaled((rect[2], rect[3] + 28))),
            radius=16 * SS,
            fill=(17, 12, 23),
            outline=(55, 42, 63),
            width=SS,
        )
        label(
            draw,
            (rect[0] + 16, rect[1]),
            heading,
            (220, 202, 188),
            mono,
        )
        for tick in range(-400, 1001, 400):
            x = rect[0] + (
                (tick - WORLD_X[0])
                / (WORLD_X[1] - WORLD_X[0])
                * (rect[2] - rect[0])
            )
            draw.line(
                (*scaled((x, rect[1] + 25)), *scaled((x, rect[3]))),
                fill=(32, 25, 39),
                width=SS,
            )
    draw_body(
        draw,
        frame["python_nodes_um"],
        frame["segment_activation"],
        body,
        panels[0],
        False,
    )
    draw_body(
        draw,
        frame["native_nodes_um"],
        frame["segment_activation"],
        body,
        panels[1],
        True,
    )
    label(
        draw,
        (54, 91),
        "← ANATOMICAL FORWARD · ANTERIOR IS LEFT · NO EYE MARKER",
        (151, 207, 193),
        small,
    )
    label(
        draw,
        (54, 425),
        f"t = {frame['time_s']:05.2f} s",
        (223, 204, 187),
        mono,
    )
    label(
        draw,
        (1025, 425),
        f"frame node max = {frame['frame_max_node_error_um']:.2e} µm",
        (151, 207, 193),
        mono,
        anchor="ra",
    )

    plot = (54.0, 493.0, 750.0, 628.0)
    draw.rounded_rectangle(
        (*scaled((38, 462)), *scaled((772, 650))),
        radius=14 * SS,
        fill=(17, 12, 23),
        outline=(55, 42, 63),
        width=SS,
    )
    label(
        draw,
        (54, 475),
        "ERROR / DECLARED TOLERANCE",
        (220, 202, 188),
        mono,
    )
    node_tol = report["tolerances"]["sampled_node_um"]
    force_tol = report["tolerances"]["node_force_model_units"]
    frames = report["paired_frames"]
    node_values = [
        item["frame_max_node_error_um"] / node_tol for item in frames
    ]
    force_values = [
        item["frame_max_force_error_model_units"] / force_tol
        for item in frames
    ]
    for ratio, color in (
        (1.0, (82, 54, 72)),
        (0.5, (45, 35, 50)),
    ):
        y = plot[3] - ratio * (plot[3] - plot[1])
        draw.line(
            (*scaled((plot[0], y)), *scaled((plot[2], y))),
            fill=color,
            width=SS,
        )
    for values, color in (
        (node_values, (244, 171, 102)),
        (force_values, (98, 201, 190)),
    ):
        points = [
            (
                plot[0] + i / (len(values) - 1) * (plot[2] - plot[0]),
                plot[3] - min(1.0, value) * (plot[3] - plot[1]),
            )
            for i, value in enumerate(values)
        ]
        draw.line(
            [scaled(point) for point in points],
            fill=color,
            width=2 * SS,
            joint="curve",
        )
    cursor = plot[0] + index / (len(frames) - 1) * (
        plot[2] - plot[0]
    )
    draw.line(
        (*scaled((cursor, plot[1])), *scaled((cursor, plot[3]))),
        fill=(245, 229, 198),
        width=2 * SS,
    )
    label(draw, (55, 637), "node", (244, 171, 102), small)
    label(draw, (105, 637), "force", (98, 201, 190), small)
    label(draw, (745, 637), "limit = 1.0", (130, 111, 133), small, anchor="ra")

    errors = report["observed_maximum_errors"]
    label(draw, (805, 475), "PARITY PASS", (116, 215, 167), mono)
    label(draw, (805, 505), "spikes      exact", (182, 164, 183), small)
    label(
        draw,
        (805, 526),
        f"node max    {errors['sampled_node_um']:.2e} µm",
        (182, 164, 183),
        small,
    )
    label(
        draw,
        (805, 547),
        f"force max   {errors['node_force_model_units']:.2e}",
        (182, 164, 183),
        small,
    )
    label(draw, (805, 568), "cycles      3 / 3", (182, 164, 183), small)
    label(
        draw,
        (805, 589),
        f"max back    {report['sampled_progress']['full_timestep_python']['maximum_backward_retrace_um']:.1f} µm PASS",
        (116, 215, 167),
        small,
    )
    label(
        draw,
        (805, 618),
        "held-out diagnostic PASS*",
        (244, 174, 103),
        small,
    )
    label(
        draw,
        (42, 682),
        "release_validated = false",
        (148, 126, 149),
        small,
    )
    label(
        draw,
        (1038, 682),
        "NUMERICAL PARITY ≠ BIOLOGICAL VALIDATION",
        (148, 126, 149),
        small,
        anchor="rs",
    )
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(output: Path) -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    body = json.loads(BODY.read_text(encoding="utf-8"))
    if (
        report["status"] != "numerical_parity_passed"
        or report["release_validated"] is not False
        or len(report["paired_frames"]) != 51
        or not all(report["lesion_gates"].values())
        or not all(
            report["sampled_progress"]["movement_gate"].values()
        )
    ):
        raise RuntimeError("native repeat parity GIF source is invalid")
    frames = [
        render_frame(index, report, body)
        for index in range(len(report["paired_frames"]))
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=DURATION_MS,
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
