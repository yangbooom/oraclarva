#include "repeat_core.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <limits>
#include <numeric>
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

std::vector<std::size_t> SplitIndices(const std::string& value) {
  std::vector<std::size_t> result;
  std::size_t start = 0;
  while (start <= value.size()) {
    const std::size_t separator = value.find(',', start);
    const std::string item = value.substr(start, separator - start);
    if (!item.empty()) result.push_back(std::stoul(item));
    if (separator == std::string::npos) break;
    start = separator + 1;
  }
  return result;
}

void RequireFields(
    const std::vector<std::string>& fields,
    std::size_t expected,
    int line_number) {
  if (fields.size() != expected) {
    throw std::runtime_error(
        "wrong field count at line " + std::to_string(line_number));
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
    RepeatParameters& p, const std::string& key, double value) {
  if (key == "posterior_touch_current_a") p.posterior_touch_current_a = value;
  else if (key == "posterior_touch_duration_s") p.posterior_touch_duration_s = value;
  else if (key == "intersegmental_relay_delay_s") p.intersegmental_relay_delay_s = value;
  else if (key == "a1_recovery_to_a6_delay_s") p.a1_recovery_to_a6_delay_s = value;
  else if (key == "sensory_maximum_current_a") p.sensory_maximum_current_a = value;
  else if (key == "sensory_adaptation_tau_s") p.sensory_adaptation_tau_s = value;
  else if (key == "sensory_adaptation_fraction") p.sensory_adaptation_fraction = value;
  else if (key == "recovery_adaptation_fraction") p.recovery_adaptation_fraction = value;
  else if (key == "recovery_rate_threshold_s_1") p.recovery_rate_threshold_s_1 = value;
  else if (key == "recovery_rate_gain_s") p.recovery_rate_gain_s = value;
  else if (key == "local_tension_gate_gain") p.local_tension_gate_gain = value;
  else if (key == "trace_arrival_window_s") p.trace_arrival_window_s = value;
  else if (key == "muscle_activation_rise_tau_s") p.muscle_activation_rise_tau_s = value;
  else if (key == "muscle_activation_decay_tau_s") p.muscle_activation_decay_tau_s = value;
  else if (key == "muscle_event_target") p.muscle_event_target = value;
  else if (key == "shortening_strain_threshold") p.shortening_strain_threshold = value;
  else if (key == "shortening_rate_threshold_s_1") p.shortening_rate_threshold_s_1 = value;
  else if (key == "shortening_strain_gain") p.shortening_strain_gain = value;
  else if (key == "shortening_rate_gain_s") p.shortening_rate_gain_s = value;
  else if (key == "maximum_external_current_a") p.maximum_external_current_a = value;
  else if (key == "active_tension_gain_model_units") p.active_tension_gain_model_units = value;
  else if (key == "passive_stiffness_model_units") p.passive_stiffness_model_units = value;
  else if (key == "damping_model_units") p.damping_model_units = value;
  else if (key == "acceleration_scale_m_s2_per_model_force") p.acceleration_scale_m_s2_per_model_force = value;
  else if (key == "body_velocity_retention") p.body_velocity_retention = value;
  else if (key == "ground_negative_x_retention") p.ground_negative_x_retention = value;
  else if (key == "ground_positive_x_retention") p.ground_positive_x_retention = value;
  else if (key == "gravity_z_m_s2") p.gravity_z_m_s2 = value;
  else if (key == "ground_z_m") p.ground_z_m = value;
  else if (key == "body_iterations") p.body_iterations = static_cast<int>(value);
  else if (key == "instantaneous_stiffness_n_m") p.instantaneous_stiffness_n_m = value;
  else throw std::runtime_error("unknown repeat parameter: " + key);
}

RepeatVec3 Add(const RepeatVec3& a, const RepeatVec3& b) {
  return {a.x + b.x, a.y + b.y, a.z + b.z};
}
RepeatVec3 Subtract(const RepeatVec3& a, const RepeatVec3& b) {
  return {a.x - b.x, a.y - b.y, a.z - b.z};
}
RepeatVec3 Multiply(const RepeatVec3& value, double scalar) {
  return {value.x * scalar, value.y * scalar, value.z * scalar};
}
double Dot(const RepeatVec3& a, const RepeatVec3& b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}
RepeatVec3 Cross(const RepeatVec3& a, const RepeatVec3& b) {
  return {
      a.y * b.z - a.z * b.y,
      a.z * b.x - a.x * b.z,
      a.x * b.y - a.y * b.x};
}
double Norm(const RepeatVec3& value) {
  return std::sqrt(Dot(value, value));
}
RepeatVec3 Normalized(const RepeatVec3& value) {
  const double magnitude = Norm(value);
  return magnitude == 0.0
      ? RepeatVec3{1.0, 0.0, 0.0}
      : Multiply(value, 1.0 / magnitude);
}

struct Particle {
  RepeatVec3 position;
  RepeatVec3 previous_position;
  double inverse_mass;
};

class RepeatBody {
 public:
  RepeatBody(
      std::vector<RepeatBodySegment> geometry,
      double stiffness)
      : geometry_(std::move(geometry)), stiffness_(stiffness) {
    std::vector<double> node_masses(geometry_.size() + 1, 0.0);
    for (std::size_t index = 0; index < geometry_.size(); ++index) {
      node_masses[index] += geometry_[index].mass_kg / 2.0;
      node_masses[index + 1] += geometry_[index].mass_kg / 2.0;
    }
    double x = 0.0;
    for (std::size_t index = 0; index < node_masses.size(); ++index) {
      const double clearance = NodeClearance(index);
      const RepeatVec3 position{x, 0.0, clearance};
      particles_.push_back({position, position, 1.0 / node_masses[index]});
      if (index < geometry_.size()) {
        const double vertical =
            NodeClearance(index + 1) - clearance;
        const double rest = geometry_[index].rest_length_m;
        if (std::abs(vertical) >= rest) {
          throw std::runtime_error("body cross-section profile is too steep");
        }
        x += std::sqrt(rest * rest - vertical * vertical);
      }
    }
  }

  double SegmentLength(std::size_t index) const {
    return Norm(Subtract(
        particles_.at(index + 1).position,
        particles_.at(index).position));
  }

  const RepeatVec3& Position(std::size_t index) const {
    return particles_.at(index).position;
  }

  std::vector<RepeatVec3> Positions() const {
    std::vector<RepeatVec3> result;
    result.reserve(particles_.size());
    for (const Particle& particle : particles_) {
      result.push_back(particle.position);
    }
    return result;
  }

  double CenterX() const {
    double total = 0.0;
    for (const Particle& particle : particles_) total += particle.position.x;
    return total / static_cast<double>(particles_.size());
  }

  void ResetVelocity() {
    for (Particle& particle : particles_) {
      particle.previous_position = particle.position;
    }
  }

  void Step(
      double dt_s,
      const RepeatParameters& p,
      const std::vector<RepeatVec3>& external_accelerations) {
    if (external_accelerations.size() != particles_.size()) {
      throw std::runtime_error("repeat body acceleration size mismatch");
    }
    for (std::size_t index = 0; index < particles_.size(); ++index) {
      Particle& particle = particles_[index];
      RepeatVec3 velocity = Multiply(
          Subtract(particle.position, particle.previous_position),
          p.body_velocity_retention);
      const double clearance = NodeClearance(index);
      if (particle.position.z <= p.ground_z_m + clearance + 1e-15) {
        const RepeatVec3 tangent = NodeTangentXY(index);
        const RepeatVec3 lateral{-tangent.y, tangent.x, 0.0};
        const double tangential_speed = Dot(velocity, tangent);
        const double lateral_speed = Dot(velocity, lateral);
        const double retention = tangential_speed < 0.0
            ? p.ground_negative_x_retention
            : p.ground_positive_x_retention;
        const RepeatVec3 planar = Add(
            Multiply(tangent, tangential_speed * retention),
            Multiply(
                lateral,
                lateral_speed * std::min(
                    p.ground_negative_x_retention,
                    p.ground_positive_x_retention)));
        velocity = {planar.x, planar.y, velocity.z};
      }
      const RepeatVec3 old_position = particle.position;
      const RepeatVec3 acceleration = Add(
          {0.0, 0.0, p.gravity_z_m_s2},
          external_accelerations[index]);
      particle.position = Add(
          Add(particle.position, velocity),
          Multiply(acceleration, dt_s * dt_s));
      particle.previous_position = old_position;
      if (particle.position.z < p.ground_z_m + clearance) {
        particle.position.z = p.ground_z_m + clearance;
      }
    }

    const double compliance = 1.0 / stiffness_;
    const double alpha = compliance / (dt_s * dt_s);
    for (int iteration = 0; iteration < p.body_iterations; ++iteration) {
      for (std::size_t index = 0; index < geometry_.size(); ++index) {
        Particle& left = particles_[index];
        Particle& right = particles_[index + 1];
        const RepeatVec3 delta =
            Subtract(right.position, left.position);
        const double distance = Norm(delta);
        if (distance == 0.0) continue;
        const double constraint =
            distance - geometry_[index].rest_length_m;
        const double denominator =
            left.inverse_mass + right.inverse_mass + alpha;
        const double lagrange = -constraint / denominator;
        const RepeatVec3 direction = Multiply(delta, 1.0 / distance);
        left.position = Subtract(
            left.position,
            Multiply(direction, left.inverse_mass * lagrange));
        right.position = Add(
            right.position,
            Multiply(direction, right.inverse_mass * lagrange));
      }
    }
  }

 private:
  double NodeClearance(std::size_t index) const {
    double clearance = -std::numeric_limits<double>::infinity();
    if (index > 0) {
      clearance = std::max(
          clearance, geometry_[index - 1].height_m / 2.0);
    }
    if (index < geometry_.size()) {
      clearance = std::max(
          clearance, geometry_[index].height_m / 2.0);
    }
    return clearance;
  }

  RepeatVec3 NodeTangentXY(std::size_t index) const {
    RepeatVec3 delta{};
    if (index == 0) {
      delta = Subtract(
          particles_[1].position, particles_[0].position);
    } else if (index + 1 == particles_.size()) {
      delta = Subtract(
          particles_.back().position,
          particles_[particles_.size() - 2].position);
    } else {
      delta = Subtract(
          particles_[index + 1].position,
          particles_[index - 1].position);
    }
    const double magnitude =
        std::sqrt(delta.x * delta.x + delta.y * delta.y);
    if (magnitude == 0.0) return {1.0, 0.0, 0.0};
    return {delta.x / magnitude, delta.y / magnitude, 0.0};
  }

  std::vector<RepeatBodySegment> geometry_;
  double stiffness_;
  std::vector<Particle> particles_;
};

RepeatVec3 AttachmentPoint(
    const RepeatBody& body,
    const RepeatBodySegment& segment,
    std::size_t segment_index,
    const RepeatCoordinate& coordinate) {
  const RepeatVec3 left = body.Position(segment_index);
  const RepeatVec3 right = body.Position(segment_index + 1);
  const RepeatVec3 tangent = Normalized(Subtract(right, left));
  const RepeatVec3 up{0.0, 0.0, 1.0};
  RepeatVec3 lateral = Cross(up, tangent);
  if (Norm(lateral) < 1e-12) {
    lateral = {0.0, 1.0, 0.0};
  } else {
    lateral = Normalized(lateral);
  }
  const RepeatVec3 dorsal = Normalized(Cross(tangent, lateral));
  const RepeatVec3 center = Add(
      Multiply(left, 1.0 - coordinate.s),
      Multiply(right, coordinate.s));
  const double radial = 1.0 - coordinate.depth_fraction;
  return Add(
      Add(
          center,
          Multiply(
              lateral,
              0.5 * segment.width_m * radial
                  * std::sin(coordinate.theta_rad))),
      Multiply(
          dorsal,
          0.5 * segment.height_m * radial
              * std::cos(coordinate.theta_rad)));
}

std::pair<RepeatVec3, RepeatVec3> AttachmentPoints(
    const RepeatBody& body,
    const std::vector<RepeatBodySegment>& segments,
    const RepeatFiber& fiber) {
  return {
      AttachmentPoint(
          body, segments.at(fiber.body_index),
          fiber.body_index, fiber.origin),
      AttachmentPoint(
          body, segments.at(fiber.body_index),
          fiber.body_index, fiber.insertion)};
}

std::size_t FindWaveIndex(
    const RepeatFixture& fixture, const std::string& id) {
  for (std::size_t index = 0; index < fixture.wave_segments.size(); ++index) {
    if (fixture.wave_segments[index].id == id) return index;
  }
  throw std::runtime_error("unknown repeat wave segment: " + id);
}

double Median(std::vector<double> values) {
  if (values.empty()) {
    return std::numeric_limits<double>::quiet_NaN();
  }
  std::sort(values.begin(), values.end());
  const std::size_t middle = values.size() / 2;
  return values.size() % 2
      ? values[middle]
      : 0.5 * (values[middle - 1] + values[middle]);
}

struct Origin {
  bool valid = false;
  double body_state_time_s = 0.0;
  std::size_t sensor_neuron = 0;
  double sensor_spike_time_s = 0.0;
  double available_time_s = 0.0;
};

struct PendingFiberEvent {
  bool valid = false;
  std::size_t source_neuron = 0;
  double source_spike_time_s = 0.0;
  RepeatTrace trace;
};

RepeatCycleMetrics MeasureCycles(
    const std::vector<std::vector<double>>& premotor,
    const std::vector<std::vector<double>>& lengths,
    const std::vector<double>& centers,
    double dt_s) {
  RepeatCycleMetrics result;
  result.median_period_s = std::numeric_limits<double>::quiet_NaN();
  result.median_stride_um = std::numeric_limits<double>::quiet_NaN();
  result.median_wave_speed_segments_s =
      std::numeric_limits<double>::quiet_NaN();
  if (premotor.empty()) return result;
  std::vector<double> periods;
  std::vector<double> strides;
  std::vector<double> speeds;
  const std::vector<double>& boundaries = premotor[0];
  for (std::size_t cycle = 0; cycle + 1 < boundaries.size(); ++cycle) {
    const double start_s = boundaries[cycle];
    const double end_s = boundaries[cycle + 1];
    std::vector<double> events(6, 0.0);
    bool neural_ordered = true;
    for (std::size_t segment = 0; segment < 6; ++segment) {
      const auto found = std::find_if(
          premotor[segment].begin(),
          premotor[segment].end(),
          [start_s, end_s](double value) {
            return start_s <= value && value < end_s;
          });
      if (found == premotor[segment].end()) {
        neural_ordered = false;
        break;
      }
      events[segment] = *found;
      if (segment > 0 && events[segment - 1] >= events[segment]) {
        neural_ordered = false;
        break;
      }
    }
    if (!neural_ordered) continue;
    const int start = std::max(
        0, static_cast<int>(std::llround(start_s / dt_s)));
    const int end = std::min(
        static_cast<int>(centers.size()),
        static_cast<int>(std::llround(end_s / dt_s)));
    if (end - start < 3) continue;
    ++result.complete_cycle_count;
    periods.push_back(end_s - start_s);
    strides.push_back(
        (centers.at(end - 1) - centers.at(start)) * 1e6);

    std::vector<double> onsets(6, 0.0);
    bool physical_ordered = true;
    for (std::size_t segment = 0; segment < 6; ++segment) {
      const int event_index = std::max(
          start,
          static_cast<int>(std::llround(events[segment] / dt_s)));
      const int response_end = std::min(
          end, event_index + static_cast<int>(std::llround(0.8 / dt_s)));
      const int peak_end = std::min(
          response_end,
          event_index + static_cast<int>(std::llround(0.05 / dt_s)));
      if (peak_end - event_index < 2) {
        physical_ordered = false;
        break;
      }
      int peak = event_index;
      for (int index = event_index + 1; index < peak_end; ++index) {
        if (lengths[segment][index] > lengths[segment][peak]) peak = index;
      }
      int trough = peak;
      for (int index = peak + 1; index < response_end; ++index) {
        if (lengths[segment][index] < lengths[segment][trough]) trough = index;
      }
      const double maximum = lengths[segment][peak];
      const double minimum = lengths[segment][trough];
      const double amplitude = maximum - minimum;
      if (amplitude <= 0.0 || maximum <= 0.0) {
        physical_ordered = false;
        break;
      }
      const double threshold = maximum - 0.25 * amplitude;
      bool found_onset = false;
      for (int index = peak + 1; index <= trough; ++index) {
        const double before = lengths[segment][index - 1];
        const double after = lengths[segment][index];
        if (before > threshold && threshold >= after && before != after) {
          const double fraction =
              (before - threshold) / (before - after);
          onsets[segment] =
              (static_cast<double>(index) + fraction) * dt_s;
          found_onset = true;
          break;
        }
      }
      if (!found_onset ||
          (segment > 0 && onsets[segment - 1] >= onsets[segment])) {
        physical_ordered = false;
        break;
      }
    }
    if (physical_ordered) {
      const double duration = onsets[5] - onsets[0];
      if (duration > 0.0) {
        ++result.physical_wave_cycle_count;
        speeds.push_back(5.0 / duration);
      }
    }
  }
  result.median_period_s = Median(periods);
  result.median_stride_um = Median(strides);
  result.median_wave_speed_segments_s = Median(speeds);
  return result;
}

}  // namespace

RepeatFixture LoadRepeatFixture(const std::string& path) {
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("cannot open repeat fixture: " + path);
  }
  RepeatFixture fixture;
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
    } else if (kind == "config_sha256") {
      RequireFields(fields, 2, line_number);
      fixture.config_sha256 = fields[1];
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
    } else if (kind == "equilibrium_steps") {
      RequireFields(fields, 2, line_number);
      fixture.equilibrium_steps = std::stoi(fields[1]);
    } else if (kind == "touch_neuron") {
      RequireFields(fields, 2, line_number);
      fixture.touch_neuron = std::stoul(fields[1]);
    } else if (kind == "recovery_neuron") {
      RequireFields(fields, 2, line_number);
      fixture.recovery_neuron = std::stoul(fields[1]);
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
        throw std::runtime_error("repeat neuron outside declared count");
      }
      fixture.neuron_labels[index] = fields[2];
    } else if (kind == "body_segment") {
      RequireFields(fields, 7, line_number);
      const std::size_t index = std::stoul(fields[1]);
      if (index != fixture.body_segments.size()) {
        throw std::runtime_error("repeat body segments must be contiguous");
      }
      fixture.body_segments.push_back({
          fields[2], std::stod(fields[3]), std::stod(fields[4]),
          std::stod(fields[5]), std::stod(fields[6])});
    } else if (kind == "wave_segment") {
      RequireFields(fields, 8, line_number);
      const std::size_t index = std::stoul(fields[1]);
      if (index != fixture.wave_segments.size()) {
        throw std::runtime_error("repeat wave segments must be contiguous");
      }
      fixture.wave_segments.push_back({
          fields[2], std::stoul(fields[3]), std::stoul(fields[4]),
          std::stoul(fields[5]), std::stoul(fields[6]),
          SplitIndices(fields[7])});
    } else if (kind == "synapse") {
      RequireFields(fields, 6, line_number);
      if (fields[4] != "excitatory" && fields[4] != "inhibitory") {
        throw std::runtime_error("invalid repeat synapse kind");
      }
      fixture.synapses.push_back({
          std::stoul(fields[1]), std::stoul(fields[2]),
          std::stod(fields[3]), fields[4] == "inhibitory",
          std::stoi(fields[5])});
    } else if (kind == "fiber") {
      RequireFields(fields, 15, line_number);
      const std::size_t index = std::stoul(fields[1]);
      if (index != fixture.fibers.size()) {
        throw std::runtime_error("repeat fibers must be contiguous");
      }
      fixture.fibers.push_back({
          fields[2], fields[3], fields[4], fields[5],
          std::stoul(fields[6]), std::stoul(fields[7]),
          {std::stod(fields[8]), std::stod(fields[9]), std::stod(fields[10])},
          {std::stod(fields[11]), std::stod(fields[12]), std::stod(fields[13])},
          fields[14]});
    } else {
      throw std::runtime_error(
          "unknown repeat fixture row at line "
          + std::to_string(line_number));
    }
  }
  const std::vector<std::string> expected{
      "A6", "A5", "A4", "A3", "A2", "A1"};
  if (fixture.schema != "repeat_crawl_native_v1"
      || fixture.model_id != "dmel_l1_repeat_crawl_v0"
      || fixture.status != "research_approximation"
      || fixture.release_validated
      || fixture.config_sha256
          != "5cbaec6a716cf2b8dd2d8e053b00469f5e9f09389fa74645c17a148143b936e3") {
    throw std::runtime_error("repeat fixture claim/freeze boundary is invalid");
  }
  if (fixture.neuron_count != 164
      || fixture.neuron_labels.size() != 164
      || fixture.body_segments.size() != 12
      || fixture.wave_segments.size() != 6
      || fixture.synapses.size() != 307
      || fixture.fibers.size() != 146
      || fixture.steps != 16000
      || fixture.sample_stride != 30
      || fixture.equilibrium_steps != 50) {
    throw std::runtime_error("repeat fixture structural contract is invalid");
  }
  for (std::size_t index = 0; index < expected.size(); ++index) {
    if (fixture.wave_segments[index].id != expected[index]) {
      throw std::runtime_error("repeat wave order changed");
    }
  }
  if (std::any_of(
          fixture.neuron_labels.begin(), fixture.neuron_labels.end(),
          [](const std::string& label) { return label.empty(); })) {
    throw std::runtime_error("repeat fixture has an unlabeled neuron");
  }
  return fixture;
}

struct RepeatSimulation::Impl {
  const RepeatFixture& fixture;
  const RepeatOptions& options;
  const RepeatParameters& p;
  double dt_s;
  SparseLIFNetwork network;
  RepeatBody body;
  std::set<std::size_t> fiber_lesions;
  std::vector<double> sensory_rest;
  std::vector<double> sensory_previous;
  std::vector<double> fiber_rest;
  std::vector<double> fiber_previous;
  std::vector<int> source_segment;
  RepeatOutput output;
  std::vector<double> adaptation;
  std::vector<double> local_tension;
  std::vector<double> activation;
  std::vector<PendingFiberEvent> pending;
  std::vector<std::size_t> last_source;
  std::vector<double> last_spike;
  std::vector<RepeatTrace> last_trace;
  std::vector<std::vector<Origin>> pending_origins;
  std::vector<Origin> last_origin;
  std::vector<std::vector<double>> length_history;
  std::vector<double> center_history;
  std::vector<std::size_t> last_step_spikes;
  std::vector<RepeatVec3> last_node_force;
  double initial_center = 0.0;
  double adaptation_decay = 0.0;
  double rise = 0.0;
  double decay = 0.0;
  int step_index = 0;

  Impl(const RepeatFixture& fixture_value, const RepeatOptions& options_value)
      : fixture(fixture_value),
        options(options_value),
        p(fixture.parameters),
        dt_s(fixture.lif_config.dt_s),
        network(
            fixture.neuron_count,
            fixture.synapses,
            fixture.lif_config),
        body(
            fixture.body_segments,
            fixture.parameters.instantaneous_stiffness_n_m),
        sensory_rest(6),
        sensory_previous(6),
        fiber_rest(fixture.fibers.size()),
        fiber_previous(fixture.fibers.size()),
        source_segment(fixture.neuron_count, -1),
        adaptation(7, 0.0),
        local_tension(6, 0.0),
        activation(fixture.fibers.size(), 0.0),
        pending(fixture.fibers.size()),
        last_source(fixture.fibers.size(), 0),
        last_spike(
            fixture.fibers.size(),
            std::numeric_limits<double>::quiet_NaN()),
        last_trace(fixture.fibers.size()),
        pending_origins(6),
        last_origin(6),
        length_history(6),
        last_node_force(fixture.body_segments.size() + 1) {
    ApplyLesions();
    const std::vector<RepeatVec3> no_acceleration(
        fixture.body_segments.size() + 1);
    for (int index = 0; index < fixture.equilibrium_steps; ++index) {
      body.Step(dt_s, p, no_acceleration);
    }
    body.ResetVelocity();

    for (std::size_t segment = 0; segment < 6; ++segment) {
      const double length = body.SegmentLength(
          fixture.wave_segments[segment].body_index);
      sensory_rest[segment] = length;
      sensory_previous[segment] = length;
    }
    for (std::size_t index = 0; index < fixture.fibers.size(); ++index) {
      const auto points = AttachmentPoints(
          body, fixture.body_segments, fixture.fibers[index]);
      const double length = Norm(Subtract(points.second, points.first));
      if (length <= 0.0) {
        throw std::runtime_error(
            "repeat fiber rest length is not positive");
      }
      fiber_rest[index] = length;
      fiber_previous[index] = length;
    }
    for (std::size_t segment = 0; segment < 6; ++segment) {
      for (const std::size_t neuron :
           fixture.wave_segments[segment].source_neurons) {
        if (source_segment[neuron] != -1
            && source_segment[neuron] != static_cast<int>(segment)) {
          throw std::runtime_error(
              "repeat source maps to multiple segments");
        }
        source_segment[neuron] = static_cast<int>(segment);
      }
    }

    output.spike_counts.assign(fixture.neuron_count, 0);
    output.first_spike_s.assign(
        fixture.neuron_count,
        std::numeric_limits<double>::quiet_NaN());
    output.premotor_spike_times_s.resize(6);
    output.motor_spike_times_s.resize(6);
    output.trace_examples.resize(6);
    initial_center = body.CenterX();
    output.trajectory.push_back({
        0.0,
        body.Positions(),
        std::vector<double>(6, 0.0),
        std::vector<RepeatVec3>(
            fixture.body_segments.size() + 1)});
    adaptation_decay =
        std::exp(-dt_s / p.sensory_adaptation_tau_s);
    rise =
        1.0 - std::exp(-dt_s / p.muscle_activation_rise_tau_s);
    decay =
        1.0 - std::exp(-dt_s / p.muscle_activation_decay_tau_s);
  }

  void ApplyLesions() {
    if (!options.sensory_lesion.empty()) {
      const std::size_t wave =
          FindWaveIndex(fixture, options.sensory_lesion);
      network.Lesion(
          options.sensory_lesion == "A1"
              ? fixture.recovery_neuron
              : fixture.wave_segments[wave].sensory_neuron);
    }
    if (!options.premotor_lesion.empty()) {
      const std::size_t wave =
          FindWaveIndex(fixture, options.premotor_lesion);
      network.Lesion(fixture.wave_segments[wave].premotor_neuron);
    }
    if (!options.motor_segment_lesion.empty()) {
      const std::size_t wave =
          FindWaveIndex(fixture, options.motor_segment_lesion);
      for (const std::size_t neuron :
           fixture.wave_segments[wave].source_neurons) {
        network.Lesion(neuron);
      }
    }
    if (!options.fiber_segment_lesion.empty()) {
      FindWaveIndex(fixture, options.fiber_segment_lesion);
      for (std::size_t index = 0;
           index < fixture.fibers.size(); ++index) {
        if (fixture.fibers[index].segment_id
            == options.fiber_segment_lesion) {
          fiber_lesions.insert(index);
        }
      }
    }
  }

  void Advance(const RepeatEnvironmentInput& input) {
    if (step_index >= fixture.steps) {
      throw std::runtime_error(
          "repeat simulation advanced beyond fixture limit");
    }
    if (!std::isfinite(input.posterior_touch_intensity)
        || input.posterior_touch_intensity < 0.0
        || input.posterior_touch_intensity > 1.0) {
      throw std::runtime_error(
          "posterior touch intensity must be finite in [0, 1]");
    }
    const double time_s = static_cast<double>(step_index) * dt_s;
    std::vector<double> strain_rate(6, 0.0);
    std::vector<double> contraction_drive(6, 0.0);
    for (std::size_t segment = 0; segment < 6; ++segment) {
      const double length = body.SegmentLength(
          fixture.wave_segments[segment].body_index);
      const double rest = sensory_rest[segment];
      const double strain = (length - rest) / rest;
      const double rate =
          (length - sensory_previous[segment]) / dt_s / rest;
      sensory_previous[segment] = length;
      strain_rate[segment] = rate;
      const double shortening = std::max(0.0, -strain);
      const double shortening_rate = std::max(0.0, -rate);
      contraction_drive[segment] = std::min(
          1.0,
          std::max(
              0.0,
              std::max(
                  0.0,
                  shortening - p.shortening_strain_threshold)
                  * p.shortening_strain_gain
              + std::max(
                  0.0,
                  shortening_rate
                      - p.shortening_rate_threshold_s_1)
                  * p.shortening_rate_gain_s));
    }

    for (double& value : adaptation) value *= adaptation_decay;
    std::map<std::size_t, double> external;
    if (input.posterior_touch_intensity > 0.0) {
      external[fixture.touch_neuron] =
          p.posterior_touch_current_a
          * input.posterior_touch_intensity;
    }
    for (std::size_t segment = 0; segment < 6; ++segment) {
      const double gate = std::min(
          1.0,
          std::max(0.0, local_tension[segment])
              * p.local_tension_gate_gain);
      const double raw =
          contraction_drive[segment] * gate
          * p.sensory_maximum_current_a;
      const double adapted =
          std::max(0.0, raw - adaptation[segment]);
      if (adapted > 0.0) {
        external[fixture.wave_segments[segment].sensory_neuron] =
            adapted;
      }
    }
    const double recovery_gate = std::min(
        1.0,
        std::max(0.0, local_tension[5])
            * p.local_tension_gate_gain);
    const double recovery_drive = std::min(
        1.0,
        std::max(
            0.0,
            strain_rate[5] - p.recovery_rate_threshold_s_1)
            * p.recovery_rate_gain_s) * recovery_gate;
    const double recovery_raw =
        recovery_drive * p.sensory_maximum_current_a;
    const double recovery_adapted =
        std::max(0.0, recovery_raw - adaptation[6]);
    if (recovery_adapted > 0.0) {
      external[fixture.recovery_neuron] = recovery_adapted;
    }

    const std::vector<std::size_t> spikes = network.Step(external);
    last_step_spikes = spikes;
    std::vector<bool> spiked(fixture.neuron_count, false);
    for (const std::size_t neuron : spikes) {
      spiked[neuron] = true;
      ++output.spike_counts[neuron];
      if (std::isnan(output.first_spike_s[neuron])) {
        output.first_spike_s[neuron] = time_s;
      }
    }

    auto queue_origin = [this, time_s](
                            std::size_t target,
                            std::size_t sensor,
                            double delay) {
      pending_origins[target].push_back(
          {true, time_s, sensor, time_s, time_s + delay});
    };
    if (spiked[fixture.touch_neuron]) {
      queue_origin(0, fixture.touch_neuron, 0.0);
    }
    for (std::size_t segment = 0; segment < 6; ++segment) {
      const std::size_t sensor =
          fixture.wave_segments[segment].sensory_neuron;
      if (spiked[sensor]) {
        adaptation[segment] = std::max(
            adaptation[segment],
            p.sensory_maximum_current_a
                * p.sensory_adaptation_fraction);
        if (segment + 1 < 6) {
          queue_origin(
              segment + 1,
              sensor,
              p.intersegmental_relay_delay_s);
        }
      }
    }
    if (spiked[fixture.recovery_neuron]) {
      adaptation[6] = std::max(
          adaptation[6],
          p.sensory_maximum_current_a
              * p.recovery_adaptation_fraction);
      queue_origin(
          0,
          fixture.recovery_neuron,
          p.a1_recovery_to_a6_delay_s);
    }

    for (std::size_t segment = 0; segment < 6; ++segment) {
      if (spiked[fixture.wave_segments[segment].premotor_neuron]) {
        output.premotor_spike_times_s[segment].push_back(time_s);
        Origin selected;
        for (const Origin& origin : pending_origins[segment]) {
          if (origin.available_time_s <= time_s
              && time_s - origin.available_time_s
                  <= p.trace_arrival_window_s
              && (!selected.valid
                  || origin.available_time_s
                      > selected.available_time_s)) {
            selected = origin;
          }
        }
        if (selected.valid) last_origin[segment] = selected;
      }
      std::vector<Origin> retained;
      for (const Origin& origin : pending_origins[segment]) {
        if (time_s - origin.available_time_s
            <= p.trace_arrival_window_s) {
          retained.push_back(origin);
        }
      }
      pending_origins[segment] = std::move(retained);
    }

    std::vector<RepeatTrace> source_trace(fixture.neuron_count);
    for (const std::size_t neuron : spikes) {
      const int segment = source_segment[neuron];
      if (segment < 0) continue;
      output.motor_spike_times_s[segment].push_back(time_s);
      if (last_origin[segment].valid) {
        source_trace[neuron] = {
            true,
            last_origin[segment].body_state_time_s,
            last_origin[segment].sensor_neuron,
            last_origin[segment].sensor_spike_time_s,
            fixture.wave_segments[segment].premotor_neuron,
            output.premotor_spike_times_s[segment].back(),
            neuron,
            time_s,
            fixture.wave_segments[segment].id};
      }
    }

    for (std::size_t index = 0;
         index < fixture.fibers.size(); ++index) {
      if (pending[index].valid) {
        activation[index] +=
            (p.muscle_event_target - activation[index]) * rise;
        last_source[index] = pending[index].source_neuron;
        last_spike[index] = pending[index].source_spike_time_s;
        last_trace[index] = pending[index].trace;
      } else {
        activation[index] += (0.0 - activation[index]) * decay;
      }
      activation[index] =
          std::min(1.0, std::max(0.0, activation[index]));
    }
    std::vector<PendingFiberEvent> next_pending(
        fixture.fibers.size());
    for (std::size_t index = 0;
         index < fixture.fibers.size(); ++index) {
      const RepeatFiber& fiber = fixture.fibers[index];
      if (spiked[fiber.source_neuron]
          && fiber_lesions.count(index) == 0) {
        next_pending[index] = {
            true,
            fiber.source_neuron,
            time_s,
            source_trace[fiber.source_neuron]};
      }
    }
    pending = std::move(next_pending);

    std::vector<RepeatVec3> node_force(
        fixture.body_segments.size() + 1);
    std::vector<double> segment_activation_sum(6, 0.0);
    std::vector<int> segment_fiber_count(6, 0);
    int active_count = 0;
    int traced_count = 0;
    for (std::size_t index = 0;
         index < fixture.fibers.size(); ++index) {
      const RepeatFiber& fiber = fixture.fibers[index];
      const std::size_t segment =
          FindWaveIndex(fixture, fiber.segment_id);
      const auto points = AttachmentPoints(
          body, fixture.body_segments, fiber);
      const RepeatVec3 delta =
          Subtract(points.second, points.first);
      const double length = Norm(delta);
      const RepeatVec3 direction = Normalized(delta);
      const double length_rate =
          (length - fiber_previous[index]) / dt_s
          / fixture.body_segments[fiber.body_index].rest_length_m;
      fiber_previous[index] = length;
      if (activation[index] > 0.0) {
        ++active_count;
        const RepeatTrace& trace = last_trace[index];
        if (std::isnan(last_spike[index])
            || !(last_spike[index] < time_s)
            || !trace.valid
            || !(trace.body_state_time_s
                 <= trace.sensor_spike_time_s)
            || !(trace.sensor_spike_time_s
                 < trace.premotor_spike_time_s)
            || !(trace.premotor_spike_time_s
                 <= trace.motor_spike_time_s)
            || !(trace.motor_spike_time_s
                 <= last_spike[index])) {
          throw std::runtime_error(
              "native repeat active force lacks ordered ancestry");
        }
        ++traced_count;
        output.trace_examples[segment] = trace;
      }
      const double active =
          p.active_tension_gain_model_units * activation[index];
      const double extension = std::max(
          0.0,
          (length - fiber_rest[index])
              / fixture.body_segments[fiber.body_index].rest_length_m);
      const double passive =
          p.passive_stiffness_model_units * extension;
      const double damping =
          p.damping_model_units * length_rate;
      const double total =
          std::max(0.0, active + passive + damping);
      const RepeatVec3 force = Multiply(direction, total);
      const std::size_t left = fiber.body_index;
      const std::size_t right = left + 1;
      node_force[left] = Add(
          node_force[left],
          Multiply(force, 1.0 - fiber.origin.s));
      node_force[right] = Add(
          node_force[right],
          Multiply(force, fiber.origin.s));
      node_force[left] = Add(
          node_force[left],
          Multiply(force, -(1.0 - fiber.insertion.s)));
      node_force[right] = Add(
          node_force[right],
          Multiply(force, -fiber.insertion.s));
      segment_activation_sum[segment] += activation[index];
      ++segment_fiber_count[segment];
    }
    if (active_count != traced_count) {
      throw std::runtime_error(
          "native repeat force trace count mismatch");
    }
    if (active_count > 0) {
      ++output.feedback_force_frames;
      output.all_active_forces_traced =
          output.all_active_forces_traced
          && active_count == traced_count;
    }
    for (std::size_t segment = 0; segment < 6; ++segment) {
      local_tension[segment] =
          segment_activation_sum[segment]
          / static_cast<double>(segment_fiber_count[segment]);
    }
    std::vector<RepeatVec3> accelerations(
        fixture.body_segments.size() + 1);
    for (std::size_t node = 0;
         node < accelerations.size(); ++node) {
      accelerations[node] = Multiply(
          node_force[node],
          p.acceleration_scale_m_s2_per_model_force);
    }
    body.Step(dt_s, p, accelerations);
    last_node_force = node_force;

    center_history.push_back(body.CenterX());
    for (std::size_t segment = 0; segment < 6; ++segment) {
      length_history[segment].push_back(body.SegmentLength(
          fixture.wave_segments[segment].body_index));
    }
    ++step_index;
    if (step_index % fixture.sample_stride == 0) {
      output.trajectory.push_back({
          static_cast<double>(step_index) * dt_s,
          body.Positions(),
          local_tension,
          last_node_force});
    }
  }

  RepeatCycleMetrics CycleMetrics() const {
    return MeasureCycles(
        output.premotor_spike_times_s,
        length_history,
        center_history,
        dt_s);
  }

  RepeatOutput Result() const {
    RepeatOutput result = output;
    result.displacement_x_um =
        (body.CenterX() - initial_center) * 1e6;
    result.cycle_metrics = CycleMetrics();
    const double current_time =
        static_cast<double>(step_index) * dt_s;
    if (result.trajectory.empty()
        || result.trajectory.back().time_s != current_time) {
      result.trajectory.push_back({
          current_time,
          body.Positions(),
          local_tension,
          last_node_force});
    }
    return result;
  }

  RepeatStateSnapshot Snapshot() const {
    return {
        step_index,
        static_cast<double>(step_index) * dt_s,
        (body.CenterX() - initial_center) * 1e6,
        body.Positions(),
        local_tension,
        last_node_force,
        output.spike_counts,
        output.first_spike_s,
        last_step_spikes,
        output.feedback_force_frames,
        output.all_active_forces_traced,
        CycleMetrics(),
        output.trace_examples};
  }
};

RepeatSimulation::RepeatSimulation(
    const RepeatFixture& fixture,
    const RepeatOptions& options)
    : fixture_(fixture), options_(options) {
  Reset();
}

RepeatSimulation::~RepeatSimulation() = default;

void RepeatSimulation::Reset() {
  impl_ = std::make_unique<Impl>(fixture_, options_);
}

void RepeatSimulation::Advance(
    const RepeatEnvironmentInput& input) {
  impl_->Advance(input);
}

int RepeatSimulation::step_index() const {
  return impl_->step_index;
}

int RepeatSimulation::maximum_steps() const {
  return fixture_.steps;
}

double RepeatSimulation::time_s() const {
  return static_cast<double>(impl_->step_index)
      * fixture_.lif_config.dt_s;
}

RepeatStateSnapshot RepeatSimulation::Snapshot() const {
  return impl_->Snapshot();
}

RepeatOutput RepeatSimulation::Result() const {
  return impl_->Result();
}

RepeatOutput RunRepeat(
    const RepeatFixture& fixture,
    const RepeatOptions& options) {
  const int steps = options.steps_override > 0
      ? options.steps_override : fixture.steps;
  if (steps <= 0 || steps > fixture.steps) {
    throw std::runtime_error(
        "repeat steps override is outside fixture");
  }
  RepeatSimulation simulation(fixture, options);
  for (int step = 0; step < steps; ++step) {
    const double time_s = simulation.time_s();
    const double touch_intensity =
        options.stimulate
            && time_s
                < fixture.parameters.posterior_touch_duration_s
        ? 1.0
        : 0.0;
    simulation.Advance({touch_intensity});
  }
  return simulation.Result();
}

}  // namespace oraclarva
