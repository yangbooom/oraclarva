#!/usr/bin/env python3
"""Fetch the public L1EM CATMAID connectome into a local, never-committed cache.

License boundary
----------------
VFB attaches a dataset license (CC BY 4.0 or CC BY-SA 4.0 so far) to every
public L1EM neuron.  This repository is public, so the raw responses and any
compiled connectome derived from them are written under ``data/local/`` (git
ignored) and are NOT redistributed.  Only this method, the pinned SHA-256 of the
resulting snapshot, and the license audit summary are committed.

Every neuron's VFB term-info is fetched so its license is recorded, never
assumed.  ``audit_licenses`` fails the run if any neuron carries a license
outside ``ALLOWED_LICENSES`` or has none, so a later compiler can exclude it.

Endpoints (public, read-only GET via the VFB cached proxy):
  https://l1em.catmaid.virtualflybrain.org/1/skeletons/
  https://v3-cached.virtualflybrain.org/catmaid/l1em/{annotations,annotations_for_skeletons,neuron_names,connectivity}
  https://v3-cached.virtualflybrain.org/get_term_info?id=VFB_...
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "local" / "l1em_public_connectome"

CATMAID = "https://l1em.catmaid.virtualflybrain.org/1/"
PROXY = "https://v3-cached.virtualflybrain.org/catmaid/l1em/"
TERM_INFO = "https://v3-cached.virtualflybrain.org/get_term_info"
# Generic client name only; no user or project contact details.
USER_AGENT = "oraclarva-data-fetch/0.1"

ALLOWED_LICENSES = frozenset({"CC-BY_4.0", "CC-BY-SA_4.0"})
WINDING_ANNOTATION = "Winding, Pedigo et al. 2023"


# ---------------------------------------------------------------- pure helpers


def batched(items: Sequence[Any], size: int) -> Iterator[list[Any]]:
    if size <= 0:
        raise ValueError("batch size must be positive")
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def license_labels(term: dict[str, Any]) -> list[dict[str, str]]:
    """Return every (license, dataset source) pair VFB attaches to a term."""
    licenses = term.get("Licenses") or {}
    values = licenses.values() if isinstance(licenses, dict) else licenses
    out = []
    for item in values:
        if not isinstance(item, dict) or not item.get("label"):
            continue
        out.append({"label": str(item["label"]), "source": str(item.get("source", ""))})
    return out


def audit_licenses(
    terms_by_skid: dict[str, dict[str, Any] | None],
    allowed: Iterable[str] = ALLOWED_LICENSES,
) -> dict[str, Any]:
    """Classify each skeleton as allowed, disallowed, or missing a license.

    A neuron is allowed only if it has at least one license and every license
    attached to it is in ``allowed``.
    """
    allowed = frozenset(allowed)
    label_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    allowed_skids, disallowed, missing = [], {}, []
    for skid in sorted(terms_by_skid, key=int):
        term = terms_by_skid[skid]
        labels = license_labels(term) if term else []
        if not labels:
            missing.append(skid)
            continue
        names = sorted({item["label"] for item in labels})
        label_counts.update(names)
        source_counts.update({item["source"] for item in labels})
        if set(names) <= allowed:
            allowed_skids.append(skid)
        else:
            disallowed[skid] = names
    return {
        "allowed_licenses": sorted(allowed),
        "neurons_total": len(terms_by_skid),
        "neurons_allowed": len(allowed_skids),
        "neurons_disallowed": disallowed,
        "neurons_missing_license": missing,
        "license_label_counts": dict(sorted(label_counts.items())),
        "dataset_source_counts": dict(sorted(source_counts.items())),
        "ok": not disallowed and not missing,
    }


def deterministic_tar(files: dict[str, bytes]) -> bytes:
    """Byte-stable tar (sorted names, zeroed metadata) so the SHA-256 is reproducible."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(files):
            data = files[name]
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


# -------------------------------------------------------------------- network


class Client:
    """Polite GET client with an on-disk response cache so runs can resume."""

    def __init__(
        self, cache_dir: Path | None = None, delay_s: float = 0.1, retries: int = 4
    ) -> None:
        self.cache_dir = cache_dir
        self.delay_s = delay_s
        self.retries = retries
        self.requests = 0
        self.cache_hits = 0
        self._lock = threading.Lock()
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()[:40]}.json"

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        cached = self._cache_path(url)
        if cached is not None and cached.exists():
            with self._lock:
                self.cache_hits += 1
            return json.loads(cached.read_text(encoding="utf-8"))
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        for attempt in range(self.retries + 1):
            try:
                time.sleep(self.delay_s)
                with self._lock:
                    self.requests += 1
                with urllib.request.urlopen(request, timeout=300) as response:
                    value = json.load(response)
                if cached is not None:
                    tmp = cached.with_suffix(".tmp")
                    tmp.write_text(json.dumps(value), encoding="utf-8")
                    tmp.replace(cached)
                return value
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                if isinstance(error, urllib.error.HTTPError) and error.code in {400, 403, 404, 405}:
                    raise
                if attempt == self.retries:
                    raise
                time.sleep(2.0 * (attempt + 1))
        raise AssertionError("unreachable")


def _dump(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")


def fetch(client: Client, out_dir: Path, workers: int = 4, log=print) -> dict[str, Any]:
    files: dict[str, bytes] = {}

    skids = sorted(int(s) for s in client.get_json(CATMAID + "skeletons/"))
    files["skeletons.json"] = _dump(skids)
    log(f"skeletons: {len(skids)}")

    files["annotations.json"] = _dump(client.get_json(PROXY + "annotations"))

    annotations, names, vfb_ids, connectivity = {}, {}, {}, []
    for index, batch in enumerate(batched(skids, 250)):
        ids = ",".join(map(str, batch))
        ann = client.get_json(PROXY + "annotations_for_skeletons", {"ids": ids})
        annotations.setdefault("skeletons", {}).update(ann["result"]["skeletons"])
        annotations.setdefault("annotations", {}).update(ann["result"].get("annotations", {}))
        nn = client.get_json(PROXY + "neuron_names", {"ids": ids})
        names.update(nn["result"])
        vfb_ids.update(nn.get("reverse_map") or {})
        log(f"annotations/names batch {index + 1}")
    files["annotations_for_skeletons.json"] = _dump(annotations)
    files["neuron_names.json"] = _dump({"names": names, "vfb_ids": vfb_ids})

    for index, batch in enumerate(batched(skids, 100)):
        response = client.get_json(PROXY + "connectivity", {"ids": ",".join(map(str, batch))})
        connectivity.append({"query_skids": batch, "result": response["result"]})
        log(f"connectivity batch {index + 1}")
    files["connectivity.json"] = _dump(connectivity)

    def one_term(skid: str) -> tuple[str, dict[str, Any] | None]:
        vfb_id = vfb_ids.get(skid)
        if not vfb_id:
            return skid, None
        try:
            return skid, client.get_json(TERM_INFO, {"id": vfb_id})
        except urllib.error.HTTPError:
            return skid, None

    terms: dict[str, dict[str, Any] | None] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, (skid, term) in enumerate(pool.map(one_term, map(str, skids))):
            terms[skid] = term
            if index % 250 == 0:
                log(f"term-info {index}/{len(skids)}")
    files["term_info.json"] = _dump(terms)

    audit = audit_licenses(terms)
    files["license_audit.json"] = _dump(audit)

    snapshot = deterministic_tar(files)
    digest = hashlib.sha256(snapshot).hexdigest()
    retrieved = date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    tar_path = out_dir / f"l1em-public-snapshot-{retrieved}.tar"
    tar_path.write_bytes(snapshot)

    winding_id = next(
        (k for k, v in annotations["annotations"].items() if v == WINDING_ANNOTATION), None
    )
    winding = sum(
        1
        for lst in annotations["skeletons"].values()
        if winding_id and any(str(a["id"]) == winding_id for a in lst)
    )
    summary = {
        "retrieved_at": retrieved,
        "snapshot": str(tar_path.relative_to(ROOT)) if tar_path.is_relative_to(ROOT) else str(tar_path),
        "sha256": digest,
        "requests": client.requests,
        "public_skeletons": len(skids),
        "winding_2023_skeletons": winding,
        "skeletons_with_vfb_id": len(vfb_ids),
        "license_audit": {k: v for k, v in audit.items() if k not in {"neurons_disallowed", "neurons_missing_license"}}
        | {
            "neurons_disallowed": len(audit["neurons_disallowed"]),
            "neurons_missing_license": len(audit["neurons_missing_license"]),
        },
    }
    (out_dir / f"l1em-public-snapshot-{retrieved}.summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--delay", type=float, default=0.1, help="seconds before each request, per worker")
    parser.add_argument("--workers", type=int, default=4, help="concurrent term-info requests (keep small)")
    args = parser.parse_args(argv)
    client = Client(cache_dir=args.out / "cache", delay_s=args.delay)
    log = lambda message: print(message, flush=True)
    summary = fetch(client, args.out, workers=args.workers, log=log)
    summary["cache_hits"] = client.cache_hits
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["license_audit"]["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
