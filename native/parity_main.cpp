#include "lif_core.hpp"

#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

template <typename Value>
std::string Join(const std::vector<Value>& values) {
  if (values.empty()) return "-";
  std::ostringstream output;
  output << std::setprecision(17);
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index > 0) output << ',';
    output << values[index];
  }
  return output.str();
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc != 2 && argc != 4) {
      std::cerr << "usage: oraclarva-native-parity FIXTURE [--lesion NEURON]\n";
      return 2;
    }
    const oraclarva::ParityFixture fixture = oraclarva::LoadParityFixture(argv[1]);
    oraclarva::SparseLIFNetwork network(
        fixture.neuron_count, fixture.synapses, fixture.config);
    if (argc == 4) {
      if (std::string(argv[2]) != "--lesion") throw std::runtime_error("expected --lesion");
      network.Lesion(static_cast<std::size_t>(std::stoul(argv[3])));
    }
    std::cout << "metadata\tsteps\t" << fixture.steps << "\tneurons\t"
              << fixture.neuron_count << '\n';
    for (int step = 0; step < fixture.steps; ++step) {
      const auto external = fixture.stimulus.find(step);
      const std::vector<std::size_t> spikes = network.Step(
          external == fixture.stimulus.end()
              ? std::map<std::size_t, double>{}
              : external->second);
      std::cout << "frame\t" << step << '\t' << Join(spikes) << '\t'
                << Join(network.voltage_v()) << '\t'
                << Join(network.excitatory_current_a()) << '\t'
                << Join(network.inhibitory_current_a()) << '\n';
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
