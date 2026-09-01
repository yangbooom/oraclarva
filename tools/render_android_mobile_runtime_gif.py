#!/usr/bin/env python3
"""Render the Stage 10 Android UI contract from frames read through JNI."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_android_host_bridge import (
    REPEAT_FIXTURE,
    SPATIAL_FIXTURE,
    build,
    required,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "oraclarva_android_mobile_runtime.gif"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
WIDTH, HEIGHT, SS = 1080, 608, 2
VERTEX_STRIDE = 7


@dataclass(frozen=True)
class Frame:
    step: int
    time_s: float
    displacement: tuple[float, float, float]
    yaw_deg: float
    pitch_deg: float
    spikes: int
    vertices: tuple[tuple[float, ...], ...]


def font(path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return (
        ImageFont.truetype(str(path), size * SS)
        if path.exists()
        else ImageFont.load_default()
    )


def xy(point: tuple[float, float]) -> tuple[int, int]:
    return tuple(round(value * SS) for value in point)


def text(
    draw: ImageDraw.ImageDraw,
    point: tuple[float, float],
    value: str,
    fill: tuple[int, int, int],
    face: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    anchor: str | None = None,
) -> None:
    draw.text(xy(point), value, fill=fill, font=face, anchor=anchor)


def dump_frames() -> tuple[list[Frame], tuple[tuple[int, int, int], ...]]:
    with tempfile.TemporaryDirectory(prefix="oraclarva-android-gif-") as temporary:
        output = Path(temporary)
        classes = build(output)
        completed = subprocess.run(
            [
                required("java"),
                f"-Djava.library.path={output}",
                "-cp",
                str(classes),
                "org.oraclarva.mobile.AndroidFrameDump",
                str(REPEAT_FIXTURE),
                str(SPATIAL_FIXTURE),
            ],
            text=True,
            capture_output=True,
            check=True,
        )
    vertex_count = triangle_count = 0
    frames: list[Frame] = []
    triangles: tuple[tuple[int, int, int], ...] = ()
    field_checked = capture_checked = False
    for line in completed.stdout.splitlines():
        fields = line.split("\t")
        if fields[0] == "schema":
            if fields[1] != "android_jni_frames_v1":
                raise RuntimeError("unexpected JNI frame schema")
        elif fields[0] == "render":
            vertex_count, triangle_count, stride = map(int, fields[1:])
            if (vertex_count, triangle_count, stride) != (302, 600, VERTEX_STRIDE):
                raise RuntimeError("Android render topology drifted")
        elif fields[0] == "frame":
            values = tuple(map(float, fields[9:]))
            if len(values) != vertex_count * VERTEX_STRIDE:
                raise RuntimeError("JNI vertex frame is incomplete")
            vertices = tuple(
                values[offset : offset + VERTEX_STRIDE]
                for offset in range(0, len(values), VERTEX_STRIDE)
            )
            frames.append(
                Frame(
                    step=int(fields[1]),
                    time_s=float(fields[2]),
                    displacement=tuple(map(float, fields[3:6])),
                    yaw_deg=float(fields[6]),
                    pitch_deg=float(fields[7]),
                    spikes=int(fields[8]),
                    vertices=vertices,
                )
            )
        elif fields[0] == "indices":
            values = tuple(map(int, fields[1:]))
            triangles = tuple(
                values[offset : offset + 3] for offset in range(0, len(values), 3)
            )
        elif fields[0] == "field":
            field_checked = fields[1:] == [
                "gradient_y_w_m3",
                "6000",
                "direct_behavior_command",
                "false",
            ]
        elif fields[0] == "capture":
            capture_checked = fields[1:] == [
                "host_jni",
                "android_device",
                "false",
                "release_validated",
                "false",
            ]
    if len(frames) != 51 or len(triangles) != triangle_count:
        raise RuntimeError("JNI frame dump is incomplete")
    if not field_checked or not capture_checked:
        raise RuntimeError("JNI capture claim boundary is invalid")
    return frames, triangles


def mix(low: tuple[int, int, int], high: tuple[int, int, int], value: float) -> tuple[int, int, int]:
    amount = min(1.0, max(0.0, value))
    return tuple(round(a + (b - a) * amount) for a, b in zip(low, high, strict=True))


def render_frame(
    frame: Frame,
    triangles: tuple[tuple[int, int, int], ...],
) -> Image.Image:
    image = Image.new("RGB", (WIDTH * SS, HEIGHT * SS), (10, 8, 15))
    draw = ImageDraw.Draw(image)
    for row in range(HEIGHT):
        shade = row / HEIGHT
        draw.line(
            (0, row * SS, WIDTH * SS, row * SS),
            fill=(round(10 + 9 * shade), round(8 + 6 * shade), round(15 + 13 * shade)),
            width=SS,
        )

    title = font(FONT_BOLD, 22)
    mono = font(FONT_MONO, 10)
    small = font(FONT_MONO, 8)
    text(draw, (28, 24), "ORACLARVA / ANDROID NDK RUNTIME", (241, 231, 215), title)
    text(
        draw,
        (29, 57),
        "PHYSICAL FIELD → SENSORY TRANSDUCTION → 168 LIF → MN → MUSCLE → C++ BODY → FIELD",
        (152, 202, 190),
        mono,
    )
    panel = (24.0, 88.0, 1056.0, 474.0)
    draw.rounded_rectangle(
        (*xy((panel[0], panel[1])), *xy((panel[2], panel[3]))),
        radius=18 * SS,
        fill=(18, 14, 25),
        outline=(65, 55, 76),
        width=SS,
    )
    for column in range(round(panel[0]) + 1, round(panel[2])):
        amount = (column - panel[0]) / (panel[2] - panel[0])
        color = mix((24, 18, 35), (16, 37, 42), amount)
        draw.line(
            (column * SS, (panel[1] + 1) * SS, column * SS, (panel[3] - 1) * SS),
            fill=color,
            width=SS,
        )

    centers = tuple(
        sum(vertex[axis] for vertex in frame.vertices) / len(frame.vertices)
        for axis in range(3)
    )
    scale = 0.78
    projected: list[tuple[float, float, float]] = []
    for vertex in frame.vertices:
        dx = vertex[0] - centers[0]
        dy = vertex[1] - centers[1]
        dz = vertex[2] - centers[2]
        projected.append(
            (
                525.0 - dx * scale,
                286.0 - (0.86 * dz - 0.51 * dy) * scale,
                0.51 * dz + 0.86 * dy,
            )
        )
    ordered = sorted(
        triangles,
        key=lambda triangle: sum(projected[index][2] for index in triangle) / 3.0,
    )
    light = (-0.35, 0.35, 0.87)
    for triangle in ordered:
        activation = sum(frame.vertices[index][6] for index in triangle) / 3.0
        normal = tuple(
            sum(frame.vertices[index][3 + axis] for index in triangle) / 3.0
            for axis in range(3)
        )
        diffuse = min(1.0, max(0.30, sum(a * b for a, b in zip(normal, light, strict=True))))
        base = mix((70, 204, 185), (245, 66, 119), activation)
        color = tuple(round(channel * (0.56 + 0.44 * diffuse)) for channel in base)
        draw.polygon([xy(projected[index][:2]) for index in triangle], fill=color)

    head = max(projected, key=lambda point: point[0])
    draw.ellipse(
        (*xy((head[0] - 11, head[1] - 11)), *xy((head[0] + 11, head[1] + 11))),
        outline=(250, 234, 211),
        width=2 * SS,
    )
    text(draw, (head[0] + 16, head[1] - 16), "ANTERIOR", (239, 224, 204), small)
    text(draw, (46, 110), "+Y LIGHT GRADIENT · 6000 W/m³", (130, 222, 205), mono)
    draw.line((*xy((78, 138)), *xy((250, 138))), fill=(130, 222, 205), width=3 * SS)
    draw.polygon([xy((250, 138)), xy((238, 131)), xy((238, 145))], fill=(130, 222, 205))
    text(draw, (1034, 111), "continuous 302v / 600△ mesh", (158, 143, 170), small, anchor="ra")

    controls = (645.0, 490.0, 1056.0, 587.0)
    draw.rounded_rectangle(
        (*xy((controls[0], controls[1])), *xy((controls[2], controls[3]))),
        radius=10 * SS,
        fill=(23, 18, 31),
        outline=(63, 52, 72),
        width=SS,
    )
    text(draw, (661, 501), "PHYSICAL LIGHT FIELD · not a heading command", (145, 212, 195), small)
    text(draw, (661, 526), "−Y", (188, 178, 194), small)
    draw.rounded_rectangle((*xy((690, 528)), *xy((1010, 538))), radius=5 * SS, fill=(54, 45, 63))
    draw.rounded_rectangle((*xy((850, 528)), *xy((1010, 538))), radius=5 * SS, fill=(92, 215, 190))
    draw.ellipse((*xy((1003, 523)), *xy((1017, 543))), fill=(229, 221, 231))
    text(draw, (1037, 526), "+Y", (188, 178, 194), small, anchor="ra")
    text(draw, (661, 555), "MODEL_FITTED · release_validated=false", (237, 164, 96), small)

    forward = -frame.displacement[0]
    text(draw, (28, 498), f"C++  t {frame.time_s:5.3f} s", (230, 218, 203), mono)
    text(draw, (28, 526), f"forward {forward:7.2f} µm", (230, 218, 203), mono)
    text(draw, (28, 554), f"yaw {frame.yaw_deg:+7.3f}°   pitch {frame.pitch_deg:+6.3f}°", (230, 218, 203), mono)
    text(draw, (360, 498), f"spikes {frame.spikes}", (187, 172, 195), mono)
    text(draw, (360, 526), "fixed dt 1 ms", (187, 172, 195), mono)
    text(draw, (360, 554), "render reads; never drives physics", (187, 172, 195), small)
    text(
        draw,
        (1053, 600),
        "HOST JVM + JNI EXECUTION · ANDROID DEVICE/EMULATOR NOT CAPTURED",
        (239, 164, 96),
        small,
        anchor="rs",
    )
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render(output: Path) -> None:
    frames, triangles = dump_frames()
    images = [render_frame(frame, triangles) for frame in frames]
    output.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        output,
        save_all=True,
        append_images=images[1:],
        duration=100,
        loop=0,
        disposal=2,
        optimize=True,
    )
    print(f"wrote {output.relative_to(ROOT)}: {len(images)} JNI frames")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    render(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
