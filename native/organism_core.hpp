#pragma once

#include "lif_core.hpp"

#include <cstddef>
#include <map>
#include <string>
#include <vector>

namespace oraclarva {

struct Vec3 {
  double x;
  double y;
  double z;
};

struct BodySegment {
  std::string id;
  double rest_length_m;
  double width_m;
  double height_m;
  double mass_kg;
  double maximum_shortening_fraction;
};

struct WaveSegment {
  std::string id;
  std::size_t body_index;
  std::size_t proprioceptor_neuron;
  std::size_t premotor_neuron;
  std::size_t inhibitory_neuron;
  std::size_t motor_neuron;
  double rise_tau_s;
  double fall_tau_s;
};

struct ClosedLoopParameters {
  double posterior_touch_current_a = 0.0;
  double posterior_touch_duration_s = 0.0;
  double proprioceptor_min_strain = 0.0;
  double proprioceptor_min_shortening_rate_m_s = 0.0;
  double proprioceptor_current_gain_a_s_m = 0.0;
  double proprioceptor_max_current_a = 0.0;
  double sensory_adaptation_tau_s = 0.0;
  double sensory_adaptation_fraction = 0.0;
  double body_velocity_retention = 0.0;
  double ground_negative_x_retention = 0.0;
  double ground_positive_x_retention = 0.0;
  double motor_excitation_tau_s = 0.0;
  double excitation_per_motor_spike = 0.0;
  double muscle_activation_excitation_threshold = 0.0;
  double gravity_z_m_s2 = -9.81;
  double ground_z_m = 0.0;
  int body_iterations = 12;
  double instantaneous_stiffness_n_m = 0.0;
};

struct ClosedLoopFixture {
  std::string schema;
  std::string model_id;
  std::string status;
  bool release_validated = false;
  std::size_t neuron_count = 0;
  int steps = 0;
  int sample_stride = 0;
  std::size_t touch_neuron = 0;
  LIFConfig lif_config;
  ClosedLoopParameters parameters;
  std::vector<std::string> neuron_labels;
  std::vector<BodySegment> body_segments;
  std::vector<WaveSegment> wave_segments;
  std::map<std::string, std::vector<std::size_t>> motor_identities;
  std::map<std::string, int> muscle_proxy_counts;
  std::vector<Synapse> synapses;
};

struct ClosedLoopOptions {
  bool stimulate = true;
  std::string premotor_lesion;
  std::string muscle_lesion;
  std::string motor_identity_lesion;
};

struct TrajectoryFrame {
  double time_s;
  std::vector<Vec3> nodes_m;
  std::vector<double> body_activation;
};

struct ClosedLoopOutput {
  double displacement_um = 0.0;
  std::vector<int> spike_counts;
  std::vector<double> first_spike_s;
  std::vector<double> peak_activation;
  std::vector<double> peak_shortening;
  int active_motor_identities = 0;
  int peak_recruited_fibers = 0;
  std::vector<TrajectoryFrame> trajectory;
};

ClosedLoopFixture LoadClosedLoopFixture(const std::string& path);
ClosedLoopOutput RunClosedLoop(
    const ClosedLoopFixture& fixture,
    const ClosedLoopOptions& options = {});

}  // namespace oraclarva
