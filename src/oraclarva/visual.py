"""Published L1 larval-optic-neuropil topology in an embodied light loop."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from math import exp, isfinite
from pathlib import Path
from typing import Any, Iterable

from .body3d import Vec3
from .environment_inputs import LinearScalarField, ScalarField
from .lif import SparseLIFNetwork, Synapse
from .spatial import (
    SpatialClosedLoopLarva,
    SpatialClosedLoopResult,
    SpatialSensoryState,
    SpatialStimulus,
)


LON_SIDES = ("left", "right")
PHOTORECEPTOR_CLASSES = ("Rh5-PR", "Rh6-PR")
BRIDGE_INPUT_LABELS = (
    "visual_descending_bridge:left",
    "visual_descending_bridge:right",
    "visual_descending_bridge:dorsal_shared",
    "visual_descending_bridge:ventral_shared",
)
BRIDGE_DIFFERENCE_LABELS = (
    "visual_lateral_difference:left",
    "visual_lateral_difference:right",
    "visual_dorsoventral_difference:dorsal_shared",
    "visual_dorsoventral_difference:ventral_shared",
)


def default_visual_config_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "organism"
        / "l1_visual_closed_loop_v0.json"
    )


def default_visual_connectome_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "connectome"
        / "l1_visual_connectome_v0.json"
    )


def load_visual_config(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else default_visual_config_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("status") != "research_approximation":
        raise ValueError("visual closed loop must remain a research approximation")
    if raw.get("stage") != "L1":
        raise ValueError("visual closed loop target stage must remain L1")
    if tuple(raw.get("causal_contract", ())) != (
        "analytic_light_field",
        "bilateral_bolwig_organ_samples",
        "fitted_rh5_rh6_phototransduction",
        "published_l1_lon_synaptic_contacts",
        "fitted_synaptic_effects",
        "published_visual_projection_neuron_readout",
        "fitted_visual_to_spatial_premotor_bridge",
        "spatial_neural_dynamics",
        "motor_pools",
        "muscle_activation",
        "3d_body_physics",
        "analytic_light_field",
    ):
        raise ValueError("visual causal contract is invalid")
    connectome = raw.get("connectome", {})
    if connectome.get("provenance") != "MEASURED_PUBLISHED":
        raise ValueError("visual connectome topology must remain measured-published")
    if (
        int(connectome.get("expected_side_scoped_matrix_entries", 0)) != 60
        or int(connectome.get("expected_nonzero_connection_pairs", 0)) != 422
        or int(connectome.get("expected_within_lon_synaptic_contacts", 0))
        != 3297
    ):
        raise ValueError("visual connectome count contract is invalid")

    transduction = raw.get("phototransduction", {})
    if transduction.get("field_unit") != "W_m-2":
        raise ValueError("visual field unit must be W_m-2")
    if transduction.get("provenance") != "MODEL_FITTED":
        raise ValueError("visual phototransduction must remain model-fitted")
    for key in (
        "ambient_half_saturation",
        "spatial_contrast_scale",
        "temporal_contrast_scale",
        "adaptation_tau_s",
    ):
        value = float(transduction.get(key, 0.0))
        if not isfinite(value) or value <= 0.0:
            raise ValueError(f"visual phototransduction {key} must be positive")
    classes = transduction.get("classes", {})
    if tuple(classes) != PHOTORECEPTOR_CLASSES:
        raise ValueError("visual photoreceptor classes are invalid")
    for neuron_class, parameters in classes.items():
        for key in (
            "ambient_gain",
            "spatial_contrast_gain",
            "temporal_contrast_gain",
            "maximum_external_current_a",
        ):
            value = float(parameters.get(key, -1.0))
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{neuron_class} {key} cannot be negative")
        if float(parameters["maximum_external_current_a"]) <= 0.0:
            raise ValueError(
                f"{neuron_class} maximum external current must be positive"
            )

    dynamics = raw.get("lon_dynamics", {})
    unit_current = float(dynamics.get("unit_current_per_synaptic_contact_a", 0.0))
    if not isfinite(unit_current) or unit_current <= 0.0:
        raise ValueError("visual contact current must be positive")
    if dynamics.get("effect_provenance") != "MODEL_FITTED":
        raise ValueError("visual synaptic effects must remain model-fitted")
    effects = dynamics.get("effect_by_presynaptic_class", {})
    if any(value not in {"excitatory", "inhibitory"} for value in effects.values()):
        raise ValueError("visual synaptic effect is invalid")
    unexecuted = tuple(dynamics.get("unexecuted_presynaptic_classes", ()))
    if unexecuted != ("SP2-1", "sVUM2", "Pdf-LaN"):
        raise ValueError("visual structural-only classes are invalid")
    if set(effects) & set(unexecuted):
        raise ValueError("visual classes cannot be both executable and structural-only")

    bridge = raw.get("descending_bridge", {})
    if bridge.get("provenance") != "MODEL_FITTED":
        raise ValueError("visual descending bridge must remain model-fitted")
    if tuple(bridge.get("readout_classes", ())) != (
        "VPLN",
        "nc-LaN",
        "5th-LaN",
        "PVL09",
        "pOLP",
    ):
        raise ValueError("visual descending readout classes are invalid")
    for key in (
        "activity_tau_s",
        "spike_increment",
        "common_output_gain",
        "lateral_difference_gain",
    ):
        value = float(bridge.get(key, 0.0))
        if not isfinite(value) or value <= 0.0:
            raise ValueError(f"visual descending bridge {key} must be positive")
    side_gains = bridge.get("side_activity_gain", {})
    if tuple(side_gains) != LON_SIDES or any(
        not isfinite(float(value)) or float(value) <= 0.0
        for value in side_gains.values()
    ):
        raise ValueError("visual bridge side activity gains are invalid")
    if float(bridge.get("direct_dorsoventral_difference_gain", -1.0)) != 0.0:
        raise ValueError("visual bridge cannot invent direct dorsoventral sensing")
    mapping_evidence = bridge.get("lateral_mapping_evidence", {})
    if (
        bridge.get("lateral_mapping") != "crossed_light_avoidance_prior"
        or mapping_evidence.get("doi") != "10.1073/pnas.1215295110"
        or mapping_evidence.get("stage") != "L2"
    ):
        raise ValueError("visual bridge lateral mapping boundary is invalid")
    if raw.get("parameter_provenance", {}).get("provenance") != "MODEL_FITTED":
        raise ValueError("visual numerical parameters must remain model-fitted")
    if raw.get("release_validated") is not False:
        raise ValueError("visual research approximation cannot be release-validated")
    return raw


def load_visual_connectome(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else default_visual_connectome_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("model_id") != "dmel_l1_visual_connectome_v0":
        raise ValueError("unexpected visual connectome model")
    if raw.get("stage") != "L1":
        raise ValueError("visual connectome must remain L1")
    source_record = raw.get("source", {})
    if (
        source_record.get("source_data_doi") != "10.7554/eLife.28387.009"
        or source_record.get("license") != "CC BY 4.0"
        or source_record.get("provenance") != "MEASURED_PUBLISHED"
    ):
        raise ValueError("visual connectome source contract is invalid")
    summary = raw.get("summary", {})
    if (
        int(summary.get("side_scoped_matrix_entries", 0)) != 60
        or int(summary.get("nonzero_connection_pairs", 0)) != 422
        or int(summary.get("within_lon_synaptic_contacts", 0)) != 3297
    ):
        raise ValueError("visual connectome summary is invalid")
    neurons = raw.get("neurons", [])
    node_ids = [item.get("node_id") for item in neurons]
    if len(neurons) != 60 or len(node_ids) != len(set(node_ids)):
        raise ValueError("visual connectome node identities are invalid")
    if any(
        item.get("synaptic_effect") is not None
        or item.get("synaptic_effect_provenance") != "unknown"
        for item in neurons
    ):
        raise ValueError("source connectome cannot claim physiological effects")
    connections = raw.get("connections", [])
    if len(connections) != 422:
        raise ValueError("visual connectome connection count is invalid")
    known = set(node_ids)
    if any(
        item.get("pre") not in known
        or item.get("post") not in known
        or not isinstance(item.get("synaptic_contacts"), int)
        or item["synaptic_contacts"] <= 0
        or item.get("provenance") != "MEASURED_PUBLISHED"
        for item in connections
    ):
        raise ValueError("visual connectome connection is invalid")
    if sum(item["synaptic_contacts"] for item in connections) != 3297:
        raise ValueError("visual connectome contact total is invalid")
    if raw.get("release_validated") is not False:
        raise ValueError("visual connectome cannot be release-validated")
    return raw


def visual_node_ids_for_class(
    connectome: dict[str, Any],
    neuron_class: str,
    *,
    lon_side: str | None = None,
) -> tuple[str, ...]:
    if lon_side is not None and lon_side not in LON_SIDES:
        raise ValueError("visual LON side must be left or right")
    result = tuple(
        item["node_id"]
        for item in connectome["neurons"]
        if item["neuron_class"] == neuron_class
        and (lon_side is None or item["lon_side"] == lon_side)
    )
    if not result:
        raise ValueError(f"visual neuron class {neuron_class!r} is absent")
    return result


@dataclass(frozen=True, slots=True)
class BolwigTransductionFrame:
    time_s: float
    sample_positions_m: dict[str, Vec3]
    irradiance_w_m2: dict[str, float]
    adapted_irradiance_w_m2: dict[str, float]
    receptor_drive: dict[str, dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_s": self.time_s,
            "sample_positions_m": {
                side: [position.x, position.y, position.z]
                for side, position in self.sample_positions_m.items()
            },
            "irradiance_w_m2": self.irradiance_w_m2,
            "adapted_irradiance_w_m2": self.adapted_irradiance_w_m2,
            "receptor_drive": self.receptor_drive,
        }


class BolwigLightTransduction:
    """Turn two local irradiance samples into fitted Rh5/Rh6 currents."""

    def __init__(self, field: ScalarField, config: dict[str, Any]) -> None:
        if field.modality_id != "light" or field.unit != "W_m-2":
            raise ValueError("Bolwig transduction requires a W_m-2 light field")
        self.field = field
        self.parameters = config["phototransduction"]
        self._adapted: dict[str, float] = {}
        self._last_time_s: float | None = None

    def sample(
        self, time_s: float, state: SpatialSensoryState
    ) -> BolwigTransductionFrame:
        if not isfinite(time_s) or time_s < 0.0:
            raise ValueError("visual sample time must be finite and non-negative")
        if self._last_time_s is not None and time_s < self._last_time_s:
            raise ValueError("visual sample time cannot move backwards")
        elapsed = (
            0.0 if self._last_time_s is None else time_s - self._last_time_s
        )
        positions = {
            "left": state.left_head_position_m,
            "right": state.right_head_position_m,
        }
        raw = {
            side: self.field.sample(position, time_s)
            for side, position in positions.items()
        }
        if any(not isfinite(value) or value < 0.0 for value in raw.values()):
            raise ValueError("Bolwig irradiance must be finite and non-negative")
        adapted = {
            side: self._adapted.get(side, value) for side, value in raw.items()
        }
        mean = sum(raw.values()) / len(raw)
        half_saturation = float(self.parameters["ambient_half_saturation"])
        spatial_scale = float(self.parameters["spatial_contrast_scale"])
        temporal_scale = float(self.parameters["temporal_contrast_scale"])
        receptor_drive: dict[str, dict[str, float]] = {}
        for neuron_class in PHOTORECEPTOR_CLASSES:
            class_parameters = self.parameters["classes"][neuron_class]
            drive_by_side = {}
            for side in LON_SIDES:
                ambient = raw[side] / (raw[side] + half_saturation)
                drive = (
                    float(class_parameters["ambient_gain"]) * ambient
                    + float(class_parameters["spatial_contrast_gain"])
                    * (raw[side] - mean)
                    / spatial_scale
                    + float(class_parameters["temporal_contrast_gain"])
                    * (raw[side] - adapted[side])
                    / temporal_scale
                )
                drive_by_side[side] = min(1.0, max(0.0, drive))
            receptor_drive[neuron_class] = drive_by_side

        coupling = (
            0.0
            if elapsed == 0.0
            else 1.0
            - exp(-elapsed / float(self.parameters["adaptation_tau_s"]))
        )
        self._adapted = {
            side: adapted[side] + (raw[side] - adapted[side]) * coupling
            for side in LON_SIDES
        }
        self._last_time_s = time_s
        return BolwigTransductionFrame(
            time_s=time_s,
            sample_positions_m=positions,
            irradiance_w_m2=raw,
            adapted_irradiance_w_m2=adapted,
            receptor_drive=receptor_drive,
        )


@dataclass(frozen=True, slots=True)
class VisualCircuitFrame:
    transduction: BolwigTransductionFrame
    spiked_neurons: tuple[str, ...]
    readout_spikes: dict[str, tuple[str, ...]]
    bridge_activity: dict[str, float]
    bridge_stimulus: SpatialStimulus

    def to_dict(self) -> dict[str, Any]:
        return {
            "transduction": self.transduction.to_dict(),
            "spiked_neurons": list(self.spiked_neurons),
            "readout_spikes": {
                side: list(values) for side, values in self.readout_spikes.items()
            },
            "bridge_activity": self.bridge_activity,
            "bridge_stimulus": list(self.bridge_stimulus.values()),
        }


class L1VisualCircuitProtocol:
    """Step the published LON matrix and emit a declared fitted bridge current."""

    def __init__(
        self,
        field: ScalarField,
        *,
        config: dict[str, Any] | None = None,
        connectome: dict[str, Any] | None = None,
        lesion_node_ids: Iterable[str] = (),
        record_frames: bool = False,
    ) -> None:
        self.config = config or load_visual_config()
        self.connectome = connectome or load_visual_connectome()
        self.transduction = BolwigLightTransduction(field, self.config)
        self.record_frames = record_frames
        self.frames: list[VisualCircuitFrame] = []
        self.neurons = tuple(self.connectome["neurons"])
        self.labels = tuple(item["node_id"] for item in self.neurons)
        self.index_by_id = {
            node_id: index for index, node_id in enumerate(self.labels)
        }
        self.metadata_by_id = {
            item["node_id"]: item for item in self.neurons
        }

        dynamics = self.config["lon_dynamics"]
        effects = dynamics["effect_by_presynaptic_class"]
        structural_only = set(dynamics["unexecuted_presynaptic_classes"])
        unit_current = float(dynamics["unit_current_per_synaptic_contact_a"])
        synapses: list[Synapse] = []
        executed_contacts = 0
        for item in self.connectome["connections"]:
            pre_class = self.metadata_by_id[item["pre"]]["neuron_class"]
            if pre_class in structural_only:
                continue
            if pre_class not in effects:
                raise ValueError(f"visual effect absent for {pre_class}")
            count = int(item["synaptic_contacts"])
            synapses.append(
                Synapse(
                    self.index_by_id[item["pre"]],
                    self.index_by_id[item["post"]],
                    unit_current * count,
                    kind=effects[pre_class],
                )
            )
            executed_contacts += count
        self.network = SparseLIFNetwork(len(self.neurons), synapses)
        self.executed_connection_pairs = len(synapses)
        self.executed_synaptic_contacts = executed_contacts

        lesions = tuple(lesion_node_ids)
        if len(lesions) != len(set(lesions)):
            raise ValueError("visual lesion node ids must be unique")
        unknown = set(lesions) - set(self.labels)
        if unknown:
            raise ValueError(f"unknown visual lesion node ids: {sorted(unknown)}")
        self.lesion_node_ids = lesions
        self.network.lesion(self.index_by_id[item] for item in lesions)

        readout_classes = set(self.config["descending_bridge"]["readout_classes"])
        self.readout_indices = {
            side: tuple(
                index
                for index, item in enumerate(self.neurons)
                if item["lon_side"] == side
                and item["neuron_class"] in readout_classes
            )
            for side in LON_SIDES
        }
        if any(not values for values in self.readout_indices.values()):
            raise ValueError("visual readout requires neurons on both LON sides")
        self.bridge_activity = {side: 0.0 for side in LON_SIDES}
        self.spike_counts = {label: 0 for label in self.labels}
        self.first_spike_s: dict[str, float | None] = {
            label: None for label in self.labels
        }

    def __call__(
        self, time_s: float, state: SpatialSensoryState
    ) -> SpatialStimulus:
        expected_time = self.network.step_index * self.network.config.dt_s
        if not isfinite(time_s) or abs(time_s - expected_time) > 1e-9:
            raise ValueError(
                "visual circuit must be stepped once per LIF dt in time order"
            )
        transduction = self.transduction.sample(time_s, state)
        external: dict[int, float] = {}
        class_parameters = self.config["phototransduction"]["classes"]
        for index, item in enumerate(self.neurons):
            neuron_class = item["neuron_class"]
            if neuron_class not in PHOTORECEPTOR_CLASSES:
                continue
            external[index] = (
                transduction.receptor_drive[neuron_class][item["lon_side"]]
                * float(
                    class_parameters[neuron_class][
                        "maximum_external_current_a"
                    ]
                )
            )
        spikes = self.network.step(external)
        spiked_labels = tuple(self.labels[index] for index in spikes)
        for label in spiked_labels:
            self.spike_counts[label] += 1
            if self.first_spike_s[label] is None:
                self.first_spike_s[label] = time_s

        bridge = self.config["descending_bridge"]
        decay = exp(-self.network.config.dt_s / float(bridge["activity_tau_s"]))
        readout_spikes: dict[str, tuple[str, ...]] = {}
        spiked = set(spikes)
        for side in LON_SIDES:
            self.bridge_activity[side] *= decay
            side_spikes = tuple(
                self.labels[index]
                for index in self.readout_indices[side]
                if index in spiked
            )
            readout_spikes[side] = side_spikes
            self.bridge_activity[side] += (
                len(side_spikes)
                * float(bridge["spike_increment"])
                * float(bridge["side_activity_gain"][side])
                / len(self.readout_indices[side])
            )

        left_activity = self.bridge_activity["left"]
        right_activity = self.bridge_activity["right"]
        common = (
            float(bridge["common_output_gain"])
            * (left_activity + right_activity)
            / 2.0
        )
        lateral = (
            float(bridge["lateral_difference_gain"])
            * (right_activity - left_activity)
            / 2.0
        )

        def bounded(value: float) -> float:
            return min(1.0, max(0.0, value))

        stimulus = SpatialStimulus(
            bounded(common + lateral),
            bounded(common - lateral),
            bounded(common),
            bounded(common),
        )
        if self.record_frames:
            self.frames.append(
                VisualCircuitFrame(
                    transduction=transduction,
                    spiked_neurons=spiked_labels,
                    readout_spikes=readout_spikes,
                    bridge_activity=dict(self.bridge_activity),
                    bridge_stimulus=stimulus,
                )
            )
        return stimulus


@dataclass(frozen=True, slots=True)
class VisualClosedLoopResult:
    model_id: str
    status: str
    spatial_result: SpatialClosedLoopResult
    visual_neuron_compartments: int
    published_connection_pairs: int
    published_synaptic_contacts: int
    executed_connection_pairs: int
    executed_synaptic_contacts: int
    visual_spike_counts: dict[str, int]
    visual_first_spike_s: dict[str, float | None]
    lesion_node_ids: tuple[str, ...]
    visual_frames: tuple[VisualCircuitFrame, ...]

    def to_dict(self) -> dict[str, Any]:
        body = self.spatial_result
        return {
            "model_id": self.model_id,
            "status": self.status,
            "duration_s": body.duration_s,
            "visual_neuron_compartments": self.visual_neuron_compartments,
            "downstream_spatial_neurons": body.neuron_count,
            "total_neuron_compartments": (
                self.visual_neuron_compartments + body.neuron_count
            ),
            "published_connection_pairs": self.published_connection_pairs,
            "published_synaptic_contacts": self.published_synaptic_contacts,
            "executed_connection_pairs": self.executed_connection_pairs,
            "executed_synaptic_contacts": self.executed_synaptic_contacts,
            "model_fitted_downstream_synapses": body.synapse_count,
            "displacement_x_um": body.displacement_x_um,
            "displacement_y_um": body.displacement_y_um,
            "displacement_z_um": body.displacement_z_um,
            "yaw_change_deg": body.yaw_change_deg,
            "head_pitch_change_deg": body.head_pitch_change_deg,
            "visual_spikes": sum(self.visual_spike_counts.values()),
            "downstream_spikes": sum(body.spike_counts.values()),
            "lesion_node_ids": list(self.lesion_node_ids),
            "release_validated": False,
            "claim_boundary": (
                "published L1 LON contacts plus fitted effects, "
                "phototransduction, and VPN-to-premotor bridge; not validated "
                "natural phototaxis or a complete sensor-to-muscle connectome"
            ),
        }


def validation_light_field(
    config: dict[str, Any] | None = None,
    *,
    lateral_sign: float = 1.0,
) -> LinearScalarField:
    if lateral_sign not in {-1.0, 1.0}:
        raise ValueError("validation lateral sign must be -1 or 1")
    raw = config or load_visual_config()
    item = raw["validation_light_field"]
    gradient = list(map(float, item["gradient_per_m"]))
    gradient[1] *= lateral_sign
    return LinearScalarField(
        modality_id="light",
        unit=item["unit"],
        origin_m=Vec3(*map(float, item["origin_m"])),
        value_at_origin=float(item["value_at_origin"]),
        gradient_per_m=Vec3(*gradient),
        temporal_rate_per_s=float(item["temporal_rate_per_s"]),
        lower_bound=float(item["lower_bound"]),
        upper_bound=float(item["upper_bound"]),
    )


class L1VisualClosedLoopLarva:
    """Compose the explicit L1 LON model with the existing embodied core."""

    def __init__(
        self,
        *,
        field: ScalarField | None = None,
        config: dict[str, Any] | None = None,
        connectome: dict[str, Any] | None = None,
        lesion_node_ids: Iterable[str] = (),
        ground_z_m: float | None = None,
        record_visual_frames: bool = False,
    ) -> None:
        self.config = config or load_visual_config()
        self.connectome = connectome or load_visual_connectome()
        self.protocol = L1VisualCircuitProtocol(
            field or validation_light_field(self.config),
            config=self.config,
            connectome=self.connectome,
            lesion_node_ids=lesion_node_ids,
            record_frames=record_visual_frames,
        )
        self.spatial = SpatialClosedLoopLarva(
            ground_z_m=ground_z_m,
            input_labels=BRIDGE_INPUT_LABELS,
            asymmetry_labels=BRIDGE_DIFFERENCE_LABELS,
        )

    def run(
        self,
        *,
        duration_s: float = 4.5,
        record_trajectory_interval_s: float | None = None,
    ) -> VisualClosedLoopResult:
        spatial_result = self.spatial.run(
            stimulus_protocol=self.protocol,
            duration_s=duration_s,
            record_trajectory_interval_s=record_trajectory_interval_s,
        )
        return VisualClosedLoopResult(
            model_id=self.config["model_id"],
            status=self.config["status"],
            spatial_result=spatial_result,
            visual_neuron_compartments=len(self.protocol.neurons),
            published_connection_pairs=int(
                self.connectome["summary"]["nonzero_connection_pairs"]
            ),
            published_synaptic_contacts=int(
                self.connectome["summary"]["within_lon_synaptic_contacts"]
            ),
            executed_connection_pairs=self.protocol.executed_connection_pairs,
            executed_synaptic_contacts=self.protocol.executed_synaptic_contacts,
            visual_spike_counts=dict(self.protocol.spike_counts),
            visual_first_spike_s=dict(self.protocol.first_spike_s),
            lesion_node_ids=self.protocol.lesion_node_ids,
            visual_frames=tuple(self.protocol.frames),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the provenance-aware L1 visual connectome body loop"
    )
    parser.add_argument("--duration", type=float, default=4.5)
    parser.add_argument("--mirror", action="store_true")
    parser.add_argument("--lesion-class")
    parser.add_argument("--lesion-side", choices=LON_SIDES)
    args = parser.parse_args(argv)
    config = load_visual_config()
    connectome = load_visual_connectome()
    lesions: tuple[str, ...] = ()
    if args.lesion_class:
        lesions = visual_node_ids_for_class(
            connectome, args.lesion_class, lon_side=args.lesion_side
        )
    result = L1VisualClosedLoopLarva(
        field=validation_light_field(
            config, lateral_sign=-1.0 if args.mirror else 1.0
        ),
        config=config,
        connectome=connectome,
        lesion_node_ids=lesions,
    ).run(duration_s=args.duration)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
