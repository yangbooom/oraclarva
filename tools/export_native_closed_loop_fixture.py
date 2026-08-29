"""Compile the Python closed-loop configuration into a native parity fixture."""

from __future__ import annotations

import argparse
from pathlib import Path

from oraclarva.organism import ClosedLoopLarva


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "parity"
    / "closed_loop_native_v1.tsv"
)


def number(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return format(float(value), ".17g")


def render_fixture() -> str:
    larva = ClosedLoopLarva()
    parameters = larva.params
    dt_s = float(parameters["dt_s"])
    lines = [
        "# Oraclarva 91-neuron embodied closed-loop native parity fixture.",
        "# Compiled from provenance-aware repository configs; do not edit by hand.",
        "# status: research_approximation",
        "# release_validated: false",
        "schema\tclosed_loop_native_v1",
        f"model_id\t{larva.config['model_id']}",
        f"status\t{larva.config['status']}",
        "release_validated\tfalse",
        f"neuron_count\t{larva.network.neuron_count}",
        f"steps\t{round(float(parameters['duration_s']) / dt_s)}",
        f"sample_stride\t{round(0.03 / dt_s)}",
        f"touch_neuron\t{larva.touch}",
    ]

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

    scalar_parameters = (
        "posterior_touch_current_a",
        "posterior_touch_duration_s",
        "proprioceptor_min_strain",
        "proprioceptor_min_shortening_rate_m_s",
        "proprioceptor_current_gain_a_s_m",
        "proprioceptor_max_current_a",
        "sensory_adaptation_tau_s",
        "sensory_adaptation_fraction",
        "body_velocity_retention",
        "ground_negative_x_retention",
        "ground_positive_x_retention",
        "motor_excitation_tau_s",
        "excitation_per_motor_spike",
        "muscle_activation_excitation_threshold",
    )
    for key in scalar_parameters:
        lines.append(f"parameter\t{key}\t{number(parameters[key])}")
    lines.extend((
        "parameter\tgravity_z_m_s2\t-9.8100000000000005",
        "parameter\tground_z_m\t0",
        "parameter\tbody_iterations\t12",
        "parameter\tinstantaneous_stiffness_n_m\t"
        + number(larva.body.spec.scaled_mechanics().instantaneous_stiffness_n_per_m),
    ))

    for index, label in enumerate(larva._labels()):
        lines.append(f"neuron\t{index}\t{label}")

    for index, segment in enumerate(larva.body.geometry):
        lines.append("\t".join((
            "body_segment",
            str(index),
            segment.id,
            number(segment.rest_length_m),
            number(segment.width_m),
            number(segment.height_m),
            number(segment.mass_kg),
            number(larva.body.maximum_shortening_fractions[index]),
        )))

    for wave_index, segment_id in enumerate(larva.segments):
        lines.append("\t".join((
            "wave_segment",
            str(wave_index),
            segment_id,
            str(larva.body_indices[segment_id]),
            str(larva.proprioceptor_offset + wave_index),
            str(larva.premotor_offset + wave_index),
            str(larva.inhibitory_offset + wave_index),
            str(larva.motor_offset + wave_index),
            number(parameters["muscle_activation_rise_tau_s_by_segment"][segment_id]),
            number(parameters["muscle_activation_fall_tau_s_by_segment"][segment_id]),
        )))

    for segment_id, projections in larva.motor_identities_by_segment.items():
        for projection in projections:
            lines.append("\t".join((
                "motor_identity",
                segment_id,
                str(larva.motor_identity_indices[projection.neuron_id]),
                projection.neuron_id,
            )))

    for segment_id, count in larva.muscle_identity_projection.expected_counts.items():
        lines.append(f"muscle_proxy\t{segment_id}\t{count}")

    for outgoing in larva.network.outgoing:
        for synapse in outgoing:
            lines.append("\t".join((
                "synapse",
                str(synapse.pre),
                str(synapse.post),
                number(synapse.current_a),
                synapse.kind,
                str(synapse.delay_steps),
            )))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile the Python embodied loop into a C++ parity fixture"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = render_fixture()
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            print(f"generated native fixture is stale: {args.output}")
            return 1
        print("generated native closed-loop fixture is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
