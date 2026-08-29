"""Validate dependency-free, JSON-compatible YAML source manifests."""
from __future__ import annotations
import argparse, json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STAGES={"L1","L2","L3","unknown"}
PROVENANCE={"MEASURED_PUBLISHED","PUBLIC_IMAGE_DERIVED","ANATOMY_DERIVED","MODEL_FITTED"}
USES={"reference","derive_coordinates","calibration","redistribution"}
REQUIRED={"source_id","stage","anatomical_scope","provenance","license","doi_or_url","local_artifact","sha256","allowed_uses","limitations"}

@dataclass(slots=True)
class SourceAudit:
    source_count:int=0
    errors:list[str]=field(default_factory=list)
    warnings:list[str]=field(default_factory=list)
    @property
    def ok(self): return not self.errors
    def to_dict(self): return {"source_count":self.source_count,"errors":self.errors,"warnings":self.warnings,"ok":self.ok}

def load_source_manifest(path:str|Path)->list[dict[str,Any]]:
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data,list): raise ValueError("source manifest root must be a list")
    return data

def audit_source_manifest(path:str|Path)->SourceAudit:
    report=SourceAudit()
    try: records=load_source_manifest(path)
    except (OSError,json.JSONDecodeError,ValueError) as error:
        report.errors.append(str(error)); return report
    seen=set()
    for index,record in enumerate(records):
        label=f"source[{index}]"
        if not isinstance(record,dict): report.errors.append(f"{label}: must be an object"); continue
        missing=REQUIRED-record.keys()
        if missing: report.errors.append(f"{label}: missing fields {sorted(missing)}"); continue
        source_id=record["source_id"]
        if not isinstance(source_id,str) or not source_id.strip(): report.errors.append(f"{label}: invalid source_id"); continue
        label=source_id
        if source_id in seen: report.errors.append(f"{label}: duplicate source_id")
        seen.add(source_id)
        if record["stage"] not in STAGES: report.errors.append(f"{label}: invalid stage")
        if record["provenance"] not in PROVENANCE: report.errors.append(f"{label}: invalid provenance")
        uses=record["allowed_uses"]
        if not isinstance(uses,list) or not set(uses)<=USES: report.errors.append(f"{label}: invalid allowed_uses"); uses=[]
        limits=record["limitations"]
        if not isinstance(limits,list) or not all(isinstance(x,str) and x.strip() for x in limits): report.errors.append(f"{label}: invalid limitations")
        if record["stage"]=="unknown" and set(uses)-{"reference"}: report.errors.append(f"{label}: unknown stage is reference-only")
        if "derive_coordinates" in uses and not record.get("has_spatial_scale",False): report.errors.append(f"{label}: coordinate derivation requires voxel size or scale bar")
        if "redistribution" in uses and not record.get("commercial_derivatives_confirmed",False): report.errors.append(f"{label}: redistribution requires confirmed commercial derivatives permission")
        artifact,digest=record["local_artifact"],record["sha256"]
        if artifact and (not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest.lower())): report.errors.append(f"{label}: local artifacts require a SHA-256 digest")
        report.source_count+=1
    return report

def validate_parameter_use(record:dict[str,Any],kind:str)->None:
    source=record.get("source_id","unknown source")
    if kind in {"absolute_length","csa","fmax"} and record.get("stage")!="L1": raise ValueError(f"{source}: {kind} requires stage L1")
    if kind=="coordinates":
        if "derive_coordinates" not in record.get("allowed_uses",[]): raise ValueError(f"{source}: coordinate derivation is not allowed")
        if not record.get("has_spatial_scale",False): raise ValueError(f"{source}: coordinates require voxel size or scale bar")

def main(argv=None):
    parser=argparse.ArgumentParser(description="Audit a scientific source manifest."); parser.add_argument("manifest")
    report=audit_source_manifest(parser.parse_args(argv).manifest); print(json.dumps(report.to_dict(),indent=2,ensure_ascii=False)); return 0 if report.ok else 1
if __name__=="__main__": raise SystemExit(main())
