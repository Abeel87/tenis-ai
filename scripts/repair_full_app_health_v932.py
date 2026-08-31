from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement, found {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_before(path: str, marker: str, block: str) -> None:
    replace_once(path, marker, block + marker)


# P0: tracking governor must preserve hard bounds after the final simplex allocation.
replace_once(
    "backend/autolearn_v84.py",
    "def _apply_tracking_governor(weights: dict[str, float], previous_tracking: dict,\n                            tabpfn_cap: float = 0.35) -> tuple[dict[str, float], dict]:\n    weights = _normalize_weights(weights)\n",
    "def _apply_tracking_governor(weights: dict[str, float], previous_tracking: dict,\n                            tabpfn_cap: float = 0.35, eligible_names=None) -> tuple[dict[str, float], dict]:\n    weights = _normalize_weights(weights)\n    initial_weights = dict(weights)\n    eligible = [str(x) for x in dict.fromkeys(eligible_names or []) if x]\n",
)
replace_once(
    "backend/autolearn_v84.py",
    "    lower_bounds = {m: 0.0 for m in weights}\n    upper_bounds = {m: 1.0 for m in weights}\n",
    "    # Cached challenger weights can omit Current even though its probability is available.\n    # Add it with zero mass before bounded redistribution so hard caps stay feasible instead\n    # of being destroyed by a later normalization back to 100%.\n    if \"current\" in eligible and \"current\" not in weights:\n        weights = {**weights, \"current\": 0.0}\n\n    lower_bounds = {m: 0.0 for m in weights}\n    upper_bounds = {m: 1.0 for m in weights}\n",
)
replace_once(
    "backend/autolearn_v84.py",
    "    w = _normalize_weights(w)\n\n    policy_details = {\n",
    "    # Do not call _normalize_weights here: proportional normalization can violate\n    # the very upper/lower bounds enforced above. The loop already projects onto the\n    # bounded simplex; only repair tiny floating-point residue inside remaining headroom.\n    residue = 1.0 - sum(w.values())\n    if abs(residue) > 1e-9:\n        if residue > 0:\n            free = [m for m in w if w[m] < upper_bounds[m] - 1e-9]\n            for m in sorted(free, key=lambda n: upper_bounds[n] - w[n], reverse=True):\n                add = min(residue, upper_bounds[m] - w[m])\n                w[m] += add\n                residue -= add\n                if residue <= 1e-9:\n                    break\n        else:\n            free = [m for m in w if w[m] > lower_bounds[m] + 1e-9]\n            for m in sorted(free, key=lambda n: w[n] - lower_bounds[n], reverse=True):\n                take = min(-residue, w[m] - lower_bounds[m])\n                w[m] -= take\n                residue += take\n                if residue >= -1e-9:\n                    break\n\n    feasible = abs(sum(w.values()) - 1.0) <= 1e-7\n    bounds_ok = all(lower_bounds[m] - 1e-9 <= w[m] <= upper_bounds[m] + 1e-9 for m in w)\n    if not (feasible and bounds_ok):\n        # Never publish a policy claiming caps were applied when the bounded simplex is\n        # infeasible. Fall back to the incoming allocation and report the guard failure.\n        return initial_weights, {\n            \"active\": False,\n            \"status\": \"infeasible_bounds\",\n            \"catboost_capped\": False,\n            \"tabpfn_boosted\": False,\n            \"current_floored\": False,\n            \"rules_applied\": [],\n            \"sample_sizes\": {\n                \"catboost_selected_n\": cat_n,\n                \"current_selected_n\": cur_n,\n                \"tabpfn_selected_n\": tab_n,\n            },\n            \"initial_weights\": {k: round(v, 4) for k, v in initial_weights.items()},\n            \"governed_weights\": {k: round(v, 4) for k, v in initial_weights.items()},\n        }\n\n    w = {m: v for m, v in w.items() if v > 1e-12}\n\n    policy_details = {\n",
)
replace_once(
    "backend/autolearn_v84.py",
    "        governed_weights, tracking_governor = _apply_tracking_governor(\n            stable, previous_tracking, tabpfn_cap=tab_cap\n        )\n",
    "        governed_weights, tracking_governor = _apply_tracking_governor(\n            stable, previous_tracking, tabpfn_cap=tab_cap, eligible_names=names\n        )\n",
)

# P1: exact mutually-exclusive operator outcomes must be coherent probabilities.
insert_before(
    "backend/symphony2_engine.py",
    "def _score_offer(match: dict, model, outcomes: list[dict]) -> list[dict]:\n",
    '''COHERENT_WINNER_MARKETS = {"match_winner", "set1_winner", "set2_winner", "set3_winner"}\nCOHERENT_OU_MARKETS = {\n    "match_total", "set1_total", "set2_total", "set3_total", "total_sets",\n    "player_total_games", "match_total_aces", "player_aces", "player_double_faults",\n}\n\n\ndef _coherence_pick(value) -> str:\n    raw = _norm(value)\n    if raw in {"o", "over", "powyzej"} or raw.startswith("over "):\n        return "over"\n    if raw in {"u", "under", "ponizej"} or raw.startswith("under "):\n        return "under"\n    return raw\n\n\ndef _cohere_exclusive_probabilities(rows: list[dict]) -> list[dict]:\n    """Normalize only exact mutually-exclusive groups, never unsupported selections.\n\n    The supervised model is still the source of relative strength. This final coherence\n    projection prevents impossible states such as both match winners being below 50%\n    or an exact Over/Under pair summing to something other than 100%.\n    """\n    groups = {}\n    for row in rows or []:\n        p = _num(row.get("operator_model_probability"))\n        if p is None:\n            continue\n        market = _market(row.get("market"))\n        if market in COHERENT_WINNER_MARKETS:\n            key = ("winner", market)\n        elif market in COHERENT_OU_MARKETS and _coherence_pick(row.get("pick")) in {"over", "under"}:\n            line = _num(row.get("line"))\n            if line is None:\n                continue\n            key = (\n                "ou", market, round(line, 6), _norm(row.get("player")),\n                int(_num(row.get("checkpoint"), 0) or 0),\n            )\n        else:\n            continue\n        groups.setdefault(key, []).append(row)\n\n    for key, group in groups.items():\n        if key[0] == "winner":\n            if len(group) != 2:\n                continue\n        else:\n            picks = {_coherence_pick(row.get("pick")) for row in group}\n            if len(group) != 2 or picks != {"over", "under"}:\n                continue\n        total = sum(_num(row.get("operator_model_probability"), 0.0) or 0.0 for row in group)\n        if total <= 0:\n            continue\n        normalized = []\n        for row in group:\n            before = float(_num(row.get("operator_model_probability"), 0.0) or 0.0)\n            after = before * 100.0 / total\n            normalized.append((row, before, after))\n        # Round the first legs and give the final leg the remainder so displayed values\n        # remain exactly 100.00 rather than 99.99/100.01 because of decimal rounding.\n        running = 0.0\n        for idx, (row, before, after) in enumerate(normalized):\n            final = round(100.0 - running, 2) if idx == len(normalized) - 1 else round(after, 2)\n            running += final\n            row["operator_model_probability_pre_coherence"] = round(before, 2)\n            row["operator_model_probability"] = final\n            row["probability_coherence"] = "NORMALIZED_EXCLUSIVE_GROUP"\n            row["probability_kind"] = "SUPERVISED_OPERATOR_LINE_P_HIT_COHERENT"\n    return rows\n\n\n''',
)
replace_once(
    "backend/symphony2_engine.py",
    "    rows.sort(key=lambda x: _num(x.get(\"operator_model_probability\"), -1.0), reverse=True)\n    return rows\n",
    "    rows = _cohere_exclusive_probabilities(rows)\n    rows.sort(key=lambda x: _num(x.get(\"operator_model_probability\"), -1.0), reverse=True)\n    return rows\n",
)

# P1: broken registration script URL.
replace_once(
    "frontend/index.html",
    '<script src="registration-ux-v752.js&amp;review=919"></script>',
    '<script src="registration-ux-v752.js?v=752&amp;review=932"></script>',
)

# P1: make Fast Boot real — history/statistics load only when those tabs need them.
replace_once(
    "frontend/app.js",
    "let statsData=null;\nlet filter='all';",
    "let statsData=null;\nlet secondaryDataPromise=null;\nlet secondaryDataLoaded=false;\nlet filter='all';",
)
replace_once(
    "frontend/app.js",
    "async function safeJson(url,fallback){try{const sep=url.includes('?')?'&':'?';const r=await fetch(`${url}${sep}ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)return fallback;return await r.json()}catch{return fallback}}\nasync function load(){try{const [results,meta,hist,stat]=await Promise.all([safeJson('data/results.json',[]),safeJson('data/meta.json',{}),safeJson('data/history.json',[]),safeJson('data/history_stats.json',{})]);all=results;historyRows=hist;statsData=stat;document.querySelector('#updated').textContent=meta.updated_at?'Aktualizacja: '+new Date(meta.updated_at).toLocaleString('pl-PL'):'Aktualizacja: —';document.querySelector('#mode').textContent='Źródło: '+(meta.fixtures_mode||'—');const hm=document.querySelector('#history-mode');if(hm){const x=meta.history_mode||'—';hm.textContent=x==='degraded-previous'?'Historia: awaria źródła · poprzednie dane':x==='cache'?'Historia: cache':x==='fresh'?'Historia: świeża':x==='fresh+cache'?'Historia: cache + świeże':'Historia: '+x}updateCounts();render()}catch(e){document.querySelector('#app').innerHTML='<div class=\"empty\">Nie udało się wczytać danych.</div>'}}\n",
    "async function safeJson(url,fallback){try{const sep=url.includes('?')?'&':'?';const r=await fetch(`${url}${sep}ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)return fallback;return await r.json()}catch{return fallback}}\nasync function loadSecondaryData(force=false){if(secondaryDataPromise&&!force)return secondaryDataPromise;if(secondaryDataLoaded&&!force)return[historyRows,statsData];secondaryDataPromise=Promise.all([safeJson('data/history.json',[]),safeJson('data/history_stats.json',{})]).then(([hist,stat])=>{historyRows=hist;statsData=stat;secondaryDataLoaded=true;return[hist,stat]}).finally(()=>{secondaryDataPromise=null});return secondaryDataPromise}\nasync function load(){try{const [results,meta]=await Promise.all([safeJson('data/results.json',[]),safeJson('data/meta.json',{})]);all=results;if(view==='stats'||view==='history')await loadSecondaryData();document.querySelector('#updated').textContent=meta.updated_at?'Aktualizacja: '+new Date(meta.updated_at).toLocaleString('pl-PL'):'Aktualizacja: —';document.querySelector('#mode').textContent='Źródło: '+(meta.fixtures_mode||'—');const hm=document.querySelector('#history-mode');if(hm){const x=meta.history_mode||'—';hm.textContent=x==='degraded-previous'?'Historia: awaria źródła · poprzednie dane':x==='cache'?'Historia: cache':x==='fresh'?'Historia: świeża':x==='fresh+cache'?'Historia: cache + świeże':'Historia: '+x}updateCounts();render()}catch(e){document.querySelector('#app').innerHTML='<div class=\"empty\">Nie udało się wczytać danych.</div>'}}\n",
)
replace_once(
    "frontend/app.js",
    "document.querySelectorAll('.main-tabs button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.main-tabs button').forEach(x=>x.classList.remove('active'));b.classList.add('active');view=b.dataset.view;render()});",
    "document.querySelectorAll('.main-tabs button').forEach(b=>b.onclick=async()=>{document.querySelectorAll('.main-tabs button').forEach(x=>x.classList.remove('active'));b.classList.add('active');view=b.dataset.view;if(view==='stats'||view==='history')await loadSecondaryData();render()});",
)
replace_once(
    "frontend/app.js",
    "document.querySelector('#refresh').onclick=load;",
    "document.querySelector('#refresh').onclick=async()=>{if(view==='stats'||view==='history')secondaryDataLoaded=false;await load()};",
)

# P1/P2: final regression must validate generated state, not only pre-generation source.
replace_once(
    ".github/workflows/update-and-pages.yml",
    "      - name: Compact frontend data v8.5.4\n        run: python scripts/compact_frontend_data_v853.py\n",
    "      - name: Final full regression after generated layers v9.3.2\n        run: |\n          python -m pytest -q\n          node tests/ui_static_smoke.mjs\n          node tests/decision_center_smoke.mjs\n          node tests/audit_consistency_smoke.mjs\n      - name: Compact frontend data v8.5.4\n        run: python scripts/compact_frontend_data_v853.py\n",
)
replace_once(
    ".github/workflows/superbet-market-refresh.yml",
    "      - name: Commit refreshed market context\n",
    "      - name: Full app health regression v9.3.2\n        run: |\n          python -m pytest -q tests/test_autolearn_v84.py tests/test_symphony2_probability_coherence_v932.py tests/test_full_app_health_v932.py\n          node tests/ui_static_smoke.mjs\n\n      - name: Commit refreshed market context\n",
)

# Release metadata only; protected v8.x compatibility markers remain untouched.
replace_once("frontend/app-meta.js", "    releaseVersion:'v9.2.3',", "    releaseVersion:'v9.3.2',")
for old, new in [
    ("<title>Tenis AI · v9.2.3</title>", "<title>Tenis AI · v9.3.2</title>"),
    ("Tenis AI v9.2.3 · Adaptive PROD + Player Learning SHADOW", "Tenis AI v9.3.2 · Adaptive PROD + Player Learning SHADOW"),
    ("v9.2.3 · Player Intelligence i Player Learning działają w SHADOW.", "v9.3.2 · Player Intelligence i Player Learning działają w SHADOW."),
]:
    replace_once("frontend/index.html", old, new)

# Add focused regression tests as normal repository files.
(ROOT / "tests/test_symphony2_probability_coherence_v932.py").write_text('''from backend.symphony2_engine import _cohere_exclusive_probabilities\n\n\ndef test_match_winner_pair_is_projected_to_exactly_100_percent():\n    rows = [\n        {"market": "match_winner", "pick": "A", "operator_model_probability": 46.24, "probability_kind": "SUPERVISED_OPERATOR_LINE_P_HIT"},\n        {"market": "match_winner", "pick": "B", "operator_model_probability": 42.10, "probability_kind": "SUPERVISED_OPERATOR_LINE_P_HIT"},\n    ]\n    out = _cohere_exclusive_probabilities(rows)\n    assert round(sum(r["operator_model_probability"] for r in out), 2) == 100.0\n    assert max(r["operator_model_probability"] for r in out) >= 50.0\n    assert all(r["probability_coherence"] == "NORMALIZED_EXCLUSIVE_GROUP" for r in out)\n\n\ndef test_over_under_same_line_is_projected_but_different_lines_are_independent():\n    rows = [\n        {"market": "match_total", "pick": "over", "line": 22.5, "operator_model_probability": 71.0},\n        {"market": "match_total", "pick": "under", "line": 22.5, "operator_model_probability": 49.0},\n        {"market": "match_total", "pick": "over", "line": 23.5, "operator_model_probability": 60.0},\n        {"market": "match_total", "pick": "under", "line": 23.5, "operator_model_probability": 30.0},\n    ]\n    out = _cohere_exclusive_probabilities(rows)\n    for line in (22.5, 23.5):\n        pair = [r for r in out if r["line"] == line]\n        assert round(sum(r["operator_model_probability"] for r in pair), 2) == 100.0\n\n\ndef test_unsupported_or_singleton_rows_are_not_invented_or_changed():\n    rows = [\n        {"market": "match_winner", "pick": "A", "operator_model_probability": None},\n        {"market": "player_total_games", "pick": "over", "line": 12.5, "operator_model_probability": 61.0},\n    ]\n    out = _cohere_exclusive_probabilities(rows)\n    assert out[0]["operator_model_probability"] is None\n    assert out[1]["operator_model_probability"] == 61.0\n    assert "probability_coherence" not in out[1]\n''', encoding="utf-8")

(ROOT / "tests/test_full_app_health_v932.py").write_text('''from pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\n\ndef test_registration_script_query_is_valid():\n    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")\n    assert "registration-ux-v752.js&amp;review=" not in html\n    assert "registration-ux-v752.js?v=752&amp;review=932" in html\n\n\ndef test_primary_boot_does_not_fetch_heavy_history_payload():\n    js = (ROOT / "frontend/app.js").read_text(encoding="utf-8")\n    primary = js.split("async function load(){", 1)[1].split("document.querySelectorAll('#tour-nav", 1)[0]\n    assert "Promise.all([safeJson('data/results.json',[]),safeJson('data/meta.json',{})])" in primary\n    assert "if(view==='stats'||view==='history')await loadSecondaryData()" in primary\n    secondary = js.split("async function loadSecondaryData", 1)[1].split("async function load(){", 1)[0]\n    assert "data/history.json" in secondary\n    assert "data/history_stats.json" in secondary\n\n\ndef test_final_generated_state_regression_gate_exists():\n    workflow = (ROOT / ".github/workflows/update-and-pages.yml").read_text(encoding="utf-8")\n    assert "Final full regression after generated layers v9.3.2" in workflow\n    assert workflow.index("Final full regression after generated layers v9.3.2") > workflow.index("Symphony 2.0 Guard")\n''', encoding="utf-8")

# Extend the existing governor tests with the exact production failure shape from the audit.
p = ROOT / "tests/test_autolearn_v84.py"
text = p.read_text(encoding="utf-8")
addition = '''\n\ndef test_tracking_governor_cached_two_model_weights_keep_hard_caps_with_eligible_current():\n    tracking = {\n        "catboost": {"selected_n": 1394, "accuracy": 70.8, "brier": 0.21715},\n        "current": {"selected_n": 1208, "accuracy": 73.6, "brier": 0.21156},\n        "tabpfn": {"selected_n": 607, "accuracy": 73.0, "brier": 0.20330},\n    }\n    initial_weights = {"catboost": 0.533, "tabpfn": 0.467}\n    w, policy = _apply_tracking_governor(\n        initial_weights, tracking, tabpfn_cap=0.35,\n        eligible_names=["current", "catboost", "tabpfn"],\n    )\n    assert policy["active"] is True\n    assert policy["catboost_capped"] is True\n    assert w["catboost"] <= 0.40 + 1e-9\n    assert w["tabpfn"] <= 0.35 + 1e-9\n    assert w["current"] >= 0.25 - 1e-9\n    assert abs(sum(w.values()) - 1.0) < 1e-9\n'''
if "test_tracking_governor_cached_two_model_weights_keep_hard_caps_with_eligible_current" not in text:
    p.write_text(text.rstrip() + addition + "\n", encoding="utf-8")

print("FULL_APP_HEALTH_V932_PATCHED")
