from pathlib import Path

from oraclarva.audit import audit_connectome


def write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_audit_accepts_consistent_csv(tmp_path):
    neurons = write(tmp_path / "neurons.csv", "neuron_id\na\nb\n")
    synapses = write(
        tmp_path / "synapses.csv", "pre,post,weight,kind\na,b,3,excitatory\n"
    )
    report = audit_connectome(neurons, synapses)
    assert report.ok
    assert (report.neuron_count, report.synapse_count) == (2, 1)


def test_audit_reports_unknown_endpoint_and_bad_weight(tmp_path):
    neurons = write(tmp_path / "neurons.csv", "neuron_id\na\n")
    synapses = write(
        tmp_path / "synapses.csv", "pre,post,weight,kind\na,missing,0,excitatory\n"
    )
    report = audit_connectome(neurons, synapses)
    assert not report.ok
    assert any("unknown post" in error for error in report.errors)
    assert any("weight must be positive" in error for error in report.errors)
