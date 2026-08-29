#pragma once

#include "lif_core.hpp"

#include <array>
#include <cstddef>
#include <map>
#include <string>
#include <vector>

namespace oraclarva {

struct BilateralVec3 {
  double x;
  double y;
  double z;
};

struct BilateralBodySegment {
  std::string id;
  double rest_length_m;
  double width_m;
  double height_m;
  double mass_kg;
  double maximum_shortening_fraction;
};

struct BilateralWaveSegment {
  std::string id;
  std::size_t body_index;
  std::array<std::size_t, 2> proprioceptor_neuron;
  std::array<std::size_t, 2> premotor_neuron;
  std::array<std::size_t, 2> inhibitory_neuron;
  std::array<std::size_t, 2> motor_neuron;
  double rise_tau_s;
  double fall_tau_s;
};

struct BilateralParameters {
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
  double active_curvature_gain = 0.0;
  double active_bending_stiffness_ratio = 0.0;
  double asymmetric_sensory_current_a = 0.0;
  double gravity_z_m_s2 = -9.81;
  double ground_z_m = 0.0;
  int body_iterations = 12;
  double instantaneous_stiffness_n_m = 0.0;
};

struct BilateralFixture {
  std::string schema;
  std::string model_id;
  std::string status;
  bool release_validated = false;
  std::size_t neuron_count = 0;
  int steps = 0;
  int sample_stride = 0;
  std::array<std::size_t, 2> touch_neuron{};
  std::array<std::size_t, 2> asymmetry_neuron{};
  LIFConfig lif_config;
  BilateralParameters parameters;
  std::vector<std::string> neuron_labels;
  std::vector<BilateralBodySegment> body_segments;
  std::vector<BilateralWaveSegment> wave_segments;
  std::map<std::string, std::vector<std::size_t>> motor_identities;
  std::map<std::string, int> muscle_proxy_counts;
  std::vector<Synapse> synapses;
};

struct BilateralOptions {
  double left_stimulus = 1.0;
  double right_stimulus = 1.0;
  std::string premotor_lesion;
  std::string muscle_lesion;
  std::string motor_identity_lesion;
};

struct BilateralTrajectoryFrame {
  double time_s;
  std::vector<BilateralVec3> nodes_m;
  std::vector<double> left_body_activation;
  std::vector<double> right_body_activation;
};

struct BilateralOutput {
  double displacement_x_um = 0.0;
  double displacement_y_um = 0.0;
  double heading_change_deg = 0.0;
  double maximum_abs_lateral_um = 0.0;
  std::vector<int> spike_counts;
  std::vector<double> first_spike_s;
  std::vector<std::array<double, 2>> peak_activation;
  std::vector<std::array<double, 2>> peak_shortening;
  int active_motor_identities = 0;
  int peak_recruited_fibers = 0;
  std::vector<BilateralTrajectoryFrame> trajectory;
};

BilateralFixture LoadBilateralFixture(const std::string& path);
BilateralOutput RunBilateral(
    const BilateralFixture& fixture,
    const BilateralOptions& options = {});

}  // namespace oraclarva
