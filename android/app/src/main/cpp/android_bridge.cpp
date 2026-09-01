#include <jni.h>

#include "mobile_environment.h"

#include <array>
#include <cstdint>
#include <memory>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr std::uint32_t kAxialSamplesPerSegment = 2;
constexpr std::uint32_t kRadialSamples = 12;
constexpr jsize kStateValueCount = 69;
constexpr std::size_t kVertexStride = 7;

struct AndroidCore {
  OraclarvaMobileCore* core = nullptr;
  std::vector<OraclarvaMobileRenderVertex> vertices;
  std::vector<OraclarvaMobileTriangle> triangles;
  std::vector<jfloat> interleaved_vertices;
  std::vector<jint> triangle_indices;

  ~AndroidCore() { oraclarva_mobile_destroy(core); }
};

class UtfString {
 public:
  UtfString(JNIEnv* environment, jstring value)
      : environment_(environment), value_(value) {
    if (value_ == nullptr) {
      throw std::invalid_argument("fixture path is required");
    }
    chars_ = environment_->GetStringUTFChars(value_, nullptr);
    if (chars_ == nullptr) {
      throw std::runtime_error("cannot access fixture path");
    }
  }

  ~UtfString() {
    if (chars_ != nullptr) {
      environment_->ReleaseStringUTFChars(value_, chars_);
    }
  }

  const char* get() const { return chars_; }

 private:
  JNIEnv* environment_;
  jstring value_;
  const char* chars_ = nullptr;
};

void ThrowJava(JNIEnv* environment, const char* class_name, const char* message) {
  if (environment->ExceptionCheck()) return;
  jclass exception_class = environment->FindClass(class_name);
  if (exception_class != nullptr) {
    environment->ThrowNew(exception_class, message);
  }
}

void ThrowState(JNIEnv* environment, const std::exception& error) {
  ThrowJava(environment, "java/lang/IllegalStateException", error.what());
}

void CheckStatus(int status, const std::array<char, 512>& error) {
  if (status != ORACLARVA_MOBILE_OK) {
    throw std::runtime_error(
        error[0] == '\0' ? "native mobile operation failed" : error.data());
  }
}

AndroidCore& Resolve(jlong handle) {
  if (handle == 0) throw std::invalid_argument("native handle is closed");
  return *reinterpret_cast<AndroidCore*>(
      static_cast<std::uintptr_t>(handle));
}

jlong Encode(AndroidCore* value) {
  return static_cast<jlong>(
      reinterpret_cast<std::uintptr_t>(value));
}

void RequireArray(
    JNIEnv* environment,
    jarray value,
    jsize required,
    const char* name) {
  if (value == nullptr || environment->GetArrayLength(value) < required) {
    throw std::invalid_argument(std::string(name) + " buffer is too small");
  }
}

}  // namespace

extern "C" {

JNIEXPORT jlong JNICALL
Java_org_oraclarva_mobile_NativeBridge_nativeCreate(
    JNIEnv* environment,
    jclass,
    jstring repeat_fixture_path,
    jstring spatial_fixture_path) {
  try {
    UtfString repeat(environment, repeat_fixture_path);
    UtfString spatial(environment, spatial_fixture_path);
    auto result = std::make_unique<AndroidCore>();
    std::array<char, 512> error{};
    const OraclarvaMobileOptions repeat_options{};
    const OraclarvaMobileSpatialOptions spatial_options{};
    CheckStatus(
        oraclarva_mobile_create_spatial(
            repeat.get(), spatial.get(), &repeat_options, &spatial_options,
            &result->core, error.data(), error.size()),
        error);
    std::size_t vertex_count = 0;
    std::size_t triangle_count = 0;
    CheckStatus(
        oraclarva_mobile_render_counts(
            result->core, kAxialSamplesPerSegment, kRadialSamples,
            &vertex_count, &triangle_count, error.data(), error.size()),
        error);
    result->vertices.resize(vertex_count);
    result->triangles.resize(triangle_count);
    result->interleaved_vertices.resize(vertex_count * kVertexStride);
    result->triangle_indices.resize(triangle_count * 3);
    return Encode(result.release());
  } catch (const std::exception& error) {
    ThrowState(environment, error);
    return 0;
  }
}

JNIEXPORT void JNICALL
Java_org_oraclarva_mobile_NativeBridge_nativeDestroy(
    JNIEnv*, jclass, jlong handle) {
  delete reinterpret_cast<AndroidCore*>(
      static_cast<std::uintptr_t>(handle));
}

JNIEXPORT void JNICALL
Java_org_oraclarva_mobile_NativeBridge_nativeReset(
    JNIEnv* environment, jclass, jlong handle) {
  try {
    AndroidCore& state = Resolve(handle);
    std::array<char, 512> error{};
    CheckStatus(
        oraclarva_mobile_reset(state.core, error.data(), error.size()), error);
  } catch (const std::exception& error) {
    ThrowState(environment, error);
  }
}

JNIEXPORT jint JNICALL
Java_org_oraclarva_mobile_NativeBridge_nativeAdvance(
    JNIEnv* environment,
    jclass,
    jlong handle,
    jdouble posterior_touch_intensity,
    jboolean light_enabled,
    jdouble origin_x_m,
    jdouble origin_y_m,
    jdouble origin_z_m,
    jdouble value_at_origin_w_m2,
    jdouble gradient_x_w_m3,
    jdouble gradient_y_w_m3,
    jdouble gradient_z_w_m3,
    jdouble temporal_rate_w_m2_s,
    jdouble lower_bound_w_m2,
    jdouble upper_bound_w_m2,
    jint steps) {
  try {
    if (steps < 0 || steps > 1000) {
      throw std::invalid_argument("advance steps must be in [0, 1000]");
    }
    AndroidCore& state = Resolve(handle);
    const OraclarvaMobileIntegratedEnvironmentInput input{
        posterior_touch_intensity,
        {
            static_cast<std::uint8_t>(light_enabled == JNI_TRUE),
            {origin_x_m, origin_y_m, origin_z_m},
            value_at_origin_w_m2,
            {gradient_x_w_m3, gradient_y_w_m3, gradient_z_w_m3},
            temporal_rate_w_m2_s,
            lower_bound_w_m2,
            upper_bound_w_m2,
        }};
    std::array<char, 512> error{};
    for (jint step = 0; step < steps; ++step) {
      CheckStatus(
          oraclarva_mobile_advance_environment(
              state.core, &input, error.data(), error.size()),
          error);
    }
    return steps;
  } catch (const std::exception& error) {
    ThrowState(environment, error);
    return 0;
  }
}

JNIEXPORT jintArray JNICALL
Java_org_oraclarva_mobile_NativeBridge_nativeRenderCounts(
    JNIEnv* environment, jclass, jlong handle) {
  try {
    AndroidCore& state = Resolve(handle);
    const std::array<jint, 2> values{
        static_cast<jint>(state.vertices.size()),
        static_cast<jint>(state.triangles.size())};
    jintArray result = environment->NewIntArray(values.size());
    if (result == nullptr) return nullptr;
    environment->SetIntArrayRegion(result, 0, values.size(), values.data());
    return result;
  } catch (const std::exception& error) {
    ThrowState(environment, error);
    return nullptr;
  }
}

JNIEXPORT jint JNICALL
Java_org_oraclarva_mobile_NativeBridge_nativeReadFrame(
    JNIEnv* environment,
    jclass,
    jlong handle,
    jdoubleArray state_values,
    jfloatArray render_vertices,
    jintArray render_indices) {
  try {
    AndroidCore& state = Resolve(handle);
    RequireArray(environment, state_values, kStateValueCount, "state");
    RequireArray(
        environment, render_vertices,
        static_cast<jsize>(state.interleaved_vertices.size()), "vertex");
    RequireArray(
        environment, render_indices,
        static_cast<jsize>(state.triangle_indices.size()), "index");

    OraclarvaMobileEnvironmentSnapshot snapshot{};
    std::array<char, 512> error{};
    CheckStatus(
        oraclarva_mobile_read_environment_snapshot(
            state.core, &snapshot, error.data(), error.size()),
        error);
    CheckStatus(
        oraclarva_mobile_read_render_mesh(
            state.core, kAxialSamplesPerSegment, kRadialSamples,
            state.vertices.data(), state.vertices.size(),
            state.triangles.data(), state.triangles.size(),
            error.data(), error.size()),
        error);

    std::array<jdouble, kStateValueCount> values{};
    values[0] = snapshot.extension_abi_version;
    values[1] = snapshot.step_index;
    values[2] = snapshot.time_s;
    values[3] = snapshot.displacement_um[0];
    values[4] = snapshot.displacement_um[1];
    values[5] = snapshot.displacement_um[2];
    values[6] = snapshot.heading_change_deg;
    values[7] = snapshot.head_pitch_change_deg;
    values[8] = snapshot.release_validated;
    values[9] = std::accumulate(
        std::begin(snapshot.spatial_spike_counts),
        std::end(snapshot.spatial_spike_counts), 0.0);
    for (std::size_t channel = 0;
         channel < ORACLARVA_MOBILE_SPATIAL_CHANNEL_COUNT; ++channel) {
      values[10 + channel] = snapshot.raw_light_w_m2[channel];
      values[14 + channel] = snapshot.adapted_light_w_m2[channel];
      values[18 + channel] = snapshot.light_drive[channel];
      values[22 + channel] = snapshot.receptor_current[channel];
      values[26 + channel] = snapshot.channel_activation[channel];
    }
    for (std::size_t coordinate = 0;
         coordinate < ORACLARVA_MOBILE_BODY_NODE_COUNT * 3u; ++coordinate) {
      values[30 + coordinate] = snapshot.physics_nodes_um[coordinate];
    }

    for (std::size_t index = 0; index < state.vertices.size(); ++index) {
      const auto& source = state.vertices[index];
      const std::size_t offset = index * kVertexStride;
      for (std::size_t axis = 0; axis < 3; ++axis) {
        state.interleaved_vertices[offset + axis] = source.position_um[axis];
        state.interleaved_vertices[offset + 3 + axis] = source.normal[axis];
      }
      state.interleaved_vertices[offset + 6] = source.activation;
    }
    for (std::size_t index = 0; index < state.triangles.size(); ++index) {
      for (std::size_t corner = 0; corner < 3; ++corner) {
        state.triangle_indices[index * 3 + corner] =
            static_cast<jint>(state.triangles[index].vertex[corner]);
      }
    }
    environment->SetDoubleArrayRegion(
        state_values, 0, values.size(), values.data());
    environment->SetFloatArrayRegion(
        render_vertices, 0, state.interleaved_vertices.size(),
        state.interleaved_vertices.data());
    environment->SetIntArrayRegion(
        render_indices, 0, state.triangle_indices.size(),
        state.triangle_indices.data());
    return static_cast<jint>(snapshot.step_index);
  } catch (const std::exception& error) {
    ThrowState(environment, error);
    return 0;
  }
}

}  // extern "C"
