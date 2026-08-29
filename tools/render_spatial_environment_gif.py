"""Render model-authored free, slope, and obstacle trajectories as a GIF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY_PATH = (
    ROOT / "data" / "trajectories" / "l1_spatial_environment_v0.json"
)
DEFAULT_OUTPUT = (
    ROOT / "docs" / "assets" / "oraclarva_spatial_environment.gif"
)
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
WIDTH = 1080
HEIGHT = 600
SUPERSAMPLE = 2
FRAME_STEP = 2
FRAME_DURATION_MS = 60
PANEL_WIDTH = 328
PANEL_LEFTS = (28, 376, 724)
SCALE = 0.25


def font(path: Path, size: int):
    if path.exists():
        return ImageFont.truetype(str(path), size * SUPERSAMPLE)
    return ImageFont.load_default()


def point(x: float, y: float) -> tuple[int, int]:
    return round(x * SUPERSAMPLE), round(y * SUPERSAMPLE)


def text(draw, xy, value, fill, text_font, anchor=None):
    draw.text(
        point(*xy),
        value,
        fill=fill,
        font=text_font,
        anchor=anchor,
    )


def project(
    scenario_id: str,
    node: list[float],
    initial_head: list[float],
    panel_left: float,
) -> tuple[float, float]:
    dx = node[0] - initial_head[0]
    dy = node[1] - initial_head[1]
    dz = node[2] - initial_head[2]
    if scenario_id == "free_combined_yaw_pitch":
        u = dx - 0.32 * dy
        v = -dz + 0.28 * dy
    elif scenario_id == "uphill_twenty_percent":
        u = dx
        v = -dz
    else:
        u = dx
        v = dy
    return (
        panel_left + 28 + (u + 125.0) * SCALE,
        337 + v * SCALE,
    )


def activation_color(frame: dict[str, object]) -> tuple[int, int, int]:
    keys = (
        "segment_activation_left",
        "segment_activation_right",
        "segment_activation_dorsal",
        "segment_activation_ventral",
    )
    values = [
        value
        for key in keys
        for value in frame[key]
    ]
    activity = sum(values) / len(values)
    return (
        round(201 + 48 * activity),
        round(151 - 65 * activity),
        round(104 + 28 * activity),
    )


def draw_environment(
    draw,
    scenario: dict[str, object],
    initial_head: list[float],
    panel_left: float,
) -> None:
    environment = scenario["environment"]
    scenario_id = scenario["id"]
    if environment["type"] == "none":
        return
    if environment["type"] == "plane":
        slope = float(environment["slope_x"])
        endpoints = []
        for x_um in (-150.0, 1050.0):
            z_um = slope * x_um - initial_head[2]
            endpoints.append(project(
                scenario_id,
                [x_um, 0.0, z_um + initial_head[2]],
                [0.0, 0.0, initial_head[2]],
                panel_left,
            ))
        draw.line(
            [point(*value) for value in endpoints],
            fill=(96, 125, 139),
            width=3 * SUPERSAMPLE,
        )
        return
    center = environment["sphere_center_um"]
    radius = float(environment["sphere_radius_um"])
    center_screen = project(
        scenario_id, center, initial_head, panel_left
    )
    radius_px = radius * SCALE
    draw.ellipse(
        (
            round((center_screen[0] - radius_px) * SUPERSAMPLE),
            round((center_screen[1] - radius_px) * SUPERSAMPLE),
            round((center_screen[0] + radius_px) * SUPERSAMPLE),
            round((center_screen[1] + radius_px) * SUPERSAMPLE),
        ),
        fill=(72, 94, 113),
        outline=(145, 184, 202),
        width=2 * SUPERSAMPLE,
    )


def draw_larva(
    draw,
    scenario: dict[str, object],
    frame: dict[str, object],
    panel_left: float,
) -> None:
    initial_head = scenario["frames"][0]["nodes_um"][0]
    nodes = [
        project(scenario["id"], node, initial_head, panel_left)
        for node in frame["nodes_um"]
    ]
    draw_environment(draw, scenario, initial_head, panel_left)
    color = activation_color(frame)
    outline = (84, 45, 55)
    draw.line(
        [point(*node) for node in nodes],
        fill=outline,
        width=25 * SUPERSAMPLE,
        joint="curve",
    )
    draw.line(
        [point(*node) for node in nodes],
        fill=color,
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
        fill=(91, 38, 51),
        outline=(250, 189, 145),
        width=2 * SUPERSAMPLE,
    )


def render_frame(index: int, artifact: dict[str, object]) -> Image.Image:
    canvas = Image.new(
        "RGB",
        (WIDTH * SUPERSAMPLE, HEIGHT * SUPERSAMPLE),
        (12, 10, 17),
    )
    draw = ImageDraw.Draw(canvas)
    title_font = font(FONT_BOLD, 22)
    label_font = font(FONT_BOLD, 12)
    mono = font(FONT, 9)
    small = font(FONT, 8)

    text(
        draw,
        (30, 26),
        "ORACLARVA / NEURAL-CAUSAL 3D MOVEMENT",
        (245, 231, 213),
        title_font,
    )
    text(
        draw,
        (31, 60),
        "4 RECEPTORS > 168 LIF > MOTOR POOLS > 358/276 MUSCLE PROXIES > XPBD CONTACT",
        (164, 145, 169),
        mono,
    )
    labels = (
        ("FREE 3D", "simultaneous yaw + pitch"),
        ("20% SLOPE", "contact-normal climb"),
        ("OBSTACLE", "receptor-distance avoidance"),
    )
    for panel_left, (label, subtitle) in zip(
        PANEL_LEFTS, labels, strict=True
    ):
        draw.rounded_rectangle(
            (
                panel_left * SUPERSAMPLE,
                102 * SUPERSAMPLE,
                (panel_left + PANEL_WIDTH) * SUPERSAMPLE,
                490 * SUPERSAMPLE,
            ),
            radius=16 * SUPERSAMPLE,
            fill=(20, 15, 26),
            outline=(59, 44, 66),
            width=SUPERSAMPLE,
        )
        text(
            draw,
            (panel_left + 18, 124),
            label,
            (238, 203, 173),
            label_font,
        )
        text(
            draw,
            (panel_left + 18, 148),
            subtitle,
            (145, 128, 150),
            small,
        )

    time_s = 0.0
    for scenario, panel_left in zip(
        artifact["scenarios"], PANEL_LEFTS, strict=True
    ):
        frame = scenario["frames"][index]
        time_s = float(frame["time_s"])
        draw_larva(draw, scenario, frame, panel_left)
        summary = scenario["summary"]
        yaw = float(summary["yaw_change_deg"])
        pitch = float(summary["head_pitch_change_deg"])
        dx = float(summary["displacement_x_um"])
        dy = float(summary["displacement_y_um"])
        dz = float(summary["displacement_z_um"])
        text(
            draw,
            (panel_left + 18, 444),
            (
                f"yaw {yaw:+.2f}  "
                f"pitch {pitch:+.2f}"
            ),
            (186, 167, 183),
            small,
        )
        text(
            draw,
            (panel_left + 18, 466),
            (
                f"d=({dx:+.1f},"
                f"{dy:+.1f},"
                f"{dz:+.1f}) um"
            ),
            (186, 167, 183),
            small,
        )

    text(
        draw,
        (30, 528),
        f"t = {time_s:0.2f} s",
        (231, 211, 193),
        mono,
    )
    text(
        draw,
        (30, 558),
        "release_validated = false / synthetic diagnostic environment",
        (143, 122, 146),
        small,
    )
    text(
        draw,
        (1050, 558),
        "NO ACTION COMMAND / NO RENDERER MOTION",
        (143, 122, 146),
        small,
        anchor="rs",
    )
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(output: Path) -> None:
    artifact = json.loads(TRAJECTORY_PATH.read_text())
    if (
        artifact["release_validated"] is not False
        or artifact["node_count"] != 13
        or artifact["channels"]
        != ["left", "right", "dorsal", "ventral"]
    ):
        raise RuntimeError("spatial trajectory contract is invalid")
    frame_count = len(artifact["scenarios"][0]["frames"])
    if any(
        len(scenario["frames"]) != frame_count
        for scenario in artifact["scenarios"]
    ):
        raise RuntimeError("spatial scenarios must share a frame cadence")
    indices = list(range(0, frame_count, FRAME_STEP))
    if indices[-1] != frame_count - 1:
        indices.append(frame_count - 1)
    frames = [render_frame(index, artifact) for index in indices]
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
        description="Render spatial/environment model trajectories as GIF"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    render(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
