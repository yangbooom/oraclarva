#include "organism_core.hpp"

#include <cmath>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

std::string JoinDoubles(const std::vector<double>& values) {
  std::ostringstream output;
  output << std::setprecision(17);
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index > 0) output << ',';
    output << values[index];
  }
  return output.str();
}

std::string JoinNodes(const std::vector<oraclarva::Vec3>& nodes) {
  std::ostringstream output;
  output << std::setprecision(17);
  for (std::size_t index = 0; index < nodes.size(); ++index) {
    if (index > 0) output << ';';
    output << nodes[index].x * 1e6 << ','
           << nodes[index].y * 1e6 << ','
           << nodes[index].z * 1e6;
  }
  return output.str();
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc < 2) {
      std::cerr << "usage: oraclarva-native-organism FIXTURE [OPTIONS]\n";
      return 2;
    }
    oraclarva::ClosedLoopOptions options;
    for (int index = 2; index < argc; ++index) {
      const std::string option = argv[index];
      if (option == "--no-stimulus") {
        options.stimulate = false;
      } else if (option == "--premotor-lesion" && index + 1 < argc) {
        options.premotor_lesion = argv[++index];
      } else if (option == "--muscle-lesion" && index + 1 < argc) {
        options.muscle_lesion = argv[++index];
      } else if (option == "--motor-identity-lesion" && index + 1 < argc) {
        options.motor_identity_lesion = argv[++index];
      } else {
        throw std::runtime_error("unknown or incomplete option: " + option);
      }
    }

    const oraclarva::ClosedLoopFixture fixture =
        oraclarva::LoadClosedLoopFixture(argv[1]);
    const oraclarva::ClosedLoopOutput result =
        oraclarva::RunClosedLoop(fixture, options);
    std::cout << std::setprecision(17);
    std::cout << "metadata\t" << fixture.schema << '\t' << fixture.model_id
              << '\t' << fixture.status << "\trelease_validated=false\n";
    std::cout << "summary\t" << result.displacement_um << '\t'
              << result.trajectory.size() << '\t'
              << result.active_motor_identities << '\t'
              << result.peak_recruited_fibers << '\n';
    for (std::size_t index = 0; index < fixture.neuron_count; ++index) {
      std::cout << "neuron\t" << index << '\t'
                << fixture.neuron_labels[index] << '\t'
                << result.spike_counts[index] << '\t';
      if (std::isnan(result.first_spike_s[index])) std::cout << '-';
      else std::cout << result.first_spike_s[index];
      std::cout << '\n';
    }
    for (std::size_t index = 0; index < fixture.wave_segments.size(); ++index) {
      std::cout << "wave\t" << index << '\t'
                << fixture.wave_segments[index].id << '\t'
                << result.peak_activation[index] << '\t'
                << result.peak_shortening[index] << '\n';
    }
    for (std::size_t index = 0; index < result.trajectory.size(); ++index) {
      const oraclarva::TrajectoryFrame& frame = result.trajectory[index];
      std::cout << "frame\t" << index << '\t' << frame.time_s << '\t'
                << JoinNodes(frame.nodes_m) << '\t'
                << JoinDoubles(frame.body_activation) << '\n';
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
