#ifndef ORACLARVA_MOBILE_CORE_H
#define ORACLARVA_MOBILE_CORE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32)
#if defined(ORACLARVA_MOBILE_BUILD)
#define ORACLARVA_MOBILE_API __declspec(dllexport)
#else
#define ORACLARVA_MOBILE_API __declspec(dllimport)
#endif
#elif defined(__GNUC__) || defined(__clang__)
#define ORACLARVA_MOBILE_API __attribute__((visibility("default")))
#else
#define ORACLARVA_MOBILE_API
#endif

#define ORACLARVA_MOBILE_ABI_VERSION 1u
#define ORACLARVA_MOBILE_NEURON_COUNT 164u
#define ORACLARVA_MOBILE_BODY_NODE_COUNT 13u
#define ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT 6u

/*
 * Host-tested source ABI for one frozen research approximation.
 *
 * A core is owned by one simulation thread. advance consumes a normalized
 * environment-contact intensity and performs one complete 1 ms causal step.
 * Snapshot and render reads copy or derive state and never advance or mutate
 * it. Lesion strings are declared interventions, not movement commands. Empty
 * or NULL lesion strings mean no intervention. All functions fail closed
 * through OraclarvaMobileStatus and an optional caller-owned error buffer.
 */

typedef struct OraclarvaMobileCore OraclarvaMobileCore;

typedef enum OraclarvaMobileStatus {
  ORACLARVA_MOBILE_OK = 0,
  ORACLARVA_MOBILE_INVALID_ARGUMENT = 1,
  ORACLARVA_MOBILE_LOAD_ERROR = 2,
  ORACLARVA_MOBILE_STATE_ERROR = 3,
  ORACLARVA_MOBILE_BUFFER_TOO_SMALL = 4
} OraclarvaMobileStatus;

typedef struct OraclarvaMobileOptions {
  const char* sensory_lesion_segment;
  const char* premotor_lesion_segment;
  const char* motor_lesion_segment;
  const char* fiber_lesion_segment;
} OraclarvaMobileOptions;

typedef struct OraclarvaMobileEnvironmentInput {
  double posterior_touch_intensity;
} OraclarvaMobileEnvironmentInput;

typedef struct OraclarvaMobileMetadata {
  uint32_t abi_version;
  uint32_t neuron_count;
  uint32_t body_node_count;
  uint32_t wave_segment_count;
  uint32_t maximum_steps;
  double fixed_dt_s;
  uint8_t release_validated;
  char fixture_schema[48];
  char model_id[64];
  char scientific_status[48];
  char config_sha256[65];
} OraclarvaMobileMetadata;

typedef struct OraclarvaMobileSnapshot {
  uint32_t step_index;
  double time_s;
  double displacement_x_um;
  double physics_nodes_um[ORACLARVA_MOBILE_BODY_NODE_COUNT * 3u];
  double segment_activation[ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT];
  double node_force_model_units[ORACLARVA_MOBILE_BODY_NODE_COUNT * 3u];
  uint32_t spike_counts[ORACLARVA_MOBILE_NEURON_COUNT];
  double first_spike_s[ORACLARVA_MOBILE_NEURON_COUNT];
  uint8_t last_step_spiked[ORACLARVA_MOBILE_NEURON_COUNT];
  uint32_t feedback_force_frames;
  uint8_t all_active_forces_traced;
  uint32_t complete_cycle_count;
  uint32_t physical_wave_cycle_count;
  double median_period_s;
  double median_stride_um;
  double median_wave_speed_segments_s;
  uint8_t trace_valid[ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT];
  uint32_t trace_sensor_neuron[ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT];
  uint32_t trace_premotor_neuron[ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT];
  uint32_t trace_motor_neuron[ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT];
  double trace_body_state_time_s[ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT];
  double trace_sensor_spike_time_s[ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT];
  double trace_premotor_spike_time_s[ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT];
  double trace_motor_spike_time_s[ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT];
} OraclarvaMobileSnapshot;

typedef struct OraclarvaMobileRenderVertex {
  float position_um[3];
  float normal[3];
  float activation;
} OraclarvaMobileRenderVertex;

typedef struct OraclarvaMobileTriangle {
  uint32_t vertex[3];
} OraclarvaMobileTriangle;

ORACLARVA_MOBILE_API int oraclarva_mobile_create(
    const char* fixture_path,
    const OraclarvaMobileOptions* options,
    OraclarvaMobileCore** output,
    char* error_message,
    size_t error_capacity);
ORACLARVA_MOBILE_API void oraclarva_mobile_destroy(OraclarvaMobileCore* core);
ORACLARVA_MOBILE_API int oraclarva_mobile_reset(
    OraclarvaMobileCore* core,
    char* error_message,
    size_t error_capacity);
ORACLARVA_MOBILE_API int oraclarva_mobile_advance(
    OraclarvaMobileCore* core,
    const OraclarvaMobileEnvironmentInput* input,
    char* error_message,
    size_t error_capacity);
ORACLARVA_MOBILE_API int oraclarva_mobile_read_metadata(
    const OraclarvaMobileCore* core,
    OraclarvaMobileMetadata* output,
    char* error_message,
    size_t error_capacity);
ORACLARVA_MOBILE_API int oraclarva_mobile_read_snapshot(
    const OraclarvaMobileCore* core,
    OraclarvaMobileSnapshot* output,
    char* error_message,
    size_t error_capacity);
ORACLARVA_MOBILE_API int oraclarva_mobile_render_counts(
    const OraclarvaMobileCore* core,
    uint32_t axial_samples_per_segment,
    uint32_t radial_samples,
    size_t* vertex_count,
    size_t* triangle_count,
    char* error_message,
    size_t error_capacity);
ORACLARVA_MOBILE_API int oraclarva_mobile_read_render_mesh(
    const OraclarvaMobileCore* core,
    uint32_t axial_samples_per_segment,
    uint32_t radial_samples,
    OraclarvaMobileRenderVertex* vertices,
    size_t vertex_capacity,
    OraclarvaMobileTriangle* triangles,
    size_t triangle_capacity,
    char* error_message,
    size_t error_capacity);

#ifdef __cplusplus
}
#endif

#endif
