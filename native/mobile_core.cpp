#include "mobile_core.h"
#include "mobile_environment.h"

#include "repeat_core.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using oraclarva::RepeatEnvironmentInput;
using oraclarva::RepeatFixture;
using oraclarva::RepeatOptions;
using oraclarva::RepeatSimulation;
using oraclarva::RepeatStateSnapshot;
using oraclarva::RepeatVec3;
using oraclarva::SpatialControllerOptions;
using oraclarva::SpatialFixture;
using oraclarva::SpatialLightField;

struct OraclarvaMobileCore {
  RepeatFixture fixture;
  SpatialFixture spatial_fixture;
  bool spatial_enabled = false;
  RepeatOptions options;
  SpatialControllerOptions spatial_options;
  RepeatSimulation simulation;
  RepeatVec3 initial_center;
  double initial_yaw_rad = 0.0;
  double initial_pitch_rad = 0.0;

  OraclarvaMobileCore(
      RepeatFixture fixture_value,
      RepeatOptions options_value)
      : fixture(std::move(fixture_value)),
        options(std::move(options_value)),
        simulation(fixture, options) {
    RecordInitial();
  }

  OraclarvaMobileCore(
      RepeatFixture fixture_value,
      SpatialFixture spatial_fixture_value,
      RepeatOptions options_value,
      SpatialControllerOptions spatial_options_value)
      : fixture(std::move(fixture_value)),
        spatial_fixture(std::move(spatial_fixture_value)),
        spatial_enabled(true),
        options(std::move(options_value)),
        spatial_options(std::move(spatial_options_value)),
        simulation(fixture, options, &spatial_fixture, spatial_options) {
    RecordInitial();
  }

  void RecordInitial() {
    const RepeatStateSnapshot snapshot = simulation.Snapshot();
    RepeatVec3 total{};
    for (const RepeatVec3& value : snapshot.nodes_m) {
      total.x += value.x;
      total.y += value.y;
      total.z += value.z;
    }
    const double inverse_count =
        1.0 / static_cast<double>(snapshot.nodes_m.size());
    initial_center = {
        total.x * inverse_count,
        total.y * inverse_count,
        total.z * inverse_count};
    const RepeatVec3& head = snapshot.nodes_m.front();
    const RepeatVec3& tail = snapshot.nodes_m.back();
    const RepeatVec3 axis{
        head.x - tail.x, head.y - tail.y, head.z - tail.z};
    initial_yaw_rad = std::atan2(axis.y, axis.x);
    initial_pitch_rad = std::atan2(
        axis.z, std::hypot(axis.x, axis.y));
  }
};

namespace {

constexpr double kPi = 3.14159265358979323846;

void SetError(char* output, std::size_t capacity, const std::string& value) {
  if (output == nullptr || capacity == 0) return;
  const std::size_t count = std::min(capacity - 1, value.size());
  std::memcpy(output, value.data(), count);
  output[count] = '\0';
}

void ClearError(char* output, std::size_t capacity) {
  if (output != nullptr && capacity > 0) output[0] = '\0';
}

void Require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}

void CopyText(char* output, std::size_t capacity, const std::string& value) {
  if (value.size() + 1 > capacity) {
    throw std::runtime_error("mobile metadata text exceeds ABI capacity");
  }
  std::memcpy(output, value.c_str(), value.size() + 1);
}

std::string OptionalText(const char* value) {
  return value == nullptr ? std::string{} : std::string(value);
}

RepeatOptions ConvertOptions(const OraclarvaMobileOptions* options) {
  RepeatOptions converted;
  converted.stimulate = false;
  if (options == nullptr) return converted;
  converted.sensory_lesion =
      OptionalText(options->sensory_lesion_segment);
  converted.premotor_lesion =
      OptionalText(options->premotor_lesion_segment);
  converted.motor_segment_lesion =
      OptionalText(options->motor_lesion_segment);
  converted.fiber_segment_lesion =
      OptionalText(options->fiber_lesion_segment);
  return converted;
}
SpatialControllerOptions ConvertSpatialOptions(
    const OraclarvaMobileSpatialOptions* options) {
  SpatialControllerOptions converted;
  if (options == nullptr) return converted;
  converted.sensory_lesion_channel =
      OptionalText(options->sensory_lesion_channel);
  converted.premotor_lesion_channel =
      OptionalText(options->premotor_lesion_channel);
  converted.motor_lesion_channel =
      OptionalText(options->motor_lesion_channel);
  converted.muscle_lesion_channel =
      OptionalText(options->muscle_lesion_channel);
  return converted;
}

SpatialLightField ConvertLight(const OraclarvaMobileLightField& input) {
  if (input.enabled > 1) {
    throw std::runtime_error("light enabled flag must be zero or one");
  }
  return {
      input.enabled == 1,
      {input.origin_m[0], input.origin_m[1], input.origin_m[2]},
      input.value_at_origin_w_m2,
      {input.gradient_w_m3[0], input.gradient_w_m3[1],
       input.gradient_w_m3[2]},
      input.temporal_rate_w_m2_s,
      input.lower_bound_w_m2,
      input.upper_bound_w_m2};
}

RepeatVec3 SnapshotCenter(const RepeatStateSnapshot& snapshot) {
  RepeatVec3 result{};
  for (const RepeatVec3& node : snapshot.nodes_m) {
    result.x += node.x;
    result.y += node.y;
    result.z += node.z;
  }
  const double inverse = 1.0 / static_cast<double>(snapshot.nodes_m.size());
  return {result.x * inverse, result.y * inverse, result.z * inverse};
}

double WrappedAngleChange(double current, double initial) {
  double difference = current - initial;
  while (difference > kPi) difference -= 2.0 * kPi;
  while (difference < -kPi) difference += 2.0 * kPi;
  return difference;
}

RepeatVec3 Add(const RepeatVec3& a, const RepeatVec3& b) {
  return {a.x + b.x, a.y + b.y, a.z + b.z};
}

RepeatVec3 Subtract(const RepeatVec3& a, const RepeatVec3& b) {
  return {a.x - b.x, a.y - b.y, a.z - b.z};
}

RepeatVec3 Multiply(const RepeatVec3& value, double scale) {
  return {value.x * scale, value.y * scale, value.z * scale};
}

double Norm(const RepeatVec3& value) {
  return std::sqrt(
      value.x * value.x + value.y * value.y + value.z * value.z);
}

RepeatVec3 Normalized(const RepeatVec3& value) {
  const double magnitude = Norm(value);
  if (magnitude == 0.0) return {1.0, 0.0, 0.0};
  return Multiply(value, 1.0 / magnitude);
}

RepeatVec3 Cross(const RepeatVec3& a, const RepeatVec3& b) {
  return {
      a.y * b.z - a.z * b.y,
      a.z * b.x - a.x * b.z,
      a.x * b.y - a.y * b.x};
}

RepeatVec3 CatmullRom(
    const std::vector<RepeatVec3>& points, double coordinate) {
  const std::size_t segment_count = points.size() - 1;
  const double bounded = std::min(
      static_cast<double>(segment_count), std::max(0.0, coordinate));
  const std::size_t segment = std::min(
      segment_count - 1,
      static_cast<std::size_t>(std::floor(bounded)));
  const double t = bounded - static_cast<double>(segment);
  const RepeatVec3& p0 = points[segment == 0 ? 0 : segment - 1];
  const RepeatVec3& p1 = points[segment];
  const RepeatVec3& p2 = points[segment + 1];
  const RepeatVec3& p3 = points[std::min(segment + 2, segment_count)];
  const double t2 = t * t;
  const double t3 = t2 * t;
  return Multiply(
      Add(
          Add(
              Multiply(p1, 2.0),
              Multiply(Subtract(p2, p0), t)),
          Add(
              Multiply(
                  Add(
                      Subtract(Multiply(p0, 2.0), Multiply(p1, 5.0)),
                      Subtract(Multiply(p2, 4.0), p3)),
                  t2),
              Multiply(
                  Add(
                      Subtract(Multiply(p1, 3.0), p0),
                      Subtract(p3, Multiply(p2, 3.0))),
                  t3))),
      0.5);
}

double NodeProfile(
    const RepeatFixture& fixture, std::size_t node, bool width) {
  double result = 0.0;
  if (node > 0) {
    const auto& segment = fixture.body_segments[node - 1];
    result = std::max(result, width ? segment.width_m : segment.height_m);
  }
  if (node < fixture.body_segments.size()) {
    const auto& segment = fixture.body_segments[node];
    result = std::max(result, width ? segment.width_m : segment.height_m);
  }
  return result;
}

double InterpolatedProfile(
    const RepeatFixture& fixture, double coordinate, bool width) {
  const std::size_t segment_count = fixture.body_segments.size();
  const double bounded = std::min(
      static_cast<double>(segment_count), std::max(0.0, coordinate));
  const std::size_t segment = std::min(
      segment_count - 1,
      static_cast<std::size_t>(std::floor(bounded)));
  const double t = bounded - static_cast<double>(segment);
  return NodeProfile(fixture, segment, width) * (1.0 - t)
      + NodeProfile(fixture, segment + 1, width) * t;
}

double RenderActivation(
    const OraclarvaMobileCore& core,
    const RepeatStateSnapshot& snapshot,
    double coordinate) {
  const std::size_t body_segment = std::min(
      core.fixture.body_segments.size() - 1,
      static_cast<std::size_t>(std::floor(std::max(0.0, coordinate))));
  for (std::size_t index = 0;
       index < core.fixture.wave_segments.size(); ++index) {
    if (core.fixture.wave_segments[index].body_index == body_segment) {
      return snapshot.segment_activation[index];
    }
  }
  return 0.0;
}

struct RenderMesh {
  std::vector<OraclarvaMobileRenderVertex> vertices;
  std::vector<OraclarvaMobileTriangle> triangles;
};

void ValidateRenderSampling(std::uint32_t axial, std::uint32_t radial) {
  if (axial < 1 || axial > 8 || radial < 3 || radial > 32) {
    throw std::runtime_error(
        "render sampling must be axial [1,8] and radial [3,32]");
  }
}

std::pair<std::size_t, std::size_t> RenderCounts(
    const RepeatFixture& fixture,
    std::uint32_t axial,
    std::uint32_t radial) {
  ValidateRenderSampling(axial, radial);
  const std::size_t rings =
      fixture.body_segments.size() * axial + 1;
  const std::size_t vertices = rings * radial + 2;
  const std::size_t triangles =
      (rings - 1) * radial * 2 + radial * 2;
  return {vertices, triangles};
}

OraclarvaMobileRenderVertex Vertex(
    const RepeatVec3& position_m,
    const RepeatVec3& normal,
    double activation) {
  OraclarvaMobileRenderVertex result{};
  result.position_um[0] = static_cast<float>(position_m.x * 1e6);
  result.position_um[1] = static_cast<float>(position_m.y * 1e6);
  result.position_um[2] = static_cast<float>(position_m.z * 1e6);
  result.normal[0] = static_cast<float>(normal.x);
  result.normal[1] = static_cast<float>(normal.y);
  result.normal[2] = static_cast<float>(normal.z);
  result.activation = static_cast<float>(activation);
  return result;
}

RenderMesh BuildRenderMesh(
    const OraclarvaMobileCore& core,
    std::uint32_t axial,
    std::uint32_t radial) {
  const RepeatStateSnapshot snapshot = core.simulation.Snapshot();
  Require(
      snapshot.nodes_m.size() == ORACLARVA_MOBILE_BODY_NODE_COUNT,
      "mobile render node count mismatch");
  const auto counts = RenderCounts(core.fixture, axial, radial);
  RenderMesh mesh;
  mesh.vertices.reserve(counts.first);
  mesh.triangles.reserve(counts.second);
  const std::size_t ring_count =
      core.fixture.body_segments.size() * axial + 1;
  for (std::size_t ring = 0; ring < ring_count; ++ring) {
    const double coordinate =
        static_cast<double>(ring) / static_cast<double>(axial);
    const RepeatVec3 center = CatmullRom(snapshot.nodes_m, coordinate);
    const double before = std::max(0.0, coordinate - 1e-3);
    const double after = std::min(
        static_cast<double>(core.fixture.body_segments.size()),
        coordinate + 1e-3);
    const RepeatVec3 tangent = Normalized(Subtract(
        CatmullRom(snapshot.nodes_m, after),
        CatmullRom(snapshot.nodes_m, before)));
    RepeatVec3 lateral = Cross({0.0, 0.0, 1.0}, tangent);
    if (Norm(lateral) < 1e-12) lateral = {0.0, 1.0, 0.0};
    lateral = Normalized(lateral);
    const RepeatVec3 dorsal = Normalized(Cross(tangent, lateral));
    const double width = InterpolatedProfile(core.fixture, coordinate, true);
    const double height = InterpolatedProfile(core.fixture, coordinate, false);
    const double activation = RenderActivation(core, snapshot, coordinate);
    for (std::uint32_t sample = 0; sample < radial; ++sample) {
      const double theta =
          2.0 * kPi * static_cast<double>(sample)
          / static_cast<double>(radial);
      const double cosine = std::cos(theta);
      const double sine = std::sin(theta);
      const RepeatVec3 offset = Add(
          Multiply(lateral, 0.5 * width * cosine),
          Multiply(dorsal, 0.5 * height * sine));
      const RepeatVec3 normal = Normalized(Add(
          Multiply(lateral, cosine / std::max(width, 1e-18)),
          Multiply(dorsal, sine / std::max(height, 1e-18))));
      mesh.vertices.push_back(Vertex(
          Add(center, offset), normal, activation));
    }
  }
  for (std::size_t ring = 0; ring + 1 < ring_count; ++ring) {
    for (std::uint32_t sample = 0; sample < radial; ++sample) {
      const std::uint32_t next = (sample + 1) % radial;
      const std::uint32_t a = static_cast<std::uint32_t>(ring * radial + sample);
      const std::uint32_t b = static_cast<std::uint32_t>(ring * radial + next);
      const std::uint32_t c = static_cast<std::uint32_t>((ring + 1) * radial + sample);
      const std::uint32_t d = static_cast<std::uint32_t>((ring + 1) * radial + next);
      mesh.triangles.push_back({{a, c, b}});
      mesh.triangles.push_back({{b, c, d}});
    }
  }
  const RepeatVec3 start_tangent = Normalized(Subtract(
      CatmullRom(snapshot.nodes_m, 1e-3), snapshot.nodes_m.front()));
  const RepeatVec3 end_tangent = Normalized(Subtract(
      snapshot.nodes_m.back(),
      CatmullRom(
          snapshot.nodes_m,
          static_cast<double>(core.fixture.body_segments.size()) - 1e-3)));
  const double start_height = NodeProfile(core.fixture, 0, false);
  const double end_height = NodeProfile(
      core.fixture, core.fixture.body_segments.size(), false);
  const std::uint32_t start_cap = static_cast<std::uint32_t>(mesh.vertices.size());
  mesh.vertices.push_back(Vertex(
      Subtract(snapshot.nodes_m.front(), Multiply(start_tangent, 0.25 * start_height)),
      Multiply(start_tangent, -1.0), 0.0));
  const std::uint32_t end_cap = static_cast<std::uint32_t>(mesh.vertices.size());
  mesh.vertices.push_back(Vertex(
      Add(snapshot.nodes_m.back(), Multiply(end_tangent, 0.25 * end_height)),
      end_tangent, 0.0));
  const std::uint32_t last_ring =
      static_cast<std::uint32_t>((ring_count - 1) * radial);
  for (std::uint32_t sample = 0; sample < radial; ++sample) {
    const std::uint32_t next = (sample + 1) % radial;
    mesh.triangles.push_back({{start_cap, next, sample}});
    mesh.triangles.push_back({{
        end_cap, last_ring + sample, last_ring + next}});
  }
  Require(mesh.vertices.size() == counts.first, "render vertex count mismatch");
  Require(mesh.triangles.size() == counts.second, "render triangle count mismatch");
  return mesh;
}

}  // namespace

extern "C" {

int oraclarva_mobile_create(
    const char* fixture_path,
    const OraclarvaMobileOptions* options,
    OraclarvaMobileCore** output,
    char* error_message,
    std::size_t error_capacity) {
  ClearError(error_message, error_capacity);
  if (output == nullptr || fixture_path == nullptr || fixture_path[0] == '\0') {
    SetError(error_message, error_capacity, "fixture path and output are required");
    return ORACLARVA_MOBILE_INVALID_ARGUMENT;
  }
  *output = nullptr;
  try {
    *output = new OraclarvaMobileCore(
        oraclarva::LoadRepeatFixture(fixture_path),
        ConvertOptions(options));
    return ORACLARVA_MOBILE_OK;
  } catch (const std::exception& error) {
    SetError(error_message, error_capacity, error.what());
    return ORACLARVA_MOBILE_LOAD_ERROR;
  }
}
int oraclarva_mobile_create_spatial(
    const char* repeat_fixture_path,
    const char* spatial_fixture_path,
    const OraclarvaMobileOptions* repeat_options,
    const OraclarvaMobileSpatialOptions* spatial_options,
    OraclarvaMobileCore** output,
    char* error_message,
    std::size_t error_capacity) {
  ClearError(error_message, error_capacity);
  if (output == nullptr
      || repeat_fixture_path == nullptr || repeat_fixture_path[0] == '\0'
      || spatial_fixture_path == nullptr || spatial_fixture_path[0] == '\0') {
    SetError(
        error_message, error_capacity,
        "repeat fixture, spatial fixture, and output are required");
    return ORACLARVA_MOBILE_INVALID_ARGUMENT;
  }
  *output = nullptr;
  try {
    *output = new OraclarvaMobileCore(
        oraclarva::LoadRepeatFixture(repeat_fixture_path),
        oraclarva::LoadSpatialFixture(spatial_fixture_path),
        ConvertOptions(repeat_options),
        ConvertSpatialOptions(spatial_options));
    return ORACLARVA_MOBILE_OK;
  } catch (const std::exception& error) {
    SetError(error_message, error_capacity, error.what());
    return ORACLARVA_MOBILE_LOAD_ERROR;
  }
}

void oraclarva_mobile_destroy(OraclarvaMobileCore* core) {
  delete core;
}

int oraclarva_mobile_reset(
    OraclarvaMobileCore* core,
    char* error_message,
    std::size_t error_capacity) {
  ClearError(error_message, error_capacity);
  if (core == nullptr) {
    SetError(error_message, error_capacity, "mobile core is required");
    return ORACLARVA_MOBILE_INVALID_ARGUMENT;
  }
  try {
    core->simulation.Reset();
    return ORACLARVA_MOBILE_OK;
  } catch (const std::exception& error) {
    SetError(error_message, error_capacity, error.what());
    return ORACLARVA_MOBILE_STATE_ERROR;
  }
}

int oraclarva_mobile_advance(
    OraclarvaMobileCore* core,
    const OraclarvaMobileEnvironmentInput* input,
    char* error_message,
    std::size_t error_capacity) {
  ClearError(error_message, error_capacity);
  if (core == nullptr || input == nullptr) {
    SetError(error_message, error_capacity, "mobile core and environment input are required");
    return ORACLARVA_MOBILE_INVALID_ARGUMENT;
  }
  try {
    core->simulation.Advance(
        RepeatEnvironmentInput{input->posterior_touch_intensity, {}});
    return ORACLARVA_MOBILE_OK;
  } catch (const std::exception& error) {
    SetError(error_message, error_capacity, error.what());
    return ORACLARVA_MOBILE_STATE_ERROR;
  }
}
int oraclarva_mobile_advance_environment(
    OraclarvaMobileCore* core,
    const OraclarvaMobileIntegratedEnvironmentInput* input,
    char* error_message,
    std::size_t error_capacity) {
  ClearError(error_message, error_capacity);
  if (core == nullptr || input == nullptr) {
    SetError(
        error_message, error_capacity,
        "spatial mobile core and integrated environment input are required");
    return ORACLARVA_MOBILE_INVALID_ARGUMENT;
  }
  if (!core->spatial_enabled) {
    SetError(
        error_message, error_capacity,
        "core was not created with a spatial fixture");
    return ORACLARVA_MOBILE_STATE_ERROR;
  }
  try {
    core->simulation.Advance(RepeatEnvironmentInput{
        input->posterior_touch_intensity, ConvertLight(input->light)});
    return ORACLARVA_MOBILE_OK;
  } catch (const std::exception& error) {
    SetError(error_message, error_capacity, error.what());
    return ORACLARVA_MOBILE_STATE_ERROR;
  }
}

int oraclarva_mobile_read_metadata(
    const OraclarvaMobileCore* core,
    OraclarvaMobileMetadata* output,
    char* error_message,
    std::size_t error_capacity) {
  ClearError(error_message, error_capacity);
  if (core == nullptr || output == nullptr) {
    SetError(error_message, error_capacity, "mobile core and metadata output are required");
    return ORACLARVA_MOBILE_INVALID_ARGUMENT;
  }
  try {
    *output = OraclarvaMobileMetadata{};
    output->abi_version = ORACLARVA_MOBILE_ABI_VERSION;
    output->neuron_count = static_cast<std::uint32_t>(core->fixture.neuron_count);
    output->body_node_count = static_cast<std::uint32_t>(
        core->fixture.body_segments.size() + 1);
    output->wave_segment_count = static_cast<std::uint32_t>(
        core->fixture.wave_segments.size());
    output->maximum_steps = static_cast<std::uint32_t>(core->fixture.steps);
    output->fixed_dt_s = core->fixture.lif_config.dt_s;
    output->release_validated = core->fixture.release_validated ? 1 : 0;
    CopyText(output->fixture_schema, sizeof(output->fixture_schema), core->fixture.schema);
    CopyText(output->model_id, sizeof(output->model_id), core->fixture.model_id);
    CopyText(output->scientific_status, sizeof(output->scientific_status), core->fixture.status);
    CopyText(output->config_sha256, sizeof(output->config_sha256), core->fixture.config_sha256);
    return ORACLARVA_MOBILE_OK;
  } catch (const std::exception& error) {
    SetError(error_message, error_capacity, error.what());
    return ORACLARVA_MOBILE_STATE_ERROR;
  }
}

int oraclarva_mobile_read_snapshot(
    const OraclarvaMobileCore* core,
    OraclarvaMobileSnapshot* output,
    char* error_message,
    std::size_t error_capacity) {
  ClearError(error_message, error_capacity);
  if (core == nullptr || output == nullptr) {
    SetError(error_message, error_capacity, "mobile core and snapshot output are required");
    return ORACLARVA_MOBILE_INVALID_ARGUMENT;
  }
  try {
    const RepeatStateSnapshot snapshot = core->simulation.Snapshot();
    Require(snapshot.nodes_m.size() == ORACLARVA_MOBILE_BODY_NODE_COUNT, "mobile node count mismatch");
    Require(snapshot.segment_activation.size() == ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT, "mobile activation count mismatch");
    Require(snapshot.node_force_model_units.size() == ORACLARVA_MOBILE_BODY_NODE_COUNT, "mobile force count mismatch");
    Require(snapshot.spike_counts.size() == ORACLARVA_MOBILE_NEURON_COUNT, "mobile spike count mismatch");
    Require(snapshot.first_spike_s.size() == ORACLARVA_MOBILE_NEURON_COUNT, "mobile first-spike count mismatch");
    *output = OraclarvaMobileSnapshot{};
    output->step_index = static_cast<std::uint32_t>(snapshot.step_index);
    output->time_s = snapshot.time_s;
    output->displacement_x_um = snapshot.displacement_x_um;
    for (std::size_t index = 0; index < snapshot.nodes_m.size(); ++index) {
      output->physics_nodes_um[index * 3] = snapshot.nodes_m[index].x * 1e6;
      output->physics_nodes_um[index * 3 + 1] = snapshot.nodes_m[index].y * 1e6;
      output->physics_nodes_um[index * 3 + 2] = snapshot.nodes_m[index].z * 1e6;
      output->node_force_model_units[index * 3] = snapshot.node_force_model_units[index].x;
      output->node_force_model_units[index * 3 + 1] = snapshot.node_force_model_units[index].y;
      output->node_force_model_units[index * 3 + 2] = snapshot.node_force_model_units[index].z;
    }
    for (std::size_t index = 0; index < snapshot.segment_activation.size(); ++index) {
      output->segment_activation[index] = snapshot.segment_activation[index];
    }
    for (std::size_t index = 0; index < snapshot.spike_counts.size(); ++index) {
      output->spike_counts[index] = static_cast<std::uint32_t>(snapshot.spike_counts[index]);
      output->first_spike_s[index] = snapshot.first_spike_s[index];
    }
    for (const std::size_t index : snapshot.last_step_spikes) {
      output->last_step_spiked[index] = 1;
    }
    output->feedback_force_frames = static_cast<std::uint32_t>(snapshot.feedback_force_frames);
    output->all_active_forces_traced = snapshot.all_active_forces_traced ? 1 : 0;
    output->complete_cycle_count = static_cast<std::uint32_t>(snapshot.cycle_metrics.complete_cycle_count);
    output->physical_wave_cycle_count = static_cast<std::uint32_t>(snapshot.cycle_metrics.physical_wave_cycle_count);
    output->median_period_s = snapshot.cycle_metrics.median_period_s;
    output->median_stride_um = snapshot.cycle_metrics.median_stride_um;
    output->median_wave_speed_segments_s = snapshot.cycle_metrics.median_wave_speed_segments_s;
    for (std::size_t index = 0; index < snapshot.trace_examples.size(); ++index) {
      const auto& trace = snapshot.trace_examples[index];
      output->trace_valid[index] = trace.valid ? 1 : 0;
      output->trace_sensor_neuron[index] = static_cast<std::uint32_t>(trace.sensor_neuron);
      output->trace_premotor_neuron[index] = static_cast<std::uint32_t>(trace.premotor_neuron);
      output->trace_motor_neuron[index] = static_cast<std::uint32_t>(trace.motor_neuron);
      output->trace_body_state_time_s[index] = trace.body_state_time_s;
      output->trace_sensor_spike_time_s[index] = trace.sensor_spike_time_s;
      output->trace_premotor_spike_time_s[index] = trace.premotor_spike_time_s;
      output->trace_motor_spike_time_s[index] = trace.motor_spike_time_s;
    }
    return ORACLARVA_MOBILE_OK;
  } catch (const std::exception& error) {
    SetError(error_message, error_capacity, error.what());
    return ORACLARVA_MOBILE_STATE_ERROR;
  }
}
int oraclarva_mobile_read_environment_snapshot(
    const OraclarvaMobileCore* core,
    OraclarvaMobileEnvironmentSnapshot* output,
    char* error_message,
    std::size_t error_capacity) {
  ClearError(error_message, error_capacity);
  if (core == nullptr || output == nullptr) {
    SetError(
        error_message, error_capacity,
        "spatial mobile core and environment snapshot are required");
    return ORACLARVA_MOBILE_INVALID_ARGUMENT;
  }
  if (!core->spatial_enabled) {
    SetError(
        error_message, error_capacity,
        "core was not created with a spatial fixture");
    return ORACLARVA_MOBILE_STATE_ERROR;
  }
  try {
    const RepeatStateSnapshot snapshot = core->simulation.Snapshot();
    Require(
        snapshot.spatial.spike_counts.size()
            == ORACLARVA_MOBILE_SPATIAL_NEURON_COUNT,
        "spatial snapshot neuron count mismatch");
    Require(
        snapshot.nodes_m.size() == ORACLARVA_MOBILE_BODY_NODE_COUNT
            && snapshot.spatial.yaw_activation.size()
                == ORACLARVA_MOBILE_BODY_SEGMENT_COUNT
            && snapshot.spatial.pitch_activation.size()
                == ORACLARVA_MOBILE_BODY_SEGMENT_COUNT,
        "spatial snapshot body count mismatch");
    *output = OraclarvaMobileEnvironmentSnapshot{};
    output->extension_abi_version =
        ORACLARVA_MOBILE_ENVIRONMENT_ABI_VERSION;
    output->step_index = static_cast<std::uint32_t>(snapshot.step_index);
    output->time_s = snapshot.time_s;
    const RepeatVec3 center = SnapshotCenter(snapshot);
    output->displacement_um[0] = (center.x - core->initial_center.x) * 1e6;
    output->displacement_um[1] = (center.y - core->initial_center.y) * 1e6;
    output->displacement_um[2] = (center.z - core->initial_center.z) * 1e6;
    const RepeatVec3& head = snapshot.nodes_m.front();
    const RepeatVec3& tail = snapshot.nodes_m.back();
    const RepeatVec3 axis{
        head.x - tail.x, head.y - tail.y, head.z - tail.z};
    const double yaw = std::atan2(axis.y, axis.x);
    const double pitch = std::atan2(axis.z, std::hypot(axis.x, axis.y));
    output->heading_change_deg =
        WrappedAngleChange(yaw, core->initial_yaw_rad) * 180.0 / kPi;
    output->head_pitch_change_deg =
        WrappedAngleChange(pitch, core->initial_pitch_rad) * 180.0 / kPi;
    for (std::size_t node = 0;
         node < ORACLARVA_MOBILE_BODY_NODE_COUNT; ++node) {
      output->physics_nodes_um[node * 3] = snapshot.nodes_m[node].x * 1e6;
      output->physics_nodes_um[node * 3 + 1] = snapshot.nodes_m[node].y * 1e6;
      output->physics_nodes_um[node * 3 + 2] = snapshot.nodes_m[node].z * 1e6;
    }
    for (std::size_t segment = 0;
         segment < ORACLARVA_MOBILE_BODY_SEGMENT_COUNT; ++segment) {
      output->segment_yaw_activation[segment * 2] =
          snapshot.spatial.yaw_activation[segment][0];
      output->segment_yaw_activation[segment * 2 + 1] =
          snapshot.spatial.yaw_activation[segment][1];
      output->segment_pitch_activation[segment * 2] =
          snapshot.spatial.pitch_activation[segment][0];
      output->segment_pitch_activation[segment * 2 + 1] =
          snapshot.spatial.pitch_activation[segment][1];
    }
    for (std::size_t channel = 0;
         channel < ORACLARVA_MOBILE_SPATIAL_CHANNEL_COUNT; ++channel) {
      output->raw_light_w_m2[channel] =
          snapshot.spatial.raw_light_w_m2[channel];
      output->adapted_light_w_m2[channel] =
          snapshot.spatial.adapted_light_w_m2[channel];
      output->light_drive[channel] = snapshot.spatial.light_drive[channel];
      output->receptor_current[channel] =
          snapshot.spatial.receptor_current[channel];
      output->channel_activation[channel] =
          snapshot.spatial.channel_activation[channel];
    }
    for (std::size_t neuron = 0;
         neuron < ORACLARVA_MOBILE_SPATIAL_NEURON_COUNT; ++neuron) {
      output->spatial_spike_counts[neuron] =
          static_cast<std::uint32_t>(snapshot.spatial.spike_counts[neuron]);
    }
    for (const std::size_t neuron : snapshot.spatial.last_step_spikes) {
      output->spatial_last_step_spiked[neuron] = 1;
    }
    output->release_validated = 0;
    CopyText(
        output->spatial_fixture_schema,
        sizeof(output->spatial_fixture_schema),
        core->spatial_fixture.schema);
    CopyText(
        output->spatial_model_id,
        sizeof(output->spatial_model_id),
        core->spatial_fixture.model_id);
    return ORACLARVA_MOBILE_OK;
  } catch (const std::exception& error) {
    SetError(error_message, error_capacity, error.what());
    return ORACLARVA_MOBILE_STATE_ERROR;
  }
}

int oraclarva_mobile_render_counts(
    const OraclarvaMobileCore* core,
    std::uint32_t axial_samples_per_segment,
    std::uint32_t radial_samples,
    std::size_t* vertex_count,
    std::size_t* triangle_count,
    char* error_message,
    std::size_t error_capacity) {
  ClearError(error_message, error_capacity);
  if (core == nullptr || vertex_count == nullptr || triangle_count == nullptr) {
    SetError(error_message, error_capacity, "mobile core and render counts are required");
    return ORACLARVA_MOBILE_INVALID_ARGUMENT;
  }
  try {
    const auto counts = RenderCounts(core->fixture, axial_samples_per_segment, radial_samples);
    *vertex_count = counts.first;
    *triangle_count = counts.second;
    return ORACLARVA_MOBILE_OK;
  } catch (const std::exception& error) {
    SetError(error_message, error_capacity, error.what());
    return ORACLARVA_MOBILE_STATE_ERROR;
  }
}

int oraclarva_mobile_read_render_mesh(
    const OraclarvaMobileCore* core,
    std::uint32_t axial_samples_per_segment,
    std::uint32_t radial_samples,
    OraclarvaMobileRenderVertex* vertices,
    std::size_t vertex_capacity,
    OraclarvaMobileTriangle* triangles,
    std::size_t triangle_capacity,
    char* error_message,
    std::size_t error_capacity) {
  ClearError(error_message, error_capacity);
  if (core == nullptr || vertices == nullptr || triangles == nullptr) {
    SetError(error_message, error_capacity, "mobile core and render buffers are required");
    return ORACLARVA_MOBILE_INVALID_ARGUMENT;
  }
  try {
    const auto counts = RenderCounts(core->fixture, axial_samples_per_segment, radial_samples);
    if (vertex_capacity < counts.first || triangle_capacity < counts.second) {
      SetError(error_message, error_capacity, "render buffer is too small");
      return ORACLARVA_MOBILE_BUFFER_TOO_SMALL;
    }
    const RenderMesh mesh = BuildRenderMesh(
        *core, axial_samples_per_segment, radial_samples);
    std::copy(mesh.vertices.begin(), mesh.vertices.end(), vertices);
    std::copy(mesh.triangles.begin(), mesh.triangles.end(), triangles);
    return ORACLARVA_MOBILE_OK;
  } catch (const std::exception& error) {
    SetError(error_message, error_capacity, error.what());
    return ORACLARVA_MOBILE_STATE_ERROR;
  }
}

}  // extern "C"
