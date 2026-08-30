"""Render checked multimodal environment-input trajectories as a GIF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY_PATH = (
    ROOT / "data" / "trajectories" / "l1_environment_inputs_v0.json"
)
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "oraclarva_environment_inputs.gif"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
WIDTH = 1080
HEIGHT = 620
SUPERSAMPLE = 2
FRAME_STEP = 2
FRAME_DURATION_MS = 60
PANEL_WIDTH = 328
PANEL_LEFTS = (28, 376, 724)
SCALE = 0.26
CHANNEL_COLORS = (
    (76, 167, 231),
    (245, 166, 35),
    (157, 214, 114),
    (196, 126, 222),
)


def font(path: Path, size: int):
    if path.exists():
        return ImageFont.truetype(str(path), size * SUPERSAMPLE)
    return ImageFont.load_default()


def point(x: float, y: float) -> tuple[int, int]:
    return round(x * SUPERSAMPLE), round(y * SUPERSAMPLE)


def text(draw, xy, value, fill, text_font, anchor=None):
    draw.text(
        point(*xy), value, fill=fill, font=text_font, anchor=anchor
    )


def mix(first, second, fraction):
    return tuple(
        round(a + (b - a) * fraction) for a, b in zip(first, second)
    )


def draw_field(draw, panel_left: float, modality: str) -> None:
    bounds = (
        panel_left + 10,
        106,
        panel_left + PANEL_WIDTH - 10,
        454,
    )
    palettes = {
        "light": ((17, 20, 43), (107, 91, 50)),
        "temperature": ((22, 55, 82), (107, 47, 42)),
        "odor": ((22, 39, 38), (37, 88, 64)),
    }
    low, high = palettes[modality]
    strips = 48
    for index in range(strips):
        fraction = index / (strips - 1)
        if modality == "light":
            fraction = fraction ** 1.4
        if modality == "light":
            y0 = bounds[1] + (strips - index - 1) * (
                bounds[3] - bounds[1]
            ) / strips
            y1 = bounds[1] + (strips - index) * (
                bounds[3] - bounds[1]
            ) / strips
            rectangle = (bounds[0], y0, bounds[2], y1)
        else:
            x0 = bounds[0] + index * (bounds[2] - bounds[0]) / strips
            x1 = bounds[0] + (index + 1) * (
                bounds[2] - bounds[0]
            ) / strips
            rectangle = (x0, bounds[1], x1, bounds[3])
        draw.rectangle(
            tuple(round(value * SUPERSAMPLE) for value in rectangle),
            fill=mix(low, high, fraction),
        )


def project(
    modality: str,
    node: list[float],
    initial_head: list[float],
    panel_left: float,
) -> tuple[float, float]:
    dx = node[0] - initial_head[0]
    dy = node[1] - initial_head[1]
    dz = node[2] - initial_head[2]
    if modality == "light":
        u = dx - 0.28 * dy
        v = -dz + 0.25 * dy
    else:
        u = dx
        v = -dy + 0.12 * dz
    return (
        panel_left + 28 + (u + 115.0) * SCALE,
        315 + v * SCALE,
    )


def activation_color(frame: dict[str, object]) -> tuple[int, int, int]:
    keys = (
        "segment_activation_left",
        "segment_activation_right",
        "segment_activation_dorsal",
        "segment_activation_ventral",
    )
    values = [value for key in keys for value in frame[key]]
    activity = sum(values) / len(values)
    return (
        round(214 + 38 * activity),
        round(166 - 60 * activity),
        round(114 + 28 * activity),
    )


def draw_trace(
    draw,
    scenario: dict[str, object],
    frame_index: int,
    panel_left: float,
) -> None:
    frames = scenario["frames"]
    modality = scenario["modality"]
    initial_head = frames[0]["nodes_um"][0]
    trace = [
        project(
            modality,
            frame["nodes_um"][0],
            initial_head,
            panel_left,
        )
        for frame in frames[: frame_index + 1]
    ]
    if len(trace) > 1:
        draw.line(
            [point(*value) for value in trace],
            fill=(238, 218, 188),
            width=2 * SUPERSAMPLE,
        )


def draw_larva(
    draw,
    scenario: dict[str, object],
    frame: dict[str, object],
    panel_left: float,
) -> None:
    modality = scenario["modality"]
    initial_head = scenario["frames"][0]["nodes_um"][0]
    nodes = [
        project(modality, node, initial_head, panel_left)
        for node in frame["nodes_um"]
    ]
    draw.line(
        [point(*node) for node in nodes],
        fill=(70, 33, 46),
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
        fill=(83, 31, 44),
        outline=(250, 205, 155),
        width=2 * SUPERSAMPLE,
    )


def draw_receptors(
    draw,
    frame: dict[str, object],
    panel_left: float,
    small,
) -> None:
    values = frame["environment_input"]["stimulus"]
    labels = ("L", "R", "D", "V")
    base_x = panel_left + 22
    for index, (label, value, color) in enumerate(
        zip(labels, values, CHANNEL_COLORS, strict=True)
    ):
        x = base_x + index * 72
        text(draw, (x, 420), label, color, small)
        draw.rounded_rectangle(
            (
                round((x + 13) * SUPERSAMPLE),
                421 * SUPERSAMPLE,
                round((x + 58) * SUPERSAMPLE),
                429 * SUPERSAMPLE,
            ),
            radius=4 * SUPERSAMPLE,
            fill=(20, 17, 25),
        )
        draw.rounded_rectangle(
            (
                round((x + 13) * SUPERSAMPLE),
                421 * SUPERSAMPLE,
                round((x + 13 + 45 * float(value)) * SUPERSAMPLE),
                429 * SUPERSAMPLE,
            ),
            radius=4 * SUPERSAMPLE,
            fill=color,
        )


def render_frame(index: int, artifact: dict[str, object]) -> Image.Image:
    canvas = Image.new(
        "RGB",
        (WIDTH * SUPERSAMPLE, HEIGHT * SUPERSAMPLE),
        (11, 10, 16),
    )
    draw = ImageDraw.Draw(canvas)
    title_font = font(FONT_BOLD, 22)
    label_font = font(FONT_BOLD, 12)
    mono = font(FONT, 9)
    small = font(FONT, 8)
    text(
        draw,
        (30, 24),
        "ORACLARVA / ENVIRONMENT BECOMES NEURAL INPUT",
        (245, 231, 213),
        title_font,
    )
    text(
        draw,
        (31, 58),
        "FIELD SAMPLE > ADAPTIVE TRANSDUCTION > 168 LIF > MUSCLE > "
        "3D BODY > NEXT SAMPLE",
        (164, 145, 169),
        mono,
    )
    labels = {
        "light": ("LIGHT", "irradiance / W m-2"),
        "temperature": ("TEMPERATURE", "thermal field / degC"),
        "odor": ("ODOR", "normalized concentration"),
    }
    for scenario, panel_left in zip(
        artifact["scenarios"], PANEL_LEFTS, strict=True
    ):
        modality = scenario["modality"]
        draw_field(draw, panel_left, modality)
        draw.rounded_rectangle(
            (
                panel_left * SUPERSAMPLE,
                92 * SUPERSAMPLE,
                (panel_left + PANEL_WIDTH) * SUPERSAMPLE,
                484 * SUPERSAMPLE,
            ),
            radius=16 * SUPERSAMPLE,
            outline=(70, 55, 75),
            width=SUPERSAMPLE,
        )
        label, subtitle = labels[modality]
        text(draw, (panel_left + 18, 112), label, (247, 218, 181), label_font)
        text(draw, (panel_left + 18, 136), subtitle, (184, 168, 184), small)
        frame = scenario["frames"][index]
        draw_trace(draw, scenario, index, panel_left)
        draw_larva(draw, scenario, frame, panel_left)
        draw_receptors(draw, frame, panel_left, small)
        summary = scenario["summary"]
        text(
            draw,
            (panel_left + 18, 455),
            (
                f"yaw {float(summary['yaw_change_deg']):+.2f}  "
                f"pitch {float(summary['head_pitch_change_deg']):+.2f}"
            ),
            (222, 202, 214),
            mono,
        )
    time_s = float(artifact["scenarios"][0]["frames"][index]["time_s"])
    text(draw, (30, 516), f"t = {time_s:4.2f} s", (244, 203, 155), label_font)
    text(
        draw,
        (30, 548),
        "L/R/D/V bars are receptor currents, not movement commands.  "
        "All gains: MODEL_FITTED.",
        (157, 140, 162),
        mono,
    )
    text(
        draw,
        (30, 574),
        "Diagnostic analytic fields / not validated natural L1 phototaxis, "
        "thermotaxis, or chemotaxis",
        (122, 108, 129),
        small,
    )
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render multimodal environment input trajectory GIF"
    )
    parser.add_argument("--trajectory", type=Path, default=TRAJECTORY_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = json.loads(args.trajectory.read_text())
    frame_count = len(artifact["scenarios"][0]["frames"])
    frames = [
        render_frame(index, artifact)
        for index in range(0, frame_count, FRAME_STEP)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        args.output,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=True,
    )
    print(f"wrote {args.output} ({len(frames)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
