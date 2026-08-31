import json, pytest
from oraclarva.sources import audit_source_manifest, load_source_manifest, validate_parameter_use

def source(**kw):
    x={"source_id":"example","stage":"L1","anatomical_scope":"body wall","provenance":"MEASURED_PUBLISHED","license":"CC BY 4.0","doi_or_url":"https://example.org","local_artifact":"","sha256":"","allowed_uses":["reference"],"limitations":["fixture"]}; x.update(kw); return x
def manifest(tmp_path,records):
    p=tmp_path/"sources.yaml"; p.write_text(json.dumps(records)); return p
def test_repository_manifest():
    r=audit_source_manifest("data/sources/source_manifest_v0.yaml"); assert r.ok,r.errors; assert r.source_count==15

def test_environment_source_stages_are_explicit():
    records={item["source_id"]:item for item in load_source_manifest("data/sources/source_manifest_v0.yaml")}
    assert records["larderet_2017_l1_visual_circuit"]["stage"]=="L1"
    assert records["larderet_2017_l1_visual_circuit"]["sha256"]=="f9c200cdea0a9a80dc1e7d48aea0a25540d7d63341f705ff7c90faed9effd08f"
    assert "redistribution" in records["larderet_2017_l1_visual_circuit"]["allowed_uses"]
    descending = records["vfb_l1em_visual_descending_path"]
    assert descending["stage"] == "L1"
    assert descending["sha256"] == "0f558cf16f30b58b760ac7053abb7cd5ccb64243de36492c937760c5642e465b"
    assert "redistribution" in descending["allowed_uses"]
    segmental = records["vfb_l1em_a03o_segmental_audit"]
    assert segmental["stage"] == "L1"
    assert segmental["sha256"] == "459763508bebc9969ae22b25697565e30001e341b363d27fe648ad429b486228"
    assert "redistribution" in segmental["allowed_uses"]
    assert records["berck_2016_l1_olfactory_circuit"]["stage"]=="L1"
    assert records["luo_2010_l1_thermotaxis"]["stage"]=="L1"
    assert records["kane_2013_l2_phototaxis"]["stage"]=="L2"
    assert records["gershow_2012_l2_odor_navigation"]["stage"]=="L2"
    activation = records["zarin_2019_l1_l2_muscle_calcium"]
    assert activation["stage"] == "unknown"
    assert activation["allowed_uses"] == ["reference"]
    assert not activation["local_artifact"]

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
