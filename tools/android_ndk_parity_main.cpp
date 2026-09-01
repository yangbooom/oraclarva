#include "mobile_environment.h"

#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <exception>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr std::uint32_t kAxialSamplesPerSegment = 2;
constexpr std::uint32_t kRadialSamples = 12;

struct CoreOwner {
  OraclarvaMobileCore* value = nullptr;
  ~CoreOwner() { oraclarva_mobile_destroy(value); }
};

struct Capture {
  OraclarvaMobileEnvironmentSnapshot snapshot{};
  std::vector<OraclarvaMobileRenderVertex> vertices;
  std::vector<OraclarvaMobileTriangle> triangles;
};

void CheckStatus(int status, const std::array<char, 512>& error) {
  if (status != ORACLARVA_MOBILE_OK) {
    throw std::runtime_error(
        error[0] == '\0' ? "native mobile operation failed" : error.data());
  }
}

void Require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}

void RequireNear(double actual, double expected, double tolerance, const char* message) {
  if (std::abs(actual - expected) > tolerance) {
    throw std::runtime_error(message);
  }
}

void Reset(OraclarvaMobileCore* core) {
  std::array<char, 512> error{};
  CheckStatus(oraclarva_mobile_reset(core, error.data(), error.size()), error);
}

void Advance(
    OraclarvaMobileCore* core,
    int steps,
    double gradient_y_w_m3,
    bool contact) {
  std::array<char, 512> error{};
  for (int step = 0; step < steps; ++step) {
    const OraclarvaMobileIntegratedEnvironmentInput input{
        contact && step < 2 ? 1.0 : 0.0,
        {
            1,
            {0.0, 0.0, 0.0},
            4.0,
            {0.0, gradient_y_w_m3, 0.0},
            0.0,
            0.0,
            20.0,
        }};
    CheckStatus(
        oraclarva_mobile_advance_environment(
            core, &input, error.data(), error.size()),
        error);
  }
}

Capture Read(OraclarvaMobileCore* core) {
  Capture result;
  std::array<char, 512> error{};
  CheckStatus(
      oraclarva_mobile_read_environment_snapshot(
          core, &result.snapshot, error.data(), error.size()),
      error);
  std::size_t vertex_count = 0;
  std::size_t triangle_count = 0;
  CheckStatus(
      oraclarva_mobile_render_counts(
          core, kAxialSamplesPerSegment, kRadialSamples,
          &vertex_count, &triangle_count, error.data(), error.size()),
      error);
  result.vertices.resize(vertex_count);
  result.triangles.resize(triangle_count);
  CheckStatus(
      oraclarva_mobile_read_render_mesh(
          core, kAxialSamplesPerSegment, kRadialSamples,
          result.vertices.data(), result.vertices.size(),
          result.triangles.data(), result.triangles.size(),
          error.data(), error.size()),
      error);
  return result;
}

bool Equal(const Capture& first, const Capture& second) {
  return std::memcmp(
             &first.snapshot, &second.snapshot, sizeof(first.snapshot)) == 0 &&
      first.vertices.size() == second.vertices.size() &&
      first.triangles.size() == second.triangles.size() &&
      std::memcmp(
          first.vertices.data(), second.vertices.data(),
          first.vertices.size() * sizeof(first.vertices[0])) == 0 &&
      std::memcmp(
          first.triangles.data(), second.triangles.data(),
          first.triangles.size() * sizeof(first.triangles[0])) == 0;
}

const char* Architecture() {
#if defined(__aarch64__)
  return "arm64-v8a";
#elif defined(__x86_64__)
  return "x86_64";
#else
  return "unknown";
#endif
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc != 3) {
      throw std::runtime_error("repeat and spatial fixture paths are required");
    }
    CoreOwner core;
    std::array<char, 512> error{};
    const OraclarvaMobileOptions repeat_options{};
    const OraclarvaMobileSpatialOptions spatial_options{};
    CheckStatus(
        oraclarva_mobile_create_spatial(
            argv[1], argv[2], &repeat_options, &spatial_options,
            &core.value, error.data(), error.size()),
        error);

    Advance(core.value, 14'600, 0.0, true);
    const Capture uniform = Read(core.value);
    const double spike_total = std::accumulate(
        std::begin(uniform.snapshot.spatial_spike_counts),
        std::end(uniform.snapshot.spatial_spike_counts), 0.0);
    Require(uniform.snapshot.step_index == 14'600, "uniform step drifted");
    RequireNear(uniform.snapshot.time_s, 14.6, 1e-12, "uniform time drifted");
    RequireNear(
        -uniform.snapshot.displacement_um[0], 467.53928512972095, 1e-8,
        "uniform forward path drifted");
    RequireNear(
        uniform.snapshot.heading_change_deg, 0.0, 1e-12,
        "uniform field produced yaw");
    RequireNear(spike_total, 53'524.0, 0.0, "spike total drifted");
    Require(
        uniform.vertices.size() == 302 && uniform.triangles.size() == 600,
        "render topology drifted");
    Require(!uniform.snapshot.release_validated, "release boundary drifted");

    Reset(core.value);
    Advance(core.value, 14'600, 0.0, true);
    const Capture replay = Read(core.value);
    Require(Equal(uniform, replay), "reset replay drifted");

    Reset(core.value);
    Advance(core.value, 4'500, 6'000.0, true);
    const Capture lateral = Read(core.value);
    RequireNear(
        lateral.snapshot.heading_change_deg, -3.8310160300481635, 2e-9,
        "lateral field yaw drifted");
    RequireNear(
        lateral.snapshot.displacement_um[1], -1.956735327396, 2e-9,
        "lateral displacement drifted");

    std::printf(
        "abi\t%s\nuniform\t%.12f\t%.12f\t%.12f\t%.0f\n"
        "lateral\t%.12f\t%.12f\nrender\t%zu\t%zu\n"
        "replay\texact\nrelease_validated\tfalse\n",
        Architecture(), uniform.snapshot.time_s,
        -uniform.snapshot.displacement_um[0],
        uniform.snapshot.heading_change_deg, spike_total,
        lateral.snapshot.heading_change_deg,
        lateral.snapshot.displacement_um[1],
        uniform.vertices.size(), uniform.triangles.size());
    return 0;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "android NDK parity failed: %s\n", error.what());
    return 1;
  }
}
