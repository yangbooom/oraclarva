import json, pytest
from oraclarva.sources import audit_source_manifest, validate_parameter_use

def source(**kw):
    x={"source_id":"example","stage":"L1","anatomical_scope":"body wall","provenance":"MEASURED_PUBLISHED","license":"CC BY 4.0","doi_or_url":"https://example.org","local_artifact":"","sha256":"","allowed_uses":["reference"],"limitations":["fixture"]}; x.update(kw); return x
def manifest(tmp_path,records):
    p=tmp_path/"sources.yaml"; p.write_text(json.dumps(records)); return p
def test_repository_manifest():
    r=audit_source_manifest("data/sources/source_manifest_v0.yaml"); assert r.ok,r.errors; assert r.source_count==4
def test_unknown_stage_is_reference_only(tmp_path):
    r=audit_source_manifest(manifest(tmp_path,[source(stage="unknown",allowed_uses=["reference","calibration"])])); assert any("reference-only" in e for e in r.errors)
def test_coordinates_need_scale(tmp_path):
    r=audit_source_manifest(manifest(tmp_path,[source(allowed_uses=["derive_coordinates"])])); assert any("voxel size" in e for e in r.errors)
@pytest.mark.parametrize("kind",["absolute_length","csa","fmax"])
def test_non_l1_absolute_parameters_fail(kind):
    with pytest.raises(ValueError,match="requires stage L1"): validate_parameter_use(source(stage="L3"),kind)
def test_coordinate_permission_and_scale():
    with pytest.raises(ValueError,match="not allowed"): validate_parameter_use(source(),"coordinates")
    validate_parameter_use(source(allowed_uses=["derive_coordinates"],has_spatial_scale=True),"coordinates")
