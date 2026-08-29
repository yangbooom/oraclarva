#include "bilateral_core.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>
#include <utility>

namespace oraclarva {

namespace {

constexpr std::array<const char*, 2> kSides{"left", "right"};

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
        "wrong bilateral fixture field count at line "
        + std::to_string(line_number));
  }
}

std::size_t SideIndex(const std::string& side) {
  if (side == "left") return 0;
  if (side == "right") return 1;
  throw std::runtime_error("invalid bilateral side: " + side);
}

std::string ChannelKey(const std::string& segment, std::size_t side) {
  return segment + ":" + kSides.at(side);
}

std::pair<std::string, std::size_t> ParseChannel(const std::string& value) {
  const std::size_t separator = value.find(':');
  if (separator == std::string::npos || value.find(':', separator + 1) != std::string::npos) {
    throw std::runtime_error("bilateral channel must be SEGMENT:SIDE");
  }
  return {value.substr(0, separator), SideIndex(value.substr(separator + 1))};
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
  else throw std::runtime_error("unknown LIF config key: " + key);
}

void SetParameter(
    BilateralParameters& parameters,
    const std::string& key,
    double value) {
  if (key == "posterior_touch_current_a") parameters.posterior_touch_current_a = value;
  else if (key == "posterior_touch_duration_s") parameters.posterior_touch_duration_s = value;
  else if (key == "proprioceptor_min_strain") parameters.proprioceptor_min_strain = value;
  else if (key == "proprioceptor_min_shortening_rate_m_s") parameters.proprioceptor_min_shortening_rate_m_s = value;
  else if (key == "proprioceptor_current_gain_a_s_m") parameters.proprioceptor_current_gain_a_s_m = value;
  else if (key == "proprioceptor_max_current_a") parameters.proprioceptor_max_current_a = value;
  else if (key == "sensory_adaptation_tau_s") parameters.sensory_adaptation_tau_s = value;
  else if (key == "sensory_adaptation_fraction") parameters.sensory_adaptation_fraction = value;
  else if (key == "body_velocity_retention") parameters.body_velocity_retention = value;
  else if (key == "ground_negative_x_retention") parameters.ground_negative_x_retention = value;
  else if (key == "ground_positive_x_retention") parameters.ground_positive_x_retention = value;
  else if (key == "motor_excitation_tau_s") parameters.motor_excitation_tau_s = value;
  else if (key == "excitation_per_motor_spike") parameters.excitation_per_motor_spike = value;
  else if (key == "muscle_activation_excitation_threshold") parameters.muscle_activation_excitation_threshold = value;
  else if (key == "active_curvature_gain") parameters.active_curvature_gain = value;
  else if (key == "active_bending_stiffness_ratio") parameters.active_bending_stiffness_ratio = value;
  else if (key == "asymmetric_sensory_current_a") parameters.asymmetric_sensory_current_a = value;
  else if (key == "gravity_z_m_s2") parameters.gravity_z_m_s2 = value;
  else if (key == "ground_z_m") parameters.ground_z_m = value;
  else if (key == "body_iterations") parameters.body_iterations = static_cast<int>(value);
  else if (key == "instantaneous_stiffness_n_m") parameters.instantaneous_stiffness_n_m = value;
  else throw std::runtime_error("unknown bilateral parameter: " + key);
}

BilateralVec3 Add(const BilateralVec3& left, const BilateralVec3& right) {
  return {left.x + right.x, left.y + right.y, left.z + right.z};
}

BilateralVec3 Subtract(const BilateralVec3& left, const BilateralVec3& right) {
  return {left.x - right.x, left.y - right.y, left.z - right.z};
}

BilateralVec3 Multiply(const BilateralVec3& value, double scalar) {
  return {value.x * scalar, value.y * scalar, value.z * scalar};
}

double Dot(const BilateralVec3& left, const BilateralVec3& right) {
  return left.x * right.x + left.y * right.y + left.z * right.z;
}

double Norm(const BilateralVec3& value) {
  return std::sqrt(value.x * value.x + value.y * value.y + value.z * value.z);
}

struct Particle {
  BilateralVec3 position;
  BilateralVec3 previous_position;
  double inverse_mass;
};

class BilateralBody {
 public:
  BilateralBody(
      std::vector<BilateralBodySegment> geometry,
      double instantaneous_stiffness_n_m)
      : geometry_(std::move(geometry)),
        left_activation_(geometry_.size(), 0.0),
        right_activation_(geometry_.size(), 0.0),
        instantaneous_stiffness_n_m_(instantaneous_stiffness_n_m) {
    std::vector<double> node_masses(geometry_.size() + 1, 0.0);
    for (std::size_t index = 0; index < geometry_.size(); ++index) {
      node_masses[index] += geometry_[index].mass_kg / 2.0;
      node_masses[index + 1] += geometry_[index].mass_kg / 2.0;
    }
    double x = 0.0;
    for (std::size_t index = 0; index < node_masses.size(); ++index) {
      const double clearance = NodeClearance(index);
      const BilateralVec3 position{x, 0.0, clearance};
      particles_.push_back({position, position, 1.0 / node_masses[index]});
      if (index < geometry_.size()) {
        const double vertical_delta = NodeClearance(index + 1) - clearance;
        const double rest = geometry_[index].rest_length_m;
        if (std::abs(vertical_delta) >= rest) {
          throw std::runtime_error("cross-section profile is too steep");
        }
        x += std::sqrt(rest * rest - vertical_delta * vertical_delta);
      }
    }
  }

  double BilateralSegmentLength(std::size_t index, std::size_t side) const {
    const double sign = side == 0 ? -1.0 : 1.0;
    return Norm(Subtract(
        SideNodePosition(index + 1, sign),
        SideNodePosition(index, sign)));
  }

  void SetActivation(std::size_t index, std::size_t side, double activation) {
    if (activation < 0.0 || activation > 1.0) {
      throw std::runtime_error("bilateral body activation outside [0, 1]");
    }
    (side == 0 ? left_activation_ : right_activation_).at(index) = activation;
  }

  void Step(double dt_s, const BilateralParameters& parameters) {
    for (std::size_t index = 0; index < particles_.size(); ++index) {
      Particle& particle = particles_[index];
      BilateralVec3 velocity = Multiply(
          Subtract(particle.position, particle.previous_position),
          parameters.body_velocity_retention);
      const double clearance = NodeClearance(index);
      if (particle.position.z <= parameters.ground_z_m + clearance + 1e-15) {
        const BilateralVec3 tangent = NodeTangent(index);
        const BilateralVec3 lateral{-tangent.y, tangent.x, 0.0};
        const double tangential_speed = Dot(velocity, tangent);
        const double lateral_speed = Dot(velocity, lateral);
        const double tangential_retention = tangential_speed < 0.0
            ? parameters.ground_negative_x_retention
            : parameters.ground_positive_x_retention;
        const BilateralVec3 planar = Add(
            Multiply(tangent, tangential_speed * tangential_retention),
            Multiply(
                lateral,
                lateral_speed * std::min(
                    parameters.ground_negative_x_retention,
                    parameters.ground_positive_x_retention)));
        velocity = {planar.x, planar.y, velocity.z};
      }
      const BilateralVec3 old_position = particle.position;
      particle.position = Add(
          Add(particle.position, velocity),
          {0.0, 0.0, parameters.gravity_z_m_s2 * dt_s * dt_s});
      particle.previous_position = old_position;
      if (particle.position.z < parameters.ground_z_m + clearance) {
        particle.position.z = parameters.ground_z_m + clearance;
      }
    }

    const double compliance = 1.0 / instantaneous_stiffness_n_m_;
    const double alpha = compliance / (dt_s * dt_s);
    const double bending_alpha = compliance
        / parameters.active_bending_stiffness_ratio / (dt_s * dt_s);
    for (int iteration = 0; iteration < parameters.body_iterations; ++iteration) {
      for (std::size_t index = 0; index < geometry_.size(); ++index) {
        Particle& left = particles_[index];
        Particle& right = particles_[index + 1];
        const BilateralVec3 delta = Subtract(right.position, left.position);
        const double distance = Norm(delta);
        if (distance == 0.0) continue;
        const double aggregate_activation =
            (left_activation_[index] + right_activation_[index]) / 2.0;
        const double target = geometry_[index].rest_length_m * (
            1.0
            - geometry_[index].maximum_shortening_fraction
            * aggregate_activation);
        const double constraint = distance - target;
        const double denominator = left.inverse_mass + right.inverse_mass + alpha;
        const double lagrange = -constraint / denominator;
        const BilateralVec3 direction = Multiply(delta, 1.0 / distance);
        left.position = Subtract(
            left.position, Multiply(direction, left.inverse_mass * lagrange));
        right.position = Add(
            right.position, Multiply(direction, right.inverse_mass * lagrange));
      }
      for (std::size_t index = 1; index + 1 < particles_.size(); ++index) {
        Particle& left = particles_[index - 1];
        Particle& middle = particles_[index];
        Particle& right = particles_[index + 1];
        const double differential = 0.5 * (
            left_activation_[index - 1] - right_activation_[index - 1]
            + left_activation_[index] - right_activation_[index]);
        const double mean_rest_length = 0.5 * (
            geometry_[index - 1].rest_length_m
            + geometry_[index].rest_length_m);
        const double target_offset = parameters.active_curvature_gain
            * mean_rest_length * differential;
        const BilateralVec3 span = Subtract(right.position, left.position);
        const double planar_span = std::sqrt(
            span.x * span.x + span.y * span.y);
        if (planar_span == 0.0) continue;
        const BilateralVec3 normal{
            -span.y / planar_span, span.x / planar_span, 0.0};
        const BilateralVec3 midpoint = Multiply(
            Add(left.position, right.position), 0.5);
        const double constraint = Dot(
            Subtract(middle.position, midpoint), normal) - target_offset;
        const double denominator = 0.25 * left.inverse_mass
            + middle.inverse_mass + 0.25 * right.inverse_mass + bending_alpha;
        const double lagrange = -constraint / denominator;
        left.position = Add(
            left.position,
            Multiply(normal, -0.5 * left.inverse_mass * lagrange));
        middle.position = Add(
            middle.position,
            Multiply(normal, middle.inverse_mass * lagrange));
        right.position = Add(
            right.position,
            Multiply(normal, -0.5 * right.inverse_mass * lagrange));
      }
    }
  }

  std::array<double, 2> CenterXY() const {
    double x = 0.0;
    double y = 0.0;
    for (const Particle& particle : particles_) {
      x += particle.position.x;
      y += particle.position.y;
    }
    const double count = static_cast<double>(particles_.size());
    return {x / count, y / count};
  }

  std::vector<BilateralVec3> Positions() const {
    std::vector<BilateralVec3> result;
    result.reserve(particles_.size());
    for (const Particle& particle : particles_) result.push_back(particle.position);
    return result;
  }

 private:
  double NodeClearance(std::size_t node_index) const {
    double clearance = -std::numeric_limits<double>::infinity();
    if (node_index > 0) {
      clearance = std::max(clearance, geometry_[node_index - 1].height_m / 2.0);
    }
    if (node_index < geometry_.size()) {
      clearance = std::max(clearance, geometry_[node_index].height_m / 2.0);
    }
    return clearance;
  }

  double NodeWidth(std::size_t node_index) const {
    double width = -std::numeric_limits<double>::infinity();
    if (node_index > 0) {
      width = std::max(width, geometry_[node_index - 1].width_m);
    }
    if (node_index < geometry_.size()) {
      width = std::max(width, geometry_[node_index].width_m);
    }
    return width;
  }

  BilateralVec3 NodeTangent(std::size_t node_index) const {
    BilateralVec3 delta{};
    if (node_index == 0) {
      delta = Subtract(particles_[1].position, particles_[0].position);
    } else if (node_index + 1 == particles_.size()) {
      delta = Subtract(particles_.back().position, particles_[particles_.size() - 2].position);
    } else {
      delta = Subtract(
          particles_[node_index + 1].position,
          particles_[node_index - 1].position);
    }
    const double magnitude = std::sqrt(delta.x * delta.x + delta.y * delta.y);
    if (magnitude == 0.0) return {1.0, 0.0, 0.0};
    return {delta.x / magnitude, delta.y / magnitude, 0.0};
  }

  BilateralVec3 SideNodePosition(std::size_t node_index, double sign) const {
    const BilateralVec3 tangent = NodeTangent(node_index);
    const BilateralVec3 normal{-tangent.y, tangent.x, 0.0};
    return Add(
        particles_[node_index].position,
        Multiply(normal, sign * NodeWidth(node_index) / 2.0));
  }

  std::vector<BilateralBodySegment> geometry_;
  std::vector<double> left_activation_;
  std::vector<double> right_activation_;
  double instantaneous_stiffness_n_m_;
  std::vector<Particle> particles_;
};

const BilateralWaveSegment& FindWave(
    const std::vector<BilateralWaveSegment>& waves,
    const std::string& id) {
  const auto found = std::find_if(
      waves.begin(), waves.end(),
      [&id](const BilateralWaveSegment& wave) { return wave.id == id; });
  if (found == waves.end()) throw std::runtime_error("unknown wave segment: " + id);
  return *found;
}

}  // namespace

BilateralFixture LoadBilateralFixture(const std::string& path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open bilateral fixture: " + path);
  BilateralFixture fixture;
  std::string line;
  int line_number = 0;
  while (std::getline(input, line)) {
    ++line_number;
    if (line.empty() || line[0] == '#') continue;
    const std::vector<std::string> fields = SplitTabs(line);
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
    } else if (kind == "steps") {
      RequireFields(fields, 2, line_number);
      fixture.steps = std::stoi(fields[1]);
    } else if (kind == "sample_stride") {
      RequireFields(fields, 2, line_number);
      fixture.sample_stride = std::stoi(fields[1]);
    } else if (kind == "touch_neuron") {
      RequireFields(fields, 3, line_number);
      fixture.touch_neuron[SideIndex(fields[1])] = std::stoul(fields[2]);
    } else if (kind == "asymmetry_neuron") {
      RequireFields(fields, 3, line_number);
      fixture.asymmetry_neuron[SideIndex(fields[1])] = std::stoul(fields[2]);
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
        throw std::runtime_error("neuron row outside declared count");
      }
      fixture.neuron_labels[index] = fields[2];
    } else if (kind == "body_segment") {
      RequireFields(fields, 8, line_number);
      const std::size_t index = std::stoul(fields[1]);
      if (index != fixture.body_segments.size()) {
        throw std::runtime_error("body segments must be contiguous");
      }
      fixture.body_segments.push_back({
          fields[2], std::stod(fields[3]), std::stod(fields[4]),
          std::stod(fields[5]), std::stod(fields[6]), std::stod(fields[7])});
    } else if (kind == "wave_segment") {
      RequireFields(fields, 14, line_number);
      const std::size_t index = std::stoul(fields[1]);
      if (index != fixture.wave_segments.size()) {
        throw std::runtime_error("wave segments must be contiguous");
      }
      fixture.wave_segments.push_back({
          fields[2], std::stoul(fields[3]),
          {std::stoul(fields[4]), std::stoul(fields[5])},
          {std::stoul(fields[6]), std::stoul(fields[7])},
          {std::stoul(fields[8]), std::stoul(fields[9])},
          {std::stoul(fields[10]), std::stoul(fields[11])},
          std::stod(fields[12]), std::stod(fields[13])});
    } else if (kind == "motor_identity") {
      RequireFields(fields, 5, line_number);
      fixture.motor_identities[fields[1] + ":" + fields[2]].push_back(
          std::stoul(fields[3]));
    } else if (kind == "muscle_proxy") {
      RequireFields(fields, 4, line_number);
      fixture.muscle_proxy_counts[fields[1] + ":" + fields[2]] =
          std::stoi(fields[3]);
    } else if (kind == "synapse") {
      RequireFields(fields, 6, line_number);
      if (fields[4] != "excitatory" && fields[4] != "inhibitory") {
        throw std::runtime_error("invalid synapse kind");
      }
      fixture.synapses.push_back({
          std::stoul(fields[1]), std::stoul(fields[2]), std::stod(fields[3]),
          fields[4] == "inhibitory", std::stoi(fields[5])});
    } else {
      throw std::runtime_error(
          "unknown bilateral fixture row at line " + std::to_string(line_number));
    }
  }

  if (fixture.schema != "bilateral_closed_loop_native_v1"
      || fixture.status != "research_approximation" || fixture.release_validated) {
    throw std::runtime_error("bilateral fixture claim boundary is invalid");
  }
  if (fixture.neuron_count != 126 || fixture.neuron_labels.size() != 126
      || fixture.body_segments.size() != 12 || fixture.wave_segments.size() != 8
      || fixture.synapses.size() != 130 || fixture.steps <= 0
      || fixture.sample_stride <= 0) {
    throw std::runtime_error("bilateral fixture structural contract is invalid");
  }
  if (std::any_of(
          fixture.neuron_labels.begin(), fixture.neuron_labels.end(),
          [](const std::string& label) { return label.empty(); })) {
    throw std::runtime_error("bilateral fixture has an unlabeled neuron");
  }
  for (std::size_t side = 0; side < 2; ++side) {
    if (fixture.motor_identities[ChannelKey("A1", side)].size() != 28
        || fixture.motor_identities[ChannelKey("A2", side)].size() != 1) {
      throw std::runtime_error("bilateral motor identity coverage is not 28/1 per side");
    }
  }
  return fixture;
}

BilateralOutput RunBilateral(
    const BilateralFixture& fixture,
    const BilateralOptions& options) {
  if (options.left_stimulus < 0.0 || options.left_stimulus > 1.0
      || options.right_stimulus < 0.0 || options.right_stimulus > 1.0) {
    throw std::runtime_error("bilateral stimulus must be in [0, 1]");
  }
  const BilateralParameters& parameters = fixture.parameters;
  const double dt_s = fixture.lif_config.dt_s;
  SparseLIFNetwork network(
      fixture.neuron_count, fixture.synapses, fixture.lif_config);
  if (!options.premotor_lesion.empty()) {
    const auto [segment, side] = ParseChannel(options.premotor_lesion);
    network.Lesion(FindWave(fixture.wave_segments, segment).premotor_neuron[side]);
  }
  if (!options.motor_identity_lesion.empty()) {
    const auto identities = fixture.motor_identities.find(options.motor_identity_lesion);
    if (identities == fixture.motor_identities.end()) {
      throw std::runtime_error("unknown bilateral motor identity lesion channel");
    }
    for (const std::size_t neuron : identities->second) network.Lesion(neuron);
  }
  if (!options.muscle_lesion.empty()
      && fixture.muscle_proxy_counts.count(options.muscle_lesion) == 0) {
    throw std::runtime_error("bilateral muscle lesion outside identity proxy coverage");
  }

  BilateralBody body(
      fixture.body_segments, parameters.instantaneous_stiffness_n_m);
  const std::size_t wave_count = fixture.wave_segments.size();
  std::vector<std::array<double, 2>> excitation(wave_count, {0.0, 0.0});
  std::vector<std::array<double, 2>> activation(wave_count, {0.0, 0.0});
  std::vector<std::array<double, 2>> adaptation(wave_count, {0.0, 0.0});
  std::vector<std::array<double, 2>> previous_length(wave_count, {0.0, 0.0});
  std::vector<double> left_body_activation(fixture.body_segments.size(), 0.0);
  std::vector<double> right_body_activation(fixture.body_segments.size(), 0.0);
  BilateralOutput output;
  output.spike_counts.assign(fixture.neuron_count, 0);
  output.first_spike_s.assign(
      fixture.neuron_count, std::numeric_limits<double>::quiet_NaN());
  output.peak_activation.assign(wave_count, {0.0, 0.0});
  output.peak_shortening.assign(wave_count, {0.0, 0.0});
  std::vector<bool> active_identity(fixture.neuron_count, false);
  std::vector<bool> is_motor_identity(fixture.neuron_count, false);
  for (const auto& entry : fixture.motor_identities) {
    for (const std::size_t neuron : entry.second) is_motor_identity[neuron] = true;
  }
  for (std::size_t index = 0; index < wave_count; ++index) {
    for (std::size_t side = 0; side < 2; ++side) {
      previous_length[index][side] = body.BilateralSegmentLength(
          fixture.wave_segments[index].body_index, side);
    }
  }
  const std::vector<std::array<double, 2>> rail_rest = previous_length;
  const std::array<double, 2> initial_center = body.CenterXY();
  output.trajectory.push_back({
      0.0, body.Positions(), left_body_activation, right_body_activation});
  const double adaptation_decay = std::exp(
      -dt_s / parameters.sensory_adaptation_tau_s);
  const double excitation_decay = std::exp(
      -dt_s / parameters.motor_excitation_tau_s);
  const std::array<double, 2> stimulus{
      options.left_stimulus, options.right_stimulus};

  for (int step = 0; step < fixture.steps; ++step) {
    const double time_s = static_cast<double>(step) * dt_s;
    std::map<std::size_t, double> external;
    if (time_s < parameters.posterior_touch_duration_s) {
      for (std::size_t side = 0; side < 2; ++side) {
        if (stimulus[side] != 0.0) {
          external[fixture.touch_neuron[side]] =
              stimulus[side] * parameters.posterior_touch_current_a;
        }
      }
      const double difference = stimulus[0] - stimulus[1];
      if (difference != 0.0) {
        const std::size_t side = difference > 0.0 ? 0 : 1;
        external[fixture.asymmetry_neuron[side]] =
            std::abs(difference) * parameters.asymmetric_sensory_current_a;
      }
    }
    for (std::size_t index = 0; index < wave_count; ++index) {
      const BilateralWaveSegment& wave = fixture.wave_segments[index];
      for (std::size_t side = 0; side < 2; ++side) {
        const double length = body.BilateralSegmentLength(wave.body_index, side);
        const double strain = std::max(
            0.0, 1.0 - length / rail_rest[index][side]);
        const double shortening_rate = std::max(
            0.0, (previous_length[index][side] - length) / dt_s);
        previous_length[index][side] = length;
        adaptation[index][side] *= adaptation_decay;
        double drive = 0.0;
        if (strain >= parameters.proprioceptor_min_strain) {
          const double excess_rate = std::max(
              0.0,
              shortening_rate - parameters.proprioceptor_min_shortening_rate_m_s);
          drive = std::min(
              parameters.proprioceptor_max_current_a,
              excess_rate * parameters.proprioceptor_current_gain_a_s_m);
        }
        const double adapted_drive = std::max(
            0.0, drive - adaptation[index][side]);
        if (adapted_drive != 0.0) {
          external[wave.proprioceptor_neuron[side]] = adapted_drive;
          adaptation[index][side] +=
              drive * parameters.sensory_adaptation_fraction;
        }
        output.peak_shortening[index][side] = std::max(
            output.peak_shortening[index][side], strain);
      }
    }

    const std::vector<std::size_t> spikes = network.Step(external);
    std::vector<bool> spiked(fixture.neuron_count, false);
    for (const std::size_t neuron : spikes) {
      spiked[neuron] = true;
      ++output.spike_counts[neuron];
      if (std::isnan(output.first_spike_s[neuron])) {
        output.first_spike_s[neuron] = time_s;
      }
      if (is_motor_identity[neuron]) active_identity[neuron] = true;
    }

    for (std::size_t index = 0; index < wave_count; ++index) {
      const BilateralWaveSegment& wave = fixture.wave_segments[index];
      for (std::size_t side = 0; side < 2; ++side) {
        excitation[index][side] *= excitation_decay;
        if (wave.id == "A1") {
          const std::vector<std::size_t>& identities =
              fixture.motor_identities.at(ChannelKey("A1", side));
          int identity_spikes = 0;
          for (const std::size_t neuron : identities) {
            if (spiked[neuron]) ++identity_spikes;
          }
          excitation[index][side] += parameters.excitation_per_motor_spike
              * static_cast<double>(identity_spikes)
              / static_cast<double>(identities.size());
        } else if (spiked[wave.motor_neuron[side]]) {
          excitation[index][side] += parameters.excitation_per_motor_spike;
        }
        const double target = excitation[index][side]
                >= parameters.muscle_activation_excitation_threshold
            ? 1.0
            : 0.0;
        const double tau = target > activation[index][side]
            ? wave.rise_tau_s
            : wave.fall_tau_s;
        const double coupling = 1.0 - std::exp(-dt_s / tau);
        activation[index][side] +=
            (target - activation[index][side]) * coupling;
        activation[index][side] = std::min(
            1.0, std::max(0.0, activation[index][side]));
        output.peak_activation[index][side] = std::max(
            output.peak_activation[index][side], activation[index][side]);
      }
    }

    std::fill(left_body_activation.begin(), left_body_activation.end(), 0.0);
    std::fill(right_body_activation.begin(), right_body_activation.end(), 0.0);
    int recruited_fibers = 0;
    for (std::size_t index = 0; index < wave_count; ++index) {
      const BilateralWaveSegment& wave = fixture.wave_segments[index];
      for (std::size_t side = 0; side < 2; ++side) {
        double applied = activation[index][side];
        const std::string channel = ChannelKey(wave.id, side);
        const auto proxy = fixture.muscle_proxy_counts.find(channel);
        if (proxy != fixture.muscle_proxy_counts.end()) {
          if (options.muscle_lesion == channel) applied = 0.0;
          if (applied > 0.0) recruited_fibers += proxy->second;
        }
        (side == 0 ? left_body_activation : right_body_activation)[wave.body_index]
            = applied;
      }
    }
    output.peak_recruited_fibers = std::max(
        output.peak_recruited_fibers, recruited_fibers);
    for (std::size_t index = 0; index < fixture.body_segments.size(); ++index) {
      body.SetActivation(index, 0, left_body_activation[index]);
      body.SetActivation(index, 1, right_body_activation[index]);
    }
    body.Step(dt_s, parameters);
    for (const BilateralVec3& position : body.Positions()) {
      output.maximum_abs_lateral_um = std::max(
          output.maximum_abs_lateral_um, std::abs(position.y) * 1e6);
    }
    if ((step + 1) % fixture.sample_stride == 0 || step + 1 == fixture.steps) {
      output.trajectory.push_back({
          static_cast<double>(step + 1) * dt_s,
          body.Positions(), left_body_activation, right_body_activation});
    }
  }

  const std::array<double, 2> final_center = body.CenterXY();
  output.displacement_x_um = (final_center[0] - initial_center[0]) * 1e6;
  output.displacement_y_um = (final_center[1] - initial_center[1]) * 1e6;
  const std::vector<BilateralVec3> final_positions = body.Positions();
  const BilateralVec3 axis = Subtract(final_positions.back(), final_positions.front());
  output.heading_change_deg = std::atan2(axis.y, axis.x)
      * 180.0 / 3.14159265358979323846;
  output.active_motor_identities = static_cast<int>(std::count(
      active_identity.begin(), active_identity.end(), true));
  return output;
}

}  // namespace oraclarva
