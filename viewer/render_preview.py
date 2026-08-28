"""Render the continuous body surface used by the native reference core."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from oraclarva.body import load_body_spec  # noqa: E402
from oraclarva.body3d import ScientificBody3D, Vec3  # noqa: E402
from oraclarva.surface import build_surface_mesh  # noqa: E402


OUTPUT = Path(__file__).with_name("l1-body-preview.png")
SPEC = load_body_spec()
BODY = ScientificBody3D(SPEC, pinned_nodes={0})
BODY.set_activations({"A3": 0.35})
for _ in range(30):
    BODY.step(0.001, gravity=Vec3(0.0, 0.0, 0.0), ground_z=None)

# A small diagnostic bend demonstrates that the skin remains connected. This is
# a render fixture, not a behavior command or calibrated posture.
for index, particle in enumerate(BODY.particles):
    phase = index / (len(BODY.particles) - 1) * np.pi
    particle.position = Vec3(
        particle.position.x,
        particle.position.y + float(np.sin(phase) * 20e-6),
        particle.position.z,
    )

MESH = build_surface_mesh(BODY, axial_subdivisions=6, radial_samples=28)
vertices = np.array([[v.x, v.y, v.z] for v in MESH.vertices]) * 1e6
polygons = [vertices[list(face)] for face in MESH.faces]
palette = {
    segment.id: color
    for segment, color in zip(
        SPEC.segments,
        ["#d6a26d", "#e2ba83", "#d8aa74", "#e4bd87"] * 3,
    )
}
facecolors = [palette[segment_id] for segment_id in MESH.face_segment_ids]

fig = plt.figure(figsize=(16, 9), facecolor="#0f0b14")
ax = fig.add_axes([0.03, 0.08, 0.70, 0.84], projection="3d", facecolor="#15101b")
info = fig.add_axes([0.75, 0.08, 0.22, 0.84], facecolor="#17111d")
info.set_xticks([])
info.set_yticks([])
for spine in info.spines.values():
    spine.set_color("#3a2b40")

skin = Poly3DCollection(
    polygons,
    facecolors=facecolors,
    edgecolors="#5a3d49",
    linewidths=0.08,
    alpha=0.97,
    shade=True,
)
ax.add_collection3d(skin)

centers = np.array(
    [[particle.position.x, particle.position.y, particle.position.z] for particle in BODY.particles]
) * 1e6
for index, segment in enumerate(SPEC.segments):
    center = (centers[index] + centers[index + 1]) / 2
    ax.text(
        center[0], center[1], center[2] + 105 + (index % 2) * 18,
        segment.id, color="#cdbacb", fontsize=7, ha="center", va="center",
    )

floor_x, floor_y = np.meshgrid(np.linspace(-80, 980, 2), np.linspace(-300, 300, 2))
floor_z = np.zeros_like(floor_x)
ax.plot_surface(floor_x, floor_y, floor_z, color="#1b1521", alpha=0.7, shade=False)
ax.set_xlim(-80, 980)
ax.set_ylim(-310, 310)
ax.set_zlim(0, 350)
ax.view_init(elev=18, azim=-67)
ax.set_axis_off()
ax.set_box_aspect((7.2, 3.0, 2.0))

fig.text(0.055, 0.925, "ORACLARVA / BODY LAB", color="#9a879d", fontsize=8, family="monospace")
fig.text(0.055, 0.885, "Continuous L1 body surface", color="#f4eadc", fontsize=25, weight="medium")
fig.text(0.055, 0.85, "one watertight skin · 12 labeled mechanical regions", color="#a996a8", fontsize=10)

info.text(0.08, 0.92, "SCIENTIFIC MODEL v0.1", color="#b59eaf", fontsize=8, family="monospace")
info.text(0.08, 0.86, "Native body state", color="#f1e6d9", fontsize=17, weight="medium")
rows = [
    ("STAGE", "newly-hatched L1"),
    ("LENGTH", "900 µm nominal"),
    ("MAX WIDTH", "150 µm constraint"),
    ("SURFACE", f"{len(MESH.vertices):,} vertices · watertight"),
    ("REGIONS", "PSC · T1–T3 · A1–A8"),
]
y = 0.78
for label, value in rows:
    info.text(0.08, y, label, color="#806f83", fontsize=7, family="monospace")
    info.text(0.08, y - 0.035, value, color="#d5c5d1", fontsize=10)
    info.plot([0.08, 0.92], [y - 0.065, y - 0.065], color="#35283a", lw=0.8)
    y -= 0.12

info.text(0.08, 0.22, "VOLUME POLICY", color="#806f83", fontsize=7, family="monospace")
info.scatter([0.10], [0.17], s=25, color="#d08d75")
info.text(0.15, 0.164, "WHOLE-CAVITY HYPOTHESIS", color="#d9a18f", fontsize=8, family="monospace")
info.text(
    0.08, 0.07,
    "Mechanical regions share one skin and one\naggregate volume constraint. Pressure and\nviscera motion remain validation targets.",
    color="#857487", fontsize=7.5, linespacing=1.65,
)

fig.savefig(OUTPUT, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.15)
print(OUTPUT)
