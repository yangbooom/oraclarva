from oraclarva.connectome_signs import assign_signs, coverage


def test_direct_annotations_and_sign_policy():
    signs = assign_signs(
        {
            "1": ["mw cholinergic"],
            "2": ["mw GABAergic"],
            "3": ["mw glutamatergic"],  # central glutamate is inhibitory
            "4": ["mw dopaminergic"],
            "5": ["mw GABAergic and glutamatergic"],
        }
    )
    assert signs["1"].fast_sign == 1
    assert signs["2"].fast_sign == -1
    assert signs["3"].fast_sign == -1
    assert signs["4"].fast_sign is None and signs["4"].modulatory
    assert signs["5"].fast_sign == -1 and not signs["5"].conflict
    assert {s.tier for s in signs.values()} == {"MEASURED_PUBLISHED"}


def test_tentative_annotations_are_not_evidence():
    signs = assign_signs({"1": ["potential GABA (segregation index)", "Dopaminergic???_xinyu"]})
    assert signs["1"].tier == "unknown" and signs["1"].fast_sign is None


def test_conflicting_fast_transmitters_stay_unresolved():
    signs = assign_signs({"1": ["mw cholinergic and glutamatergic"]})
    assert signs["1"].conflict and signs["1"].fast_sign is None


def test_lineage_consensus_requires_agreement_and_support():
    annotations = {str(i): ["mw cholinergic"] for i in range(3)}
    annotations.update({"10": [], "20": ["mw GABAergic"], "21": ["mw cholinergic"], "22": []})
    lineages = {
        "0": ["linA"], "1": ["linA"], "2": ["linA"], "10": ["linA"],
        "20": ["linB"], "21": ["linB"], "22": ["linB"],
    }
    signs = assign_signs(annotations, lineages, min_support=3)
    assert signs["10"].tier == "ANATOMY_DERIVED" and signs["10"].fast_sign == 1
    assert signs["10"].evidence == ["lineage_consensus:linA(n=3)"]
    assert signs["22"].tier == "unknown"  # linB disagrees and lacks support


def test_lineage_consensus_below_support_is_not_used():
    signs = assign_signs(
        {"0": ["mw GABAergic"], "1": ["mw GABAergic"], "9": []},
        {"0": ["lin"], "1": ["lin"], "9": ["lin"]},
        min_support=3,
    )
    assert signs["9"].tier == "unknown"


def test_cell_class_rule_and_coverage():
    signs = assign_signs({"1": ["mw KC"], "2": []})
    assert signs["1"].evidence == ["cell_class_rule:kenyon_cells_cholinergic"]
    report = coverage(signs)
    assert report["by_tier"] == {"ANATOMY_DERIVED": 1, "unknown": 1}
    assert report["fast_sign_resolved_fraction"] == 0.5
