#pragma once

#include "lif_core.hpp"

#include <cstddef>
#include <map>
#include <string>
#include <vector>

namespace oraclarva {

struct RepeatVec3 {
  double x = 0.0;
  double y = 0.0;
  double z = 0.0;
};

struct RepeatBodySegment {
  std::string id;
  double rest_length_m = 0.0;
  double width_m = 0.0;
  double height_m = 0.0;
  double mass_kg = 0.0;
};

struct RepeatWaveSegment {
  std::string id;
  std::size_t body_index = 0;
  std::size_t sensory_neuron = 0;
  std::size_t premotor_neuron = 0;
  std::size_t inhibitory_neuron = 0;
  std::vector<std::size_t> source_neurons;
};

struct RepeatCoordinate {
  double s = 0.0;
  double theta_rad = 0.0;
  double depth_fraction = 0.0;
};

struct RepeatFiber {
  std::string id;
  std::string segment_id;
  std::string side;
  std::string muscle_number;
  std::size_t body_index = 0;
  std::size_t source_neuron = 0;
  RepeatCoordinate origin;
  RepeatCoordinate insertion;
  std::string mapping_provenance;
};

struct RepeatParameters {
  double posterior_touch_current_a = 0.0;
  double posterior_touch_duration_s = 0.0;
  double intersegmental_relay_delay_s = 0.0;
  double a1_recovery_to_a6_delay_s = 0.0;
  double sensory_maximum_current_a = 0.0;
  double sensory_adaptation_tau_s = 0.0;
  double sensory_adaptation_fraction = 0.0;
  double recovery_adaptation_fraction = 0.0;
  double recovery_rate_threshold_s_1 = 0.0;
  double recovery_rate_gain_s = 0.0;
  double local_tension_gate_gain = 0.0;
  double trace_arrival_window_s = 0.0;
  double muscle_activation_rise_tau_s = 0.0;
  double muscle_activation_decay_tau_s = 0.0;
  double muscle_event_target = 0.0;
  double shortening_strain_threshold = 0.0;
  double shortening_rate_threshold_s_1 = 0.0;
  double shortening_strain_gain = 0.0;
  double shortening_rate_gain_s = 0.0;
  double maximum_external_current_a = 0.0;
  double active_tension_gain_model_units = 0.0;
  double passive_stiffness_model_units = 0.0;
  double damping_model_units = 0.0;
  double acceleration_scale_m_s2_per_model_force = 0.0;
  double body_velocity_retention = 0.0;
  double ground_negative_x_retention = 0.0;
  double ground_positive_x_retention = 0.0;
  double gravity_z_m_s2 = -9.81;
  double ground_z_m = 0.0;
  int body_iterations = 12;
  double instantaneous_stiffness_n_m = 0.0;
};

struct RepeatFixture {
  std::string schema;
  std::string model_id;
  std::string status;
  bool release_validated = false;
  std::string config_sha256;
  std::size_t neuron_count = 0;
  int steps = 0;
  int sample_stride = 0;
  int equilibrium_steps = 0;
  std::size_t touch_neuron = 0;
  std::size_t recovery_neuron = 0;
  LIFConfig lif_config;
  RepeatParameters parameters;
  std::vector<std::string> neuron_labels;
  std::vector<RepeatBodySegment> body_segments;
  std::vector<RepeatWaveSegment> wave_segments;
  std::vector<Synapse> synapses;
  std::vector<RepeatFiber> fibers;
};

struct RepeatOptions {
  bool stimulate = true;
  int steps_override = 0;
  std::string sensory_lesion;
  std::string premotor_lesion;
  std::string motor_segment_lesion;
  std::string fiber_segment_lesion;
};

struct RepeatTrace {
  bool valid = false;
  double body_state_time_s = 0.0;
  std::size_t sensor_neuron = 0;
  double sensor_spike_time_s = 0.0;
  std::size_t premotor_neuron = 0;
  double premotor_spike_time_s = 0.0;
  std::size_t motor_neuron = 0;
  double motor_spike_time_s = 0.0;
  std::string segment_id;
};

struct RepeatFrame {
  double time_s = 0.0;
  std::vector<RepeatVec3> nodes_m;
  std::vector<double> segment_activation;
  std::vector<RepeatVec3> node_force_model_units;
};

struct RepeatCycleMetrics {
  int complete_cycle_count = 0;
  int physical_wave_cycle_count = 0;
  double median_period_s = 0.0;
  double median_stride_um = 0.0;
  double median_wave_speed_segments_s = 0.0;
};

struct RepeatOutput {
  double displacement_x_um = 0.0;
  int feedback_force_frames = 0;
  bool all_active_forces_traced = true;
  std::vector<int> spike_counts;
  std::vector<double> first_spike_s;
  std::vector<std::vector<double>> premotor_spike_times_s;
  std::vector<std::vector<double>> motor_spike_times_s;
  std::vector<RepeatFrame> trajectory;
  std::vector<RepeatTrace> trace_examples;
  RepeatCycleMetrics cycle_metrics;
};

RepeatFixture LoadRepeatFixture(const std::string& path);
RepeatOutput RunRepeat(
    const RepeatFixture& fixture,
    const RepeatOptions& options = {});

}  // namespace oraclarva
