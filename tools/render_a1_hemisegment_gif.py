"""Render the checked A1-left attachment/mechanics artifact as a GIF."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY = (
    ROOT / "data" / "trajectories" / "l1_a1_left_hemisegment_mechanics_v0.json"
)
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "oraclarva_a1_hemisegment_mechanics.gif"
WIDTH, HEIGHT = 1080, 650
TARGET = "A1:left:M1:DA1"
SIBLING = "A1:left:M10:DO2"
GROUP_COLORS = {
    "DL": (240, 111, 109),
    "DO": (224, 149, 106),
    "T": (211, 205, 213),
    "VL": (91, 167, 229),
    "VO": (82, 126, 215),
    "VA": (146, 112, 215),
}


def _font(size: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = Path("/usr/share/fonts/truetype/dejavu") / name
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def _xy(coordinate, left: int, top: int, width: int, height: int):
    return (
        left + 18 + coordinate["s"] * (width - 36),
        top + 18 + (-coordinate["theta_rad"] / 3.141592653589793) * (height - 36),
    )


def _lerp(a, b, fraction):
    return (
        a[0] + (b[0] - a[0]) * fraction,
        a[1] + (b[1] - a[1]) * fraction,
    )


def _panel(draw, bounds, title, subtitle):
    left, top, right, bottom = bounds
    draw.rounded_rectangle(bounds, radius=12, fill=(23, 24, 34), outline=(59, 61, 76), width=2)
    draw.text((left + 14, top + 10), title, fill=(243, 237, 226), font=_font(18, True))
    draw.text((left + 14, top + 34), subtitle, fill=(159, 158, 174), font=_font(11))
    plot = (left + 10, top + 62, right - 10, bottom - 50)
    draw.rounded_rectangle(plot, radius=8, fill=(13, 15, 23), outline=(45, 47, 61))
    draw.text((plot[0] + 5, plot[1] + 5), "dorsal", fill=(112, 114, 133), font=_font(10))
    draw.text((plot[0] + 5, plot[3] - 18), "ventral", fill=(112, 114, 133), font=_font(10))
    draw.text((plot[0] + 5, plot[3] + 10), "anterior", fill=(112, 114, 133), font=_font(10))
    draw.text((plot[2] - 52, plot[3] + 10), "posterior", fill=(112, 114, 133), font=_font(10))
    return plot


def _draw_fibers(draw, geometry, plot, target_fraction=0.0, sibling_fraction=0.0, lesion=False):
    left, top, right, bottom = plot
    for fiber in geometry:
        origin = _xy(fiber["origin"], left, top, right - left, bottom - top)
        rest_insertion = _xy(fiber["insertion"], left, top, right - left, bottom - top)
        fraction = 0.0
        if fiber["fiber_id"] == TARGET:
            fraction = target_fraction
        elif fiber["fiber_id"] == SIBLING:
            fraction = sibling_fraction
        insertion = _lerp(rest_insertion, origin, min(0.75, fraction * 2.0))
        color = GROUP_COLORS[fiber["spatial_group"]]
        width = 2
        if fiber["fiber_id"] == TARGET:
            color = (112, 112, 119) if lesion else (255, 92, 94)
            width = 5
        elif fiber["fiber_id"] == SIBLING:
            color = (64, 204, 255)
            width = 4
        draw.line((origin, insertion), fill=color, width=width)
        if fiber["fiber_id"] in {TARGET, SIBLING}:
            draw.ellipse((origin[0]-3, origin[1]-3, origin[0]+3, origin[1]+3), fill=color)
            draw.ellipse((insertion[0]-3, insertion[1]-3, insertion[0]+3, insertion[1]+3), fill=color)


def _bar(draw, x, y, width, value, color, label):
    draw.text((x, y - 1), label, fill=(176, 177, 190), font=_font(11))
    draw.rounded_rectangle((x + 76, y, x + 76 + width, y + 10), radius=5, fill=(45, 46, 59))
    draw.rounded_rectangle(
        (x + 76, y, x + 76 + width * min(1.0, max(0.0, value)), y + 10),
        radius=5,
        fill=color,
    )


def render(output: Path) -> None:
    artifact = json.loads(TRAJECTORY.read_text())
    control, lesion = artifact["scenarios"]
    geometry = artifact["geometry"]
    frames = []
    for index, (control_frame, lesion_frame) in enumerate(
        zip(control["frames"], lesion["frames"], strict=True)
    ):
        image = Image.new("RGB", (WIDTH, HEIGHT), (12, 13, 20))
        draw = ImageDraw.Draw(image)
        time_s = control_frame["time_s"]
        draw.text((28, 20), "ORACLARVA · ISOLATED A1-LEFT MUSCLE MECHANICS", fill=(248, 236, 214), font=_font(25, True))
        draw.text((28, 52), f"t = {time_s:0.2f} s  ·  normalized geometry / model-force units", fill=(173, 171, 185), font=_font(14))
        draw.text((1052, 24), "STAGE 3", fill=(105, 214, 148), font=_font(14, True), anchor="ra")

        p0 = _panel(draw, (24, 90, 352, 535), "29-FIBER ATTACHMENT HYPOTHESIS", "unwrapped (s, θ); ANATOMY_DERIVED")
        p1 = _panel(draw, (376, 90, 704, 535), "MAPPED ACTIVATION → MECHANICS", "M1 red · M10 blue · MODEL_FITTED")
        p2 = _panel(draw, (728, 90, 1056, 535), "M1 MECHANICS LESION", "upstream activation preserved; tension blocked")
        _draw_fibers(draw, geometry, p0)
        _draw_fibers(
            draw,
            geometry,
            p1,
            control_frame["target_shortening_fraction"],
            control_frame["sibling_shortening_fraction"],
        )
        _draw_fibers(
            draw,
            geometry,
            p2,
            lesion_frame["target_shortening_fraction"],
            lesion_frame["sibling_shortening_fraction"],
            lesion=True,
        )

        _bar(draw, 34, 555, 190, control_frame["target_activation"], (255, 92, 94), "M1 ACT")
        _bar(draw, 34, 578, 190, control_frame["target_shortening_fraction"] / 0.3, (230, 127, 81), "M1 ΔL")
        _bar(draw, 375, 555, 190, control_frame["sibling_activation"], (64, 204, 255), "M10 ACT")
        _bar(draw, 375, 578, 190, control_frame["sibling_shortening_fraction"] / 0.3, (96, 164, 240), "M10 ΔL")
        _bar(draw, 728, 555, 190, lesion_frame["target_activation"], (255, 92, 94), "M1 ACT")
        _bar(draw, 728, 578, 190, lesion_frame["target_shortening_fraction"] / 0.3, (112, 112, 119), "M1 ΔL")
        draw.text((28, 622), "MN spike → +1 ms activation → model tension → passive/damped shortening", fill=(108, 213, 149), font=_font(13, True))
        draw.text((1052, 622), "NO CSA · NO Fmax · NO SI FORCE · NO FULL-BODY MOTION", fill=(232, 150, 103), font=_font(12, True), anchor="ra")
        frames.append(image)

    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=75,
        loop=0,
        optimize=True,
        disposal=2,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    render(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
