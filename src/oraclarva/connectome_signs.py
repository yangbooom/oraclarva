"""Assign neurotransmitter identity and fast synaptic sign to connectome neurons.

Evidence tiers, strongest first.  Every neuron records the tier that decided it.

1. ``MEASURED_PUBLISHED`` - curated neurotransmitter annotations on the public
   L1EM CATMAID neuron (``DIRECT_ANNOTATIONS``).  Heuristic or tentative
   annotations (e.g. "potential GABA (segregation index)", "Dopaminergic???")
   are deliberately excluded.
2. ``ANATOMY_DERIVED`` / ``lineage_consensus`` - a neuron without direct
   evidence inherits the transmitter of its lineage only when at least
   ``min_support`` directly-annotated members of that lineage exist and all of
   them agree.  No lineage-to-transmitter table is imported or invented; the
   consensus is computed from this dataset alone.
3. ``ANATOMY_DERIVED`` / ``cell_class_rule`` - explicit, named cell-class rules
   (``CELL_CLASS_RULES``), e.g. Kenyon cells are cholinergic.
4. ``unknown`` - left unresolved for ensemble sampling or fitting later.

Sign policy (project decision 2026-11-25):
* acetylcholine -> +1 (excitatory)
* GABA -> -1
* glutamate -> -1 inside the CNS (GluCl-alpha).  The motor-neuron-to-muscle
  junction is excitatory, but that edge lives in the neuromuscular layer, not in
  this CNS graph.
* dopamine, octopamine, serotonin -> no fast sign; flagged as a modulatory
  channel (used for plasticity / gain, never as a direct current).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Iterable, Mapping

FAST_SIGN = {"acetylcholine": 1, "GABA": -1, "glutamate": -1}
MODULATORY = frozenset({"dopamine", "octopamine", "serotonin"})

# Curated annotation -> transmitter(s).  Only annotations whose wording asserts
# identity are listed; anything tentative stays out on purpose.
DIRECT_ANNOTATIONS: Mapping[str, tuple[str, ...]] = {
    "mw cholinergic": ("acetylcholine",),
    "cholinergic": ("acetylcholine",),
    "Cholinergic": ("acetylcholine",),
    "acetylcholine": ("acetylcholine",),
    "mw GABAergic": ("GABA",),
    "GABA": ("GABA",),
    "mw glutamatergic": ("glutamate",),
    "glutamate": ("glutamate",),
    "Glutamatergic": ("glutamate",),
    "mw GABAergic and glutamatergic": ("GABA", "glutamate"),
    "mw cholinergic and glutamatergic": ("acetylcholine", "glutamate"),
    "mw dopaminergic": ("dopamine",),
    "dopamine": ("dopamine",),
    "Dopaminergic": ("dopamine",),
    "mw octopaminergic": ("octopamine",),
    "octopamine": ("octopamine",),
    "OANs": ("octopamine",),
    "serotonin": ("serotonin",),
}

# (rule id, annotation that defines the class, transmitter).
CELL_CLASS_RULES: tuple[tuple[str, str, str], ...] = (
    ("kenyon_cells_cholinergic", "mw KC", "acetylcholine"),
)


@dataclass(slots=True)
class NeuronSign:
    skid: str
    transmitters: list[str] = field(default_factory=list)
    fast_sign: int | None = None  # +1, -1, or None (unknown / modulatory only / conflict)
    modulatory: bool = False
    tier: str = "unknown"
    evidence: list[str] = field(default_factory=list)
    conflict: bool = False


def _resolve(transmitters: Iterable[str]) -> tuple[int | None, bool, bool]:
    """Return (fast_sign, modulatory, conflict) for a set of transmitters."""
    names = set(transmitters)
    signs = {FAST_SIGN[name] for name in names if name in FAST_SIGN}
    modulatory = bool(names & MODULATORY)
    if len(signs) > 1:
        return None, modulatory, True
    return (signs.pop() if signs else None), modulatory, False


def assign_signs(
    annotations_by_skid: Mapping[str, Iterable[str]],
    lineages_by_skid: Mapping[str, Iterable[str]] | None = None,
    min_support: int = 3,
) -> dict[str, NeuronSign]:
    lineages_by_skid = lineages_by_skid or {}
    out: dict[str, NeuronSign] = {}

    # Tier 1: direct annotations.
    for skid, names in annotations_by_skid.items():
        names = set(names)
        record = NeuronSign(skid=str(skid))
        hits = sorted(name for name in names if name in DIRECT_ANNOTATIONS)
        if hits:
            transmitters = sorted({t for name in hits for t in DIRECT_ANNOTATIONS[name]})
            sign, modulatory, conflict = _resolve(transmitters)
            record.transmitters = transmitters
            record.fast_sign, record.modulatory, record.conflict = sign, modulatory, conflict
            record.evidence = [f"annotation:{name}" for name in hits]
            record.tier = "MEASURED_PUBLISHED"
        out[record.skid] = record

    # Tier 2: lineage consensus computed from tier-1 members only.
    votes: dict[str, Counter[tuple[str, ...]]] = defaultdict(Counter)
    for skid, lineages in lineages_by_skid.items():
        record = out.get(str(skid))
        if record is None or record.tier != "MEASURED_PUBLISHED" or record.conflict:
            continue
        for lineage in lineages:
            votes[lineage][tuple(record.transmitters)] += 1
    consensus = {
        lineage: next(iter(counter))
        for lineage, counter in votes.items()
        if len(counter) == 1 and sum(counter.values()) >= min_support
    }
    for skid, lineages in lineages_by_skid.items():
        record = out.get(str(skid))
        if record is None or record.tier != "unknown":
            continue
        agreed = {consensus[lin] for lin in lineages if lin in consensus}
        if len(agreed) == 1:
            transmitters = list(agreed.pop())
            sign, modulatory, conflict = _resolve(transmitters)
            if not conflict:
                record.transmitters = transmitters
                record.fast_sign, record.modulatory = sign, modulatory
                record.tier = "ANATOMY_DERIVED"
                record.evidence = [
                    f"lineage_consensus:{lin}(n={sum(votes[lin].values())})"
                    for lin in sorted(lineages)
                    if lin in consensus
                ]

    # Tier 3: explicit cell-class rules.
    for skid, names in annotations_by_skid.items():
        record = out[str(skid)]
        if record.tier != "unknown":
            continue
        for rule_id, annotation, transmitter in CELL_CLASS_RULES:
            if annotation in set(names):
                record.transmitters = [transmitter]
                record.fast_sign, record.modulatory, _ = _resolve([transmitter])
                record.tier = "ANATOMY_DERIVED"
                record.evidence = [f"cell_class_rule:{rule_id}"]
                break
    return out


def coverage(signs: Mapping[str, NeuronSign], subset: Iterable[str] | None = None) -> dict:
    keys = [str(s) for s in subset] if subset is not None else list(signs)
    records = [signs[k] for k in keys if k in signs]
    tiers = Counter(r.tier for r in records)
    fast = Counter(
        "excitatory" if r.fast_sign == 1 else "inhibitory" if r.fast_sign == -1 else "none"
        for r in records
    )
    return {
        "neurons": len(records),
        "by_tier": dict(sorted(tiers.items())),
        "by_fast_sign": dict(sorted(fast.items())),
        "modulatory": sum(r.modulatory for r in records),
        "conflicts": sum(r.conflict for r in records),
        "fast_sign_resolved_fraction": (
            round(sum(r.fast_sign is not None for r in records) / len(records), 4) if records else 0.0
        ),
    }


def to_jsonable(signs: Mapping[str, NeuronSign]) -> dict[str, dict]:
    return {skid: asdict(record) for skid, record in sorted(signs.items(), key=lambda kv: int(kv[0]))}
