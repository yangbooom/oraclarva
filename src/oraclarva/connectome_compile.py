"""Compile a local L1EM CATMAID snapshot into a neuron-level signed connectome.

Pure, dependency-free functions; ``tools/compile_l1em_connectome.py`` wraps them
and writes the result to the git-ignored ``data/local/`` tree.

Edges come only from each skeleton's own *outgoing* query, so every directed
pair is counted once.  The *incoming* half of the same responses is used as an
independent integrity check (``cross_check``).  Contacts are kept per CATMAID
confidence bin (1-5); no threshold is applied here.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable, Mapping

from .connectome_signs import NeuronSign

WINDING_ANNOTATION = "Winding, Pedigo et al. 2023"
_SEGMENT_TYPE = re.compile(r"(abdominal|thoracic) (\d)")
_SEGMENT_NAME = re.compile(r"_([at])(\d)[lr]\b", re.IGNORECASE)


def segments_for(term: Mapping[str, Any] | None) -> list[str]:
    """Segment labels (e.g. ``A1``, ``T3``) from the VFB type and neuron name."""
    if not term:
        return []
    text = f"{(term.get('Meta') or {}).get('Types', '')} {term.get('Name', '')}"
    found = {("A" if kind == "abdominal" else "T") + n for kind, n in _SEGMENT_TYPE.findall(text)}
    found |= {kind.upper() + n for kind, n in _SEGMENT_NAME.findall(str(term.get("Name", "")))}
    return sorted(found)


def lineages_for(term: Mapping[str, Any] | None) -> list[str]:
    return sorted(tag for tag in (term or {}).get("Tags") or [] if tag.startswith("lineage_"))


def dataset_sources(term: Mapping[str, Any] | None) -> list[str]:
    licenses = (term or {}).get("Licenses") or {}
    values = licenses.values() if isinstance(licenses, dict) else licenses
    return sorted({str(item.get("source", "")) for item in values if isinstance(item, dict)})


def _bins(value: Iterable[int]) -> list[int]:
    bins = [int(x) for x in value]
    if len(bins) != 5 or any(x < 0 for x in bins):
        raise ValueError(f"expected 5 non-negative confidence bins, got {bins}")
    return bins


def outgoing_edges(batches: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], list[int]]:
    """(pre, post) -> contacts per confidence bin, from each query's outgoing half."""
    edges: dict[tuple[str, str], list[int]] = {}
    for batch in batches:
        queried = {str(s) for s in batch["query_skids"]}
        for post, info in batch["result"].get("outgoing", {}).items():
            for pre, bins in info.get("skids", {}).items():
                if pre not in queried:
                    raise ValueError(f"outgoing pre {pre} was not queried in this batch")
                key = (pre, str(post))
                if key in edges:
                    raise ValueError(f"duplicate edge {key}")
                edges[key] = _bins(bins)
    return edges


def cross_check(
    batches: Iterable[Mapping[str, Any]], edges: Mapping[tuple[str, str], list[int]]
) -> dict[str, int]:
    """Compare every incoming record whose pre was also queried with the outgoing edge set."""
    batches = list(batches)
    queried_all = {str(s) for b in batches for s in b["query_skids"]}
    checked = mismatched = 0
    for batch in batches:
        for pre, info in batch["result"].get("incoming", {}).items():
            if pre not in queried_all:
                continue
            for post, bins in info.get("skids", {}).items():
                checked += 1
                if edges.get((pre, str(post))) != _bins(bins):
                    mismatched += 1
    return {"incoming_records_checked": checked, "mismatched": mismatched}


def compile_connectome(
    skeletons: Iterable[int | str],
    annotations_by_skid: Mapping[str, list[str]],
    names: Mapping[str, str],
    vfb_ids: Mapping[str, str],
    terms: Mapping[str, Mapping[str, Any] | None],
    edges: Mapping[tuple[str, str], list[int]],
    signs: Mapping[str, NeuronSign],
) -> dict[str, Any]:
    public = sorted({str(s) for s in skeletons}, key=int)
    public_set = set(public)
    neurons = []
    for skid in public:
        sign = signs.get(skid)
        term = terms.get(skid)
        annotations = annotations_by_skid.get(skid, [])
        neurons.append(
            {
                "skid": skid,
                "name": names.get(skid, ""),
                "vfb_id": vfb_ids.get(skid, ""),
                "winding_2023": WINDING_ANNOTATION in annotations,
                "segments": segments_for(term),
                "lineages": lineages_for(term),
                "datasets": dataset_sources(term),
                "transmitters": sign.transmitters if sign else [],
                "fast_sign": sign.fast_sign if sign else None,
                "modulatory": sign.modulatory if sign else False,
                "sign_tier": sign.tier if sign else "unknown",
                "sign_evidence": sign.evidence if sign else [],
            }
        )
    kept = sorted(
        ((pre, post, bins) for (pre, post), bins in edges.items() if pre in public_set and post in public_set),
        key=lambda e: (int(e[0]), int(e[1])),
    )
    dropped = Counter(
        "post_not_public" for (pre, post) in edges if pre in public_set and post not in public_set
    )
    return {
        "neurons": neurons,
        "edges": [{"pre": pre, "post": post, "contacts_by_confidence": bins} for pre, post, bins in kept],
        "summary": {
            "neurons": len(neurons),
            "winding_2023_neurons": sum(n["winding_2023"] for n in neurons),
            "edges_between_public_neurons": len(kept),
            "contacts_between_public_neurons": sum(sum(b) for _, _, b in kept),
            "edges_to_non_public_partners": dropped["post_not_public"],
            "contacts_to_non_public_partners": sum(
                sum(b) for (pre, post), b in edges.items() if pre in public_set and post not in public_set
            ),
        },
    }
