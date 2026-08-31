#include "mobile_core.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#if defined(__linux__)
#include <sys/resource.h>
#endif

namespace {

struct CoreOwner {
  OraclarvaMobileCore* value = nullptr;
  ~CoreOwner() { oraclarva_mobile_destroy(value); }
};

struct RunResult {
  std::uint64_t digest = 1469598103934665603ULL;
  OraclarvaMobileSnapshot initial{};
  OraclarvaMobileSnapshot final{};
  double wall_s = 0.0;
};

std::string ErrorText(const char* value) {
  return value[0] == '\0' ? std::string("unknown mobile error") : value;
}

void Check(int status, const char* error) {
  if (status != ORACLARVA_MOBILE_OK) {
    throw std::runtime_error(ErrorText(error));
  }
}

void HashByte(std::uint64_t& hash, std::uint8_t value) {
  hash ^= value;
  hash *= 1099511628211ULL;
}

void HashU32(std::uint64_t& hash, std::uint32_t value) {
  for (int shift = 0; shift < 32; shift += 8) {
    HashByte(hash, static_cast<std::uint8_t>((value >> shift) & 0xff));
  }
}

void HashU64(std::uint64_t& hash, std::uint64_t value) {
  for (int shift = 0; shift < 64; shift += 8) {
    HashByte(hash, static_cast<std::uint8_t>((value >> shift) & 0xff));
  }
}

void HashDouble(std::uint64_t& hash, double value) {
  std::uint64_t bits = 0;
  static_assert(sizeof(bits) == sizeof(value));
  std::memcpy(&bits, &value, sizeof(bits));
  HashU64(hash, bits);
}

void HashFloat(std::uint64_t& hash, float value) {
  std::uint32_t bits = 0;
  static_assert(sizeof(bits) == sizeof(value));
  std::memcpy(&bits, &value, sizeof(bits));
  HashU32(hash, bits);
}

std::uint64_t SnapshotHash(const OraclarvaMobileSnapshot& snapshot) {
  std::uint64_t hash = 1469598103934665603ULL;
  HashU32(hash, snapshot.step_index);
  HashDouble(hash, snapshot.time_s);
  HashDouble(hash, snapshot.displacement_x_um);
  for (double value : snapshot.physics_nodes_um) HashDouble(hash, value);
  for (double value : snapshot.segment_activation) HashDouble(hash, value);
  for (double value : snapshot.node_force_model_units) HashDouble(hash, value);
  for (std::uint32_t value : snapshot.spike_counts) HashU32(hash, value);
  for (double value : snapshot.first_spike_s) HashDouble(hash, value);
  for (std::uint8_t value : snapshot.last_step_spiked) HashByte(hash, value);
  HashU32(hash, snapshot.feedback_force_frames);
  HashByte(hash, snapshot.all_active_forces_traced);
  HashU32(hash, snapshot.complete_cycle_count);
  HashU32(hash, snapshot.physical_wave_cycle_count);
  HashDouble(hash, snapshot.median_period_s);
  HashDouble(hash, snapshot.median_stride_um);
  HashDouble(hash, snapshot.median_wave_speed_segments_s);
  for (std::uint8_t value : snapshot.trace_valid) HashByte(hash, value);
  for (std::uint32_t value : snapshot.trace_sensor_neuron) HashU32(hash, value);
  for (std::uint32_t value : snapshot.trace_premotor_neuron) HashU32(hash, value);
  for (std::uint32_t value : snapshot.trace_motor_neuron) HashU32(hash, value);
  for (double value : snapshot.trace_body_state_time_s) HashDouble(hash, value);
  for (double value : snapshot.trace_sensor_spike_time_s) HashDouble(hash, value);
  for (double value : snapshot.trace_premotor_spike_time_s) HashDouble(hash, value);
  for (double value : snapshot.trace_motor_spike_time_s) HashDouble(hash, value);
  return hash;
}

void MixSnapshot(std::uint64_t& digest, const OraclarvaMobileSnapshot& value) {
  HashU64(digest, SnapshotHash(value));
}

void MixMesh(
    std::uint64_t& digest,
    const std::vector<OraclarvaMobileRenderVertex>& vertices,
    const std::vector<OraclarvaMobileTriangle>& triangles) {
  HashU64(digest, vertices.size());
  HashU64(digest, triangles.size());
  for (const auto& vertex : vertices) {
    for (float value : vertex.position_um) HashFloat(digest, value);
    for (float value : vertex.normal) HashFloat(digest, value);
    HashFloat(digest, vertex.activation);
  }
  for (const auto& triangle : triangles) {
    for (std::uint32_t value : triangle.vertex) HashU32(digest, value);
  }
}

OraclarvaMobileSnapshot ReadSnapshot(OraclarvaMobileCore* core) {
  OraclarvaMobileSnapshot result{};
  char error[256]{};
  Check(oraclarva_mobile_read_snapshot(
      core, &result, error, sizeof(error)), error);
  return result;
}

void ReadMesh(
    OraclarvaMobileCore* core,
    std::uint32_t axial,
    std::uint32_t radial,
    std::vector<OraclarvaMobileRenderVertex>& vertices,
    std::vector<OraclarvaMobileTriangle>& triangles) {
  char error[256]{};
  std::size_t vertex_count = 0;
  std::size_t triangle_count = 0;
  Check(oraclarva_mobile_render_counts(
      core, axial, radial, &vertex_count, &triangle_count,
      error, sizeof(error)), error);
  vertices.resize(vertex_count);
  triangles.resize(triangle_count);
  Check(oraclarva_mobile_read_render_mesh(
      core, axial, radial,
      vertices.data(), vertices.size(),
      triangles.data(), triangles.size(),
      error, sizeof(error)), error);
}

void PrintVector3(const double* values, std::size_t count) {
  for (std::size_t index = 0; index < count; ++index) {
    if (index) std::cout << ';';
    std::cout << values[index * 3] << ','
              << values[index * 3 + 1] << ','
              << values[index * 3 + 2];
  }
}

void PrintFrame(
    int index,
    const OraclarvaMobileSnapshot& snapshot,
    const std::vector<OraclarvaMobileRenderVertex>& vertices,
    bool emit_mesh_positions) {
  std::cout << "frame\t" << index << '\t' << snapshot.time_s << '\t';
  PrintVector3(
      snapshot.physics_nodes_um, ORACLARVA_MOBILE_BODY_NODE_COUNT);
  std::cout << '\t';
  for (std::size_t segment = 0;
       segment < ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT; ++segment) {
    if (segment) std::cout << ',';
    std::cout << snapshot.segment_activation[segment];
  }
  std::cout << '\t';
  PrintVector3(
      snapshot.node_force_model_units,
      ORACLARVA_MOBILE_BODY_NODE_COUNT);
  std::cout << '\t';
  if (emit_mesh_positions) {
    for (std::size_t index_value = 0;
         index_value < vertices.size(); ++index_value) {
      if (index_value) std::cout << ';';
      const auto& vertex = vertices[index_value];
      std::cout << vertex.position_um[0] << ','
                << vertex.position_um[1] << ','
                << vertex.position_um[2] << ','
                << vertex.activation;
    }
  }
  std::cout << '\n';
}

RunResult RunSchedule(
    OraclarvaMobileCore* core,
    int steps,
    int touch_steps,
    double touch_intensity,
    int sample_stride,
    bool emit_frames,
    bool emit_mesh_positions,
    std::uint32_t axial,
    std::uint32_t radial) {
  char error[256]{};
  Check(oraclarva_mobile_reset(core, error, sizeof(error)), error);
  RunResult result;
  result.initial = ReadSnapshot(core);
  int frame_index = 0;
  auto capture = [&](const OraclarvaMobileSnapshot& snapshot) {
    std::vector<OraclarvaMobileRenderVertex> vertices;
    std::vector<OraclarvaMobileTriangle> triangles;
    const std::uint64_t before = SnapshotHash(snapshot);
    ReadMesh(core, axial, radial, vertices, triangles);
    const OraclarvaMobileSnapshot after = ReadSnapshot(core);
    if (before != SnapshotHash(after)) {
      throw std::runtime_error("read-only render projection mutated simulation state");
    }
    MixSnapshot(result.digest, snapshot);
    MixMesh(result.digest, vertices, triangles);
    if (emit_frames) {
      PrintFrame(frame_index, snapshot, vertices, emit_mesh_positions);
    }
    ++frame_index;
  };
  capture(result.initial);
  const auto start = std::chrono::steady_clock::now();
  for (int step = 0; step < steps; ++step) {
    const OraclarvaMobileEnvironmentInput input{
        step < touch_steps ? touch_intensity : 0.0};
    Check(oraclarva_mobile_advance(
        core, &input, error, sizeof(error)), error);
    if ((step + 1) % sample_stride == 0 || step + 1 == steps) {
      capture(ReadSnapshot(core));
    }
  }
  const auto end = std::chrono::steady_clock::now();
  result.wall_s = std::chrono::duration<double>(end - start).count();
  result.final = ReadSnapshot(core);
  return result;
}

void PrintMaybe(double value) {
  if (std::isnan(value)) std::cout << '-';
  else std::cout << value;
}

void PrintSummary(const RunResult& result) {
  const auto& snapshot = result.final;
  std::cout << "summary\t" << snapshot.step_index << '\t'
            << std::hex << std::setw(16) << std::setfill('0')
            << result.digest << std::dec << std::setfill(' ') << '\t'
            << snapshot.displacement_x_um << '\t'
            << snapshot.feedback_force_frames << '\t'
            << (snapshot.all_active_forces_traced ? "true" : "false")
            << '\t' << snapshot.complete_cycle_count
            << '\t' << snapshot.physical_wave_cycle_count << '\t';
  PrintMaybe(snapshot.median_period_s);
  std::cout << '\t';
  PrintMaybe(snapshot.median_stride_um);
  std::cout << '\t';
  PrintMaybe(snapshot.median_wave_speed_segments_s);
  std::cout << '\t';
  for (std::size_t index = 0;
       index < ORACLARVA_MOBILE_NEURON_COUNT; ++index) {
    if (index) std::cout << ',';
    std::cout << snapshot.spike_counts[index];
  }
  std::cout << '\t';
  for (std::size_t index = 0;
       index < ORACLARVA_MOBILE_NEURON_COUNT; ++index) {
    if (index) std::cout << ',';
    PrintMaybe(snapshot.first_spike_s[index]);
  }
  std::cout << '\t';
  for (std::size_t index = 0;
       index < ORACLARVA_MOBILE_WAVE_SEGMENT_COUNT; ++index) {
    if (index) std::cout << ',';
    std::cout << static_cast<int>(snapshot.trace_valid[index]);
  }
  std::cout << '\n';
}

long PeakRssKb() {
#if defined(__linux__)
  struct rusage usage {};
  if (getrusage(RUSAGE_SELF, &usage) == 0) return usage.ru_maxrss;
#endif
  return -1;
}

std::string RequireValue(
    int& index, int argc, char** argv, const std::string& option) {
  if (index + 1 >= argc) {
    throw std::runtime_error("missing value for " + option);
  }
  return argv[++index];
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc < 2) {
      throw std::runtime_error(
          "usage: mobile_core_host FIXTURE [--steps N] [--touch-steps N] "
          "[--touch-intensity X] [--no-frame-output] "
          "[--omit-mesh-output] [--sample-stride N] "
          "[--benchmark-runs N] "
          "[--sensory-lesion SEGMENT] [--premotor-lesion SEGMENT] "
          "[--motor-lesion SEGMENT] [--fiber-lesion SEGMENT]");
    }
    int steps = -1;
    int touch_steps = 2;
    double touch_intensity = 1.0;
    int sample_stride = 320;
    int benchmark_runs = 0;
    bool emit_frames = true;
    bool emit_mesh_positions = true;
    std::string sensory_lesion;
    std::string premotor_lesion;
    std::string motor_lesion;
    std::string fiber_lesion;
    for (int index = 2; index < argc; ++index) {
      const std::string option = argv[index];
      if (option == "--steps") {
        steps = std::stoi(RequireValue(index, argc, argv, option));
      } else if (option == "--touch-steps") {
        touch_steps = std::stoi(RequireValue(index, argc, argv, option));
      } else if (option == "--touch-intensity") {
        touch_intensity = std::stod(
            RequireValue(index, argc, argv, option));
      } else if (option == "--no-frame-output") {
        emit_frames = false;
      } else if (option == "--omit-mesh-output") {
        emit_mesh_positions = false;
      } else if (option == "--sample-stride") {
        sample_stride = std::stoi(RequireValue(index, argc, argv, option));
      } else if (option == "--benchmark-runs") {
        benchmark_runs = std::stoi(RequireValue(index, argc, argv, option));
      } else if (option == "--sensory-lesion") {
        sensory_lesion = RequireValue(index, argc, argv, option);
      } else if (option == "--premotor-lesion") {
        premotor_lesion = RequireValue(index, argc, argv, option);
      } else if (option == "--motor-lesion") {
        motor_lesion = RequireValue(index, argc, argv, option);
      } else if (option == "--fiber-lesion") {
        fiber_lesion = RequireValue(index, argc, argv, option);
      } else {
        throw std::runtime_error("unknown mobile host option: " + option);
      }
    }
    if (touch_steps < 0 || sample_stride <= 0 || benchmark_runs < 0) {
      throw std::runtime_error("mobile host counts must be nonnegative");
    }
    OraclarvaMobileOptions options{
        sensory_lesion.empty() ? nullptr : sensory_lesion.c_str(),
        premotor_lesion.empty() ? nullptr : premotor_lesion.c_str(),
        motor_lesion.empty() ? nullptr : motor_lesion.c_str(),
        fiber_lesion.empty() ? nullptr : fiber_lesion.c_str()};
    CoreOwner core;
    char error[256]{};
    const auto initialize_start = std::chrono::steady_clock::now();
    Check(oraclarva_mobile_create(
        argv[1], &options, &core.value, error, sizeof(error)), error);
    const auto initialize_end = std::chrono::steady_clock::now();
    const double initialize_ms = std::chrono::duration<double, std::milli>(
        initialize_end - initialize_start).count();
    OraclarvaMobileMetadata metadata{};
    Check(oraclarva_mobile_read_metadata(
        core.value, &metadata, error, sizeof(error)), error);
    if (steps < 0) steps = static_cast<int>(metadata.maximum_steps);
    if (steps <= 0 || steps > static_cast<int>(metadata.maximum_steps)
        || touch_steps > steps) {
      throw std::runtime_error("mobile host schedule is outside fixture");
    }
    std::size_t vertex_count = 0;
    std::size_t triangle_count = 0;
    Check(oraclarva_mobile_render_counts(
        core.value, 2, 12, &vertex_count, &triangle_count,
        error, sizeof(error)), error);
    std::cout << std::setprecision(17);
    std::cout << "metadata\t" << metadata.abi_version << '\t'
              << metadata.fixture_schema << '\t' << metadata.model_id
              << '\t' << metadata.scientific_status << '\t'
              << "release_validated=false\t" << metadata.config_sha256
              << '\t' << metadata.fixed_dt_s << '\t'
              << metadata.neuron_count << '\t'
              << metadata.body_node_count << '\t'
              << metadata.wave_segment_count << '\t'
              << vertex_count << '\t' << triangle_count << '\n';

    const RunResult first = RunSchedule(
        core.value, steps, touch_steps, touch_intensity,
        sample_stride, emit_frames, emit_mesh_positions, 2, 12);
    PrintSummary(first);
    const RunResult replay = RunSchedule(
        core.value, steps, touch_steps, touch_intensity,
        sample_stride, false, false, 2, 12);
    std::cout << "replay\t" << std::hex << std::setw(16)
              << std::setfill('0') << first.digest << '\t'
              << std::setw(16) << replay.digest
              << std::dec << std::setfill(' ') << '\t'
              << (first.digest == replay.digest ? "exact" : "mismatch")
              << '\n';
    if (first.digest != replay.digest) {
      throw std::runtime_error("reset replay digest mismatch");
    }

    if (benchmark_runs > 0) {
      std::vector<double> times;
      times.reserve(benchmark_runs);
      for (int run = 0; run < benchmark_runs; ++run) {
        const RunResult measured = RunSchedule(
            core.value, steps, touch_steps, touch_intensity,
            steps, false, false, 1, 3);
        times.push_back(measured.wall_s);
      }
      std::sort(times.begin(), times.end());
      const double median_s = times[times.size() / 2];
      const double simulated_s =
          static_cast<double>(steps) * metadata.fixed_dt_s;
      const auto snapshot_start = std::chrono::steady_clock::now();
      for (int index = 0; index < 100; ++index) {
        (void)ReadSnapshot(core.value);
      }
      const auto snapshot_end = std::chrono::steady_clock::now();
      std::vector<OraclarvaMobileRenderVertex> vertices;
      std::vector<OraclarvaMobileTriangle> triangles;
      const auto render_start = std::chrono::steady_clock::now();
      for (int index = 0; index < 100; ++index) {
        ReadMesh(core.value, 2, 12, vertices, triangles);
      }
      const auto render_end = std::chrono::steady_clock::now();
      const double snapshot_us = std::chrono::duration<double, std::micro>(
          snapshot_end - snapshot_start).count() / 100.0;
      const double render_us = std::chrono::duration<double, std::micro>(
          render_end - render_start).count() / 100.0;
      std::cout << "benchmark\t" << initialize_ms << '\t'
                << median_s * 1000.0 << '\t'
                << simulated_s / median_s << '\t'
                << PeakRssKb() << '\t' << sizeof(OraclarvaMobileSnapshot)
                << '\t' << snapshot_us << '\t' << render_us << '\n';
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
