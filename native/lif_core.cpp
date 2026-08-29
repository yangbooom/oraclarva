#include "lif_core.hpp"

#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace oraclarva {

namespace {

void SetConfigValue(LIFConfig& config, const std::string& key, double value) {
  if (key == "dt_s") config.dt_s = value;
  else if (key == "tau_m_s") config.tau_m_s = value;
  else if (key == "tau_exc_s") config.tau_exc_s = value;
  else if (key == "tau_inh_s") config.tau_inh_s = value;
  else if (key == "resistance_ohm") config.resistance_ohm = value;
  else if (key == "v_rest_v") config.v_rest_v = value;
  else if (key == "v_reset_v") config.v_reset_v = value;
  else if (key == "v_threshold_v") config.v_threshold_v = value;
  else if (key == "refractory_s") config.refractory_s = value;
  else throw std::runtime_error("unknown config key: " + key);
}

void ValidateConfig(const LIFConfig& config) {
  if (config.dt_s <= 0 || config.tau_m_s <= 0 || config.tau_exc_s <= 0 ||
      config.tau_inh_s <= 0 || config.resistance_ohm <= 0) {
    throw std::runtime_error("time constants, dt, and resistance must be positive");
  }
  if (config.refractory_s < 0 || config.v_threshold_v <= config.v_reset_v) {
    throw std::runtime_error("invalid refractory period or voltage threshold");
  }
}

}  // namespace

SparseLIFNetwork::SparseLIFNetwork(
    std::size_t neuron_count,
    std::vector<Synapse> synapses,
    LIFConfig config)
    : neuron_count_(neuron_count),
      config_(config),
      voltage_v_(neuron_count, config.v_rest_v),
      excitatory_current_a_(neuron_count, 0.0),
      inhibitory_current_a_(neuron_count, 0.0),
      refractory_steps_(neuron_count, 0),
      lesioned_(neuron_count, false),
      outgoing_(neuron_count) {
  if (neuron_count == 0) throw std::runtime_error("neuron_count must be positive");
  ValidateConfig(config_);
  for (const Synapse& synapse : synapses) {
    CheckNeuron(synapse.pre);
    CheckNeuron(synapse.post);
    if (synapse.current_a <= 0 || synapse.delay_steps < 0) {
      throw std::runtime_error("invalid synaptic current or delay");
    }
    outgoing_[synapse.pre].push_back(synapse);
  }
}

void SparseLIFNetwork::Lesion(std::size_t neuron_id) {
  CheckNeuron(neuron_id);
  lesioned_[neuron_id] = true;
  voltage_v_[neuron_id] = config_.v_reset_v;
  excitatory_current_a_[neuron_id] = 0.0;
  inhibitory_current_a_[neuron_id] = 0.0;
}

std::vector<std::size_t> SparseLIFNetwork::Step(
    const std::map<std::size_t, double>& external_current_a) {
  const auto pending = pending_synapses_.find(step_index_);
  if (pending != pending_synapses_.end()) {
    for (const Synapse& synapse : pending->second) Deliver(synapse);
    pending_synapses_.erase(pending);
  }
  for (const auto& [neuron_id, current] : external_current_a) {
    (void)current;
    CheckNeuron(neuron_id);
  }

  const double exc_decay = std::exp(-config_.dt_s / config_.tau_exc_s);
  const double inh_decay = std::exp(-config_.dt_s / config_.tau_inh_s);
  std::vector<std::size_t> spikes;
  for (std::size_t neuron_id = 0; neuron_id < neuron_count_; ++neuron_id) {
    excitatory_current_a_[neuron_id] *= exc_decay;
    inhibitory_current_a_[neuron_id] *= inh_decay;
    if (lesioned_[neuron_id]) continue;
    if (refractory_steps_[neuron_id] > 0) {
      --refractory_steps_[neuron_id];
      voltage_v_[neuron_id] = config_.v_reset_v;
      continue;
    }

    const auto external = external_current_a.find(neuron_id);
    const double external_a = external == external_current_a.end() ? 0.0 : external->second;
    const double total_current = excitatory_current_a_[neuron_id] -
        inhibitory_current_a_[neuron_id] + external_a;
    const double dv = config_.dt_s * (
        (config_.v_rest_v - voltage_v_[neuron_id]) +
        config_.resistance_ohm * total_current) / config_.tau_m_s;
    voltage_v_[neuron_id] += dv;
    if (voltage_v_[neuron_id] >= config_.v_threshold_v) spikes.push_back(neuron_id);
  }

  const int refractory = static_cast<int>(std::round(
      config_.refractory_s / config_.dt_s));
  for (const std::size_t neuron_id : spikes) {
    voltage_v_[neuron_id] = config_.v_reset_v;
    refractory_steps_[neuron_id] = refractory;
    for (const Synapse& synapse : outgoing_[neuron_id]) {
      if (synapse.delay_steps > 0) {
        pending_synapses_[step_index_ + synapse.delay_steps].push_back(synapse);
      } else {
        Deliver(synapse);
      }
    }
  }
  ++step_index_;
  return spikes;
}

void SparseLIFNetwork::CheckNeuron(std::size_t neuron_id) const {
  if (neuron_id >= neuron_count_) throw std::out_of_range("neuron outside network");
}

void SparseLIFNetwork::Deliver(const Synapse& synapse) {
  if (lesioned_[synapse.post]) return;
  if (synapse.inhibitory) inhibitory_current_a_[synapse.post] += synapse.current_a;
  else excitatory_current_a_[synapse.post] += synapse.current_a;
}

ParityFixture LoadParityFixture(const std::string& path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open parity fixture: " + path);
  ParityFixture fixture;
  std::string line;
  int line_number = 0;
  while (std::getline(input, line)) {
    ++line_number;
    if (line.empty() || line[0] == '#') continue;
    std::istringstream fields(line);
    std::string kind;
    fields >> kind;
    if (kind == "neuron_count") {
      fields >> fixture.neuron_count;
    } else if (kind == "steps") {
      fields >> fixture.steps;
    } else if (kind == "config") {
      std::string key;
      double value;
      fields >> key >> value;
      SetConfigValue(fixture.config, key, value);
    } else if (kind == "synapse") {
      Synapse synapse{};
      std::string synapse_kind;
      fields >> synapse.pre >> synapse.post >> synapse.current_a >>
          synapse_kind >> synapse.delay_steps;
      if (synapse_kind != "excitatory" && synapse_kind != "inhibitory") {
        throw std::runtime_error("invalid synapse kind at line " + std::to_string(line_number));
      }
      synapse.inhibitory = synapse_kind == "inhibitory";
      fixture.synapses.push_back(synapse);
    } else if (kind == "stimulus") {
      int step;
      std::size_t neuron_id;
      double current_a;
      fields >> step >> neuron_id >> current_a;
      fixture.stimulus[step][neuron_id] = current_a;
    } else {
      throw std::runtime_error("unknown fixture row at line " + std::to_string(line_number));
    }
    if (!fields) throw std::runtime_error("malformed fixture line " + std::to_string(line_number));
  }
  ValidateConfig(fixture.config);
  if (fixture.neuron_count == 0 || fixture.steps < 0) {
    throw std::runtime_error("fixture must declare positive neurons and nonnegative steps");
  }
  return fixture;
}

}  // namespace oraclarva
