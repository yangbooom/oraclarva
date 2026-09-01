#ifndef ORACLARVA_MOBILE_ENVIRONMENT_H
#define ORACLARVA_MOBILE_ENVIRONMENT_H

#include "mobile_core.h"

#ifdef __cplusplus
extern "C" {
#endif

#define ORACLARVA_MOBILE_ENVIRONMENT_ABI_VERSION 1u
#define ORACLARVA_MOBILE_SPATIAL_NEURON_COUNT 168u
#define ORACLARVA_MOBILE_SPATIAL_CHANNEL_COUNT 4u
#define ORACLARVA_MOBILE_BODY_SEGMENT_COUNT 12u

/*
 * Additive Stage 9 extension. The field contains physical scalar parameters;
 * it never contains a heading, turn, gait, target, or animation command.
 */

typedef struct OraclarvaMobileSpatialOptions {
  const char* sensory_lesion_channel;
  const char* premotor_lesion_channel;
  const char* motor_lesion_channel;
  const char* muscle_lesion_channel;
} OraclarvaMobileSpatialOptions;

typedef struct OraclarvaMobileLightField {
  uint8_t enabled;
  double origin_m[3];
  double value_at_origin_w_m2;
  double gradient_w_m3[3];
  double temporal_rate_w_m2_s;
  double lower_bound_w_m2;
  double upper_bound_w_m2;
} OraclarvaMobileLightField;

typedef struct OraclarvaMobileIntegratedEnvironmentInput {
  double posterior_touch_intensity;
  OraclarvaMobileLightField light;
} OraclarvaMobileIntegratedEnvironmentInput;

typedef struct OraclarvaMobileEnvironmentSnapshot {
  uint32_t extension_abi_version;
  uint32_t step_index;
  double time_s;
  double displacement_um[3];
  double heading_change_deg;
  double head_pitch_change_deg;
  double physics_nodes_um[ORACLARVA_MOBILE_BODY_NODE_COUNT * 3u];
  double segment_yaw_activation[
      ORACLARVA_MOBILE_BODY_SEGMENT_COUNT * 2u];
  double segment_pitch_activation[
      ORACLARVA_MOBILE_BODY_SEGMENT_COUNT * 2u];
  double raw_light_w_m2[ORACLARVA_MOBILE_SPATIAL_CHANNEL_COUNT];
  double adapted_light_w_m2[ORACLARVA_MOBILE_SPATIAL_CHANNEL_COUNT];
  double light_drive[ORACLARVA_MOBILE_SPATIAL_CHANNEL_COUNT];
  double receptor_current[ORACLARVA_MOBILE_SPATIAL_CHANNEL_COUNT];
  double channel_activation[ORACLARVA_MOBILE_SPATIAL_CHANNEL_COUNT];
  uint32_t spatial_spike_counts[ORACLARVA_MOBILE_SPATIAL_NEURON_COUNT];
  uint8_t spatial_last_step_spiked[ORACLARVA_MOBILE_SPATIAL_NEURON_COUNT];
  uint8_t release_validated;
  char spatial_fixture_schema[48];
  char spatial_model_id[64];
} OraclarvaMobileEnvironmentSnapshot;

ORACLARVA_MOBILE_API int oraclarva_mobile_create_spatial(
    const char* repeat_fixture_path,
    const char* spatial_fixture_path,
    const OraclarvaMobileOptions* repeat_options,
    const OraclarvaMobileSpatialOptions* spatial_options,
    OraclarvaMobileCore** output,
    char* error_message,
    size_t error_capacity);

ORACLARVA_MOBILE_API int oraclarva_mobile_advance_environment(
    OraclarvaMobileCore* core,
    const OraclarvaMobileIntegratedEnvironmentInput* input,
    char* error_message,
    size_t error_capacity);

ORACLARVA_MOBILE_API int oraclarva_mobile_read_environment_snapshot(
    const OraclarvaMobileCore* core,
    OraclarvaMobileEnvironmentSnapshot* output,
    char* error_message,
    size_t error_capacity);

#ifdef __cplusplus
}
#endif

#endif
