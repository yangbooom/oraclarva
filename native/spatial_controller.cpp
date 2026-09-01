#include "spatial_controller.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <limits>
#include <map>
#include <stdexcept>
#include <utility>

namespace oraclarva {
namespace {

constexpr std::array<const char*, kSpatialChannelCount> kChannels{
    "left", "right", "dorsal", "ventral"};

std::vector<std::string> SplitTabs(const std::string& line) {
  std::vector<std::string> result;
  std::size_t start = 0;
  while (true) {
    const std::size_t separator = line.find('\t', start);
    result.push_back(line.substr(start, separator - start));
    if (separator == std::string::npos) return result;
    start = separator + 1;
  }
}

void RequireFields(
    const std::vector<std::string>& fields,
    std::size_t expected,
    int line_number) {
  if (fields.size() != expected) {
    throw std::runtime_error(
        "wrong spatial fixture field count at line "
        + std::to_string(line_number));
  }
}

std::size_t ChannelIndex(const std::string& value) {
  for (std::size_t index = 0; index < kChannels.size(); ++index) {
    if (value == kChannels[index]) return index;
  }
  throw std::runtime_error("unknown spatial channel: " + value);
}

std::pair<std::string, std::size_t> ParseSegmentChannel(
    const std::string& value) {
  const std::size_t separator = value.find(':');
  if (separator == std::string::npos
      || value.find(':', separator + 1) != std::string::npos) {
    throw std::runtime_error("spatial channel lesion must be SEGMENT:CHANNEL");
  }
  return {value.substr(0, separator), ChannelIndex(value.substr(separator + 1))};
}

void SetLIFConfig(LIFConfig& config, const std::string& key, double value) {
  if (key == "dt_s") config.dt_s = value;
  else if (key == "tau_m_s") config.tau_m_s = value;
  else if (key == "tau_exc_s") config.tau_exc_s = value;
  else if (key == "tau_inh_s") config.tau_inh_s = value;
  else if (key == "resistance_ohm") config.resistance_ohm = value;
  else if (key == "v_rest_v") config.v_rest_v = value;
  else if (key == "v_reset_v") config.v_reset_v = value;
  else if (key == "v_threshold_v") config.v_threshold_v = value;
  else if (key == "refractory_s") config.refractory_s = value;
  else throw std::runtime_error("unknown spatial LIF config: " + key);
}

void SetParameter(SpatialParameters& p, const std::string& key, double value) {
  if (key == "posterior_touch_current_a") p.posterior_touch_current_a = value;
  else if (key == "proprioceptor_min_strain") p.proprioceptor_min_strain = value;
  else if (key == "proprioceptor_min_shortening_rate_m_s") p.proprioceptor_min_shortening_rate_m_s = value;
  else if (key == "proprioceptor_current_gain_a_s_m") p.proprioceptor_current_gain_a_s_m = value;
  else if (key == "proprioceptor_max_current_a") p.proprioceptor_max_current_a = value;
  else if (key == "sensory_adaptation_tau_s") p.sensory_adaptation_tau_s = value;
  else if (key == "sensory_adaptation_fraction") p.sensory_adaptation_fraction = value;
  else if (key == "integrated_proprioception_enabled") p.integrated_proprioception_enabled = value;
  else if (key == "motor_excitation_tau_s") p.motor_excitation_tau_s = value;
  else if (key == "excitation_per_motor_spike") p.excitation_per_motor_spike = value;
  else if (key == "muscle_activation_excitation_threshold") p.muscle_activation_excitation_threshold = value;
  else if (key == "active_yaw_curvature_gain") p.active_yaw_curvature_gain = value;
  else if (key == "active_pitch_curvature_gain") p.active_pitch_curvature_gain = value;
  else if (key == "active_bending_stiffness_ratio") p.active_bending_stiffness_ratio = value;
  else if (key == "asymmetric_sensory_current_a") p.asymmetric_sensory_current_a = value;
  else if (key == "baseline_intensity") p.baseline_intensity = value;
  else if (key == "light_response_scale") p.light_response_scale = value;
  else if (key == "light_polarity") p.light_polarity = value;
  else if (key == "light_spatial_gain") p.light_spatial_gain = value;
  else if (key == "light_temporal_gain") p.light_temporal_gain = value;
  else if (key == "light_adaptation_tau_s") p.light_adaptation_tau_s = value;
  else if (key == "light_weight") p.light_weight = value;
  else throw std::runtime_error("unknown spatial parameter: " + key);
}

SpatialVec3 Add(const SpatialVec3& a, const SpatialVec3& b) {
  return {a.x + b.x, a.y + b.y, a.z + b.z};
}

SpatialVec3 Subtract(const SpatialVec3& a, const SpatialVec3& b) {
  return {a.x - b.x, a.y - b.y, a.z - b.z};
}

SpatialVec3 Multiply(const SpatialVec3& value, double scale) {
  return {value.x * scale, value.y * scale, value.z * scale};
}

double Dot(const SpatialVec3& a, const SpatialVec3& b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

SpatialVec3 Cross(const SpatialVec3& a, const SpatialVec3& b) {
  return {
      a.y * b.z - a.z * b.y,
      a.z * b.x - a.x * b.z,
      a.x * b.y - a.y * b.x};
}

double Norm(const SpatialVec3& value) {
  return std::sqrt(Dot(value, value));
}

SpatialVec3 Normalized(const SpatialVec3& value) {
  const double magnitude = Norm(value);
  return magnitude == 0.0
      ? SpatialVec3{1.0, 0.0, 0.0}
      : Multiply(value, 1.0 / magnitude);
}

double NodeWidth(const SpatialBodyState& body, std::size_t node) {
  double value = -std::numeric_limits<double>::infinity();
  if (node > 0) value = std::max(value, body.segments[node - 1].width_m);
  if (node < body.segments.size()) {
    value = std::max(value, body.segments[node].width_m);
  }
  return value;
}

double NodeHeight(const SpatialBodyState& body, std::size_t node) {
  double value = -std::numeric_limits<double>::infinity();
  if (node > 0) value = std::max(value, body.segments[node - 1].height_m);
  if (node < body.segments.size()) {
    value = std::max(value, body.segments[node].height_m);
  }
  return value;
}

SpatialVec3 NodeTangent(const SpatialBodyState& body, std::size_t node) {
  if (node == 0) {
    return Normalized(Subtract(body.nodes_m[1], body.nodes_m[0]));
  }
  if (node + 1 == body.nodes_m.size()) {
    return Normalized(Subtract(body.nodes_m.back(), body.nodes_m[node - 1]));
  }
  return Normalized(Subtract(body.nodes_m[node + 1], body.nodes_m[node - 1]));
}

std::array<SpatialVec3, 2> NodeFrame(
    const SpatialBodyState& body, std::size_t node) {
  const SpatialVec3 tangent = NodeTangent(body, node);
  SpatialVec3 lateral = Cross({0.0, 0.0, 1.0}, tangent);
  if (Norm(lateral) == 0.0) lateral = {0.0, 1.0, 0.0};
  else lateral = Normalized(lateral);
  return {lateral, Normalized(Cross(tangent, lateral))};
}

SpatialVec3 SurfacePosition(
    const SpatialBodyState& body,
    std::size_t node,
    std::size_t channel) {
  const auto frame = NodeFrame(body, node);
  if (channel < 2) {
    const double sign = channel == 0 ? -1.0 : 1.0;
    return Add(
        body.nodes_m[node],
        Multiply(frame[0], sign * NodeWidth(body, node) / 2.0));
  }
  const double sign = channel == 2 ? 1.0 : -1.0;
  return Add(
      body.nodes_m[node],
      Multiply(frame[1], sign * NodeHeight(body, node) / 2.0));
}

double RailLength(
    const SpatialBodyState& body,
    std::size_t segment,
    std::size_t channel) {
  return Norm(Subtract(
      SurfacePosition(body, segment + 1, channel),
      SurfacePosition(body, segment, channel)));
}

void ValidateBody(
    const SpatialFixture& fixture, const SpatialBodyState& body) {
  if (body.nodes_m.size() != fixture.body_segments.size() + 1
      || body.segments.size() != fixture.body_segments.size()) {
    throw std::runtime_error("spatial body structural count mismatch");
  }
  for (std::size_t index = 0; index < body.segments.size(); ++index) {
    if (body.segments[index].id != fixture.body_segments[index].id
        || std::abs(body.segments[index].rest_length_m
                    - fixture.body_segments[index].rest_length_m) > 1e-18
        || std::abs(body.segments[index].width_m
                    - fixture.body_segments[index].width_m) > 1e-18
        || std::abs(body.segments[index].height_m
                    - fixture.body_segments[index].height_m) > 1e-18) {
      throw std::runtime_error("spatial/repeat body geometry mismatch");
    }
  }
}

const SpatialWaveSegment& FindWave(
    const SpatialFixture& fixture, const std::string& id) {
  const auto found = std::find_if(
      fixture.wave_segments.begin(), fixture.wave_segments.end(),
      [&id](const SpatialWaveSegment& wave) { return wave.id == id; });
  if (found == fixture.wave_segments.end()) {
    throw std::runtime_error("unknown spatial wave segment: " + id);
  }
  return *found;
}

}  // namespace

SpatialFixture LoadSpatialFixture(const std::string& path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open spatial fixture: " + path);
  SpatialFixture fixture;
  std::string line;
  int line_number = 0;
  while (std::getline(input, line)) {
    ++line_number;
    if (line.empty() || line[0] == '#') continue;
    const auto fields = SplitTabs(line);
    const std::string& kind = fields[0];
    if (kind == "schema") {
      RequireFields(fields, 2, line_number);
      fixture.schema = fields[1];
    } else if (kind == "model_id") {
      RequireFields(fields, 2, line_number);
      fixture.model_id = fields[1];
    } else if (kind == "status") {
      RequireFields(fields, 2, line_number);
      fixture.status = fields[1];
    } else if (kind == "release_validated") {
      RequireFields(fields, 2, line_number);
      fixture.release_validated = fields[1] == "true";
    } else if (kind == "neuron_count") {
      RequireFields(fields, 2, line_number);
      fixture.neuron_count = std::stoul(fields[1]);
      fixture.neuron_labels.resize(fixture.neuron_count);
    } else if (kind == "synapse_count") {
      RequireFields(fields, 2, line_number);
      fixture.declared_synapse_count = std::stoul(fields[1]);
    } else if (kind == "touch_neuron") {
      RequireFields(fields, 3, line_number);
      fixture.touch_neuron[ChannelIndex(fields[1])] = std::stoul(fields[2]);
    } else if (kind == "asymmetry_neuron") {
      RequireFields(fields, 3, line_number);
      fixture.asymmetry_neuron[ChannelIndex(fields[1])] = std::stoul(fields[2]);
    } else if (kind == "config") {
      RequireFields(fields, 3, line_number);
      SetLIFConfig(fixture.lif_config, fields[1], std::stod(fields[2]));
    } else if (kind == "parameter") {
      RequireFields(fields, 3, line_number);
      SetParameter(fixture.parameters, fields[1], std::stod(fields[2]));
    } else if (kind == "neuron") {
      RequireFields(fields, 3, line_number);
      const std::size_t index = std::stoul(fields[1]);
      if (index >= fixture.neuron_labels.size()) {
        throw std::runtime_error("spatial neuron outside declared count");
      }
      fixture.neuron_labels[index] = fields[2];
    } else if (kind == "body_segment") {
      RequireFields(fields, 6, line_number);
      const std::size_t index = std::stoul(fields[1]);
      if (index != fixture.body_segments.size()) {
        throw std::runtime_error("spatial body segments must be contiguous");
      }
      fixture.body_segments.push_back({
          fields[2], std::stod(fields[3]), std::stod(fields[4]),
          std::stod(fields[5])});
    } else if (kind == "wave_segment") {
      RequireFields(fields, 22, line_number);
      const std::size_t index = std::stoul(fields[1]);
      if (index != fixture.wave_segments.size()) {
        throw std::runtime_error("spatial waves must be contiguous");
      }
      SpatialWaveSegment wave;
      wave.id = fields[2];
      wave.body_index = std::stoul(fields[3]);
      std::size_t field = 4;
      for (auto* values : {&wave.proprioceptor_neuron, &wave.premotor_neuron,
                           &wave.inhibitory_neuron, &wave.motor_neuron}) {
        for (std::size_t channel = 0; channel < kSpatialChannelCount; ++channel) {
          (*values)[channel] = std::stoul(fields[field++]);
        }
      }
      wave.rise_tau_s = std::stod(fields[field++]);
      wave.fall_tau_s = std::stod(fields[field]);
      fixture.wave_segments.push_back(wave);
    } else if (kind == "synapse") {
      RequireFields(fields, 6, line_number);
      if (fields[4] != "excitatory" && fields[4] != "inhibitory") {
        throw std::runtime_error("invalid spatial synapse kind");
      }
      fixture.synapses.push_back({
          std::stoul(fields[1]), std::stoul(fields[2]), std::stod(fields[3]),
          fields[4] == "inhibitory", std::stoi(fields[5])});
    } else {
      throw std::runtime_error(
          "unknown spatial fixture row at line " + std::to_string(line_number));
    }
  }
  if (fixture.schema != "spatial_environment_native_v1"
      || fixture.status != "research_approximation"
      || fixture.release_validated
      || fixture.neuron_count != kSpatialNeuronCount
      || fixture.declared_synapse_count != 188
      || fixture.synapses.size() != fixture.declared_synapse_count
      || fixture.body_segments.size() != 12
      || fixture.wave_segments.size() != 10) {
    throw std::runtime_error("spatial fixture structural/claim contract is invalid");
  }
  if (std::any_of(
          fixture.neuron_labels.begin(), fixture.neuron_labels.end(),
          [](const std::string& label) { return label.empty(); })) {
    throw std::runtime_error("spatial fixture has an unlabeled neuron");
  }
  return fixture;
}

struct SpatialEnvironmentController::Impl {
  const SpatialFixture& fixture;
  const SpatialParameters& p;
  SpatialControllerOptions options;
  SparseLIFNetwork network;
  std::vector<std::array<double, kSpatialChannelCount>> rail_rest;
  std::vector<std::array<double, kSpatialChannelCount>> previous_length;
  std::vector<std::array<double, kSpatialChannelCount>> proprio_adaptation;
  std::vector<std::array<double, kSpatialChannelCount>> excitation;
  std::vector<std::array<double, kSpatialChannelCount>> activation;
  std::array<double, kSpatialChannelCount> light_adapted{};
  bool light_adaptation_initialized = false;
  int step_index = 0;
  SpatialControllerFrame last;

  Impl(
      const SpatialFixture& fixture_value,
      const SpatialBodyState& body,
      SpatialControllerOptions options_value)
      : fixture(fixture_value),
        p(fixture.parameters),
        options(std::move(options_value)),
        network(fixture.neuron_count, fixture.synapses, fixture.lif_config),
        rail_rest(fixture.wave_segments.size()),
        previous_length(fixture.wave_segments.size()),
        proprio_adaptation(fixture.wave_segments.size()),
        excitation(fixture.wave_segments.size()),
        activation(fixture.wave_segments.size()) {
    ValidateBody(fixture, body);
    for (std::size_t wave = 0; wave < fixture.wave_segments.size(); ++wave) {
      for (std::size_t channel = 0; channel < kSpatialChannelCount; ++channel) {
        const double length = RailLength(
            body, fixture.wave_segments[wave].body_index, channel);
        rail_rest[wave][channel] = length;
        previous_length[wave][channel] = length;
      }
    }
    if (!options.sensory_lesion_channel.empty()) {
      const std::size_t channel = ChannelIndex(options.sensory_lesion_channel);
      network.Lesion(fixture.touch_neuron[channel]);
      network.Lesion(fixture.asymmetry_neuron[channel]);
    }
    if (!options.premotor_lesion_channel.empty()) {
      const auto [segment, channel] = ParseSegmentChannel(
          options.premotor_lesion_channel);
      network.Lesion(FindWave(fixture, segment).premotor_neuron[channel]);
    }
    if (!options.motor_lesion_channel.empty()) {
      const auto [segment, channel] = ParseSegmentChannel(
          options.motor_lesion_channel);
      network.Lesion(FindWave(fixture, segment).motor_neuron[channel]);
    }
    if (!options.muscle_lesion_channel.empty()) {
      const auto [segment, channel] = ParseSegmentChannel(
          options.muscle_lesion_channel);
      (void)channel;
      FindWave(fixture, segment);
    }
    last.spike_counts.assign(fixture.neuron_count, 0);
    last.yaw_activation.assign(fixture.body_segments.size(), {0.0, 0.0});
    last.pitch_activation.assign(fixture.body_segments.size(), {0.0, 0.0});
  }

  double SampleLight(
      const SpatialLightField& light,
      const SpatialVec3& position,
      double time_s) const {
    double value = light.value_at_origin_w_m2
        + Dot(Subtract(position, light.origin_m), light.gradient_w_m3)
        + light.temporal_rate_w_m2_s * time_s;
    return std::min(
        light.upper_bound_w_m2, std::max(light.lower_bound_w_m2, value));
  }

  SpatialControllerFrame Step(
      double time_s,
      const SpatialLightField& light,
      const SpatialBodyState& body) {
    ValidateBody(fixture, body);
    const double expected_time = step_index * fixture.lif_config.dt_s;
    if (!std::isfinite(time_s) || std::abs(time_s - expected_time) > 1e-12) {
      throw std::runtime_error("spatial controller time is not a fixed-step sequence");
    }
    const auto numeric = {
        light.origin_m.x, light.origin_m.y, light.origin_m.z,
        light.value_at_origin_w_m2,
        light.gradient_w_m3.x, light.gradient_w_m3.y, light.gradient_w_m3.z,
        light.temporal_rate_w_m2_s,
        light.lower_bound_w_m2, light.upper_bound_w_m2};
    if (std::any_of(numeric.begin(), numeric.end(),
                    [](double value) { return !std::isfinite(value); })
        || light.lower_bound_w_m2 > light.upper_bound_w_m2) {
      throw std::runtime_error("light field values must be finite and bounded");
    }

    SpatialControllerFrame frame;
    frame.spike_counts = last.spike_counts;
    frame.yaw_activation.assign(fixture.body_segments.size(), {0.0, 0.0});
    frame.pitch_activation.assign(fixture.body_segments.size(), {0.0, 0.0});
    std::array<double, kSpatialChannelCount> stimulus{};
    if (light.enabled) {
      double mean = 0.0;
      for (std::size_t channel = 0; channel < kSpatialChannelCount; ++channel) {
        frame.raw_light_w_m2[channel] = SampleLight(
            light, SurfacePosition(body, 0, channel), time_s);
        mean += frame.raw_light_w_m2[channel];
      }
      mean /= static_cast<double>(kSpatialChannelCount);
      if (!light_adaptation_initialized) {
        light_adapted = frame.raw_light_w_m2;
        light_adaptation_initialized = true;
      }
      const double coupling = 1.0 - std::exp(
          -fixture.lif_config.dt_s / p.light_adaptation_tau_s);
      for (std::size_t channel = 0; channel < kSpatialChannelCount; ++channel) {
        frame.adapted_light_w_m2[channel] = light_adapted[channel];
        frame.light_drive[channel] = p.light_weight * p.light_polarity * (
            p.light_spatial_gain
                * (frame.raw_light_w_m2[channel] - mean)
                / p.light_response_scale
            + p.light_temporal_gain
                * (frame.raw_light_w_m2[channel] - light_adapted[channel])
                / p.light_response_scale);
        stimulus[channel] = std::min(
            1.0, std::max(0.0, p.baseline_intensity + frame.light_drive[channel]));
        frame.receptor_current[channel] = stimulus[channel];
        light_adapted[channel] +=
            (frame.raw_light_w_m2[channel] - light_adapted[channel]) * coupling;
      }
    }

    std::map<std::size_t, double> external;
    if (light.enabled) {
      for (std::size_t channel = 0; channel < kSpatialChannelCount; ++channel) {
        if (stimulus[channel] != 0.0) {
          external[fixture.touch_neuron[channel]] =
              stimulus[channel] * p.posterior_touch_current_a;
        }
      }
      for (const auto pair : {std::array<std::size_t, 2>{0, 1},
                              std::array<std::size_t, 2>{2, 3}}) {
        const double difference = stimulus[pair[0]] - stimulus[pair[1]];
        if (difference != 0.0) {
          const std::size_t channel = difference > 0.0 ? pair[0] : pair[1];
          external[fixture.asymmetry_neuron[channel]] =
              std::abs(difference) * p.asymmetric_sensory_current_a;
        }
      }
    }

    if (p.integrated_proprioception_enabled > 0.5) {
      const double proprio_decay = std::exp(
          -fixture.lif_config.dt_s / p.sensory_adaptation_tau_s);
      for (std::size_t wave = 0; wave < fixture.wave_segments.size(); ++wave) {
        for (std::size_t channel = 0; channel < kSpatialChannelCount; ++channel) {
          const double length = RailLength(
              body, fixture.wave_segments[wave].body_index, channel);
          const double strain = std::max(
              0.0, 1.0 - length / rail_rest[wave][channel]);
          const double shortening_rate = std::max(
              0.0,
              (previous_length[wave][channel] - length)
                  / fixture.lif_config.dt_s);
          previous_length[wave][channel] = length;
          proprio_adaptation[wave][channel] *= proprio_decay;
          double drive = 0.0;
          if (strain >= p.proprioceptor_min_strain) {
            drive = std::min(
                p.proprioceptor_max_current_a,
                std::max(
                    0.0,
                    shortening_rate - p.proprioceptor_min_shortening_rate_m_s)
                    * p.proprioceptor_current_gain_a_s_m);
          }
          const double adapted = std::max(
              0.0, drive - proprio_adaptation[wave][channel]);
          if (adapted != 0.0) {
            external[
                fixture.wave_segments[wave].proprioceptor_neuron[channel]]
                = adapted;
            proprio_adaptation[wave][channel] +=
                drive * p.sensory_adaptation_fraction;
          }
        }
      }
    }

    const std::vector<std::size_t> spikes = network.Step(external);
    frame.last_step_spikes = spikes;
    std::vector<bool> spiked(fixture.neuron_count, false);
    for (const std::size_t neuron : spikes) {
      spiked[neuron] = true;
      ++frame.spike_counts[neuron];
    }
    const double excitation_decay = std::exp(
        -fixture.lif_config.dt_s / p.motor_excitation_tau_s);
    for (std::size_t wave = 0; wave < fixture.wave_segments.size(); ++wave) {
      const auto& definition = fixture.wave_segments[wave];
      for (std::size_t channel = 0; channel < kSpatialChannelCount; ++channel) {
        excitation[wave][channel] *= excitation_decay;
        if (spiked[definition.motor_neuron[channel]]) {
          excitation[wave][channel] += p.excitation_per_motor_spike;
        }
        const double target =
            excitation[wave][channel] >= p.muscle_activation_excitation_threshold
            ? 1.0 : 0.0;
        const double tau = target > activation[wave][channel]
            ? definition.rise_tau_s : definition.fall_tau_s;
        activation[wave][channel] +=
            (target - activation[wave][channel])
            * (1.0 - std::exp(-fixture.lif_config.dt_s / tau));
        activation[wave][channel] = std::min(
            1.0, std::max(0.0, activation[wave][channel]));
      }
      auto values = activation[wave];
      if (!options.muscle_lesion_channel.empty()) {
        const auto [segment, channel] = ParseSegmentChannel(
            options.muscle_lesion_channel);
        if (segment == definition.id) values[channel] = 0.0;
      }
      frame.yaw_activation[definition.body_index] = {values[0], values[1]};
      frame.pitch_activation[definition.body_index] = {values[2], values[3]};
    }
    for (std::size_t channel = 0; channel < kSpatialChannelCount; ++channel) {
      double peak = 0.0;
      for (const auto& row : activation) peak = std::max(peak, row[channel]);
      frame.channel_activation[channel] = peak;
    }
    ++step_index;
    last = frame;
    return frame;
  }
};

SpatialEnvironmentController::SpatialEnvironmentController(
    const SpatialFixture& fixture,
    const SpatialBodyState& initial_body,
    const SpatialControllerOptions& options)
    : impl_(std::make_unique<Impl>(fixture, initial_body, options)) {}

SpatialEnvironmentController::~SpatialEnvironmentController() = default;

SpatialControllerFrame SpatialEnvironmentController::Step(
    double time_s,
    const SpatialLightField& light,
    const SpatialBodyState& body) {
  return impl_->Step(time_s, light, body);
}

SpatialControllerFrame SpatialEnvironmentController::Snapshot() const {
  return impl_->last;
}

}  // namespace oraclarva
