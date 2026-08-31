#include "repeat_core.hpp"

#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

void PrintMaybe(double value) {
  if (std::isnan(value)) std::cout << "-";
  else std::cout << value;
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
          "usage: repeat_native FIXTURE [--no-stimulus] [--steps N] "
          "[--sensory-lesion SEGMENT] [--premotor-lesion SEGMENT] "
          "[--motor-segment-lesion SEGMENT] "
          "[--fiber-segment-lesion SEGMENT]");
    }
    oraclarva::RepeatOptions options;
    for (int index = 2; index < argc; ++index) {
      const std::string option = argv[index];
      if (option == "--no-stimulus") {
        options.stimulate = false;
      } else if (option == "--steps") {
        options.steps_override = std::stoi(
            RequireValue(index, argc, argv, option));
      } else if (option == "--sensory-lesion") {
        options.sensory_lesion =
            RequireValue(index, argc, argv, option);
      } else if (option == "--premotor-lesion") {
        options.premotor_lesion =
            RequireValue(index, argc, argv, option);
      } else if (option == "--motor-segment-lesion") {
        options.motor_segment_lesion =
            RequireValue(index, argc, argv, option);
      } else if (option == "--fiber-segment-lesion") {
        options.fiber_segment_lesion =
            RequireValue(index, argc, argv, option);
      } else {
        throw std::runtime_error("unknown repeat option: " + option);
      }
    }

    const oraclarva::RepeatFixture fixture =
        oraclarva::LoadRepeatFixture(argv[1]);
    const oraclarva::RepeatOutput output =
        oraclarva::RunRepeat(fixture, options);
    std::cout << std::setprecision(17);
    std::cout << "metadata\t" << fixture.schema << '\t'
              << fixture.model_id << '\t' << fixture.status
              << "\trelease_validated=false\t"
              << fixture.config_sha256 << '\n';
    std::cout << "summary\t" << output.displacement_x_um << '\t'
              << output.feedback_force_frames << '\t'
              << (output.all_active_forces_traced ? "true" : "false")
              << '\t' << output.cycle_metrics.complete_cycle_count
              << '\t' << output.cycle_metrics.physical_wave_cycle_count
              << '\t';
    PrintMaybe(output.cycle_metrics.median_period_s);
    std::cout << '\t';
    PrintMaybe(output.cycle_metrics.median_stride_um);
    std::cout << '\t';
    PrintMaybe(output.cycle_metrics.median_wave_speed_segments_s);
    std::cout << '\t' << output.trajectory.size() << '\n';

    for (std::size_t index = 0; index < fixture.neuron_count; ++index) {
      std::cout << "neuron\t" << index << '\t'
                << fixture.neuron_labels[index] << '\t'
                << output.spike_counts[index] << '\t';
      PrintMaybe(output.first_spike_s[index]);
      std::cout << '\n';
    }
    for (std::size_t segment = 0;
         segment < fixture.wave_segments.size(); ++segment) {
      std::cout << "premotor\t" << segment << '\t'
                << fixture.wave_segments[segment].id;
      for (double value : output.premotor_spike_times_s[segment]) {
        std::cout << '\t' << value;
      }
      std::cout << '\n';
      if (output.trace_examples[segment].valid) {
        const oraclarva::RepeatTrace& trace =
            output.trace_examples[segment];
        std::cout << "trace\t" << segment << '\t'
                  << trace.segment_id << '\t'
                  << trace.body_state_time_s << '\t'
                  << trace.sensor_neuron << '\t'
                  << trace.sensor_spike_time_s << '\t'
                  << trace.premotor_neuron << '\t'
                  << trace.premotor_spike_time_s << '\t'
                  << trace.motor_neuron << '\t'
                  << trace.motor_spike_time_s << '\n';
      }
    }
    for (std::size_t index = 0;
         index < output.trajectory.size(); ++index) {
      const oraclarva::RepeatFrame& frame = output.trajectory[index];
      std::cout << "frame\t" << index << '\t' << frame.time_s << '\t';
      for (std::size_t node = 0; node < frame.nodes_m.size(); ++node) {
        if (node) std::cout << ';';
        const oraclarva::RepeatVec3& value = frame.nodes_m[node];
        std::cout << value.x * 1e6 << ',' << value.y * 1e6
                  << ',' << value.z * 1e6;
      }
      std::cout << '\t';
      for (std::size_t segment = 0;
           segment < frame.segment_activation.size(); ++segment) {
        if (segment) std::cout << ',';
        std::cout << frame.segment_activation[segment];
      }
      std::cout << '\t';
      for (std::size_t node = 0;
           node < frame.node_force_model_units.size(); ++node) {
        if (node) std::cout << ';';
        const oraclarva::RepeatVec3& value =
            frame.node_force_model_units[node];
        std::cout << value.x << ',' << value.y << ',' << value.z;
      }
      std::cout << '\n';
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
