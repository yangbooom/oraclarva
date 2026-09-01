"""ctypes harness for the additive Stage 9 native environment ABI."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Any


CHANNEL_COUNT = 4
NEURON_COUNT = 168
BODY_NODE_COUNT = 13
BODY_SEGMENT_COUNT = 12


class RepeatOptions(ctypes.Structure):
    _fields_ = [
        ("sensory_lesion_segment", ctypes.c_char_p),
        ("premotor_lesion_segment", ctypes.c_char_p),
        ("motor_lesion_segment", ctypes.c_char_p),
        ("fiber_lesion_segment", ctypes.c_char_p),
    ]


class SpatialOptions(ctypes.Structure):
    _fields_ = [
        ("sensory_lesion_channel", ctypes.c_char_p),
        ("premotor_lesion_channel", ctypes.c_char_p),
        ("motor_lesion_channel", ctypes.c_char_p),
        ("muscle_lesion_channel", ctypes.c_char_p),
    ]


class LightField(ctypes.Structure):
    _fields_ = [
        ("enabled", ctypes.c_uint8),
        ("origin_m", ctypes.c_double * 3),
        ("value_at_origin_w_m2", ctypes.c_double),
        ("gradient_w_m3", ctypes.c_double * 3),
        ("temporal_rate_w_m2_s", ctypes.c_double),
        ("lower_bound_w_m2", ctypes.c_double),
        ("upper_bound_w_m2", ctypes.c_double),
    ]


class IntegratedInput(ctypes.Structure):
    _fields_ = [
        ("posterior_touch_intensity", ctypes.c_double),
        ("light", LightField),
    ]


class EnvironmentSnapshot(ctypes.Structure):
    _fields_ = [
        ("extension_abi_version", ctypes.c_uint32),
        ("step_index", ctypes.c_uint32),
        ("time_s", ctypes.c_double),
        ("displacement_um", ctypes.c_double * 3),
        ("heading_change_deg", ctypes.c_double),
        ("head_pitch_change_deg", ctypes.c_double),
        ("physics_nodes_um", ctypes.c_double * (BODY_NODE_COUNT * 3)),
        (
            "segment_yaw_activation",
            ctypes.c_double * (BODY_SEGMENT_COUNT * 2),
        ),
        (
            "segment_pitch_activation",
            ctypes.c_double * (BODY_SEGMENT_COUNT * 2),
        ),
        ("raw_light_w_m2", ctypes.c_double * CHANNEL_COUNT),
        ("adapted_light_w_m2", ctypes.c_double * CHANNEL_COUNT),
        ("light_drive", ctypes.c_double * CHANNEL_COUNT),
        ("receptor_current", ctypes.c_double * CHANNEL_COUNT),
        ("channel_activation", ctypes.c_double * CHANNEL_COUNT),
        ("spatial_spike_counts", ctypes.c_uint32 * NEURON_COUNT),
        ("spatial_last_step_spiked", ctypes.c_uint8 * NEURON_COUNT),
        ("release_validated", ctypes.c_uint8),
        ("spatial_fixture_schema", ctypes.c_char * 48),
        ("spatial_model_id", ctypes.c_char * 64),
    ]


def _bytes(value: str | None) -> bytes | None:
    return None if value is None else value.encode()


def load_library(path: Path) -> ctypes.CDLL:
    library = ctypes.CDLL(str(path))
    library.oraclarva_mobile_create_spatial.restype = ctypes.c_int
    library.oraclarva_mobile_create_spatial.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(RepeatOptions),
        ctypes.POINTER(SpatialOptions),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    library.oraclarva_mobile_advance_environment.restype = ctypes.c_int
    library.oraclarva_mobile_advance_environment.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(IntegratedInput),
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    library.oraclarva_mobile_read_environment_snapshot.restype = ctypes.c_int
    library.oraclarva_mobile_read_environment_snapshot.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(EnvironmentSnapshot),
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    library.oraclarva_mobile_reset.restype = ctypes.c_int
    library.oraclarva_mobile_reset.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    library.oraclarva_mobile_destroy.argtypes = [ctypes.c_void_p]
    return library


def _check(status: int, error: ctypes.Array[ctypes.c_char]) -> None:
    if status:
        raise RuntimeError(error.value.decode() or f"native status {status}")


def _pairs(values: Any) -> list[list[float]]:
    return [
        [float(values[index * 2]), float(values[index * 2 + 1])]
        for index in range(BODY_SEGMENT_COUNT)
    ]


def snapshot_dict(value: EnvironmentSnapshot) -> dict[str, Any]:
    nodes = [
        [
            float(value.physics_nodes_um[index * 3]),
            float(value.physics_nodes_um[index * 3 + 1]),
            float(value.physics_nodes_um[index * 3 + 2]),
        ]
        for index in range(BODY_NODE_COUNT)
    ]
    return {
        "step_index": int(value.step_index),
        "time_s": float(value.time_s),
        "displacement_um": list(map(float, value.displacement_um)),
        "anatomical_forward_um": -float(value.displacement_um[0]),
        "heading_change_deg": float(value.heading_change_deg),
        "head_pitch_change_deg": float(value.head_pitch_change_deg),
        "physics_nodes_um": nodes,
        "segment_yaw_activation": _pairs(value.segment_yaw_activation),
        "segment_pitch_activation": _pairs(value.segment_pitch_activation),
        "raw_light_w_m2": list(map(float, value.raw_light_w_m2)),
        "adapted_light_w_m2": list(map(float, value.adapted_light_w_m2)),
        "light_drive": list(map(float, value.light_drive)),
        "receptor_current": list(map(float, value.receptor_current)),
        "channel_activation": list(map(float, value.channel_activation)),
        "spatial_spike_total": sum(map(int, value.spatial_spike_counts)),
        "spatial_spike_counts": list(map(int, value.spatial_spike_counts)),
        "spatial_last_step_spikes": [
            index for index, active in enumerate(value.spatial_last_step_spiked) if active
        ],
    }


def run_scenario(
    library: ctypes.CDLL,
    repeat_fixture: Path,
    spatial_fixture: Path,
    *,
    gradient_w_m3: tuple[float, float, float],
    steps: int = 6000,
    sample_stride: int = 60,
    touch_steps: int = 2,
    sensory_lesion_channel: str | None = None,
    premotor_lesion_channel: str | None = None,
    motor_lesion_channel: str | None = None,
    muscle_lesion_channel: str | None = None,
) -> dict[str, Any]:
    error = ctypes.create_string_buffer(512)
    core = ctypes.c_void_p()
    repeat_options = RepeatOptions(None, None, None, None)
    spatial_options = SpatialOptions(
        _bytes(sensory_lesion_channel),
        _bytes(premotor_lesion_channel),
        _bytes(motor_lesion_channel),
        _bytes(muscle_lesion_channel),
    )
    _check(
        library.oraclarva_mobile_create_spatial(
            str(repeat_fixture).encode(),
            str(spatial_fixture).encode(),
            ctypes.byref(repeat_options),
            ctypes.byref(spatial_options),
            ctypes.byref(core),
            error,
            len(error),
        ),
        error,
    )
    try:
        field = LightField(
            1,
            (ctypes.c_double * 3)(0.0, 0.0, 0.0),
            4.0,
            (ctypes.c_double * 3)(*gradient_w_m3),
            0.0,
            0.0,
            20.0,
        )
        frames: list[dict[str, Any]] = []
        initial = EnvironmentSnapshot()
        _check(
            library.oraclarva_mobile_read_environment_snapshot(
                core, ctypes.byref(initial), error, len(error)
            ),
            error,
        )
        frames.append(snapshot_dict(initial))
        for step in range(steps):
            value = IntegratedInput(1.0 if step < touch_steps else 0.0, field)
            _check(
                library.oraclarva_mobile_advance_environment(
                    core, ctypes.byref(value), error, len(error)
                ),
                error,
            )
            if (step + 1) % sample_stride == 0 or step + 1 == steps:
                snapshot = EnvironmentSnapshot()
                _check(
                    library.oraclarva_mobile_read_environment_snapshot(
                        core, ctypes.byref(snapshot), error, len(error)
                    ),
                    error,
                )
                frames.append(snapshot_dict(snapshot))
        final = frames[-1]
        return {
            "gradient_w_m3": list(gradient_w_m3),
            "steps": steps,
            "sample_stride": sample_stride,
            "lesions": {
                "sensory_channel": sensory_lesion_channel,
                "premotor_channel": premotor_lesion_channel,
                "motor_channel": motor_lesion_channel,
                "muscle_channel": muscle_lesion_channel,
            },
            "frames": frames,
            "result_summary": {
                key: final[key]
                for key in (
                    "displacement_um",
                    "anatomical_forward_um",
                    "heading_change_deg",
                    "head_pitch_change_deg",
                    "spatial_spike_total",
                    "receptor_current",
                    "channel_activation",
                )
            },
        }
    finally:
        library.oraclarva_mobile_destroy(core)
