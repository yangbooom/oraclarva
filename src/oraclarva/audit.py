"""Audit simple neuron and synapse CSV exports before simulation."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(slots=True)
class AuditReport:
    neuron_count: int = 0
    synapse_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["ok"] = self.ok
        return result


def audit_connectome(neurons_path: str | Path, synapses_path: str | Path) -> AuditReport:
    report = AuditReport()
    neuron_ids: set[str] = set()
    with Path(neurons_path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "neuron_id" not in reader.fieldnames:
            report.errors.append("neurons CSV must contain neuron_id")
            return report
        for line, row in enumerate(reader, start=2):
            neuron_id = (row.get("neuron_id") or "").strip()
            if not neuron_id:
                report.errors.append(f"neurons:{line}: empty neuron_id")
            elif neuron_id in neuron_ids:
                report.errors.append(f"neurons:{line}: duplicate neuron_id {neuron_id}")
            else:
                neuron_ids.add(neuron_id)
    report.neuron_count = len(neuron_ids)

    seen_edges: set[tuple[str, str, str]] = set()
    with Path(synapses_path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"pre", "post", "weight", "kind"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            report.errors.append("synapses CSV must contain pre,post,weight,kind")
            return report
        for line, row in enumerate(reader, start=2):
            pre = (row.get("pre") or "").strip()
            post = (row.get("post") or "").strip()
            kind = (row.get("kind") or "").strip().lower()
            edge = (pre, post, kind)
            report.synapse_count += 1
            if pre not in neuron_ids:
                report.errors.append(f"synapses:{line}: unknown pre neuron {pre}")
            if post not in neuron_ids:
                report.errors.append(f"synapses:{line}: unknown post neuron {post}")
            if kind not in {"excitatory", "inhibitory", "unknown"}:
                report.errors.append(f"synapses:{line}: invalid kind {kind}")
            try:
                weight = float(row.get("weight") or "")
                if weight <= 0:
                    raise ValueError
            except ValueError:
                report.errors.append(f"synapses:{line}: weight must be positive")
            if edge in seen_edges:
                report.warnings.append(f"synapses:{line}: duplicate edge {pre}->{post} ({kind})")
            seen_edges.add(edge)
            if pre == post:
                report.warnings.append(f"synapses:{line}: self-loop {pre}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit connectome CSVs. Neurons: neuron_id. Synapses: pre,post,weight,kind."
    )
    parser.add_argument("neurons")
    parser.add_argument("synapses")
    args = parser.parse_args(argv)
    report = audit_connectome(args.neurons, args.synapses)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
