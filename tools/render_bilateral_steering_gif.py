"""Render the checked bilateral trajectory and its exact mirror as an animated GIF."""

from __future__ import annotations

import argparse
import json
from math import hypot
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY_PATH = ROOT / "data" / "trajectories" / "l1_bilateral_steering_v0.json"
BODY_PATH = ROOT / "data" / "body" / "l1_body_v0.json"
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "oraclarva_bilateral_steering.gif"
FONT_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")

WIDTH = 960
HEIGHT = 540
SUPERSAMPLE = 2
FRAME_STEP = 2
FRAME_DURATION_MS = 60
PIXELS_PER_UM = 0.82
X_ORIGIN = 74.0
PANEL_CENTERS = (174.0, 374.0)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path.exists():
        return ImageFont.truetype(str(path), size * SUPERSAMPLE)
    return ImageFont.load_default()


def scaled(point: tuple[float, float]) -> tuple[int, int]:
    return tuple(round(value * SUPERSAMPLE) for value in point)


def mix(
    left: tuple[int, int, int],
    right: tuple[int, int, int],
    amount: float,
) -> tuple[int, int, int]:
    amount = min(1.0, max(0.0, amount))
    return tuple(
        round(a * (1.0 - amount) + b * amount)
        for a, b in zip(left, right, strict=True)
    )


def node_profile(values: list[float]) -> list[float]:
    return [
        values[0] * 0.55,
        *[
            (values[index - 1] + value) / 2.0
            for index, value in enumerate(values[1:], 1)
        ],
        values[-1] * 0.45,
    ]


def text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    value: str,
    fill: tuple[int, int, int],
    text_font: ImageFont.ImageFont,
    *,
    anchor: str | None = None,
) -> None:
    draw.text(scaled(xy), value, fill=fill, font=text_font, anchor=anchor)


def mirrored_frame(frame: dict[str, object]) -> dict[str, object]:
    return {
        "time_s": frame["time_s"],
        "nodes_um": [[node[0], -node[1], node[2]] for node in frame["nodes_um"]],
        "segment_activation_left": frame["segment_activation_right"],
        "segment_activation_right": frame["segment_activation_left"],
    }


def screen_nodes(
    frame: dict[str, object],
    initial_head_x: float,
    center_y: float,
) -> list[tuple[float, float]]:
    return [
        (
            X_ORIGIN + (node[0] - initial_head_x) * PIXELS_PER_UM,
            center_y + node[1] * PIXELS_PER_UM,
        )
        for node in frame["nodes_um"]
    ]


def node_normals(nodes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result = []
    for index in range(len(nodes)):
        if index == 0:
            dx = nodes[1][0] - nodes[0][0]
            dy = nodes[1][1] - nodes[0][1]
        elif index == len(nodes) - 1:
            dx = nodes[-1][0] - nodes[-2][0]
            dy = nodes[-1][1] - nodes[-2][1]
        else:
            dx = nodes[index + 1][0] - nodes[index - 1][0]
            dy = nodes[index + 1][1] - nodes[index - 1][1]
        magnitude = hypot(dx, dy)
        result.append((-dy / magnitude, dx / magnitude))
    return result


def draw_larva(
    draw: ImageDraw.ImageDraw,
    frame: dict[str, object],
    body: dict[str, object],
    initial_head_x: float,
    center_y: float,
) -> None:
    nodes = screen_nodes(frame, initial_head_x, center_y)
    normals = node_normals(nodes)
    maximum_width_um = body["global_geometry"]["maximum_width_m"]["nominal"] * 1e6
    widths = [
        segment["width_scale"] * maximum_width_um
        for segment in body["segments"]
    ]
    radii = [value * PIXELS_PER_UM / 2.0 for value in node_profile(widths)]
    left_activation = frame["segment_activation_left"]
    right_activation = frame["segment_activation_right"]
    base = (211, 163, 109)
    active = (245, 78, 110)

    for index in range(len(nodes) - 1):
        c0, c1 = nodes[index], nodes[index + 1]
        n0, n1 = normals[index], normals[index + 1]
        left0 = (c0[0] - n0[0] * radii[index], c0[1] - n0[1] * radii[index])
        left1 = (
            c1[0] - n1[0] * radii[index + 1],
            c1[1] - n1[1] * radii[index + 1],
        )
        right0 = (c0[0] + n0[0] * radii[index], c0[1] + n0[1] * radii[index])
        right1 = (
            c1[0] + n1[0] * radii[index + 1],
            c1[1] + n1[1] * radii[index + 1],
        )
        draw.polygon(
            [scaled(point) for point in (c0, c1, left1, left0)],
            fill=mix(base, active, float(left_activation[index]) * 0.92),
        )
        draw.polygon(
            [scaled(point) for point in (c0, right0, right1, c1)],
            fill=mix(base, active, float(right_activation[index]) * 0.92),
        )
        draw.line(
            [scaled(left0), scaled(left1)],
            fill=(255, 218, 169),
            width=2 * SUPERSAMPLE,
        )
        draw.line(
            [scaled(right0), scaled(right1)],
            fill=(94, 53, 64),
            width=SUPERSAMPLE,
        )
    head = nodes[0]
    draw.ellipse(
        (
            head[0] * SUPERSAMPLE - 4 * SUPERSAMPLE,
            head[1] * SUPERSAMPLE - 4 * SUPERSAMPLE,
            head[0] * SUPERSAMPLE + 4 * SUPERSAMPLE,
            head[1] * SUPERSAMPLE + 4 * SUPERSAMPLE,
        ),
        fill=(91, 42, 52),
    )


def render_frame(
    frame_index: int,
    trajectory: dict[str, object],
    body: dict[str, object],
) -> Image.Image:
    frame = trajectory["frames"][frame_index]
    mirror = mirrored_frame(frame)
    initial_head_x = trajectory["frames"][0]["nodes_um"][0][0]
    canvas = Image.new(
        "RGB", (WIDTH * SUPERSAMPLE, HEIGHT * SUPERSAMPLE), "#0d0a12"
    )
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        color = mix((13, 10, 18), (27, 18, 33), y / HEIGHT)
        draw.line(
            (0, y * SUPERSAMPLE, WIDTH * SUPERSAMPLE, y * SUPERSAMPLE),
            fill=color,
            width=SUPERSAMPLE,
        )

    title = font(FONT_BOLD, 23)
    mono = font(FONT_MONO, 9)
    small = font(FONT_MONO, 8)
    text(draw, (42, 25), "ORACLARVA / BILATERAL STEERING", (244, 232, 217), title)
    text(
        draw,
        (43, 58),
        "SENSORY DIFFERENCE > 126 LIF > SIDE-RESOLVED MN/MUSCLE > XPBD",
        (165, 143, 167),
        mono,
    )
    for top in (84, 284):
        draw.rounded_rectangle(
            (*scaled((38, top)), *scaled((922, top + 180))),
            radius=15 * SUPERSAMPLE,
            fill=(18, 13, 24),
            outline=(56, 40, 62),
            width=SUPERSAMPLE,
        )
        for offset in range(1, 6):
            y = top + offset * 30
            draw.line(
                (*scaled((55, y)), *scaled((905, y))),
                fill=(31, 24, 37),
                width=SUPERSAMPLE,
            )

    draw_larva(draw, frame, body, initial_head_x, PANEL_CENTERS[0])
    draw_larva(draw, mirror, body, initial_head_x, PANEL_CENTERS[1])
    heading = float(trajectory["result_summary"]["heading_change_deg"])
    time_s = float(frame["time_s"])
    text(draw, (57, 101), "LEFT receptor 1.0 / RIGHT 0.0", (231, 122, 139), mono)
    text(draw, (900, 101), f"heading {heading:+0.3f} deg", (199, 181, 198), mono, anchor="ra")
    text(draw, (57, 301), "LEFT receptor 0.0 / RIGHT 1.0", (231, 122, 139), mono)
    text(draw, (900, 301), f"heading {-heading:+0.3f} deg", (199, 181, 198), mono, anchor="ra")
    text(draw, (42, 492), f"t = {time_s:0.2f} s", (230, 211, 196), mono)
    text(draw, (153, 492), "exact mirror regression", (143, 124, 146), small)
    text(draw, (42, 516), "release_validated = false", (143, 120, 145), small)
    text(
        draw,
        (918, 516),
        "NO TURN COMMAND / NO GAIT ANIMATION",
        (143, 120, 145),
        small,
        anchor="rs",
    )
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(output: Path) -> None:
    trajectory = json.loads(TRAJECTORY_PATH.read_text())
    body = json.loads(BODY_PATH.read_text())
    if (
        trajectory["release_validated"] is not False
        or trajectory["node_count"] != 13
        or trajectory["sides"] != ["left", "right"]
    ):
        raise RuntimeError("bilateral trajectory claim or body-node contract is invalid")
    indices = list(range(0, len(trajectory["frames"]), FRAME_STEP))
    if indices[-1] != len(trajectory["frames"]) - 1:
        indices.append(len(trajectory["frames"]) - 1)
    frames = [render_frame(index, trajectory, body) for index in indices]
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
    print(f"wrote {output}: {len(frames)} frames")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the checked bilateral steering trajectory as GIF"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    render(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
