import hashlib
import importlib.util
import io
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "fetch_l1em", ROOT / "tools" / "fetch_l1em_public_connectome.py"
)
fetch_l1em = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_l1em)


def _term(*labels):
    return {
        "Licenses": {
            str(i): {"label": label, "source": f"dataset {i}"} for i, label in enumerate(labels)
        }
    }


def test_batched_splits_and_rejects_bad_size():
    assert list(fetch_l1em.batched([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
    with pytest.raises(ValueError):
        list(fetch_l1em.batched([1], 0))


def test_license_audit_allows_only_listed_licenses():
    audit = fetch_l1em.audit_licenses(
        {
            "1": _term("CC-BY_4.0"),
            "2": _term("CC-BY-SA_4.0", "CC-BY_4.0"),
            "3": _term("CC-BY-NC_4.0"),
            "4": None,
            "5": {"Licenses": {}},
        }
    )
    assert audit["neurons_allowed"] == 2
    assert audit["neurons_disallowed"] == {"3": ["CC-BY-NC_4.0"]}
    assert audit["neurons_missing_license"] == ["4", "5"]
    assert audit["ok"] is False


def test_license_audit_ok_when_all_allowed():
    audit = fetch_l1em.audit_licenses({"7": _term("CC-BY-SA_4.0")})
    assert audit["ok"] is True
    assert audit["license_label_counts"] == {"CC-BY-SA_4.0": 1}


def test_deterministic_tar_is_byte_stable():
    a = fetch_l1em.deterministic_tar({"b.json": b"2", "a.json": b"1"})
    b = fetch_l1em.deterministic_tar({"a.json": b"1", "b.json": b"2"})
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()
    with tarfile.open(fileobj=io.BytesIO(a)) as archive:
        assert archive.getnames() == ["a.json", "b.json"]


def test_local_data_directory_is_git_ignored():
    probe = "data/local/l1em_public_connectome/probe.tar"
    result = subprocess.run(
        ["git", "check-ignore", "-q", probe], cwd=ROOT, check=False
    )
    assert result.returncode == 0, "data/local/ must never be committed"


def test_client_serves_cached_response_without_network(tmp_path):
    client = fetch_l1em.Client(cache_dir=tmp_path, delay_s=0.0)
    url = "https://example.invalid/x?id=1"
    client._cache_path(url).write_text('{"cached": true}', encoding="utf-8")
    assert client.get_json("https://example.invalid/x", {"id": 1}) == {"cached": True}
    assert client.requests == 0 and client.cache_hits == 1
