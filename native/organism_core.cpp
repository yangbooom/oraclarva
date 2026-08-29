#include "organism_core.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace oraclarva {

namespace {

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
    throw std::runtime_error("wrong field count at line " + std::to_string(line_number));
  }
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
    ClosedLoopParameters& parameters,
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
  else if (key == "gravity_z_m_s2") parameters.gravity_z_m_s2 = value;
  else if (key == "ground_z_m") parameters.ground_z_m = value;
  else if (key == "body_iterations") parameters.body_iterations = static_cast<int>(value);
  else if (key == "instantaneous_stiffness_n_m") parameters.instantaneous_stiffness_n_m = value;
  else throw std::runtime_error("unknown closed-loop parameter: " + key);
}

Vec3 Add(const Vec3& left, const Vec3& right) {
  return {left.x + right.x, left.y + right.y, left.z + right.z};
}

Vec3 Subtract(const Vec3& left, const Vec3& right) {
  return {left.x - right.x, left.y - right.y, left.z - right.z};
}

Vec3 Multiply(const Vec3& value, double scalar) {
  return {value.x * scalar, value.y * scalar, value.z * scalar};
}

double Norm(const Vec3& value) {
  return std::sqrt(value.x * value.x + value.y * value.y + value.z * value.z);
}

struct Particle {
  Vec3 position;
  Vec3 previous_position;
  double inverse_mass;
};

class NativeBody {
 public:
  NativeBody(
      std::vector<BodySegment> geometry,
      double instantaneous_stiffness_n_m)
      : geometry_(std::move(geometry)),
        activations_(geometry_.size(), 0.0),
        instantaneous_stiffness_n_m_(instantaneous_stiffness_n_m) {
    std::vector<double> node_masses(geometry_.size() + 1, 0.0);
    for (std::size_t index = 0; index < geometry_.size(); ++index) {
      node_masses[index] += geometry_[index].mass_kg / 2.0;
      node_masses[index + 1] += geometry_[index].mass_kg / 2.0;
    }
    double x = 0.0;
    for (std::size_t index = 0; index < node_masses.size(); ++index) {
      const double clearance = NodeClearance(index);
      const Vec3 position{x, 0.0, clearance};
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

  double SegmentLength(std::size_t index) const {
    return Norm(Subtract(particles_.at(index + 1).position, particles_.at(index).position));
  }

  void SetActivation(std::size_t index, double activation) {
    if (activation < 0.0 || activation > 1.0) {
      throw std::runtime_error("body activation outside [0, 1]");
    }
    activations_.at(index) = activation;
  }

  void Step(double dt_s, const ClosedLoopParameters& parameters) {
    for (std::size_t index = 0; index < particles_.size(); ++index) {
      Particle& particle = particles_[index];
      Vec3 velocity = Multiply(
          Subtract(particle.position, particle.previous_position),
          parameters.body_velocity_retention);
      const double clearance = NodeClearance(index);
      if (particle.position.z <= parameters.ground_z_m + clearance + 1e-15) {
        const double tangential_retention = velocity.x < 0.0
            ? parameters.ground_negative_x_retention
            : parameters.ground_positive_x_retention;
        velocity = {
            velocity.x * tangential_retention,
            velocity.y * std::min(
                parameters.ground_negative_x_retention,
                parameters.ground_positive_x_retention),
            velocity.z};
      }
      const Vec3 old_position = particle.position;
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
    for (int iteration = 0; iteration < parameters.body_iterations; ++iteration) {
      for (std::size_t index = 0; index < geometry_.size(); ++index) {
        Particle& left = particles_[index];
        Particle& right = particles_[index + 1];
        const Vec3 delta = Subtract(right.position, left.position);
        const double distance = Norm(delta);
        if (distance == 0.0) continue;
        const double target = geometry_[index].rest_length_m * (
            1.0 - geometry_[index].maximum_shortening_fraction * activations_[index]);
        const double constraint = distance - target;
        const double denominator = left.inverse_mass + right.inverse_mass + alpha;
        const double lagrange = -constraint / denominator;
        const Vec3 direction = Multiply(delta, 1.0 / distance);
        left.position = Subtract(
            left.position,
            Multiply(direction, left.inverse_mass * lagrange));
        right.position = Add(
            right.position,
            Multiply(direction, right.inverse_mass * lagrange));
      }
    }
  }

  double CenterX() const {
    double sum = 0.0;
    for (const Particle& particle : particles_) sum += particle.position.x;
    return sum / static_cast<double>(particles_.size());
  }

  std::vector<Vec3> Positions() const {
    std::vector<Vec3> result;
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

  std::vector<BodySegment> geometry_;
  std::vector<double> activations_;
  double instantaneous_stiffness_n_m_;
  std::vector<Particle> particles_;
};

const WaveSegment& FindWave(
    const std::vector<WaveSegment>& waves,
    const std::string& id) {
  const auto found = std::find_if(
      waves.begin(), waves.end(),
      [&id](const WaveSegment& wave) { return wave.id == id; });
  if (found == waves.end()) throw std::runtime_error("unknown wave segment: " + id);
  return *found;
}

}  // namespace

ClosedLoopFixture LoadClosedLoopFixture(const std::string& path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open closed-loop fixture: " + path);
  ClosedLoopFixture fixture;
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
      RequireFields(fields, 2, line_number);
      fixture.touch_neuron = std::stoul(fields[1]);
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
      RequireFields(fields, 10, line_number);
      const std::size_t index = std::stoul(fields[1]);
      if (index != fixture.wave_segments.size()) {
        throw std::runtime_error("wave segments must be contiguous");
      }
      fixture.wave_segments.push_back({
          fields[2], std::stoul(fields[3]), std::stoul(fields[4]),
          std::stoul(fields[5]), std::stoul(fields[6]), std::stoul(fields[7]),
          std::stod(fields[8]), std::stod(fields[9])});
    } else if (kind == "motor_identity") {
      RequireFields(fields, 4, line_number);
      fixture.motor_identities[fields[1]].push_back(std::stoul(fields[2]));
    } else if (kind == "muscle_proxy") {
      RequireFields(fields, 3, line_number);
      fixture.muscle_proxy_counts[fields[1]] = std::stoi(fields[2]);
    } else if (kind == "synapse") {
      RequireFields(fields, 6, line_number);
      if (fields[4] != "excitatory" && fields[4] != "inhibitory") {
        throw std::runtime_error("invalid synapse kind");
      }
      fixture.synapses.push_back({
          std::stoul(fields[1]), std::stoul(fields[2]), std::stod(fields[3]),
          fields[4] == "inhibitory", std::stoi(fields[5])});
    } else {
      throw std::runtime_error("unknown fixture row at line " + std::to_string(line_number));
    }
  }

  if (fixture.schema != "closed_loop_native_v1" ||
      fixture.status != "research_approximation" || fixture.release_validated) {
    throw std::runtime_error("closed-loop fixture claim boundary is invalid");
  }
  if (fixture.neuron_count != 91 || fixture.neuron_labels.size() != 91 ||
      fixture.body_segments.size() != 12 || fixture.wave_segments.size() != 8 ||
      fixture.synapses.size() != 90 || fixture.steps <= 0 || fixture.sample_stride <= 0) {
    throw std::runtime_error("closed-loop fixture structural contract is invalid");
  }
  if (std::any_of(
          fixture.neuron_labels.begin(), fixture.neuron_labels.end(),
          [](const std::string& label) { return label.empty(); })) {
    throw std::runtime_error("closed-loop fixture has an unlabeled neuron");
  }
  if (fixture.motor_identities["A1"].size() != 56 ||
      fixture.motor_identities["A2"].size() != 2) {
    throw std::runtime_error("motor identity coverage is not 56 A1 plus 2 A2");
  }
  return fixture;
}

ClosedLoopOutput RunClosedLoop(
    const ClosedLoopFixture& fixture,
    const ClosedLoopOptions& options) {
  const ClosedLoopParameters& parameters = fixture.parameters;
  const double dt_s = fixture.lif_config.dt_s;
  SparseLIFNetwork network(
      fixture.neuron_count, fixture.synapses, fixture.lif_config);
  if (!options.premotor_lesion.empty()) {
    network.Lesion(FindWave(fixture.wave_segments, options.premotor_lesion).premotor_neuron);
  }
  if (!options.motor_identity_lesion.empty()) {
    const auto identities = fixture.motor_identities.find(options.motor_identity_lesion);
    if (identities == fixture.motor_identities.end()) {
      throw std::runtime_error("unknown motor identity lesion segment");
    }
    for (const std::size_t neuron : identities->second) network.Lesion(neuron);
  }
  if (!options.muscle_lesion.empty() &&
      fixture.muscle_proxy_counts.count(options.muscle_lesion) == 0) {
    throw std::runtime_error("muscle lesion outside identity proxy coverage");
  }

  NativeBody body(
      fixture.body_segments,
      parameters.instantaneous_stiffness_n_m);
  const std::size_t wave_count = fixture.wave_segments.size();
  std::vector<double> excitation(wave_count, 0.0);
  std::vector<double> activation(wave_count, 0.0);
  std::vector<double> adaptation(wave_count, 0.0);
  std::vector<double> previous_length(wave_count, 0.0);
  std::vector<double> body_activation(fixture.body_segments.size(), 0.0);
  ClosedLoopOutput output;
  output.spike_counts.assign(fixture.neuron_count, 0);
  output.first_spike_s.assign(
      fixture.neuron_count, std::numeric_limits<double>::quiet_NaN());
  output.peak_activation.assign(wave_count, 0.0);
  output.peak_shortening.assign(wave_count, 0.0);
  std::vector<bool> active_identity(fixture.neuron_count, false);
  std::vector<bool> is_motor_identity(fixture.neuron_count, false);
  for (const auto& [segment, identities] : fixture.motor_identities) {
    (void)segment;
    for (const std::size_t neuron : identities) is_motor_identity[neuron] = true;
  }
  for (std::size_t index = 0; index < wave_count; ++index) {
    previous_length[index] = body.SegmentLength(fixture.wave_segments[index].body_index);
  }
  const double initial_center_x = body.CenterX();
  output.trajectory.push_back({0.0, body.Positions(), body_activation});
  const double adaptation_decay = std::exp(
      -dt_s / parameters.sensory_adaptation_tau_s);
  const double excitation_decay = std::exp(
      -dt_s / parameters.motor_excitation_tau_s);

  for (int step = 0; step < fixture.steps; ++step) {
    const double time_s = static_cast<double>(step) * dt_s;
    std::map<std::size_t, double> external;
    if (options.stimulate && time_s < parameters.posterior_touch_duration_s) {
      external[fixture.touch_neuron] = parameters.posterior_touch_current_a;
    }
    for (std::size_t index = 0; index < wave_count; ++index) {
      const WaveSegment& wave = fixture.wave_segments[index];
      const double length = body.SegmentLength(wave.body_index);
      const double rest = fixture.body_segments[wave.body_index].rest_length_m;
      const double strain = std::max(0.0, 1.0 - length / rest);
      const double shortening_rate = std::max(
          0.0, (previous_length[index] - length) / dt_s);
      previous_length[index] = length;
      adaptation[index] *= adaptation_decay;
      double drive = 0.0;
      if (strain >= parameters.proprioceptor_min_strain) {
        const double excess_rate = std::max(
            0.0,
            shortening_rate - parameters.proprioceptor_min_shortening_rate_m_s);
        drive = std::min(
            parameters.proprioceptor_max_current_a,
            excess_rate * parameters.proprioceptor_current_gain_a_s_m);
      }
      const double adapted_drive = std::max(0.0, drive - adaptation[index]);
      if (adapted_drive != 0.0) {
        external[wave.proprioceptor_neuron] = adapted_drive;
        adaptation[index] += drive * parameters.sensory_adaptation_fraction;
      }
      output.peak_shortening[index] = std::max(
          output.peak_shortening[index], strain);
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
      const WaveSegment& wave = fixture.wave_segments[index];
      excitation[index] *= excitation_decay;
      if (wave.id == "A1") {
        const std::vector<std::size_t>& identities = fixture.motor_identities.at("A1");
        int identity_spikes = 0;
        for (const std::size_t neuron : identities) {
          if (spiked[neuron]) ++identity_spikes;
        }
        excitation[index] += parameters.excitation_per_motor_spike *
            static_cast<double>(identity_spikes) /
            static_cast<double>(identities.size());
      } else if (spiked[wave.motor_neuron]) {
        excitation[index] += parameters.excitation_per_motor_spike;
      }
      const double target = excitation[index] >=
              parameters.muscle_activation_excitation_threshold
          ? 1.0
          : 0.0;
      const double tau = target > activation[index]
          ? wave.rise_tau_s
          : wave.fall_tau_s;
      const double coupling = 1.0 - std::exp(-dt_s / tau);
      activation[index] += (target - activation[index]) * coupling;
      activation[index] = std::min(1.0, std::max(0.0, activation[index]));
      output.peak_activation[index] = std::max(
          output.peak_activation[index], activation[index]);
    }

    std::fill(body_activation.begin(), body_activation.end(), 0.0);
    int recruited_fibers = 0;
    for (std::size_t index = 0; index < wave_count; ++index) {
      const WaveSegment& wave = fixture.wave_segments[index];
      double applied = activation[index];
      const auto proxy = fixture.muscle_proxy_counts.find(wave.id);
      if (proxy != fixture.muscle_proxy_counts.end()) {
        if (options.muscle_lesion == wave.id) applied = 0.0;
        if (applied > 0.0) recruited_fibers += proxy->second;
      }
      body_activation[wave.body_index] = applied;
    }
    output.peak_recruited_fibers = std::max(
        output.peak_recruited_fibers, recruited_fibers);
    for (std::size_t index = 0; index < body_activation.size(); ++index) {
      body.SetActivation(index, body_activation[index]);
    }
    body.Step(dt_s, parameters);
    if ((step + 1) % fixture.sample_stride == 0 || step + 1 == fixture.steps) {
      output.trajectory.push_back({
          static_cast<double>(step + 1) * dt_s,
          body.Positions(),
          body_activation});
    }
  }

  output.displacement_um = (body.CenterX() - initial_center_x) * 1e6;
  output.active_motor_identities = static_cast<int>(std::count(
      active_identity.begin(), active_identity.end(), true));
  return output;
}

}  // namespace oraclarva
