import inspect
from math import atan, degrees

import pytest

from oraclarva.body3d import Vec3
from oraclarva.environment import (
    RhythmicObstacleTransduction,
    load_environment_config,
)
from oraclarva.spatial import (
    SpatialClosedLoopLarva,
    SpatialSensoryState,
    SpatialStimulus,
    load_spatial_config,
)
from oraclarva.terrain import ContactWorld, PlaneCollider, SphereCollider


@pytest.fixture(scope="module")
def uphill_result_and_gap():
    slope = -0.2
    plane = PlaneCollider.from_slopes(slope, 0.0)
    world = ContactWorld((plane,))
    larva = SpatialClosedLoopLarva(
        initial_pitch_deg=degrees(atan(-slope)),
        ground_z_m=None,
        contact_surface=world,
    )
    result = larva.run(SpatialStimulus(1.0, 1.0, 1.0, 1.0))
    gap = min(
        plane.signed_distance_m(particle.position)
        - larva.body._node_clearance(index)
        for index, particle in enumerate(larva.body.particles)
    )
    return result, gap


@pytest.fixture(scope="module")
def obstacle_result_and_gap():
    config = load_environment_config()
    fixture = config["validation_fixtures"]
    sphere = SphereCollider(
        Vec3(*fixture["obstacle_center_m"]),
        fixture["obstacle_radius_m"],
    )
    world = ContactWorld((
        PlaneCollider.from_slopes(0.0, 0.0),
        sphere,
    ))
    larva = SpatialClosedLoopLarva(
        ground_z_m=None,
        contact_surface=world,
    )
    result = larva.run(
        stimulus_protocol=RhythmicObstacleTransduction.from_config(world)
    )
    gap = min(
        sphere.signed_distance_m(particle.position)
        - larva.body._node_clearance(index)
        for index, particle in enumerate(larva.body.particles)
    )
    return result, gap


def test_environment_config_is_explicitly_synthetic_and_model_fitted():
    config = load_environment_config()
    assert config["status"] == "research_approximation"
    assert config["provenance"] == "MODEL_FITTED"
    assert config["release_validated"] is False
    assert config["parameters"]["contact_friction_coefficient"] == (
        load_spatial_config()["parameters"]["contact_friction_coefficient"]
    )
    assert any(
        "synthetic diagnostic geometry" in limitation
        for limitation in config["limitations"]
    )


def test_four_receptors_sample_obstacle_distance_only_during_sensory_pulse():
    sphere = SphereCollider(Vec3(-65e-6, -25e-6, 20e-6), 20e-6)
    world = ContactWorld((
        PlaneCollider.from_slopes(0.0, 0.0),
        sphere,
    ))
    larva = SpatialClosedLoopLarva(
        ground_z_m=None,
        contact_surface=world,
    )
    transduction = RhythmicObstacleTransduction.from_config(world)
    state = SpatialSensoryState.from_body(larva.body)
    pulse = transduction(0.0, state)
    quiet = transduction(0.2, state)

    assert pulse.left_intensity > pulse.right_intensity
    assert pulse.ventral_intensity > pulse.dorsal_intensity
    assert quiet == SpatialStimulus(0.0, 0.0, 0.0, 0.0)


def test_closed_loop_climbs_twenty_percent_slope_without_penetration(
    uphill_result_and_gap,
):
    result, gap = uphill_result_and_gap
    assert result.displacement_x_um < -20.0
    assert result.displacement_z_um > 5.0
    assert result.displacement_z_um == pytest.approx(
        -0.2 * result.displacement_x_um, abs=1.0
    )
    assert gap >= -1e-12
    assert sum(result.spike_counts.values()) > 0
    assert result.peak_yaw_recruited_fibers == 358
    assert result.peak_pitch_recruited_fibers == 276


def test_obstacle_receptor_loop_steers_clear_before_contact(
    obstacle_result_and_gap,
):
    result, gap = obstacle_result_and_gap
    assert result.displacement_x_um < -50.0
    assert result.displacement_y_um > 1.0
    assert result.yaw_change_deg > 5.0
    assert gap > 5e-6
    assert sum(result.spike_counts.values()) > 0


def test_environment_transduction_exposes_no_movement_commands():
    source = inspect.getsource(RhythmicObstacleTransduction).lower()
    forbidden = (
        "turn_left",
        "turn_right",
        "pitch_up",
        "pitch_down",
        "crawl(",
        "move_3d",
        "behavior_tree",
        "fsm",
    )
    assert all(token not in source for token in forbidden)
