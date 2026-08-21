
from backend.joint_builder_v78b import build_joint_builder, validate_joint_builder

def sample():
    return {
        "p1":"Alpha","p2":"Beta",
        "service_model":{"p1_hold":82.0,"p2_hold":76.0},
        "first_set_win":{"Alpha":63.0,"Beta":37.0},
        "model_confidence":78,
    }

def test_ready_and_mass():
    x=build_joint_builder(sample())
    assert x["status"]=="READY"
    assert x["mass"]==100.0
    assert x["validation_errors"]==[]

def test_joint_never_above_marginals():
    x=build_joint_builder(sample())
    for side in ("p1","p2"):
        r=x[side]
        assert r["joint_all_3"] <= r["lead_after_6"] + 0.11
        assert r["joint_all_3"] <= r["over_8_5_set1"] + 0.11
        assert r["joint_all_3"] <= r["win_set1"] + 0.11

def test_set_win_marginal_matches_model_target():
    x=build_joint_builder(sample())
    assert abs(x["p1"]["win_set1"]-63.0)<=0.1
    assert abs(x["p2"]["win_set1"]-37.0)<=0.1

def test_naive_product_is_exposed_but_not_used_as_joint():
    x=build_joint_builder(sample())
    assert x["p1"]["joint_all_3"] != x["p1"]["naive_independent"]
    assert x["p1"]["dependency_ratio"] is not None

def test_missing_service_model_is_nd():
    m=sample(); m.pop("service_model")
    x=build_joint_builder(m)
    assert x["status"]=="N/D"

def test_missing_first_set_target_is_nd():
    m=sample(); m.pop("first_set_win")
    x=build_joint_builder(m)
    assert x["status"]=="N/D"

def test_validator_catches_impossible_joint():
    payload=build_joint_builder(sample())
    payload["p1"]["joint_all_3"]=99.0
    assert validate_joint_builder(payload)

def test_swap_symmetry():
    x=build_joint_builder(sample())
    m={
      "p1":"Beta","p2":"Alpha",
      "service_model":{"p1_hold":76.0,"p2_hold":82.0},
      "first_set_win":{"Beta":37.0,"Alpha":63.0},
      "model_confidence":78,
    }
    y=build_joint_builder(m)
    assert abs(x["p1"]["joint_all_3"]-y["p2"]["joint_all_3"])<=0.2
    assert abs(x["p2"]["joint_all_3"]-y["p1"]["joint_all_3"])<=0.2
