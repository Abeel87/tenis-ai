from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from pbp_enrich import extract_first_set_games, enrich_match


def _row(a, b, points, server):
    return {
        "games": [[a], [b]],
        "points": list(points),
        "server": server,
        "sets": [0, 0],
    }


def synthetic_tape():
    rows = []
    # Six games, p1 serves first; all holds -> 3:3.
    game_scores = [(0,0),(1,0),(1,1),(2,1),(2,2),(3,2),(3,3)]
    for g in range(6):
        a,b = game_scores[g]
        server = 1 if g % 2 == 0 else 2
        rows.append(_row(a,b,("0","0"),server))
        rows.append(_row(a,b,("15","0"),server))
        na,nb = game_scores[g+1]
        next_server = 2 if server == 1 else 1
        rows.append(_row(na,nb,("0","0"),next_server))
    # Continue to 6:4 for p1.
    for before, after, server in [
        ((3,3),(4,3),1),
        ((4,3),(4,4),2),
        ((4,4),(5,4),1),
        ((5,4),(6,4),2),  # break to finish
    ]:
        rows.append(_row(*before,("15","15"),server))
        rows.append(_row(*after,("0","0"),3-server))
    return {
        "match": {"players":{"p1":{"name":"A"},"p2":{"name":"B"}}},
        "meta":{"coverage":"from_start","point_source":"observed"},
        "tape":rows,
    }


def profile(name):
    return {
        "player":name,"matches":8,"surface_matches":6,"ready":True,"quality":"HIGH","ehs":80,
        "hold1":82.0,"hold2":80.0,"hold3":78.0,
        "after2_11":75.0,"after4_22":60.0,"after6_33":50.0,"sequence_11_22_33":45.0,
    }


def test_extract_first_set_games():
    x=extract_first_set_games(synthetic_tape())
    assert x is not None
    assert x["checkpoints"]["2"] == "1:1"
    assert x["checkpoints"]["4"] == "2:2"
    assert x["checkpoints"]["6"] == "3:3"
    assert x["service_games"][1]["1"] == 1.0
    assert x["service_games"][2]["3"] == 1.0


def test_enrich_produces_joint_not_product_placeholder():
    m={
        "p1":"A","p2":"B","model_ready":True,
        "service_model":{"p1_hold":75.0,"p2_hold":74.0},
        "first_set_win":{"A":55.0,"B":45.0},
    }
    enrich_match(m,profile("A"),profile("B"))
    assert m["early_hold_v7"]["ready"] is True
    assert m["game_states"]["6"]["3:3"] > 0
    assert 0 <= m["score_lead_after6"] <= 100
    assert 0 <= m["score_joint_builder"] <= m["score_lead_after6"]
    assert m["service_model"]["pbp_adjusted"] is True


def test_nd_under_five_matches():
    p=profile("A")
    p.update({"matches":4,"ready":False,"ehs":None})
    m={"p1":"A","p2":"B","model_ready":True,"service_model":{"p1_hold":75,"p2_hold":75}}
    enrich_match(m,p,profile("B"))
    assert m["early_hold_v7"]["ready"] is False
    assert "score_joint_builder" not in m
