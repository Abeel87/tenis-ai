from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ERR=[]

def read(p):
    f=ROOT/p
    if not f.exists():
        ERR.append(f"brak pliku: {p}")
        return ""
    return f.read_text(encoding="utf-8")

def req(text,needle,msg):
    if needle not in text:
        ERR.append(msg)

def main():
    helper=read("backend/game_state_tracking_v84e1.py")
    auto=read("backend/autolearn_v84.py")
    hist=read("backend/history_tracker.py")
    settle=read("backend/live_history_settle.py") + read("backend/signal_settlement.py")
    pbp=read("backend/pbp_tracker.py")
    wf=read(".github/workflows/update-and-pages.yml")

    req(helper,'VERSION = "v8.4E1"',"helper nie jest v8.4E1")
    req(helper,"CHECKPOINTS = (2, 4, 6)","brak checkpointów 2/4/6")
    req(helper,"select_tracking_signals","brak bounded reservation")
    req(helper,"settle_from_states","brak PBP settlement")
    req(helper,"No fuzzy matching","brak exact-only deklaracji")

    req(auto,"_game_state_current_signals","AutoLearn nie dostaje current game-state")
    req(auto,"_select_game_state_tracking_signals","AutoLearn nie rezerwuje game-state")
    req(auto,'"game_state_learning_v84e1"',"AutoLearn nie czyta hidden game-state")
    req(auto,'"checkpoint": _game_state_checkpoint(reference)',"brak checkpoint metadata")
    req(auto,"MAX_TRACK_SIGNALS_PER_MATCH = 12","zmieniono limit 12")

    if "game_state_learning_v84e1" not in hist:
        ERR.append("historia nie zamraża hidden game-state")
    req(settle,'"game_state_learning_v84e1"',"live settlement nie obsługuje hidden listy")
    req(pbp,'"autolearn_signals_v84"',"PBP nie upgradeuje AutoLearn state")
    req(pbp,'"game_state_learning_v84e1"',"PBP nie upgradeuje hidden state")
    req(wf,"Game-State Tracking Guard v8.4E1","workflow nie ma guarda E1")

    if ERR:
        print("❌ Game-State Tracking Guard v8.4E1 — FAIL")
        for e in ERR:
            print("  -",e)
        return 1
    print("✅ Game-State Tracking Guard v8.4E1 — PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
