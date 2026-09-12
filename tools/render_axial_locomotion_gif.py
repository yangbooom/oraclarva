#!/usr/bin/env python3
"""Render checked forward/backward axial trajectories side by side."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY = ROOT / "data" / "trajectories" / "l1_axial_locomotion_v1.json"
BODY = ROOT / "data" / "body" / "l1_body_v0.json"
DEFAULT_OUTPUT = (
    ROOT / "docs" / "assets" / "oraclarva_axial_locomotion_v1.gif"
)
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
WIDTH, HEIGHT, SS = 1280, 720, 2
FRAME_COUNT = 61
FRAME_DURATION_MS = 70
WORLD_X = (-180.0, 1080.0)
PANELS = ((45, 135, 615, 465), (665, 135, 1235, 465))
AXIAL_SEGMENTS = ("A1", "A2", "A3", "A4", "A5", "A6")


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


def node_widths(body):
    maximum = body["global_geometry"]["maximum_width_m"]["nominal"] * 1e6
    segment = [item["width_scale"] * maximum for item in body["segments"]]
    return [
        segment[0] * 0.55,
        *[
            0.5 * (segment[index - 1] + segment[index])
            for index in range(1, len(segment))
        ],
        segment[-1] * 0.45,
    ]


def screen_x(value, panel):
    return panel[0] + (value - WORLD_X[0]) / (
        WORLD_X[1] - WORLD_X[0]
    ) * (panel[2] - panel[0])


def draw_body(draw, frame, body, panel):
    center_y = 0.5 * (panel[1] + panel[3]) - 12
    xs = [screen_x(float(node[0]), panel) for node in frame["nodes_um"]]
    widths = node_widths(body)
    pixels_per_um = (panel[2] - panel[0]) / (WORLD_X[1] - WORLD_X[0])
    radii = [0.5 * width * pixels_per_um for width in widths]
    segments = [item["id"] for item in body["segments"]]
    activations = [
        float(frame["segment_activation"].get(segment, 0.0))
        for segment in segments
    ]
    node_activation = [
        activations[0],
        *[
            0.5 * (activations[index - 1] + activations[index])
            for index in range(1, len(activations))
        ],
        activations[-1],
    ]

    for color, padding in (((66, 45, 69), 5.0), ((212, 171, 112), 0.0)):
        for index in range(len(xs) - 1):
            radius = 0.5 * (radii[index] + radii[index + 1])
            draw.line(
                [
                    scaled((xs[index], center_y)),
                    scaled((xs[index + 1], center_y)),
                ],
                fill=color,
                width=max(2 * SS, round((2 * radius + padding) * SS)),
            )
        for x, radius in zip(xs, radii, strict=True):
            expanded = radius + padding / 2.0
            draw.ellipse(
                (
                    *scaled((x - expanded, center_y - expanded)),
                    *scaled((x + expanded, center_y + expanded)),
                ),
                fill=color,
            )

    for index in range(len(xs) - 1):
        activation = 0.5 * (
            node_activation[index] + node_activation[index + 1]
        )
        if activation <= 0.01:
            continue
        radius = 0.5 * (radii[index] + radii[index + 1])
        draw.line(
            [
                scaled((xs[index], center_y)),
                scaled((xs[index + 1], center_y)),
            ],
            fill=mix((212, 171, 112), (241, 73, 107), activation),
            width=max(2 * SS, round(1.25 * radius * SS)),
        )

    initial_center = 0.5 * (
        float(frame["nodes_um"][0][0]) + float(frame["nodes_um"][-1][0])
    )
    center_x = screen_x(initial_center, panel)
    draw.line(
        (*scaled((center_x, panel[1] + 45)), *scaled((center_x, panel[3] - 50))),
        fill=(93, 76, 96),
        width=SS,
    )
    label(
        draw,
        (xs[0], center_y - max(radii) - 15),
        "ANTERIOR",
        (147, 211, 194),
        font(FONT_MONO, 8),
        anchor="ms",
    )

    retention = frame["contact_retention_by_node"]
    cell_width = (panel[2] - panel[0] - 30) / len(retention)
    y = panel[3] - 34
    for index, value in enumerate(retention):
        left = panel[0] + 15 + index * cell_width
        draw.rectangle(
            (
                *scaled((left, y)),
                *scaled((left + cell_width - 2, y + 11)),
            ),
            fill=mix((35, 144, 132), (230, 177, 91), float(value)),
        )
    label(
        draw,
        (panel[0] + 15, y + 19),
        "PLANTED",
        (113, 173, 164),
        font(FONT_MONO, 7),
    )
    label(
        draw,
        (panel[2] - 15, y + 19),
        "RELEASED",
        (201, 161, 103),
        font(FONT_MONO, 7),
        anchor="ra",
    )


def active_segment(frame):
    values = {
        segment: float(frame["segment_activation"].get(segment, 0.0))
        for segment in AXIAL_SEGMENTS
    }
    segment = max(values, key=values.get)
    return segment if values[segment] > 0.02 else "-"


def render_frame(artifact, body, frame_index):
    canvas = Image.new("RGB", (WIDTH * SS, HEIGHT * SS), "#0b0a10")
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        draw.line(
            (0, y * SS, WIDTH * SS, y * SS),
            fill=mix((11, 10, 16), (24, 19, 28), y / HEIGHT),
            width=SS,
        )
    title = font(FONT_BOLD, 26)
    mono = font(FONT_MONO, 10)
    small = font(FONT_MONO, 8)
    label(
        draw,
        (40, 25),
        "ORACLARVA / BIDIRECTIONAL AXIAL CLOSED LOOP",
        (242, 231, 214),
        title,
    )
    label(
        draw,
        (41, 65),
        "TOUCH -> LIF CIRCUIT -> SHARED MNs -> 146 FIBERS -> BODY -> LOCAL CONTACT",
        (157, 142, 162),
        mono,
    )

    for panel, direction, heading, pathway in zip(
        PANELS,
        ("forward", "backward"),
        ("POSTERIOR TOUCH / FORWARD", "ANTERIOR TOUCH / BACKWARD"),
        ("A27h-LIKE  A6 -> A1", "MDN -> A18b-LIKE  A1 -> A6"),
        strict=True,
    ):
        draw.rounded_rectangle(
            (*scaled((panel[0], panel[1] - 20)), *scaled((panel[2], panel[3]))),
            radius=15 * SS,
            fill=(17, 14, 22),
            outline=(58, 45, 62),
            width=SS,
        )
        frames = artifact[direction]["trajectory_samples"]
        index = round(frame_index * (len(frames) - 1) / (FRAME_COUNT - 1))
        frame = frames[index]
        draw_body(draw, frame, body, panel)
        label(
            draw,
            (panel[0] + 15, panel[1]),
            heading,
            (230, 209, 190),
            mono,
        )
        label(
            draw,
            (panel[0] + 15, panel[1] + 24),
            pathway,
            (143, 205, 190),
            small,
        )
        initial_nodes = frames[0]["nodes_um"]
        current_center = sum(float(node[0]) for node in frame["nodes_um"]) / len(
            frame["nodes_um"]
        )
        initial_center = sum(float(node[0]) for node in initial_nodes) / len(
            initial_nodes
        )
        anatomical_forward = -(current_center - initial_center)
        label(
            draw,
            (panel[2] - 15, panel[1] + 24),
            f"active {active_segment(frame)} / anatomical forward {anatomical_forward:+.1f} um",
            (194, 174, 192),
            small,
            anchor="ra",
        )

    time_s = (
        frame_index
        / (FRAME_COUNT - 1)
        * float(artifact["forward"]["duration_s"])
    )
    label(draw, (40, 505), f"t = {time_s:04.2f} s", (224, 205, 187), mono)
    label(
        draw,
        (40, 543),
        "T fibers drive contact only; non-T fibers drive axial shortening and force.",
        (183, 164, 184),
        mono,
    )
    label(
        draw,
        (40, 570),
        "The T3 backward proxy is neural-traced and exerts zero axial force.",
        (183, 164, 184),
        mono,
    )
    forward = artifact["forward"]["anatomical_forward_displacement_um"]
    backward = artifact["backward"]["anatomical_forward_displacement_um"]
    label(
        draw,
        (40, 620),
        f"{artifact['forward']['duration_s']:.1f} s result   forward {forward:+.2f} um   backward {backward:+.2f} um",
        (226, 190, 133),
        font(FONT_BOLD, 13),
    )
    label(
        draw,
        (40, 670),
        "RESEARCH APPROXIMATION / MODEL_FITTED CONTACT PHASE / release_validated=false",
        (140, 122, 143),
        small,
    )
    label(
        draw,
        (1240, 670),
        "NO ACTION COMMAND / NO FSM / NO AUTHORED TRANSLATION",
        (140, 122, 143),
        small,
        anchor="ra",
    )
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(output: Path) -> None:
    artifact = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
    body = json.loads(BODY.read_text(encoding="utf-8"))
    if (
        artifact["release_validated"] is not False
        or artifact["action_command"] is not False
        or artifact["continuous_ground_contact"]["movement_direction_input"]
        is not False
        or artifact["shared_mapped_fiber_count"] != 146
        or artifact["forward"]["t3_contact_proxy_peak_activation"] != 0.0
        or artifact["backward"]["t3_contact_proxy_peak_activation"] <= 0.0
        or artifact["backward"]["t3_contact_proxy_neural_traced"] is not True
        or artifact["forward"]["anatomical_forward_displacement_um"] <= 0.0
        or artifact["backward"]["anatomical_forward_displacement_um"] >= 0.0
    ):
        raise RuntimeError("axial GIF source contract is invalid")
    frames = [
        render_frame(artifact, body, index)
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
