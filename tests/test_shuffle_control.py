import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_shuffle_control", ROOT / "tools" / "run_shuffle_control.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


def behaviour(paired, fictive, runs, stop):
    return {"paired_LI": paired, "fictive_punishment_LI": fictive, "spontaneous_forward_runs": runs, "pdm_stop_waves": stop}


def test_judge_marks_specific_only_when_every_shuffle_fails():
    verdicts = control.judge(
        {
            "intact": behaviour(1.2, -1.8, 10, 0.0),
            "1": behaviour(-0.05, -0.1, 10, 0.0),
            "2": behaviour(0.27, 0.8, 9, 0.0),
        },
        ["1", "2"],
    )
    assert verdicts["paired_LI"]["connectome_specific"] is True
    assert verdicts["fictive_punishment_LI"]["connectome_specific"] is True
    assert verdicts["spontaneous_forward_runs"] == {
        "criterion": ">= 8 of 10", "intact_passes": True, "shuffles_passing": ["1", "2"], "connectome_specific": False,
    }


def test_judge_not_specific_when_intact_fails():
    verdicts = control.judge({"intact": behaviour(0.1, -1.0, 10, 1.0), "1": behaviour(0.0, 0.0, 0, 1.0)}, ["1"])
    assert verdicts["paired_LI"]["connectome_specific"] is False
    assert verdicts["pdm_stop_waves"]["connectome_specific"] is False


@pytest.mark.parametrize("argv", [["--tag", "x"], ["--tag", "x", "--intact-fit", "a.json"], ["--tag", "x", "--init", "a.json"]])
def test_cli_requires_fits_or_fit_args(argv):
    with pytest.raises(SystemExit) as err:
        control.main(argv)
    assert err.value.code == 2
