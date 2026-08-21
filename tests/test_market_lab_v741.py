from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("ml",ROOT/"backend"/"market_lab_v741.py")
ml=importlib.util.module_from_spec(spec);spec.loader.exec_module(ml)
def sample():
    return {"id":1,"p1":"A","p2":"B","model_ready":True,"service_model":{"p1_hold":82.0,"p2_hold":76.0},
      "exact_first_set":{"6:0":5,"6:1":7,"6:2":10,"6:3":13,"6:4":15,"7:5":10,"7:6":8,"0:6":3,"1:6":4,"2:6":6,"3:6":7,"4:6":7,"5:7":3,"6:7":2},
      "second_set_win":{"A":60,"B":40},"third_set_win":{"A":58,"B":42}}
def test_lower_line():
    x=ml.enrich(sample())["market_lab_v741"]
    assert "6.5" in x["set1_total"] and x["set1_exact_six_games"]>0
def test_player_lines():
    x=ml.enrich(sample())["market_lab_v741"]
    assert "6.5" in x["player_total_games"]["A"] and "15.5" in x["player_total_games"]["A"]
def test_combo():
    x=ml.enrich(sample())["market_lab_v741"]
    assert 0<=x["set1_winner_player_games_6_5"]["p1"]["under"]<=100
