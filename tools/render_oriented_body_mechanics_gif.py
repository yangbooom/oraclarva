#!/usr/bin/env python3
"""Render the oriented-section mechanics v2 mirror/invariant diagnostic."""

from __future__ import annotations

import argparse
import json
from math import cos, radians, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "data/validation/oriented_body_mechanics_v2.json"
DEFAULT_OUTPUT = ROOT / "docs/assets/oraclarva_oriented_body_mechanics_v2.gif"
WIDTH, HEIGHT, SS = 1200, 680, 2
LATERAL_VISUAL_GAIN = 1000.0
TWIST_GLYPH_GAIN = 90.0


def font(size: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = Path("/usr/share/fonts/truetype/dejavu") / name
    return ImageFont.truetype(str(path), size * SS)


def point(panel, x_um: float, lateral_um: float) -> tuple[int, int]:
    left, top, right, bottom = panel
    x = left + 18 + (x_um + 20.0) / 800.0 * (right - left - 36)
    y = (top + bottom) / 2.0 - lateral_um / 190.0 * (bottom - top - 60)
    return round(x * SS), round(y * SS)


def blend(first, second, fraction):
    return tuple(
        round(left + (right - left) * fraction)
        for left, right in zip(first, second, strict=True)
    )


def twist_color(value: float):
    fraction = min(1.0, abs(value) / 0.22)
    return (
        blend((102, 181, 205), (239, 103, 125), fraction)
        if value >= 0.0
        else blend((102, 181, 205), (84, 224, 207), fraction)
    )


def render_frame(report, frame_index: int) -> Image.Image:
    image = Image.new("RGB", (WIDTH * SS, HEIGHT * SS), (5, 8, 12))
    draw = ImageDraw.Draw(image)
    for row in range(HEIGHT):
        color = blend((5, 8, 12), (15, 21, 27), row / HEIGHT)
        draw.line((0, row * SS, WIDTH * SS, row * SS), fill=color, width=SS)
    draw.text(
        (34 * SS, 24 * SS),
        "ORACLARVA / BODY MECHANICS v2",
        fill=(228, 240, 239),
        font=font(25, True),
    )
    draw.text(
        (34 * SS, 58 * SS),
        "OFF-AXIS FORCE  →  CENTERLINE FORCE + MATERIAL-SECTION TORQUE",
        fill=(91, 199, 191),
        font=font(12),
    )
    scenarios = report["scenarios"]
    time_s = scenarios["left"]["trajectory_samples"][frame_index]["time_s"]
    draw.text(
        (1050 * SS, 31 * SS),
        f"t={time_s:0.3f}s",
        fill=(196, 209, 211),
        font=font(14, True),
    )
    definitions = (
        ("left", "LEFT M1", (75, 222, 209)),
        ("uniform", "EQUAL L + R", (173, 184, 188)),
        ("right", "RIGHT M1", (241, 113, 139)),
    )
    panels = (
        (28, 108, 398, 545),
        (415, 108, 785, 545),
        (802, 108, 1172, 545),
    )
    for (name, title, color), panel in zip(definitions, panels, strict=True):
        left, top, right, bottom = panel
        draw.rounded_rectangle(
            tuple(value * SS for value in panel),
            radius=16 * SS,
            fill=(8, 16, 22),
            outline=(38, 56, 65),
            width=2 * SS,
        )
        draw.text(
            ((left + 18) * SS, (top + 15) * SS),
            title,
            fill=color,
            font=font(16, True),
        )
        sample = scenarios[name]["trajectory_samples"][frame_index]
        center_y = (top + bottom) // 2
        draw.line(
            ((left + 18) * SS, center_y * SS, (right - 18) * SS, center_y * SS),
            fill=(33, 49, 57),
            width=SS,
        )
        nodes = sample["nodes_um"]
        twist = sample["twist_deg"]
        locations = [
            point(panel, node[0], node[1] * LATERAL_VISUAL_GAIN)
            for node in nodes
        ]
        draw.line(locations, fill=color, width=5 * SS, joint="curve")
        for node_index, (location, angle) in enumerate(
            zip(locations, twist, strict=True)
        ):
            x, y = location
            glyph_angle = radians(angle * TWIST_GLYPH_GAIN)
            dx = 8 * SS * cos(glyph_angle)
            dy = 8 * SS * sin(glyph_angle)
            draw.line(
                (round(x - dx), round(y - dy), round(x + dx), round(y + dy)),
                fill=(246, 232, 186),
                width=2 * SS,
            )
            radius = 4 * SS
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=twist_color(angle),
                outline=(231, 241, 239),
                width=SS,
            )
            if node_index in (4, 5):
                ring = 8 * SS
                draw.ellipse(
                    (x - ring, y - ring, x + ring, y + ring),
                    outline=(255, 199, 87),
                    width=2 * SS,
                )
        maximum_twist = max(abs(value) for value in twist)
        draw.text(
            ((left + 18) * SS, (bottom - 53) * SS),
            f"active fibers  {sample['active_fiber_count']}",
            fill=(156, 174, 180),
            font=font(10),
        )
        draw.text(
            ((left + 18) * SS, (bottom - 33) * SS),
            f"max twist     {maximum_twist:0.3f}°",
            fill=(156, 174, 180),
            font=font(10),
        )
        draw.text(
            ((right - 67) * SS, (top + 17) * SS),
            "A1",
            fill=(255, 199, 87),
            font=font(10, True),
        )
    draw.text(
        (35 * SS, 574 * SS),
        "DIAGNOSTIC VISUAL SCALE",
        fill=(237, 212, 150),
        font=font(11, True),
    )
    draw.text(
        (35 * SS, 597 * SS),
        "lateral deformation ×1000  ·  twist glyph angle ×90  ·  gold rings = A1 boundaries",
        fill=(141, 157, 162),
        font=font(11),
    )
    draw.text(
        (35 * SS, 626 * SS),
        "internal net force ≈ 0   /   generalized net torque ≈ 0   /   exact left-right mirror",
        fill=(110, 206, 198),
        font=font(11, True),
    )
    draw.text(
        (780 * SS, 626 * SS),
        "FREE-SPACE FIXTURE · NOT LOCOMOTION",
        fill=(234, 117, 137),
        font=font(11, True),
    )
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).convert(
        "P", palette=Image.Palette.ADAPTIVE
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    report = json.loads(VALIDATION.read_text(encoding="utf-8"))
    count = min(
        len(report["scenarios"][name]["trajectory_samples"])
        for name in ("left", "uniform", "right")
    )
    frames = [render_frame(report, index) for index in range(count)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        args.output,
        save_all=True,
        append_images=frames[1:],
        duration=80,
        loop=0,
        optimize=False,
        disposal=2,
    )
    print(f"wrote {args.output.relative_to(ROOT)} ({len(frames)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
