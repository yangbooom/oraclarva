import pytest

from oraclarva.connectome_compile import (
    compile_connectome,
    cross_check,
    outgoing_edges,
    segments_for,
)
from oraclarva.connectome_signs import assign_signs

BATCHES = [
    {
        "query_skids": [1, 2],
        "result": {
            "outgoing": {"2": {"skids": {"1": [0, 0, 0, 1, 3]}}, "9": {"skids": {"2": [0, 0, 0, 0, 2]}}},
            "incoming": {"3": {"skids": {"1": [0, 0, 0, 0, 1]}}},
        },
    },
    {
        "query_skids": [3],
        "result": {
            "outgoing": {"1": {"skids": {"3": [0, 0, 0, 0, 1]}}},
            "incoming": {"1": {"skids": {"3": [0, 0, 0, 1, 3]}}},
        },
    },
]


def test_outgoing_edges_counts_each_pair_once():
    edges = outgoing_edges(BATCHES)
    assert edges == {("1", "2"): [0, 0, 0, 1, 3], ("2", "9"): [0, 0, 0, 0, 2], ("3", "1"): [0, 0, 0, 0, 1]}


def test_outgoing_rejects_unqueried_pre_and_bad_bins():
    with pytest.raises(ValueError):
        outgoing_edges([{"query_skids": [1], "result": {"outgoing": {"2": {"skids": {"5": [1, 0, 0, 0, 0]}}}}}])
    with pytest.raises(ValueError):
        outgoing_edges([{"query_skids": [1], "result": {"outgoing": {"2": {"skids": {"1": [1]}}}}}])


def test_cross_check_detects_mismatch():
    edges = outgoing_edges(BATCHES)
    assert cross_check(BATCHES, edges) == {"incoming_records_checked": 2, "mismatched": 1}
    # incoming 3->1 matches outgoing; incoming 1->3 has no outgoing counterpart.


def test_segments_from_type_and_name():
    term = {"Name": "MN1 aCC_a1r (L1EM:1)", "Meta": {"Types": "larval motor neuron of abdominal 1 neuromere"}}
    assert segments_for(term) == ["A1"]
    assert segments_for({"Name": "A27h_t3l", "Meta": {}}) == ["T3"]
    assert segments_for(None) == []


def test_compile_keeps_public_edges_and_signs():
    edges = {("1", "2"): [0, 0, 0, 1, 3], ("2", "9"): [0, 0, 0, 0, 2]}
    annotations = {"1": ["mw cholinergic", "Winding, Pedigo et al. 2023"], "2": ["mw GABAergic"]}
    signs = assign_signs(annotations)
    result = compile_connectome([1, 2], annotations, {"1": "a"}, {}, {}, edges, signs)
    assert [(e["pre"], e["post"]) for e in result["edges"]] == [("1", "2")]
    assert result["summary"]["contacts_to_non_public_partners"] == 2
    neuron = {n["skid"]: n for n in result["neurons"]}
    assert neuron["1"]["fast_sign"] == 1 and neuron["1"]["winding_2023"]
    assert neuron["2"]["fast_sign"] == -1 and not neuron["2"]["winding_2023"]
