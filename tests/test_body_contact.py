from __future__ import annotations

import pytest

from oraclarva.body import load_body_spec
from oraclarva.body3d import ScientificBody3D, Vec3


def test_continuous_node_contact_is_sign_symmetric_and_rejects_direction_mix():
    def shifted(acceleration_x: float) -> float:
        body = ScientificBody3D(load_body_spec())
        before = sum(item.position.x for item in body.particles) / len(
            body.particles
        )
        body.step(
            0.001,
            gravity=Vec3(0.0, 0.0, 0.0),
            ground_z=0.0,
            external_accelerations_m_s2={
                index: Vec3(acceleration_x, 0.0, 0.0)
                for index in range(len(body.particles))
            },
            velocity_retention=0.0,
            ground_velocity_retention_by_node={
                index: 0.25 for index in range(len(body.particles))
            },
        )
        after = sum(item.position.x for item in body.particles) / len(
            body.particles
        )
        return after - before

    positive = shifted(1.0)
    negative = shifted(-1.0)
    assert positive == pytest.approx(-negative, rel=1e-9, abs=1e-15)

    body = ScientificBody3D(load_body_spec())
    with pytest.raises(ValueError, match="unknown body node"):
        body.step(
            0.001,
            ground_velocity_retention_by_node={len(body.particles): 0.5},
        )
    with pytest.raises(ValueError, match="directional or continuous"):
        body.step(
            0.001,
            ground_velocity_retention_x=(0.9, 0.1),
            ground_velocity_retention_by_node={0: 0.5},
        )
