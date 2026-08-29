"""Render the checked embodied trajectory as a PR-friendly animated GIF."""

from __future__ import annotations

import argparse
import json
from math import sqrt
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY_PATH = ROOT / "data" / "trajectories" / "l1_closed_loop_v0.json"
BODY_PATH = ROOT / "data" / "body" / "l1_body_v0.json"
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "oraclarva_closed_loop.gif"
FONT_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")

WIDTH = 960
HEIGHT = 540
SUPERSAMPLE = 2
FRAME_STEP = 2
FRAME_DURATION_MS = 60


def font(path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path.exists():
        return ImageFont.truetype(str(path), size * SUPERSAMPLE)
    return ImageFont.load_default()


def scaled(point: tuple[float, float]) -> tuple[int, int]:
    return tuple(round(value * SUPERSAMPLE) for value in point)


def mix(left: tuple[int, int, int], right: tuple[int, int, int], amount: float):
    amount = min(1.0, max(0.0, amount))
    return tuple(round(a * (1.0 - amount) + b * amount) for a, b in zip(left, right))


def smoothstep(value: float) -> float:
    return value * value * (3.0 - 2.0 * value)


def node_profile(values: list[float]) -> list[float]:
    return [
        values[0] * 0.55,
        *[(values[index - 1] + value) / 2.0 for index, value in enumerate(values[1:], 1)],
        values[-1] * 0.45,
    ]


def draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    fill: tuple[int, int, int],
    text_font: ImageFont.ImageFont,
    *,
    anchor: str | None = None,
) -> None:
    draw.text(scaled(xy), text, fill=fill, font=text_font, anchor=anchor)


def render_frame(
    frame: dict[str, object],
    body: dict[str, object],
    trajectory: dict[str, object],
    initial_center_x: float,
) -> Image.Image:
    canvas = Image.new("RGB", (WIDTH * SUPERSAMPLE, HEIGHT * SUPERSAMPLE), "#0d0a12")
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        color = mix((13, 10, 18), (24, 16, 30), y / HEIGHT)
        draw.line((0, y * SUPERSAMPLE, WIDTH * SUPERSAMPLE, y * SUPERSAMPLE), fill=color, width=SUPERSAMPLE)

    title = font(FONT_BOLD, 25)
    subtitle = font(FONT_MONO, 9)
    label = font(FONT_BOLD, 10)
    small = font(FONT_MONO, 8)
    value_font = font(FONT_MONO, 11)
    draw_text(draw, (48, 32), "ORACLARVA / EMBODIED LOOP", (244, 232, 217), title)
    draw_text(
        draw,
        (49, 67),
        "ENVIRONMENT > SENSORY > 91 LIF > MOTOR > MUSCLE > XPBD > ENVIRONMENT",
        (164, 143, 166),
        subtitle,
    )
    draw.rounded_rectangle(
        (*scaled((47, 91)), *scaled((697, 402))),
        radius=18 * SUPERSAMPLE,
        fill=(18, 13, 24),
        outline=(55, 39, 61),
        width=SUPERSAMPLE,
    )
    draw.rounded_rectangle(
        (*scaled((718, 91)), *scaled((925, 477))),
        radius=18 * SUPERSAMPLE,
        fill=(21, 15, 27),
        outline=(58, 42, 64),
        width=SUPERSAMPLE,
    )

    floor_y = 350.0
    for index in range(7):
        y = floor_y + index * 7
        color = mix((67, 49, 70), (24, 18, 29), index / 6)
        draw.line((*scaled((65, y)), *scaled((680, y))), fill=color, width=SUPERSAMPLE)
    for x in range(80, 680, 70):
        draw.line((*scaled((x, floor_y)), *scaled((x - 15, 390))), fill=(34, 26, 40), width=SUPERSAMPLE)

    nodes = frame["nodes_um"]
    activations = frame["segment_activation"]
    segments = body["segments"]
    geometry = body["global_geometry"]
    total_length_um = geometry["total_length_m"]["nominal"] * 1e6
    maximum_width_um = geometry["maximum_width_m"]["nominal"] * 1e6
    height_ratio = geometry["height_to_width_ratio"]["nominal"]
    rest_lengths = [segment["length_fraction"] * total_length_um for segment in segments]
    widths = [segment["width_scale"] * maximum_width_um for segment in segments]
    heights = [width * height_ratio for width in widths]
    node_heights = node_profile(heights)
    current_lengths = [
        sqrt(sum((right[axis] - left[axis]) ** 2 for axis in range(3)))
        for left, right in zip(nodes[:-1], nodes[1:], strict=True)
    ]
    rest_volume = sum(length * width * height for length, width, height in zip(rest_lengths, widths, heights, strict=True))
    current_volume = sum(length * width * height for length, width, height in zip(current_lengths, widths, heights, strict=True))
    cavity_scale = sqrt(rest_volume / current_volume)
    pixels_per_um = 0.665
    world_origin_x = 69.0

    def center(node: list[float]) -> tuple[float, float]:
        return (
            world_origin_x + node[0] * pixels_per_um,
            floor_y - node[2] * pixels_per_um,
        )

    centers = [center(node) for node in nodes]
    shadow_left = min(point[0] for point in centers) - 3
    shadow_right = max(point[0] for point in centers) + 3
    draw.ellipse(
        (*scaled((shadow_left, floor_y - 3)), *scaled((shadow_right, floor_y + 14))),
        fill=(10, 8, 13),
    )

    base_colors = [
        (193, 139, 91), (218, 174, 113), (209, 153, 101), (226, 181, 119),
        (211, 157, 105), (225, 177, 117), (207, 151, 101), (223, 173, 115),
        (206, 147, 100), (218, 162, 109), (195, 133, 94), (180, 116, 86),
    ]
    active_color = (244, 94, 111)
    upper_edge: list[tuple[float, float]] = []
    lower_edge: list[tuple[float, float]] = []
    segment_polygons: list[list[tuple[float, float]]] = []
    subdivisions = 7
    for segment_index in range(len(segments)):
        upper: list[tuple[float, float]] = []
        lower: list[tuple[float, float]] = []
        for step in range(subdivisions + 1):
            amount = step / subdivisions
            profile = smoothstep(amount)
            cx = centers[segment_index][0] * (1 - amount) + centers[segment_index + 1][0] * amount
            cy = centers[segment_index][1] * (1 - amount) + centers[segment_index + 1][1] * amount
            height_um = (
                node_heights[segment_index] * (1 - profile)
                + node_heights[segment_index + 1] * profile
            ) * cavity_scale
            radius = max(3.0, height_um * pixels_per_um * 0.5)
            upper.append((cx, cy - radius))
            lower.append((cx, cy + radius))
        polygon = upper + list(reversed(lower))
        segment_polygons.append(polygon)
        upper_edge.extend(upper[:-1] if segment_index < len(segments) - 1 else upper)
        lower_edge.extend(lower[:-1] if segment_index < len(segments) - 1 else lower)

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    glow = ImageDraw.Draw(overlay)
    for index, polygon in enumerate(segment_polygons):
        activation = float(activations[index])
        if activation > 0.03:
            xs = [point[0] for point in polygon]
            ys = [point[1] for point in polygon]
            pad = 7 + activation * 9
            glow.ellipse(
                (*scaled((min(xs) - pad, min(ys) - pad)), *scaled((max(xs) + pad, max(ys) + pad))),
                fill=(232, 72, 100, round(24 + activation * 38)),
            )
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    for index, polygon in enumerate(segment_polygons):
        activation = float(activations[index])
        color = mix(base_colors[index], active_color, min(1.0, activation * 0.92))
        draw.polygon([scaled(point) for point in polygon], fill=color)
        draw.line([scaled(point) for point in polygon + [polygon[0]]], fill=(83, 51, 62), width=SUPERSAMPLE)
    draw.line([scaled(point) for point in upper_edge], fill=(255, 220, 176), width=2 * SUPERSAMPLE)
    draw.line([scaled(point) for point in lower_edge], fill=(91, 50, 60), width=SUPERSAMPLE)

    for index in (3, 6, 9):
        segment = segments[index]
        cx = (centers[index][0] + centers[index + 1][0]) / 2
        top = min(point[1] for point in segment_polygons[index])
        draw_text(draw, (cx, top - 13), segment["id"], (188, 169, 184), small, anchor="mm")

    current_center = sum(node[0] for node in nodes) / len(nodes)
    forward_um = initial_center_x - current_center
    time_s = float(frame["time_s"])
    draw_text(draw, (72, 116), "NEURAL-CAUSAL BODY STATE", (145, 127, 148), small)
    draw_text(draw, (72, 142), f"t = {time_s:4.2f} s", (239, 222, 207), value_font)
    draw_text(draw, (186, 142), f"forward = {forward_um:5.2f} um", (239, 142, 132), value_font)

    draw_text(draw, (742, 117), "MUSCLE ACTIVATION", (198, 181, 194), label)
    draw_text(draw, (742, 139), "actual simulator channels", (115, 100, 120), small)
    body_index = {segment["id"]: index for index, segment in enumerate(segments)}
    wave_order = ["A7", "A6", "A5", "A4", "A3", "A2", "A1", "T3"]
    for row, segment_id in enumerate(wave_order):
        activation = float(activations[body_index[segment_id]])
        y = 174 + row * 32
        draw_text(draw, (742, y), segment_id, (196, 178, 190), small)
        draw.rounded_rectangle(
            (*scaled((776, y - 1)), *scaled((902, y + 9))),
            radius=5 * SUPERSAMPLE,
            fill=(44, 33, 49),
        )
        if activation > 0:
            draw.rounded_rectangle(
                (*scaled((776, y - 1)), *scaled((776 + 126 * activation, y + 9))),
                radius=5 * SUPERSAMPLE,
                fill=mix((201, 142, 95), (241, 83, 108), activation),
            )
        draw_text(draw, (907, y + 4), f"{activation:0.2f}", (151, 132, 151), small, anchor="lm")

    draw_text(draw, (48, 434), "MEASURED_PUBLISHED", (219, 175, 117), small)
    draw_text(draw, (174, 434), "motor identities", (125, 109, 128), small)
    draw_text(draw, (316, 434), "MODEL_FITTED", (235, 101, 121), small)
    draw_text(draw, (409, 434), "gains + mechanics", (125, 109, 128), small)
    draw_text(draw, (48, 467), "release_validated = false", (139, 119, 141), subtitle)
    draw_text(
        draw,
        (48, 490),
        "movement is generated by the 91-neuron closed loop; no gait animation or position command",
        (104, 90, 109),
        small,
    )
    draw_text(
        draw,
        (925, 507),
        f"FRAME {round(time_s / trajectory['sample_interval_s']):03d} / {len(trajectory['frames']) - 1:03d}",
        (91, 78, 96),
        small,
        anchor="rs",
    )
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(output: Path) -> None:
    trajectory = json.loads(TRAJECTORY_PATH.read_text())
    body = json.loads(BODY_PATH.read_text())
    if trajectory["release_validated"] is not False or trajectory["node_count"] != 13:
        raise RuntimeError("trajectory claim or body-node contract is invalid")
    source_frames = trajectory["frames"]
    indices = list(range(0, len(source_frames), FRAME_STEP))
    if indices[-1] != len(source_frames) - 1:
        indices.append(len(source_frames) - 1)
    initial_center_x = sum(node[0] for node in source_frames[0]["nodes_um"]) / 13
    frames = [
        render_frame(source_frames[index], body, trajectory, initial_center_x)
        for index in indices
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
    print(f"wrote {output}: {len(frames)} frames")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the checked neural closed-loop trajectory as GIF"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    render(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
