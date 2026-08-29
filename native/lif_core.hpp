#pragma once

#include <cstddef>
#include <map>
#include <string>
#include <vector>

namespace oraclarva {

struct LIFConfig {
  double dt_s = 0.001;
  double tau_m_s = 0.020;
  double tau_exc_s = 0.005;
  double tau_inh_s = 0.010;
  double resistance_ohm = 100e6;
  double v_rest_v = -0.065;
  double v_reset_v = -0.065;
  double v_threshold_v = -0.050;
  double refractory_s = 0.002;
};

struct Synapse {
  std::size_t pre;
  std::size_t post;
  double current_a;
  bool inhibitory;
  int delay_steps;
};

struct ParityFixture {
  std::size_t neuron_count = 0;
  int steps = 0;
  LIFConfig config;
  std::vector<Synapse> synapses;
  std::map<int, std::map<std::size_t, double>> stimulus;
};

class SparseLIFNetwork {
 public:
  SparseLIFNetwork(
      std::size_t neuron_count,
      std::vector<Synapse> synapses,
      LIFConfig config);

  void Lesion(std::size_t neuron_id);
  std::vector<std::size_t> Step(
      const std::map<std::size_t, double>& external_current_a = {});

  const std::vector<double>& voltage_v() const { return voltage_v_; }
  const std::vector<double>& excitatory_current_a() const {
    return excitatory_current_a_;
  }
  const std::vector<double>& inhibitory_current_a() const {
    return inhibitory_current_a_;
  }

 private:
  void CheckNeuron(std::size_t neuron_id) const;
  void Deliver(const Synapse& synapse);

  std::size_t neuron_count_;
  LIFConfig config_;
  std::vector<double> voltage_v_;
  std::vector<double> excitatory_current_a_;
  std::vector<double> inhibitory_current_a_;
  std::vector<int> refractory_steps_;
  std::vector<bool> lesioned_;
  int step_index_ = 0;
  std::map<int, std::vector<Synapse>> pending_synapses_;
  std::vector<std::vector<Synapse>> outgoing_;
};

ParityFixture LoadParityFixture(const std::string& path);

}  // namespace oraclarva
