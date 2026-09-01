"""Compile the checked corrective repeat-crawl model into a C++17 fixture."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from oraclarva.repeat_crawl import (
    RepeatCrawlLarva,
    WAVE_SEGMENTS,
    default_repeat_crawl_path,
    load_repeat_crawl_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = default_repeat_crawl_path()
DEFAULT_OUTPUT = ROOT / "data" / "parity" / "repeat_crawl_native_v1.tsv"


def number(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return format(float(value), ".17g")


def render_fixture() -> str:
    config = load_repeat_crawl_config(CONFIG)
    config_sha = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    larva = RepeatCrawlLarva(config)
    protocol = larva.protocol
    dt_s = float(config["parameters"]["dt_s"])
    lines = [
        "# Oraclarva Stage 7 repeat-crawl native parity fixture.",
        "# Compiled from checked provenance-aware config; do not edit by hand.",
        "# No action command, FSM, policy network, or authored motion.",
        "schema\trepeat_crawl_native_v1",
        f"model_id\t{config['model_id']}",
        f"status\t{config['status']}",
        "release_validated\tfalse",
        f"config_sha256\t{config_sha}",
        f"neuron_count\t{len(protocol.labels)}",
        f"steps\t{round(float(config['parameters']['duration_s']) / dt_s)}",
        f"sample_stride\t{round(0.03 / dt_s)}",
        "equilibrium_steps\t50",
        f"touch_neuron\t{protocol.index_by_id['environment_touch_receptor']}",
        f"recovery_neuron\t{protocol.index_by_id['mechanosensory:recovery:A1']}",
    ]
    lif = protocol.network.config
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
        lines.append(f"config\t{key}\t{number(getattr(lif, key))}")

    parameters = config["parameters"]
    for key in (
        "posterior_touch_current_a",
        "posterior_touch_duration_s",
        "intersegmental_relay_delay_s",
        "a1_recovery_to_a6_delay_s",
        "sensory_maximum_current_a",
        "sensory_adaptation_tau_s",
        "sensory_adaptation_fraction",
        "recovery_adaptation_fraction",
        "recovery_rate_threshold_s_1",
        "recovery_rate_gain_s",
        "local_tension_gate_gain",
        "trace_arrival_window_s",
        "muscle_activation_rise_tau_s",
        "muscle_activation_decay_tau_s",
        "muscle_event_target",
    ):
        lines.append(f"parameter\t{key}\t{number(parameters[key])}")

    transduction = config["body_state_transduction"]
    for key in (
        "shortening_strain_threshold",
        "shortening_rate_threshold_s_1",
        "shortening_strain_gain",
        "shortening_rate_gain_s",
        "maximum_external_current_a",
    ):
        lines.append(f"parameter\t{key}\t{number(transduction[key])}")

    coupling = config["named_fiber_body_coupling"]
    for key in (
        "active_tension_gain_model_units",
        "passive_stiffness_model_units",
        "damping_model_units",
        "acceleration_scale_m_s2_per_model_force",
        "body_velocity_retention",
        "ground_negative_x_retention",
        "ground_positive_x_retention",
    ):
        lines.append(f"parameter\t{key}\t{number(coupling[key])}")
    lines.extend(
        (
            "parameter\tgravity_z_m_s2\t-9.8100000000000005",
            "parameter\tground_z_m\t0",
            "parameter\tbody_iterations\t12",
            "parameter\tinstantaneous_stiffness_n_m\t"
            + number(larva.body._instantaneous_stiffness),
        )
    )

    for index, label in enumerate(protocol.labels):
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
                    number(segment.mass_kg),
                    number(larva.body.maximum_shortening_fractions[index]),
                )
            )
        )

    for index, segment in enumerate(WAVE_SEGMENTS):
        source_indices = [
            protocol.index_by_id[node]
            for node in protocol.source_nodes_by_segment[segment]
        ]
        lines.append(
            "\t".join(
                (
                    "wave_segment",
                    str(index),
                    segment,
                    str(larva.body_index[segment]),
                    str(
                        protocol.index_by_id[
                            f"mechanosensory:shortening:{segment}"
                        ]
                    ),
                    str(protocol.index_by_id[f"premotor_A27h_like:{segment}"]),
                    str(protocol.index_by_id[f"inhibitory_PMSI_like:{segment}"]),
                    ",".join(str(value) for value in source_indices),
                    number(
                        parameters["muscle_activation_decay_tau_s_by_segment"][
                            segment
                        ]
                    ),
                )
            )
        )

    for outgoing in protocol.network.outgoing:
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

    for index, (mapping, geometry) in enumerate(
        zip(larva.projection.mappings, larva.coupling.geometries, strict=True)
    ):
        if mapping.fiber_id != geometry.fiber_id:
            raise RuntimeError("fiber mapping/geometry order drifted")
        lines.append(
            "\t".join(
                (
                    "fiber",
                    str(index),
                    mapping.fiber_id,
                    mapping.segment_id,
                    mapping.side,
                    mapping.muscle_number,
                    str(geometry.segment_index),
                    str(protocol.index_by_id[mapping.source_node_id]),
                    number(geometry.origin.s),
                    number(geometry.origin.theta_rad),
                    number(geometry.origin.depth_fraction),
                    number(geometry.insertion.s),
                    number(geometry.insertion.theta_rad),
                    number(geometry.insertion.depth_fraction),
                    mapping.mapping_provenance,
                    number(
                        1.0
                        if larva.coupling.fiber_force_scale_by_id is None
                        else larva.coupling.fiber_force_scale_by_id[
                            mapping.fiber_id
                        ]
                    ),
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
            print(f"generated native repeat-crawl fixture is stale: {args.output}")
            return 1
        print("generated native repeat-crawl fixture is current")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
