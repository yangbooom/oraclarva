"""Render a static preview from the same body spec used by the Three.js viewer."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "data/body/l1_body_v0.json").read_text())
OUTPUT = Path(__file__).with_name("l1-body-preview.png")


def ellipsoid(center, radii, color, alpha=0.96):
    u = np.linspace(0, 2 * np.pi, 48)
    v = np.linspace(0, np.pi, 30)
    x = center[0] + radii[0] * np.outer(np.cos(u), np.sin(v))
    y = center[1] + radii[1] * np.outer(np.sin(u), np.sin(v))
    z = center[2] + radii[2] * np.outer(np.ones_like(u), np.cos(v))
    return x, y, z, color, alpha


segments = SPEC["segments"]
world_length = 6.3
width_ratio = (
    SPEC["global_geometry"]["maximum_width_m"]["nominal"]
    / SPEC["global_geometry"]["total_length_m"]["nominal"]
)
height_ratio = SPEC["global_geometry"]["height_to_width_ratio"]["nominal"]

fig = plt.figure(figsize=(16, 9), facecolor="#0f0b14")
ax = fig.add_axes([0.03, 0.08, 0.70, 0.84], projection="3d", facecolor="#15101b")
info = fig.add_axes([0.75, 0.08, 0.22, 0.84], facecolor="#17111d")
info.set_xticks([])
info.set_yticks([])
for spine in info.spines.values():
    spine.set_color("#3a2b40")

cursor = -world_length / 2
palette = ["#d6a26d", "#e2ba83", "#d8aa74", "#e4bd87"]
centers = []
for index, segment in enumerate(segments):
    length = world_length * segment["length_fraction"]
    radius = world_length * width_ratio * segment["width_scale"] / 2
    activation = np.exp(-((index - 6.0) ** 2) / 1.5) * 0.35
    shorten = 1 - 0.45 * activation
    plump = np.sqrt(1 / shorten)
    display_length = length * shorten
    center_x = cursor + display_length / 2
    normalized = center_x / (world_length / 2)
    center_y = np.sin((normalized + 1) * np.pi) * 0.13
    center_z = 0.10 + np.cos(normalized * np.pi * 1.6) * 0.03
    centers.append((center_x, center_y, center_z))

    surface = ellipsoid(
        (center_x, center_y, center_z),
        (max(display_length * 0.58, radius * 0.74), radius * plump, radius * height_ratio * plump),
        palette[index % len(palette)],
    )
    ax.plot_surface(
        surface[0], surface[1], surface[2],
        color=surface[3], alpha=surface[4], linewidth=0.15,
        edgecolor="#6f4d51", shade=True, antialiased=True,
    )
    cursor += display_length - 0.018

# Mouth and paired sensory markers.
head = centers[0]
ax.scatter([head[0] - 0.34], [head[1]], [head[2]], s=150, color="#5f3038", depthshade=True)
ax.scatter(
    [head[0] - 0.16, head[0] - 0.16],
    [head[1] - 0.13, head[1] + 0.13],
    [head[2] + 0.23, head[2] + 0.23],
    s=24,
    color="#723746",
    depthshade=False,
)

# Substrate and segment labels.
xx, yy = np.meshgrid(np.linspace(-4.2, 4.2, 2), np.linspace(-2.2, 2.2, 2))
zz = np.full_like(xx, -0.58)
ax.plot_surface(xx, yy, zz, color="#1b1521", alpha=0.68, shade=False)
for index, (segment, center) in enumerate(zip(segments, centers)):
    ax.text(
        center[0], center[1], 0.86 + (index % 2) * 0.11,
        segment["id"], color="#cdbacb", fontsize=7, ha="center", va="center",
    )

ax.set_xlim(-3.7, 3.5)
ax.set_ylim(-2.05, 2.05)
ax.set_zlim(-0.65, 1.45)
ax.view_init(elev=17, azim=-66)
ax.set_axis_off()
ax.set_box_aspect((7.2, 3.0, 2.0))

fig.text(0.055, 0.925, "ORACLARVA / BODY LAB", color="#9a879d", fontsize=8, family="monospace")
fig.text(0.055, 0.885, "L1 neuromechanical body", color="#f4eadc", fontsize=25, weight="medium")
fig.text(0.055, 0.85, "12-region hypothesis model · posterior→anterior contraction", color="#a996a8", fontsize=10)

info.text(0.08, 0.92, "SCIENTIFIC MODEL v0", color="#b59eaf", fontsize=8, family="monospace")
info.text(0.08, 0.86, "Nominal body", color="#f1e6d9", fontsize=17, weight="medium")
rows = [
    ("STAGE", "newly-hatched L1"),
    ("LENGTH", "900 µm"),
    ("MAX WIDTH", "150 µm"),
    ("REGIONS", "PSC · T1–T3 · A1–A8"),
    ("ACTIVE WAVE", "35% · A3 centered"),
]
y = 0.78
for label, value in rows:
    info.text(0.08, y, label, color="#806f83", fontsize=7, family="monospace")
    info.text(0.08, y - 0.035, value, color="#d5c5d1", fontsize=10)
    info.plot([0.08, 0.92], [y - 0.065, y - 0.065], color="#35283a", lw=0.8)
    y -= 0.12

info.text(0.08, 0.22, "EVIDENCE", color="#806f83", fontsize=7, family="monospace")
info.scatter([0.10], [0.17], s=25, color="#d08d75")
info.text(0.15, 0.164, "HYPOTHESIS", color="#d9a18f", fontsize=8, family="monospace")
info.text(
    0.08, 0.07,
    "L1 length, width and per-region profile\nare explicit v0 hypotheses. Replace with\ncalibrated dorsal/lateral image cohorts.",
    color="#857487", fontsize=7.5, linespacing=1.65,
)

fig.savefig(OUTPUT, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.15)
print(OUTPUT)
