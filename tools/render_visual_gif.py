"""Render checked L1 visual-connectome trajectories as an audit GIF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY_PATH = (
    ROOT / "data" / "trajectories" / "l1_visual_closed_loop_v0.json"
)
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "oraclarva_l1_visual_connectome.gif"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
WIDTH = 1080
HEIGHT = 680
SUPERSAMPLE = 2
FRAME_DURATION_MS = 75
PANEL_LEFTS = (22, 377, 732)
PANEL_WIDTH = 326
BODY_SCALE = 0.29


def font(path: Path, size: int):
    if path.exists():
        return ImageFont.truetype(str(path), size * SUPERSAMPLE)
    return ImageFont.load_default()


def point(x: float, y: float) -> tuple[int, int]:
    return round(x * SUPERSAMPLE), round(y * SUPERSAMPLE)


def draw_text(draw, xy, value, fill, text_font, anchor=None):
    draw.text(
        point(*xy), value, fill=fill, font=text_font, anchor=anchor
    )


def mix(first, second, fraction):
    return tuple(
        round(a + (b - a) * fraction) for a, b in zip(first, second)
    )


def draw_light_field(draw, panel_left: int, sign: float) -> None:
    bounds = (panel_left + 8, 125, panel_left + PANEL_WIDTH - 8, 406)
    dark = (15, 18, 38)
    bright = (111, 91, 43)
    strips = 48
    for index in range(strips):
        fraction = index / (strips - 1)
        if sign < 0:
            fraction = 1.0 - fraction
        fraction = fraction**1.35
        y0 = bounds[1] + index * (bounds[3] - bounds[1]) / strips
        y1 = bounds[1] + (index + 1) * (bounds[3] - bounds[1]) / strips
        draw.rectangle(
            (
                round(bounds[0] * SUPERSAMPLE),
                round(y0 * SUPERSAMPLE),
                round(bounds[2] * SUPERSAMPLE),
                round(y1 * SUPERSAMPLE),
            ),
            fill=mix(bright, dark, fraction),
        )
    draw.rounded_rectangle(
        tuple(round(value * SUPERSAMPLE) for value in bounds),
        radius=8 * SUPERSAMPLE,
        outline=(75, 66, 79),
        width=1 * SUPERSAMPLE,
    )


def project(node, initial_head, panel_left):
    return (
        panel_left + 25 + (node[0] - initial_head[0]) * BODY_SCALE,
        267 - (node[1] - initial_head[1]) * BODY_SCALE,
    )


def activation_color(frame):
    keys = (
        "segment_activation_left",
        "segment_activation_right",
        "segment_activation_dorsal",
        "segment_activation_ventral",
    )
    values = [value for key in keys for value in frame[key]]
    activity = min(1.0, sum(values) / len(values))
    return (
        round(222 + 30 * activity),
        round(170 - 65 * activity),
        round(116 + 25 * activity),
    )


def draw_trace(draw, scenario, frame_index, panel_left):
    frames = scenario["frames"]
    initial_head = frames[0]["nodes_um"][0]
    trace = [
        project(frame["nodes_um"][0], initial_head, panel_left)
        for frame in frames[: frame_index + 1]
    ]
    if len(trace) > 1:
        draw.line(
            [point(*value) for value in trace],
            fill=(241, 215, 169),
            width=2 * SUPERSAMPLE,
        )


def draw_larva(draw, scenario, frame, panel_left):
    initial_head = scenario["frames"][0]["nodes_um"][0]
    nodes = [
        project(node, initial_head, panel_left) for node in frame["nodes_um"]
    ]
    draw.line(
        [point(*node) for node in nodes],
        fill=(65, 27, 43),
        width=25 * SUPERSAMPLE,
        joint="curve",
    )
    draw.line(
        [point(*node) for node in nodes],
        fill=activation_color(frame),
        width=20 * SUPERSAMPLE,
        joint="curve",
    )
    head = nodes[0]
    draw.ellipse(
        (
            round((head[0] - 7) * SUPERSAMPLE),
            round((head[1] - 7) * SUPERSAMPLE),
            round((head[0] + 7) * SUPERSAMPLE),
            round((head[1] + 7) * SUPERSAMPLE),
        ),
        fill=(80, 28, 43),
        outline=(252, 219, 173),
        width=2 * SUPERSAMPLE,
    )


def bar(draw, x, y, value, color, width=78):
    draw.rounded_rectangle(
        (
            round(x * SUPERSAMPLE),
            round(y * SUPERSAMPLE),
            round((x + width) * SUPERSAMPLE),
            round((y + 7) * SUPERSAMPLE),
        ),
        radius=3 * SUPERSAMPLE,
        fill=(28, 25, 34),
    )
    draw.rounded_rectangle(
        (
            round(x * SUPERSAMPLE),
            round(y * SUPERSAMPLE),
            round((x + width * min(1.0, max(0.0, value))) * SUPERSAMPLE),
            round((y + 7) * SUPERSAMPLE),
        ),
        radius=3 * SUPERSAMPLE,
        fill=color,
    )


def draw_pair(draw, panel_left, y, label, left, right, small, scale=1.0):
    draw_text(draw, (panel_left + 14, y - 2), label, (181, 169, 187), small)
    draw_text(draw, (panel_left + 73, y - 2), "L", (83, 169, 230), small)
    bar(draw, panel_left + 87, y, left * scale, (83, 169, 230), 79)
    draw_text(draw, (panel_left + 178, y - 2), "R", (242, 164, 63), small)
    bar(draw, panel_left + 192, y, right * scale, (242, 164, 63), 79)


def draw_causal_trace(draw, scenario, frame, panel_left, small):
    time_s = frame["visual_input"]["sample_time_s"]
    trace = scenario["first_spike_trace_s"]
    stages = (
        ("PR", trace["photoreceptor"]),
        ("VPN", trace["visual_projection_readout"]),
        ("BR", trace["fitted_descending_bridge"]),
        ("PM", trace["a7_premotor"]),
        ("MN", trace["a7_motor"]),
    )
    x = panel_left + 44
    for index, (label, onset) in enumerate(stages):
        active = onset is not None and time_s >= onset
        color = (105, 220, 143) if active else (68, 62, 75)
        draw.ellipse(
            (
                round((x - 4) * SUPERSAMPLE),
                431 * SUPERSAMPLE,
                round((x + 4) * SUPERSAMPLE),
                439 * SUPERSAMPLE,
            ),
            fill=color,
        )
        draw_text(draw, (x, 443), label, color, small, anchor="ma")
        if index < len(stages) - 1:
            draw.line(
                [point(x + 7, 435), point(x + 38, 435)],
                fill=(69, 63, 78),
                width=1 * SUPERSAMPLE,
            )
        x += 57


def draw_circuit_panel(draw, scenario, frame, panel_left, small, mono):
    visual = frame["visual_input"]
    irradiance = visual["irradiance_w_m2"]
    rh5 = visual["receptor_drive"]["Rh5-PR"]
    rh6 = visual["receptor_drive"]["Rh6-PR"]
    spike_counts = visual["spike_counts_in_window"]
    bridge = visual["bridge_stimulus"]
    draw_pair(
        draw,
        panel_left,
        478,
        "LIGHT",
        irradiance["left"],
        irradiance["right"],
        small,
        0.125,
    )
    draw_pair(draw, panel_left, 501, "Rh5", rh5["left"], rh5["right"], small)
    draw_pair(draw, panel_left, 524, "Rh6", rh6["left"], rh6["right"], small)
    draw_pair(
        draw,
        panel_left,
        547,
        "VPN",
        spike_counts["left:readout"],
        spike_counts["right:readout"],
        small,
        0.05,
    )
    draw_pair(draw, panel_left, 570, "BRIDGE", bridge[0], bridge[1], small)
    summary = scenario["summary"]
    draw_text(
        draw,
        (panel_left + 16, 601),
        f"dy {summary['displacement_y_um']:+.2f} um   "
        f"yaw {summary['yaw_change_deg']:+.2f} deg",
        (204, 190, 208),
        mono,
    )
    if scenario["lesion_node_ids"]:
        draw_text(
            draw,
            (panel_left + PANEL_WIDTH - 18, 459),
            "VPN READOUT LESION x12",
            (240, 91, 91),
            mono,
            anchor="ra",
        )


def render_frame(index: int, artifact: dict[str, object]) -> Image.Image:
    canvas = Image.new(
        "RGB",
        (WIDTH * SUPERSAMPLE, HEIGHT * SUPERSAMPLE),
        (10, 9, 15),
    )
    draw = ImageDraw.Draw(canvas)
    title_font = font(FONT_BOLD, 22)
    label_font = font(FONT_BOLD, 11)
    mono = font(FONT, 8)
    small = font(FONT, 7)
    draw_text(
        draw,
        (24, 20),
        "ORACLARVA / L1 VISUAL CONNECTOME IN THE BODY LOOP",
        (246, 231, 211),
        title_font,
    )
    draw_text(
        draw,
        (25, 53),
        "LIGHT > BOLWIG Rh5/Rh6 > PUBLISHED LON CONTACTS > FITTED BRIDGE "
        "> PREMOTOR > MOTOR > MUSCLE > 3D BODY",
        (165, 148, 172),
        mono,
    )
    panel_titles = (
        "BRIGHTER RIGHT / INTACT",
        "BRIGHTER LEFT / INTACT",
        "BRIGHTER RIGHT / VPN LESION",
    )
    scenarios = artifact["scenarios"]
    for panel_left, title, scenario in zip(
        PANEL_LEFTS, panel_titles, scenarios, strict=True
    ):
        frame = scenario["frames"][index]
        draw_text(
            draw,
            (panel_left + PANEL_WIDTH / 2, 92),
            title,
            (230, 213, 220),
            label_font,
            anchor="ma",
        )
        draw_light_field(draw, panel_left, scenario["lateral_gradient_sign"])
        draw_trace(draw, scenario, index, panel_left)
        draw_larva(draw, scenario, frame, panel_left)
        draw_causal_trace(draw, scenario, frame, panel_left, small)
        draw_circuit_panel(draw, scenario, frame, panel_left, small, mono)
    draw_text(
        draw,
        (24, 649),
        "MEASURED: 60 matrix entries / 422 pairs / 3297 contacts   "
        "MODEL_FITTED: response gains, effect signs, VPN->premotor bridge   "
        "NO DIRECT DORSAL-VS-VENTRAL VISUAL SENSOR",
        (137, 126, 145),
        mono,
    )
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(output: Path) -> None:
    artifact = json.loads(TRAJECTORY_PATH.read_text(encoding="utf-8"))
    frame_count = min(
        len(scenario["frames"]) for scenario in artifact["scenarios"]
    )
    frames = [render_frame(index, artifact) for index in range(frame_count)]
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"wrote {output.relative_to(ROOT)} ({len(frames)} frames)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the checked L1 visual-connectome trajectory"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    render(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
