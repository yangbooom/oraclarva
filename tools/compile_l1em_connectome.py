#!/usr/bin/env python3
"""Compile the local L1EM snapshot into data/local/.../compiled/ (never committed).

Verifies the snapshot SHA-256 pinned in the source manifest, assigns
transmitter signs, extracts neuron-level edges between public neurons, cross
checks outgoing against incoming records and writes:

  compiled/l1em_connectome_v0.json          neurons + signed metadata + edges
  compiled/l1em_connectome_v0.summary.json  aggregate counts (safe to quote)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from oraclarva.connectome_compile import (  # noqa: E402
    compile_connectome,
    cross_check,
    lineages_for,
    outgoing_edges,
)
from oraclarva.connectome_signs import assign_signs, coverage  # noqa: E402
from oraclarva.sources import load_source_manifest  # noqa: E402

SOURCE_ID = "vfb_l1em_public_connectome_2026_11_25"
DEFAULT_SNAPSHOT = (
    ROOT / "data" / "local" / "l1em_public_connectome" / "l1em-public-snapshot-2026-11-25.tar"
)


def pinned_sha256() -> str:
    for record in load_source_manifest(ROOT / "data" / "sources" / "source_manifest_v0.yaml"):
        if record["source_id"] == SOURCE_ID:
            return record["sha256"]
    raise KeyError(SOURCE_ID)


def read_snapshot(path: Path, expected_sha256: str) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise ValueError(f"snapshot checksum {digest} differs from manifest {expected_sha256}")
    with tarfile.open(path) as archive:
        return {m.name: json.load(archive.extractfile(m)) for m in archive.getmembers() if m.isfile()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_SNAPSHOT.parent / "compiled")
    args = parser.parse_args(argv)

    snap = read_snapshot(args.snapshot, pinned_sha256())
    ann_raw = snap["annotations_for_skeletons.json"]
    names = ann_raw["annotations"]
    annotations = {
        skid: [names.get(str(a["id"]), "") for a in items] for skid, items in ann_raw["skeletons"].items()
    }
    terms = snap["term_info.json"]
    signs = assign_signs(annotations, {s: lineages_for(t) for s, t in terms.items()}, min_support=3)

    batches = snap["connectivity.json"]
    edges = outgoing_edges(batches)
    check = cross_check(batches, edges)
    if check["mismatched"]:
        raise ValueError(f"outgoing/incoming mismatch: {check}")

    compiled = compile_connectome(
        snap["skeletons.json"],
        annotations,
        snap["neuron_names.json"]["names"],
        snap["neuron_names.json"]["vfb_ids"],
        terms,
        edges,
        signs,
    )
    winding = [n["skid"] for n in compiled["neurons"] if n["winding_2023"]]
    summary = compiled["summary"] | {
        "source_id": SOURCE_ID,
        "integrity": check,
        "sign_coverage_winding": coverage(signs, winding),
        "sign_coverage_all_public": coverage(signs),
        "signed_contacts_between_public_neurons": {
            label: sum(
                sum(e["contacts_by_confidence"])
                for e in compiled["edges"]
                if signs[e["pre"]].fast_sign == value
            )
            for label, value in (("excitatory", 1), ("inhibitory", -1), ("unknown_or_modulatory", None))
        },
    }
    compiled["summary"] = summary
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "l1em_connectome_v0.json").write_text(
        json.dumps(compiled, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (args.out / "l1em_connectome_v0.summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
