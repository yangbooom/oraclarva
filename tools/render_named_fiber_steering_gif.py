#!/usr/bin/env python3
"""Render Stage 10 mirrored steering with named attachment lines."""

from __future__ import annotations

import argparse
import json
from math import hypot, sin
from pathlib import Path

from PIL import Image, ImageDraw

from oraclarva.named_fiber_steering import NamedFiberSteeringLarva
from render_axial_steering_gif import (
    BODY,
    FONT_BOLD,
    FONT_MONO,
    FRAME_COUNT,
    FRAME_DURATION_MS,
    HEIGHT,
    PANELS,
    ROOT,
    SS,
    WIDTH,
    WORLD_X,
    WORLD_Y,
    draw_body,
    draw_field,
    font,
    label,
    mix,
    scaled,
    world_to_screen,
)


TRAJECTORY = ROOT / "data/trajectories/l1_named_fiber_steering_v1.json"
DEFAULT_OUTPUT = ROOT / "docs/assets/oraclarva_named_fiber_steering_v1.gif"


def attachment_point_screen(frame, body, geometry, coordinate, panel):
    left_node = frame["nodes_um"][geometry.segment_index]
    right_node = frame["nodes_um"][geometry.segment_index + 1]
    left = world_to_screen(float(left_node[0]), float(left_node[1]), panel)
    right = world_to_screen(float(right_node[0]), float(right_node[1]), panel)
    dx = right[0] - left[0]
    dy = right[1] - left[1]
    length = hypot(dx, dy) or 1.0
    lateral_x, lateral_y = -dy / length, dx / length
    center_x = left[0] * (1.0 - coordinate.s) + right[0] * coordinate.s
    center_y = left[1] * (1.0 - coordinate.s) + right[1] * coordinate.s
    maximum_width_um = (
        float(body["global_geometry"]["maximum_width_m"]["nominal"]) * 1e6
    )
    width_um = (
        float(body["segments"][geometry.segment_index]["width_scale"])
        * maximum_width_um
    )
    pixels_per_um = min(
        (panel[2] - panel[0]) / (WORLD_X[1] - WORLD_X[0]),
        (panel[3] - panel[1]) / (WORLD_Y[1] - WORLD_Y[0]),
    )
    lateral_offset = (
        0.5
        * width_um
        * pixels_per_um
        * (1.0 - coordinate.depth_fraction)
        * sin(coordinate.theta_rad)
    )
    return (
        center_x + lateral_x * lateral_offset,
        center_y + lateral_y * lateral_offset,
    )


def draw_attachment_lines(draw, frame, body, panel, geometries):
    left_values = frame["segment_activation_left"]
    right_values = frame["segment_activation_right"]
    for geometry in geometries:
        activation = float(
            (left_values if geometry.side == "left" else right_values)[
                geometry.segment_id
            ]
        )
        origin = attachment_point_screen(
            frame, body, geometry, geometry.origin, panel
        )
        insertion = attachment_point_screen(
            frame, body, geometry, geometry.insertion, panel
        )
        color = (
            mix((126, 105, 111), (240, 79, 105), activation)
            if geometry.side == "left"
            else mix((91, 121, 120), (77, 221, 205), activation)
        )
        draw.line(
            [
                scaled(origin),
                scaled(insertion),
            ],
            fill=color,
            width=max(1, round((0.8 + 1.8 * activation) * SS)),
        )


def render_frame(artifact, body, geometries, frame_index):
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
        "ORACLARVA / NAMED-FIBER ATTACHMENT STEERING",
        (241, 231, 213),
        font(FONT_BOLD, 24),
    )
    label(
        draw,
        (41, 60),
        "FIELD -> L/R SENSOR -> LIF -> A1-A3 MN -> 17 MIRRORED FIBER PAIRS -> 3D FORCE + CONTACT",
        (151, 174, 172),
        font(FONT_MONO, 9),
    )

    cases = (
        ("positive_y_gradient", "+Y FIELD GRADIENT", 5000.0),
        ("negative_y_gradient", "-Y FIELD GRADIENT", -5000.0),
    )
    selected_frames = []
    for panel, (key, title, gradient) in zip(PANELS, cases, strict=True):
        scenario = artifact["scenarios"][key]
        frames = scenario["trajectory_samples"]
        index = round(frame_index * (len(frames) - 1) / (FRAME_COUNT - 1))
        frame = frames[index]
        selected_frames.append(frame)
        draw.rounded_rectangle(
            (*scaled((panel[0] - 2, panel[1] - 35)), *scaled((panel[2] + 2, panel[3] + 2))),
            radius=14 * SS,
            fill=(16, 19, 25),
            outline=(66, 73, 78),
            width=SS,
        )
        draw_field(draw, panel, gradient)
        draw_body(draw, frame, body, panel)
        draw_attachment_lines(draw, frame, body, panel, geometries)
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
            f"heading {float(frame['heading_change_deg']):+.3f} deg",
            (154, 205, 193),
            font(FONT_MONO, 9),
            anchor="ra",
        )

    time_s = frame_index / (FRAME_COUNT - 1) * artifact["duration_s"]
    left_torque = float(selected_frames[0]["attachment_torque_z_model_units_m"])
    right_torque = float(selected_frames[1]["attachment_torque_z_model_units_m"])
    label(
        draw, (40, 590), f"t = {time_s:04.2f} s", (230, 213, 190), font(FONT_MONO, 10)
    )
    label(
        draw,
        (640, 590),
        f"instant attachment Mz  {left_torque:+.2e} / {right_torque:+.2e}",
        (154, 205, 193),
        font(FONT_MONO, 9),
        anchor="ma",
    )
    label(
        draw,
        (40, 623),
        "COLORED LINES = ANATOMY_DERIVED ATTACHMENTS / FORCE = MODEL_FITTED UNITS",
        (226, 187, 128),
        font(FONT_BOLD, 10),
    )
    label(
        draw,
        (40, 655),
        "A1 LEFT HYPOTHESIS -> RIGHT MIRROR -> A2-A3 HOMOLOGY / NOT MEASURED 3D COORDINATES",
        (145, 132, 151),
        font(FONT_MONO, 8),
    )
    label(
        draw,
        (1240, 623),
        "ACTIVE CURVATURE OFF / NO YAW COMMAND / NO TARGET HEADING",
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
    larva = NamedFiberSteeringLarva()
    paired_ids = {fiber_id for pair in larva.attachment_fiber_pairs for fiber_id in pair}
    geometries = tuple(
        item for item in larva.coupling.geometries if item.fiber_id in paired_ids
    )
    positive = artifact["scenarios"]["positive_y_gradient"]
    negative = artifact["scenarios"]["negative_y_gradient"]
    if (
        artifact["release_validated"] is not False
        or artifact["attachment_pair_count"] != 17
        or artifact["active_curvature_constraint"] is not False
        or artifact["yaw_input_to_body"] is not False
        or positive["heading_change_deg"] <= 0.0
        or negative["heading_change_deg"] >= 0.0
        or positive["attachment_active_force_samples"]
        != positive["attachment_traced_force_samples"]
        or len(geometries) != 34
    ):
        raise RuntimeError("named-fiber steering GIF source contract is invalid")
    frames = [
        render_frame(artifact, body, geometries, index)
        for index in range(FRAME_COUNT)
    ]
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
