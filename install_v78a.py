from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parent
B=ROOT/"backend"
F=ROOT/"frontend"
WF=ROOT/".github"/"workflows"/"update-and-pages.yml"

def read(p):
    return p.read_text(encoding="utf-8")

def write(p,s):
    p.write_text(s,encoding="utf-8")

def replace_once(path, old, new, marker=None):
    s=read(path)
    if marker and marker in s:
        return False
    if old not in s:
        raise SystemExit(f"{path}: brak oczekiwanego markera")
    write(path,s.replace(old,new,1))
    return True


# Keep the v7.7.2 regression test meaningful after the new shell/cache version.
legacy_test=ROOT/"tests"/"test_v772_logic_audit.py"
if legacy_test.exists():
    t=read(legacy_test)
    t=t.replace("assert 'tenis-ai-v772-logic-audit-fix' in sw","assert 'tenis-ai-v78a-integrity-guard' in sw")
    t=t.replace("assert 'Tenis AI v7.7.2 · Logic Audit Fix' in idx","assert 'Tenis AI v7.8A · Integrity Guard' in idx")
    write(legacy_test,t)

for p in (
    B/"history_hygiene_v78a.py",
    B/"prediction_integrity_v78a.py",
    F/"integrity-v78a.js",
    F/"integrity-v78a.css",
):
    if not p.exists():
        raise SystemExit(f"Brak pliku {p}")

update=B/"update.py"
replace_once(update, 'from model import normalize_matches, analyse_match\n', 'from model import normalize_matches, analyse_match\nfrom history_hygiene_v78a import clean_history\nfrom prediction_integrity_v78a import apply_pre_output_guards\n', marker='from history_hygiene_v78a import clean_history')
replace_once(update, '\ndef fetch_fixtures():\n', "\ndef _extract_best_of(match):\n    for key in ('best_of','best_of_sets'):\n        try:\n            value=int(match.get(key))\n            if value in (3,5):\n                return value\n        except (TypeError,ValueError):\n            pass\n    text=str(match.get('format') or match.get('match_format') or '').lower()\n    if 'best of 5' in text or 'bo5' in text:\n        return 5\n    if 'best of 3' in text or 'bo3' in text:\n        return 3\n    return None\n\n\ndef fetch_fixtures():\n", marker='def _extract_best_of(match):')
replace_once(update, "'scheduled_time':m.get('scheduled_time') or '',", "'scheduled_time':m.get('scheduled_time') or '',\n                'best_of':_extract_best_of(m),", marker="'best_of':_extract_best_of(m)")
replace_once(update, '    long_df=normalize_matches(hist)\n    save_sqlite(long_df)\n    fixtures,mode=fetch_fixtures()\n    analysed=[analyse_match(long_df,m) for m in fixtures]\n', '    hist,hygiene=clean_history(hist)\n    long_df=normalize_matches(hist)\n    save_sqlite(long_df)\n    fixtures,mode=fetch_fixtures()\n    analysed=[apply_pre_output_guards(analyse_match(long_df,m)) for m in fixtures]\n', marker='hist,hygiene=clean_history(hist)')
replace_once(update, "        'history_rows_raw':len(hist),'player_rows':len(long_df),'download_warnings':errors,\n", "        'history_rows_raw':len(hist),'player_rows':len(long_df),'download_warnings':errors,\n        'history_hygiene_removed':hygiene.get('removed_rows',0),\n        'history_hygiene_kept':hygiene.get('kept_rows',len(hist)),\n", marker="'history_hygiene_removed':")

trends=B/"player_trends.py"
s=read(trends)
old='x = x[x["date"].isna() | (x["date"].dt.date <= cut.date())]'
new='x = x[x["date"].isna() | (x["date"].dt.date < cut.date())]'
if new not in s:
    if old not in s:
        raise SystemExit("player_trends.py: brak same-day markera")
    s=s.replace(old,new,1)
    s=s.replace(
        "# Source history has day precision, so same-day completed matches may legitimately be included.",
        "# v7.8A: source history has day precision; exclude target day to prevent pre-match leakage.",
        1
    )
    write(trends,s)
serve=B/"serve_props.py"
replace_once(serve, 'import pandas as pd\n', 'import pandas as pd\n\nfrom history_hygiene_v78a import clean_history\n', marker='from history_hygiene_v78a import clean_history')
replace_once(serve, '    raw = load_raw_history()\n    hist = normalize_serve_props(raw)\n', '    raw = load_raw_history()\n    raw,hygiene = clean_history(raw)\n    hist = normalize_serve_props(raw)\n', marker='raw,hygiene = clean_history(raw)')
replace_once(serve, '    profile_cache = {}\n    for m in results:\n        surface = str(m.get("surface") or "").strip().lower()\n', '    profile_cache = {}\n    for m in results:\n        try:\n            best_of=5 if int(m.get("best_of") or 3)==5 else 3\n        except (TypeError,ValueError):\n            best_of=3\n        if best_of==5:\n            m["serve_props_v72"]={\n                "version":"v7.8A-serve-props-hygiene",\n                "ready":False,\n                "reason":"bo5_full_match_not_supported",\n                "format":"BO5 · N/D until dedicated engine",\n            }\n            continue\n        surface = str(m.get("surface") or "").strip().lower()\n', marker='"reason":"bo5_full_match_not_supported"')
replace_once(serve, '            "serve_props_v72_history_rows": int(len(hist)),\n', '            "serve_props_v72_history_rows": int(len(hist)),\n            "serve_props_v78a_hygiene_removed": int(hygiene.get("removed_rows",0)),\n', marker='"serve_props_v78a_hygiene_removed"')
lab=B/"market_lab_v741.py"
replace_once(lab, '    first=parse_exact(m.get("exact_first_set"))\n    if not first:return m\n    raw=base_set(h1,h2);p1=m.get("p1");p2=m.get("p2")\n', '    first=parse_exact(m.get("exact_first_set"))\n    if not first:return m\n    p1=m.get("p1");p2=m.get("p2")\n    try:\n        best_of=5 if int(m.get("best_of") or 3)==5 else 3\n    except (TypeError,ValueError):\n        best_of=3\n    if best_of==5:\n        tb1=sum(p for s,p in first.items() if set(s)=={6,7})\n        six=sum(p for s,p in first.items() if sum(s)==6)\n        m["market_lab_v741"]={\n          "status":"LAB_SET1_ONLY",\n          "note":"BO5 guard: tylko 1. set; pełne rynki meczu N/D do czasu dedykowanego silnika BO5.",\n          "set1_total":ou(first),\n          "set1_exact_six_games":pct(six),\n          "set1_tiebreak":{"yes":pct(tb1),"no":pct(1-tb1)},\n          "set1_winner_player_games_6_5":combo(first),\n        }\n        return m\n    raw=base_set(h1,h2)\n', marker='"status":"LAB_SET1_ONLY"')

history=B/"history_tracker.py"
s=read(history)
if "MODEL_VERSION = 'v7.8A-adaptive-hygiene'" not in s:
    if "MODEL_VERSION = 'v5-adaptive'" not in s:
        raise SystemExit("history_tracker.py: brak MODEL_VERSION")
    s=s.replace("MODEL_VERSION = 'v5-adaptive'","MODEL_VERSION = 'v7.8A-adaptive-hygiene'",1)
    write(history,s)

multi=F/"multi-model.js"
s=read(multi)
old_desc="Łączy 5 modeli. Wysoko trafia tylko typy, które dostają poparcie kilku niezależnych wag."
new_desc="Łączy 5 wariantów modelu współdzielących część danych. Wynik Consensus to siła zgodności /100, nie niezależne prawdopodobieństwo."
if new_desc not in s:
    if old_desc not in s:
        raise SystemExit("multi-model.js: brak opisu Consensus")
    s=s.replace(old_desc,new_desc,1)
    write(multi,s)
ui=F/"ui-v751.js"
replace_once(ui, "function modelLine(x){const p=String(x?.key||'').split('|');return p.length>1?p[1]:''}\n", "function modelLine(x){const p=String(x?.key||'').split('|');return p.length>1?p[1]:''}\n  const signalIsProbability=()=>activeModelId()==='adaptive';\n  const signalText=v=>num(v)==null?'—':(signalIsProbability()?`${Math.round(Number(v))}%`:`${Math.round(Number(v))}/100`);\n", marker='const signalIsProbability=')

s=read(ui)
s=s.replace("${Math.round(s.value)}%","${signalText(s.value)}")
s=s.replace("${s?Math.round(s.value)+'%':'—'}","${s?signalText(s.value):'—'}")
s=s.replace("${a?Math.round(a.value)+'%':'—'}","${a?signalText(a.value):'—'}")
s=s.replace("${b?Math.round(b.value)+'%':'—'}","${b?signalText(b.value):'—'}")
s=s.replace("${Math.round(z.v)}%","${signalText(z.v)}",1)
s=s.replace("${side} ${Math.round(v)}%","${side} ${signalText(v)}",1)
s=s.replace("Tenis AI v7.7.2 · Logic Audit Fix","Tenis AI v7.8A · Integrity Guard")
write(ui,s)

wf=read(WF)
if "Prediction integrity gate v7.8A" not in wf:
    anchor="      - name: Track + backtest PBP\n"
    step="      - name: Prediction integrity gate v7.8A\n        run: python backend/prediction_integrity_v78a.py\n"
    if anchor not in wf:
        raise SystemExit("workflow: brak Track + backtest PBP")
    wf=wf.replace(anchor,step+anchor,1)
    write(WF,wf)

index=F/"index.html"
s=read(index)
if "integrity-v78a.css" not in s:
    anchor='<link rel="stylesheet" href="logic-audit-v772.css">'
    if anchor not in s:
        raise SystemExit("index: brak CSS anchor")
    s=s.replace(anchor,anchor+'\n  <link rel="stylesheet" href="integrity-v78a.css">',1)
if "integrity-v78a.js" not in s:
    anchor='  <script src="early-hold-paths-v771.js"></script>'
    if anchor not in s:
        raise SystemExit("index: brak JS anchor")
    s=s.replace(anchor,anchor+'\n  <script src="integrity-v78a.js"></script>',1)
s=s.replace("Tenis AI v7.7.2 · Logic Audit Fix","Tenis AI v7.8A · Integrity Guard")
s=s.replace("LAB v7.7.2","LAB v7.8A")
if "v7.8A: Integrity Guard" not in s:
    s=s.replace(
        "<div>v7.7.2:",
        "<div>v7.8A: Integrity Guard — RET/W/O/nieukończone mecze nie uczą modelu; same-day leak zablokowany; BO5 zabezpieczony; score /100 oddzielony od probability; workflow zatrzymuje deploy przy niespójności. v7.7.2:",
        1
    )
write(index,s)

sw=F/"sw.js"
s=read(sw)
s=re.sub(r"const C='[^']+';","const C='tenis-ai-v78a-integrity-guard';",s,count=1)
for asset,anchor in (
    ("integrity-v78a.css","logic-audit-v772.css"),
    ("integrity-v78a.js","early-hold-paths-v771.js"),
):
    if f"'{asset}'" not in s:
        if f"'{anchor}'" not in s:
            raise SystemExit(f"sw.js: brak {anchor}")
        s=s.replace(f"'{anchor}'",f"'{anchor}','{asset}'",1)
write(sw,s)

for p in (
    B/"history_hygiene_v78a.py", B/"prediction_integrity_v78a.py",
    B/"update.py", B/"player_trends.py", B/"serve_props.py",
    B/"market_lab_v741.py", B/"history_tracker.py",
):
    compile(read(p),str(p),"exec")

for p in (F/"integrity-v78a.js",F/"multi-model.js",F/"ui-v751.js"):
    try:
        subprocess.run(["node","--check",str(p)],check=True,capture_output=True,text=True)
    except FileNotFoundError:
        pass

print("Tenis AI v7.8A Integrity Guard: install + syntax OK")
