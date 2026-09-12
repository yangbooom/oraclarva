from __future__ import annotations

from oraclarva.axial import AxialLocomotionLarva


def final_activation(result, segment: str) -> float:
    return float(result.trajectory_samples[-1]["segment_activation"][segment])


def test_pair1_lesion_releases_forward_path_during_competing_touch():
    control = AxialLocomotionLarva().run(
        posterior_touch=True,
        anterior_touch=True,
        duration_s=1.0,
        record_trajectory_interval_s=None,
    )
    lesion = AxialLocomotionLarva(
        lesion_node_ids=("descending:Pair1",)
    ).run(
        posterior_touch=True,
        anterior_touch=True,
        duration_s=1.0,
        record_trajectory_interval_s=None,
    )

    assert control.premotor_spike_times_s["backward"]["A2"]
    assert lesion.premotor_spike_times_s["backward"]["A2"]
    assert not control.premotor_spike_times_s["forward"]["A5"]
    assert lesion.premotor_spike_times_s["forward"]["A5"]


def test_named_inhibitory_lesions_delay_local_relaxation():
    forward_control = AxialLocomotionLarva().run(
        posterior_touch=True,
        duration_s=0.45,
        record_trajectory_interval_s=0.45,
    )
    gdl_lesion = AxialLocomotionLarva(
        lesion_node_ids=("inhibitory:GDL:A6",)
    ).run(
        posterior_touch=True,
        duration_s=0.45,
        record_trajectory_interval_s=0.45,
    )
    assert forward_control.relaxation_spike_times_s["GDL"]["A6"]
    assert not gdl_lesion.relaxation_spike_times_s["GDL"]["A6"]
    assert final_activation(gdl_lesion, "A6") > final_activation(
        forward_control, "A6"
    )

    backward_control = AxialLocomotionLarva().run(
        anterior_touch=True,
        duration_s=0.45,
        record_trajectory_interval_s=0.45,
    )
    ifb_lesion = AxialLocomotionLarva(
        lesion_node_ids=("inhibitory:Ifb-Bwd:A1",)
    ).run(
        anterior_touch=True,
        duration_s=0.45,
        record_trajectory_interval_s=0.45,
    )
    canon_lesion = AxialLocomotionLarva(
        lesion_node_ids=("inhibitory:Canon-A18g:A1",)
    ).run(
        anterior_touch=True,
        duration_s=0.45,
        record_trajectory_interval_s=0.45,
    )

    assert backward_control.relaxation_spike_times_s["Ifb-Bwd"]["A1"]
    assert backward_control.relaxation_spike_times_s["Canon-A18g"]["A1"]
    assert not ifb_lesion.relaxation_spike_times_s["Ifb-Bwd"]["A1"]
    assert not canon_lesion.relaxation_spike_times_s["Canon-A18g"]["A1"]
    assert final_activation(ifb_lesion, "A1") > final_activation(
        backward_control, "A1"
    )
    assert final_activation(canon_lesion, "A1") > final_activation(
        backward_control, "A1"
    )
