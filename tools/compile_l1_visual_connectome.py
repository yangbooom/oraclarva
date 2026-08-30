"""Compile the published L1 larval-optic-neuropil connection matrices.

The input is Larderet et al. Figure 2 source data 1 (CC BY 4.0).  This
compiler preserves observed contact counts and neuron identities; it does not
infer synapse signs, photoreceptor gains, or a path from VPNs to the VNC.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    ROOT
    / "data"
    / "sources"
    / "larderet_2017_l1_visual_circuit"
    / "elife-28387-fig2-data1-v2.xlsx"
)
OUTPUT_PATH = ROOT / "data" / "connectome" / "l1_visual_connectome_v0.json"
SOURCE_SHA256 = "f9c200cdea0a9a80dc1e7d48aea0a25540d7d63341f705ff7c90faed9effd08f"
XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
}


LAYOUTS = (
    {
        "lon_side": "left",
        "header_row": 7,
        "first_row": 8,
        "last_row": 35,
        "first_column": 5,
        "last_column": 32,
    },
    {
        "lon_side": "right",
        "header_row": 42,
        "first_row": 43,
        "last_row": 74,
        "first_column": 5,
        "last_column": 36,
    },
)


TRANSMITTER_BY_CLASS = {
    "Rh5-PR": "cholinergic",
    "Rh6-PR": "cholinergic",
    "cha-lOLP": "cholinergic",
    "glu-lOLP": "glutamatergic",
    "extra-glu-lOLP": "glutamatergic",
    "VPLN": "glutamatergic",
    "nc-LaN": "cholinergic",
    "5th-LaN": "cholinergic",
    "Pdf-LaN": "Pdf_peptidergic_transmitter_not_resolved",
    "PVL09": "cholinergic",
    "pOLP": "cholinergic",
    "SP2-1": "serotonergic",
    "sVUM2": "octopaminergic_or_tyraminergic",
}


def _column_number(reference: str) -> int:
    match = re.match(r"[A-Z]+", reference)
    if match is None:
        raise ValueError(f"invalid XLSX cell reference {reference!r}")
    result = 0
    for character in match.group():
        result = result * 26 + ord(character) - 64
    return result


def _read_cells(path: Path) -> dict[tuple[int, int], str]:
    with ZipFile(path) as workbook:
        shared_root = ElementTree.fromstring(
            workbook.read("xl/sharedStrings.xml")
        )
        shared = [
            "".join(
                node.text or ""
                for node in item.findall(".//main:t", XML_NS)
            )
            for item in shared_root.findall("main:si", XML_NS)
        ]
        sheet_root = ElementTree.fromstring(
            workbook.read("xl/worksheets/sheet1.xml")
        )

    cells: dict[tuple[int, int], str] = {}
    for cell in sheet_root.findall(".//main:c", XML_NS):
        reference = cell.attrib["r"]
        row_match = re.search(r"[0-9]+$", reference)
        if row_match is None:
            raise ValueError(f"invalid XLSX cell reference {reference!r}")
        value_node = cell.find("main:v", XML_NS)
        value = "" if value_node is None else value_node.text or ""
        if cell.attrib.get("t") == "s" and value:
            value = shared[int(value)]
        cells[(int(row_match.group()), _column_number(reference))] = value
    return cells


def _neuron_class(identity: str) -> str:
    if identity.startswith("Rh5-PR"):
        return "Rh5-PR"
    if identity.startswith("Rh6-PR"):
        return "Rh6-PR"
    if identity.startswith("Pdf-LaN"):
        return "Pdf-LaN"
    if identity.startswith("nc-LaN"):
        return "nc-LaN"
    if identity.startswith("sVUM2"):
        return "sVUM2"
    if identity in TRANSMITTER_BY_CLASS:
        return identity
    raise ValueError(f"unrecognized visual neuron identity {identity!r}")


def _node_id(lon_side: str, identity: str) -> str:
    return f"{lon_side}:{identity.replace(' ', '_')}"


def _integer_cell(
    cells: dict[tuple[int, int], str], row: int, column: int
) -> int:
    raw = cells.get((row, column), "")
    if raw == "":
        return 0
    value = float(raw)
    if not value.is_integer() or value < 0:
        raise ValueError(f"non-integer connection count at row {row}, column {column}")
    return int(value)


def compile_connectome() -> dict[str, object]:
    digest = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(
            "Larderet source-data checksum differs from the audited artifact"
        )
    cells = _read_cells(SOURCE_PATH)
    if cells.get((2, 4)) != (
        "Figure 2 - source data 1: Complete synaptic connection matrices "
        "from both LON."
    ):
        raise ValueError("unexpected Larderet workbook title")

    neurons: list[dict[str, object]] = []
    connections: list[dict[str, object]] = []
    hemisphere_summary: dict[str, dict[str, int]] = {}

    for layout in LAYOUTS:
        lon_side = str(layout["lon_side"])
        header_row = int(layout["header_row"])
        first_row = int(layout["first_row"])
        last_row = int(layout["last_row"])
        first_column = int(layout["first_column"])
        last_column = int(layout["last_column"])
        identities = [
            cells.get((header_row, column), "")
            for column in range(first_column, last_column + 1)
        ]
        row_identities = [
            cells.get((row, 4), "") for row in range(first_row, last_row + 1)
        ]
        if not all(identities) or identities != row_identities:
            raise ValueError(f"{lon_side} LON matrix labels are not square")

        for matrix_index, identity in enumerate(identities):
            neuron_class = _neuron_class(identity)
            neurons.append(
                {
                    "node_id": _node_id(lon_side, identity),
                    "lon_side": lon_side,
                    "matrix_index": matrix_index,
                    "identity": identity,
                    "neuron_class": neuron_class,
                    "transmitter": TRANSMITTER_BY_CLASS[neuron_class],
                    "transmitter_provenance": "MEASURED_PUBLISHED",
                    "synaptic_effect": None,
                    "synaptic_effect_provenance": "unknown",
                    "shared_unpaired_identity": neuron_class == "sVUM2",
                }
            )

        side_contacts = 0
        side_pairs = 0
        for row, pre_identity in zip(
            range(first_row, last_row + 1), identities, strict=True
        ):
            for column, post_identity in zip(
                range(first_column, last_column + 1),
                identities,
                strict=True,
            ):
                count = _integer_cell(cells, row, column)
                if count == 0:
                    continue
                connections.append(
                    {
                        "pre": _node_id(lon_side, pre_identity),
                        "post": _node_id(lon_side, post_identity),
                        "synaptic_contacts": count,
                        "provenance": "MEASURED_PUBLISHED",
                    }
                )
                side_contacts += count
                side_pairs += 1
        hemisphere_summary[lon_side] = {
            "matrix_entries": len(identities),
            "photoreceptors": sum(
                identity.startswith(("Rh5-PR", "Rh6-PR"))
                for identity in identities
            ),
            "nonzero_connection_pairs": side_pairs,
            "synaptic_contacts": side_contacts,
        }

    if len(neurons) != 60:
        raise ValueError("expected 60 side-scoped matrix entries")
    if len(connections) != 422:
        raise ValueError("expected 422 nonzero connection pairs")
    if sum(item["synaptic_contacts"] for item in connections) != 3297:
        raise ValueError("expected 3297 within-LON synaptic contacts")

    return {
        "schema_version": 1,
        "model_id": "dmel_l1_visual_connectome_v0",
        "status": "published_l1_lon_matrix_with_unresolved_effect_signs",
        "stage": "L1",
        "source": {
            "source_id": "larderet_2017_l1_visual_circuit",
            "article_doi": "10.7554/eLife.28387",
            "source_data_doi": "10.7554/eLife.28387.009",
            "url": (
                "https://cdn.elifesciences.org/articles/28387/"
                "elife-28387-fig2-data1-v2.xlsx"
            ),
            "license": "CC BY 4.0",
            "local_artifact": str(SOURCE_PATH.relative_to(ROOT)),
            "sha256": SOURCE_SHA256,
            "provenance": "MEASURED_PUBLISHED",
        },
        "specimen": {
            "age_h": 6,
            "section_thickness_nm": 50,
            "image_pixel_size_nm": 4,
            "scope": "first-instar CNS ssTEM; bilateral larval optic neuropils",
            "provenance": "MEASURED_PUBLISHED",
        },
        "summary": {
            "side_scoped_matrix_entries": len(neurons),
            "unpaired_svum_identities_repeated_across_lon_matrices": 2,
            "tiny_vlns_absent_from_connection_matrix": 2,
            "nonzero_connection_pairs": len(connections),
            "within_lon_synaptic_contacts": sum(
                item["synaptic_contacts"] for item in connections
            ),
            "by_lon_side": hemisphere_summary,
        },
        "neurons": neurons,
        "connections": connections,
        "limitations": [
            "The two LON matrices contain side-scoped entries. sVUM2md and "
            "sVUM2mx are unpaired neurons represented in both matrices and must "
            "not be counted as four unique biological neurons.",
            "The two Tiny VLNs described in the article are absent from this "
            "published connection matrix and are not invented here.",
            "Connection counts are observed structural contacts; physiological "
            "weights, delays, and synaptic effects are not measured by this file.",
            "The source covers the larval optic neuropil through projection "
            "neurons. It does not identify a visual-VPN-to-VNC-premotor path.",
            "The matrix contains connections within each LON and counts of "
            "outputs beyond it, but identities of beyond-LON targets are absent.",
        ],
        "release_validated": False,
    }


def encoded_connectome() -> str:
    return json.dumps(
        compile_connectome(), indent=2, ensure_ascii=False
    ) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile the published L1 visual connection matrices"
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = encoded_connectome()
    if args.check:
        if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(
            encoding="utf-8"
        ) != rendered:
            print(
                "stale generated visual connectome: run "
                f"{Path(__file__).relative_to(ROOT)}"
            )
            return 1
        print("generated visual connectome is current")
        return 0
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
