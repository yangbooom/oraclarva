"""Provenance-aware body-state sensing for the shared 13-node L1 body.

This module converts physical state into sensory drive.  It never chooses an
action, changes a muscle activation, or moves a body node directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .body3d import ContactSurface, ScientificBody3D, Vec3


SENSED_SEGMENTS = ("A1", "A2", "A3", "A4", "A5", "A6")
SIDES = ("left", "right")
CONTRACTION_RECEPTORS = ("vbd", "ddaD", "ddaE", "vpda", "dmd1")


@dataclass(frozen=True, slots=True)
class SegmentBodyState:
    segment_id: str
    length_m: float
    rest_length_m: float
    strain: float
    strain_rate_s_1: float
    shortening_fraction: float
    shortening_rate_s_1: float
    contact: bool
    contact_depth_m: float
    contact_normal: Vec3 | None


@dataclass(frozen=True, slots=True)
class SensoryChannelState:
    neuron_id: str
    segment_id: str
    side: str
    receptor_identity: str
    drive_0_1: float
    external_current_a: float
    identity_provenance: str
    transduction_provenance: str = "MODEL_FITTED"


@dataclass(frozen=True, slots=True)
class BodyStateSensoryFrame:
    time_s: float
    segments: Mapping[str, SegmentBodyState]
    dbd_channels: Mapping[str, SensoryChannelState]
    contraction_channels: Mapping[str, SensoryChannelState]
    contact_drive_by_segment: Mapping[str, float]
    contact_neural_path_executed: bool = False

    @property
    def maximum_dbd_drive(self) -> float:
        return max((item.drive_0_1 for item in self.dbd_channels.values()), default=0.0)


class BodyStateSensoryTransducer:
    """Measure segment geometry/contact and emit fitted sensory currents."""

    def __init__(
        self,
        body: ScientificBody3D,
        parameters: Mapping[str, object],
        *,
        ground_z_m: float | None = None,
        contact_surface: ContactSurface | None = None,
    ) -> None:
        if ground_z_m is not None and contact_surface is not None:
            raise ValueError("provide either ground_z or a contact surface")
        self.body = body
        self.parameters = parameters
        self.ground_z_m = ground_z_m
        self.contact_surface = contact_surface
        self.dt_s = float(parameters["dt_s"])
        numeric = (
            self.dt_s,
            float(parameters["stretch_strain_threshold"]),
            float(parameters["stretch_rate_threshold_s_1"]),
            float(parameters["stretch_strain_gain"]),
            float(parameters["stretch_rate_gain_s"]),
            float(parameters["shortening_strain_threshold"]),
            float(parameters["shortening_rate_threshold_s_1"]),
            float(parameters["shortening_strain_gain"]),
            float(parameters["shortening_rate_gain_s"]),
            float(parameters["maximum_external_current_a"]),
            float(parameters["contact_sensing_range_m"]),
            float(parameters["contact_touch_drive"]),
        )
        if any(not isfinite(value) or value < 0.0 for value in numeric):
            raise ValueError("body-state transduction parameters must be finite and non-negative")
        if self.dt_s <= 0.0 or float(parameters["maximum_external_current_a"]) <= 0.0:
            raise ValueError("dt and maximum sensory current must be positive")
        if parameters.get("provenance") != "MODEL_FITTED":
            raise ValueError("body-state transduction must remain MODEL_FITTED")
        self.index_by_segment = {
            geometry.id: index for index, geometry in enumerate(body.geometry)
        }
        if any(segment not in self.index_by_segment for segment in SENSED_SEGMENTS):
            raise ValueError("shared body is missing an A1-A6 sensed segment")
        self.rest_lengths_m = {
            segment: self._length(segment) for segment in SENSED_SEGMENTS
        }
        self.previous_lengths_m = dict(self.rest_lengths_m)
        self._step_index = 0

    def _length(self, segment: str) -> float:
        index = self.index_by_segment[segment]
        return (
            self.body.particles[index + 1].position
            - self.body.particles[index].position
        ).norm()

    def _contact(self, segment: str) -> tuple[bool, float, Vec3 | None]:
        index = self.index_by_segment[segment]
        hits: list[tuple[float, Vec3]] = []
        for node in (index, index + 1):
            particle = self.body.particles[node]
            clearance = self.body.node_clearance_m(node)
            if self.contact_surface is not None:
                projection = self.contact_surface.query(particle.position, clearance)
                if projection is not None:
                    depth = max(0.0, (projection.position - particle.position).norm())
                    hits.append((depth, projection.normal))
            elif self.ground_z_m is not None:
                depth = max(0.0, self.ground_z_m + clearance - particle.position.z)
                if depth > 0.0 or abs(particle.position.z - self.ground_z_m - clearance) <= 1e-12:
                    hits.append((depth, Vec3(0.0, 0.0, 1.0)))
        if not hits:
            return False, 0.0, None
        depth, normal = max(hits, key=lambda item: item[0])
        return True, depth, normal

    @staticmethod
    def _bounded_drive(strain_term: float, rate_term: float) -> float:
        return min(1.0, max(0.0, strain_term + rate_term))

    def sample(self, time_s: float) -> BodyStateSensoryFrame:
        expected = self._step_index * self.dt_s
        if not isfinite(time_s) or abs(time_s - expected) > 1e-9:
            raise ValueError("body-state transducer must be sampled once per dt")
        p = self.parameters
        segment_states: dict[str, SegmentBodyState] = {}
        dbd: dict[str, SensoryChannelState] = {}
        contraction: dict[str, SensoryChannelState] = {}
        contact_drive: dict[str, float] = {}
        max_current = float(p["maximum_external_current_a"])
        contact_range = float(p["contact_sensing_range_m"])
        contact_touch_drive = float(p["contact_touch_drive"])
        for segment in SENSED_SEGMENTS:
            length = self._length(segment)
            rest = self.rest_lengths_m[segment]
            strain = (length - rest) / rest
            rate = (length - self.previous_lengths_m[segment]) / self.dt_s / rest
            self.previous_lengths_m[segment] = length
            shortening = max(0.0, -strain)
            shortening_rate = max(0.0, -rate)
            contact, depth, normal = self._contact(segment)
            segment_states[segment] = SegmentBodyState(
                segment_id=segment,
                length_m=length,
                rest_length_m=rest,
                strain=strain,
                strain_rate_s_1=rate,
                shortening_fraction=shortening,
                shortening_rate_s_1=shortening_rate,
                contact=contact,
                contact_depth_m=depth,
                contact_normal=normal,
            )
            stretch_drive = self._bounded_drive(
                max(0.0, strain - float(p["stretch_strain_threshold"]))
                * float(p["stretch_strain_gain"]),
                max(0.0, rate - float(p["stretch_rate_threshold_s_1"]))
                * float(p["stretch_rate_gain_s"]),
            )
            contraction_drive = self._bounded_drive(
                max(0.0, shortening - float(p["shortening_strain_threshold"]))
                * float(p["shortening_strain_gain"]),
                max(0.0, shortening_rate - float(p["shortening_rate_threshold_s_1"]))
                * float(p["shortening_rate_gain_s"]),
            )
            contact_drive[segment] = 0.0 if not contact else min(
                1.0,
                contact_touch_drive
                + (1.0 - contact_touch_drive)
                * depth
                / max(contact_range, 1e-15),
            )
            for side in SIDES:
                channel = f"{segment}:{side}"
                dbd[channel] = SensoryChannelState(
                    neuron_id=f"proprioceptor:dbd:{segment}:{side}",
                    segment_id=segment,
                    side=side,
                    receptor_identity="dbd",
                    drive_0_1=stretch_drive,
                    external_current_a=stretch_drive * max_current,
                    identity_provenance=(
                        "MEASURED_PUBLISHED" if segment == "A1" else "ANATOMY_DERIVED"
                    ),
                )
                contraction[channel] = SensoryChannelState(
                    neuron_id=f"proprioceptor:contraction_ensemble:{segment}:{side}",
                    segment_id=segment,
                    side=side,
                    receptor_identity="+".join(CONTRACTION_RECEPTORS),
                    drive_0_1=contraction_drive,
                    external_current_a=0.0,
                    identity_provenance=(
                        "MEASURED_PUBLISHED" if segment == "A1" else "ANATOMY_DERIVED"
                    ),
                )
        self._step_index += 1
        return BodyStateSensoryFrame(
            time_s=time_s,
            segments=segment_states,
            dbd_channels=dbd,
            contraction_channels=contraction,
            contact_drive_by_segment=contact_drive,
        )
