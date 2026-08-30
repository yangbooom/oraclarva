import inspect
import json

import pytest

from oraclarva.artifacts import NUMERIC_TOLERANCE, first_mismatch
from oraclarva.body3d import Vec3
from oraclarva.environment_inputs import (
    LinearScalarField,
    ModalityTransduction,
    MultimodalFieldTransduction,
    load_environment_input_config,
    validation_fields,
)
from oraclarva.spatial import (
    SpatialClosedLoopLarva,
    SpatialSensoryState,
    SpatialStimulus,
)

@pytest.fixture
def receptor_state():
    return SpatialSensoryState(
        left_head_position_m=Vec3(0.0, -100e-6, 0.0),
        right_head_position_m=Vec3(0.0, 100e-6, 0.0),
        dorsal_head_position_m=Vec3(0.0, 0.0, 100e-6),
        ventral_head_position_m=Vec3(0.0, 0.0, -100e-6),
    )


def protocol_for(field, *, record_frames=False):
    return MultimodalFieldTransduction.from_config(
        (field,),
        enabled_modalities=(field.modality_id,),
        record_frames=record_frames,
    )


def test_artifact_comparison_is_schema_exact_and_float_tolerant():
    expected = {"count": 1, "values": [0.5, {"label": "light"}]}
    within = {
        "count": 1,
        "values": [0.5 + NUMERIC_TOLERANCE / 2, {"label": "light"}],
    }
    outside = {
        "count": 1,
        "values": [0.5 + NUMERIC_TOLERANCE * 2, {"label": "light"}],
    }
    wrong_schema = {"count": 1, "other": []}

    assert first_mismatch(expected, within) is None
    assert "values[0]" in first_mismatch(expected, outside)
    assert "keys mismatch" in first_mismatch(expected, wrong_schema)
    assert "integer/type mismatch" in first_mismatch(1, 1.0)
    assert "non-finite" in first_mismatch(float("nan"), float("nan"))

def test_environment_input_config_preserves_claim_boundary():
    config = load_environment_input_config()
    assert config["status"] == "research_approximation"
    assert config["stage"] == "L1"
    assert config["provenance"] == "MODEL_FITTED"
    assert config["modalities"] == ["light", "temperature", "odor"]
    assert config["release_validated"] is False
    assert all(
        item["provenance"] == "MODEL_FITTED"
        for item in config["transduction"].values()
    )
    assert config["transduction"]["light"]["spatial_contrast_gain"] > 0.0
    assert (
        config["transduction"]["temperature"]["spatial_contrast_gain"] == 0.0
    )
    assert config["transduction"]["odor"]["spatial_contrast_gain"] == 0.0
    assert any(
        "does not yet reproduce" in limitation
        for limitation in config["limitations"]
    )


def test_config_rejects_invented_temperature_spatial_sensing(tmp_path):
    config = load_environment_input_config()
    config["transduction"]["temperature"]["spatial_contrast_gain"] = 0.1
    path = tmp_path / "invalid_environment.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="temporal-only"):
        load_environment_input_config(path)

def test_linear_field_has_units_space_time_and_clamps():
    field = LinearScalarField(
        modality_id="light",
        unit="W_m-2",
        origin_m=Vec3(1.0, 2.0, 3.0),
        value_at_origin=4.0,
        gradient_per_m=Vec3(2.0, -1.0, 0.5),
        temporal_rate_per_s=3.0,
        lower_bound=0.0,
        upper_bound=10.0,
    )
    assert field.sample(Vec3(2.0, 1.0, 5.0), 0.5) == pytest.approx(9.5)
    assert field.sample(Vec3(10.0, 0.0, 3.0), 5.0) == 10.0
    with pytest.raises(ValueError, match="non-negative"):
        field.sample(Vec3(0.0, 0.0, 0.0), -1.0)
    with pytest.raises(ValueError, match="position must be finite"):
        field.sample(Vec3(float("nan"), 0.0, 0.0), 0.0)


def test_uniform_field_produces_symmetric_baseline(receptor_state):
    field = LinearScalarField(
        modality_id="light",
        unit="W_m-2",
        origin_m=Vec3(0.0, 0.0, 0.0),
        value_at_origin=4.0,
        gradient_per_m=Vec3(0.0, 0.0, 0.0),
    )
    assert protocol_for(field)(0.0, receptor_state) == SpatialStimulus(
        0.5, 0.5, 0.5, 0.5
    )


def test_validation_modalities_preserve_supported_spatial_scope(
    receptor_state,
):
    light, temperature, odor = validation_fields()
    light_response = protocol_for(light)(0.0, receptor_state)
    temperature_response = protocol_for(temperature)(0.0, receptor_state)
    odor_response = protocol_for(odor)(0.0, receptor_state)

    assert light_response.right_intensity > light_response.left_intensity
    assert light_response.dorsal_intensity > light_response.ventral_intensity
    assert temperature_response == SpatialStimulus(0.5, 0.5, 0.5, 0.5)
    assert odor_response == SpatialStimulus(0.5, 0.5, 0.5, 0.5)


@pytest.mark.parametrize(
    ("modality", "unit", "rate", "expected_direction"),
    (
        ("light", "W_m-2", 1.0, 1),
        ("temperature", "degC", 0.01, -1),
        ("odor", "normalized_concentration", -0.1, 1),
    ),
)
def test_adaptive_transduction_responds_to_temporal_change(
    receptor_state, modality, unit, rate, expected_direction
):
    value = {"light": 4.0, "temperature": 18.0, "odor": 0.5}[modality]
    field = LinearScalarField(
        modality_id=modality,
        unit=unit,
        origin_m=Vec3(0.0, 0.0, 0.0),
        value_at_origin=value,
        gradient_per_m=Vec3(0.0, 0.0, 0.0),
        temporal_rate_per_s=rate,
    )
    protocol = protocol_for(field, record_frames=True)
    baseline = protocol(0.0, receptor_state)
    changed = protocol(0.1, receptor_state)

    assert baseline == SpatialStimulus(0.5, 0.5, 0.5, 0.5)
    if expected_direction > 0:
        assert all(value > 0.5 for value in changed.values())
    else:
        assert all(value < 0.5 for value in changed.values())
    assert len(protocol.frames) == 2
    assert protocol.frames[-1].raw_values[modality] != (
        protocol.frames[-1].adapted_values[modality]
    )


def test_multimodal_drives_sum_before_single_bounded_receptor_output(
    receptor_state,
):
    light, temperature, _ = validation_fields()
    protocol = MultimodalFieldTransduction.from_config(
        (light, temperature),
        enabled_modalities=("light", "temperature"),
        record_frames=True,
    )
    stimulus = protocol(0.0, receptor_state)

    assert all(0.0 <= value <= 1.0 for value in stimulus.values())
    assert set(protocol.frames[0].raw_values) == {"light", "temperature"}
    assert set(protocol.frames[0].drive_values) == {"light", "temperature"}


def test_transduction_rejects_time_reversal(receptor_state):
    protocol = protocol_for(validation_fields(modalities=("light",))[0])
    protocol(1.0, receptor_state)
    with pytest.raises(ValueError, match="backwards"):
        protocol(0.5, receptor_state)


def test_nonfinite_transduction_parameter_is_rejected():
    with pytest.raises(ValueError, match="must be finite"):
        ModalityTransduction(
            modality_id="light",
            unit="W_m-2",
            polarity="increased_excites",
            response_scale=float("nan"),
            spatial_contrast_gain=0.4,
            temporal_contrast_gain=0.6,
            adaptation_tau_s=0.5,
            weight=1.0,
        )


def test_explicit_empty_modality_set_is_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        MultimodalFieldTransduction.from_config(
            validation_fields(modalities=("light",)),
            enabled_modalities=(),
        )


def test_mirrored_light_fields_produce_mirrored_neural_body_trajectories():
    results = []
    for sign in (-1.0, 1.0):
        field = LinearScalarField(
            modality_id="light",
            unit="W_m-2",
            origin_m=Vec3(0.0, 0.0, 0.0),
            value_at_origin=4.0,
            gradient_per_m=Vec3(0.0, sign * 6000.0, 0.0),
            lower_bound=0.0,
            upper_bound=20.0,
        )
        result = SpatialClosedLoopLarva(ground_z_m=None).run(
            stimulus_protocol=protocol_for(field),
            duration_s=2.0,
        )
        results.append(result)

    negative, positive = results
    assert positive.displacement_x_um == pytest.approx(
        negative.displacement_x_um, abs=1e-9
    )
    assert positive.displacement_y_um == pytest.approx(
        -negative.displacement_y_um, abs=1e-9
    )
    assert positive.displacement_z_um == pytest.approx(
        negative.displacement_z_um, abs=1e-9
    )
    assert positive.yaw_change_deg == pytest.approx(
        -negative.yaw_change_deg, abs=1e-9
    )
    assert positive.head_pitch_change_deg == pytest.approx(
        negative.head_pitch_change_deg, abs=1e-9
    )
    assert sum(positive.spike_counts.values()) == sum(
        negative.spike_counts.values()
    )
    assert abs(positive.displacement_y_um) > 10.0
    assert abs(positive.yaw_change_deg) > 5.0


def test_environment_input_exposes_no_movement_commands():
    source = inspect.getsource(MultimodalFieldTransduction).lower()
    forbidden = (
        "turn_left",
        "turn_right",
        "pitch_up",
        "pitch_down",
        "crawl(",
        "move_3d",
        "behavior_tree",
        "fsm",
    )
    assert all(token not in source for token in forbidden)
