#!/usr/bin/env python3
"""Compile the Python four-channel spatial loop into a native fixture."""

from __future__ import annotations

import argparse
from pathlib import Path

from oraclarva.environment_inputs import load_environment_input_config
from oraclarva.spatial import CHANNELS, SpatialClosedLoopLarva


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "parity" / "spatial_environment_native_v1.tsv"


def number(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return format(float(value), ".17g")


def render_fixture() -> str:
    larva = SpatialClosedLoopLarva()
    environment = load_environment_input_config()
    parameters = larva.params
    spatial = larva.spatial_params
    transduction = environment["transduction"]["light"]
    lines = [
        "# Oraclarva Stage 9 four-channel native environment fixture.",
        "# Generated from checked Python configs; do not edit by hand.",
        "# Environment samples never encode a target heading or movement command.",
        "schema\tspatial_environment_native_v1",
        "model_id\tdmel_l1_native_environment_closed_loop_v1",
        "status\tresearch_approximation",
        "release_validated\tfalse",
        f"neuron_count\t{larva.network.neuron_count}",
        f"synapse_count\t{larva.synapse_count}",
    ]
    for channel_index, channel in enumerate(CHANNELS):
        lines.append(f"touch_neuron\t{channel}\t{larva.touch_offset + channel_index}")
        lines.append(
            f"asymmetry_neuron\t{channel}\t"
            f"{larva.asymmetry_offset + channel_index}"
        )

    config = larva.network.config
    for key in (
        "dt_s",
        "tau_m_s",
        "tau_exc_s",
        "tau_inh_s",
        "resistance_ohm",
        "v_rest_v",
        "v_reset_v",
        "v_threshold_v",
        "refractory_s",
    ):
        lines.append(f"config\t{key}\t{number(getattr(config, key))}")

    for key in (
        "posterior_touch_current_a",
        "proprioceptor_min_strain",
        "proprioceptor_min_shortening_rate_m_s",
        "proprioceptor_current_gain_a_s_m",
        "proprioceptor_max_current_a",
        "sensory_adaptation_tau_s",
        "sensory_adaptation_fraction",
        "motor_excitation_tau_s",
        "excitation_per_motor_spike",
        "muscle_activation_excitation_threshold",
    ):
        lines.append(f"parameter\t{key}\t{number(parameters[key])}")
    lines.append("parameter\tintegrated_proprioception_enabled\t0")
    for key in (
        "active_yaw_curvature_gain",
        "active_pitch_curvature_gain",
        "active_bending_stiffness_ratio",
        "asymmetric_sensory_current_a",
    ):
        lines.append(f"parameter\t{key}\t{number(spatial[key])}")
    lines.extend(
        (
            f"parameter\tbaseline_intensity\t{number(environment['baseline_intensity'])}",
            f"parameter\tlight_response_scale\t{number(transduction['response_scale'])}",
            "parameter\tlight_polarity\t1",
            f"parameter\tlight_spatial_gain\t{number(transduction['spatial_contrast_gain'])}",
            f"parameter\tlight_temporal_gain\t{number(transduction['temporal_contrast_gain'])}",
            f"parameter\tlight_adaptation_tau_s\t{number(transduction['adaptation_tau_s'])}",
            f"parameter\tlight_weight\t{number(transduction['weight'])}",
        )
    )

    for index, label in enumerate(larva._labels()):
        lines.append(f"neuron\t{index}\t{label}")
    for index, segment in enumerate(larva.body.geometry):
        lines.append(
            "\t".join(
                (
                    "body_segment",
                    str(index),
                    segment.id,
                    number(segment.rest_length_m),
                    number(segment.width_m),
                    number(segment.height_m),
                )
            )
        )
    for wave_index, segment_id in enumerate(larva.segments):
        neuron_fields: list[str] = []
        for offset in (
            larva.proprioceptor_offset,
            larva.premotor_offset,
            larva.inhibitory_offset,
            larva.motor_offset,
        ):
            neuron_fields.extend(
                str(larva._channel_index(offset, wave_index, channel_index))
                for channel_index in range(len(CHANNELS))
            )
        lines.append(
            "\t".join(
                (
                    "wave_segment",
                    str(wave_index),
                    segment_id,
                    str(larva.body_indices[segment_id]),
                    *neuron_fields,
                    number(larva.rise_tau[segment_id]),
                    number(larva.fall_tau[segment_id]),
                )
            )
        )
    for outgoing in larva.network.outgoing:
        for synapse in outgoing:
            lines.append(
                "\t".join(
                    (
                        "synapse",
                        str(synapse.pre),
                        str(synapse.post),
                        number(synapse.current_a),
                        synapse.kind,
                        str(synapse.delay_steps),
                    )
                )
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_fixture()
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            print(f"generated native spatial fixture is stale: {args.output}")
            return 1
        print("generated native spatial fixture is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
