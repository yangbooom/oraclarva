#pragma once

#include "lif_core.hpp"

#include <array>
#include <cstddef>
#include <memory>
#include <string>
#include <vector>

namespace oraclarva {

constexpr std::size_t kSpatialChannelCount = 4;
constexpr std::size_t kSpatialNeuronCount = 168;

struct SpatialVec3 {
  double x = 0.0;
  double y = 0.0;
  double z = 0.0;
};

struct SpatialBodySegment {
  std::string id;
  double rest_length_m = 0.0;
  double width_m = 0.0;
  double height_m = 0.0;
};

struct SpatialBodyState {
  std::vector<SpatialVec3> nodes_m;
  std::vector<SpatialBodySegment> segments;
};

struct SpatialLightField {
  bool enabled = false;
  SpatialVec3 origin_m;
  double value_at_origin_w_m2 = 0.0;
  SpatialVec3 gradient_w_m3;
  double temporal_rate_w_m2_s = 0.0;
  double lower_bound_w_m2 = 0.0;
  double upper_bound_w_m2 = 20.0;
};

struct SpatialParameters {
  double posterior_touch_current_a = 0.0;
  double proprioceptor_min_strain = 0.0;
  double proprioceptor_min_shortening_rate_m_s = 0.0;
  double proprioceptor_current_gain_a_s_m = 0.0;
  double proprioceptor_max_current_a = 0.0;
  double sensory_adaptation_tau_s = 0.0;
  double sensory_adaptation_fraction = 0.0;
  double integrated_proprioception_enabled = 0.0;
  double motor_excitation_tau_s = 0.0;
  double excitation_per_motor_spike = 0.0;
  double muscle_activation_excitation_threshold = 0.0;
  double active_yaw_curvature_gain = 0.0;
  double active_pitch_curvature_gain = 0.0;
  double active_bending_stiffness_ratio = 0.0;
  double asymmetric_sensory_current_a = 0.0;
  double baseline_intensity = 0.0;
  double light_response_scale = 0.0;
  double light_polarity = 0.0;
  double light_spatial_gain = 0.0;
  double light_temporal_gain = 0.0;
  double light_adaptation_tau_s = 0.0;
  double light_weight = 0.0;
};

struct SpatialWaveSegment {
  std::string id;
  std::size_t body_index = 0;
  std::array<std::size_t, kSpatialChannelCount> proprioceptor_neuron{};
  std::array<std::size_t, kSpatialChannelCount> premotor_neuron{};
  std::array<std::size_t, kSpatialChannelCount> inhibitory_neuron{};
  std::array<std::size_t, kSpatialChannelCount> motor_neuron{};
  double rise_tau_s = 0.0;
  double fall_tau_s = 0.0;
};

struct SpatialFixture {
  std::string schema;
  std::string model_id;
  std::string status;
  bool release_validated = false;
  std::size_t neuron_count = 0;
  std::size_t declared_synapse_count = 0;
  std::array<std::size_t, kSpatialChannelCount> touch_neuron{};
  std::array<std::size_t, kSpatialChannelCount> asymmetry_neuron{};
  LIFConfig lif_config;
  SpatialParameters parameters;
  std::vector<std::string> neuron_labels;
  std::vector<SpatialBodySegment> body_segments;
  std::vector<SpatialWaveSegment> wave_segments;
  std::vector<Synapse> synapses;
};

struct SpatialControllerOptions {
  std::string sensory_lesion_channel;
  std::string premotor_lesion_channel;
  std::string motor_lesion_channel;
  std::string muscle_lesion_channel;
};

struct SpatialControllerFrame {
  std::array<double, kSpatialChannelCount> raw_light_w_m2{};
  std::array<double, kSpatialChannelCount> adapted_light_w_m2{};
  std::array<double, kSpatialChannelCount> light_drive{};
  std::array<double, kSpatialChannelCount> receptor_current{};
  std::array<double, kSpatialChannelCount> channel_activation{};
  std::vector<std::array<double, 2>> yaw_activation;
  std::vector<std::array<double, 2>> pitch_activation;
  std::vector<int> spike_counts;
  std::vector<std::size_t> last_step_spikes;
};

SpatialFixture LoadSpatialFixture(const std::string& path);

class SpatialEnvironmentController {
 public:
  SpatialEnvironmentController(
      const SpatialFixture& fixture,
      const SpatialBodyState& initial_body,
      const SpatialControllerOptions& options = {});
  ~SpatialEnvironmentController();
  SpatialEnvironmentController(const SpatialEnvironmentController&) = delete;
  SpatialEnvironmentController& operator=(const SpatialEnvironmentController&) = delete;

  SpatialControllerFrame Step(
      double time_s,
      const SpatialLightField& light,
      const SpatialBodyState& body);
  SpatialControllerFrame Snapshot() const;

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace oraclarva
