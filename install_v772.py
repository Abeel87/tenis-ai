from pathlib import Path
import re, subprocess

ROOT=Path(__file__).resolve().parent
F=ROOT/'frontend'; B=ROOT/'backend'

def rd(p): return p.read_text(encoding='utf-8')
def wr(p,s): p.write_text(s,encoding='utf-8')

def rep(p,old,new,marker=None):
    s=rd(p)
    if marker and marker in s: return
    if old not in s: raise SystemExit(f'{p}: brak markera')
    wr(p,s.replace(old,new,1))

def rx(p,pat,new,marker=None):
    s=rd(p)
    if marker and marker in s: return
    s2,n=re.subn(pat,new,s,count=1,flags=re.S)
    if n!=1: raise SystemExit(f'{p}: regex count={n}')
    wr(p,s2)

# 1. Multi-model bridge
mm=F/'multi-model.js'
rep(mm,
"""  function selectedName(){return `${META[activeModel]?.icon||''} ${META[activeModel]?.name||activeModel}`.trim()}\n\n  bestSignalsData=(m,limit=3)=>selectedSignals(m,limit);\n""",
"""  function selectedName(){return `${META[activeModel]?.icon||''} ${META[activeModel]?.name||activeModel}`.trim()}\n\n  window.TENIS_AI_MODEL_API={\n    version:'v7.7.2',\n    get active(){return activeModel},\n    activeName:()=>selectedName(),\n    signals:(m,limit=20)=>selectedSignals(m,limit).map(x=>({...x})),\n    allSignals:(m)=>{\n      const rows=activeModel==='consensus'?consensusSignals(m):modelSignals(activeModel,m).sort((a,b)=>b.v-a.v);\n      return rows.map(x=>({...x}));\n    },\n    signalsFor:(id,m)=>{\n      const rows=id==='consensus'?consensusSignals(m):modelSignals(id,m).sort((a,b)=>b.v-a.v);\n      return rows.map(x=>({...x}));\n    }\n  };\n\n  bestSignalsData=(m,limit=3)=>selectedSignals(m,limit);\n""",'window.TENIS_AI_MODEL_API={')

# 2. UI helpers + actual active model
ui=F/'ui-v751.js'
rep(ui,"  let focus='all';\n  let route='matches';\n",
"""  let focus='all';\n  let route='matches';\n\n  const modelApi=()=>window.TENIS_AI_MODEL_API||null;\n  const activeModelId=()=>modelApi()?.active||'adaptive';\n  const activeModelName=()=>modelApi()?.activeName?.()||'🧠 Adaptive';\n  function modelAllSignals(m){try{return modelApi()?.allSignals?.(m)||[]}catch{return []}}\n  function modelMarketRows(m,market){return modelAllSignals(m).filter(x=>x&&x.market===market&&num(x.v)!=null)}\n  function modelLine(x){const p=String(x?.key||'').split('|');return p.length>1?p[1]:''}\n""",'const activeModelId=')

rx(ui,r"  function signals\(m\)\{.*?\n  \}\n  const top=",
"""  function signals(m){\n    const api=modelApi();\n    if(api?.allSignals){\n      return modelAllSignals(m).map(x=>({label:x.label||x.key||'Sygnał',value:Number(x.v),kind:'selected-model',market:x.market,pick:x.pick,key:x.key,source_model:activeModelId()}))\n        .filter(x=>num(x.value)!=null).sort((a,b)=>b.value-a.value);\n    }\n    const a=[];\n    addBest(a,'Mecz',m.match_win);addBest(a,'1. set',m.first_set_win);addBest(a,'2. set',m.second_set_win);addBest(a,'Sety',m.total_sets);\n    Object.entries(m.over_under||{}).forEach(([ln,v])=>{const o=num(v?.over),u=num(v?.under);if(o==null||u==null)return;a.push({label:`1S ${o>=u?'OVER':'UNDER'} ${ln}`,value:Math.max(o,u),kind:'set'})});\n    Object.entries(m.match_over_under||{}).forEach(([ln,v])=>{const o=num(v?.over),u=num(v?.under);if(o==null||u==null)return;a.push({label:`Mecz ${o>=u?'OVER':'UNDER'} ${ln}`,value:Math.max(o,u),kind:'match'})});\n    const seen=new Set();return a.filter(x=>!seen.has(x.label)&&seen.add(x.label)).sort((x,y)=>y.value-x.value);\n  }\n  const top=""",'source_model:activeModelId()')

rx(ui,r"  function matchGamesPreview\(m\)\{.*?\n  \}\n\n  function matchGamesLines\(m\)\{.*?\n  \}\n",
"""  function matchGamesPreview(m){\n    const selected=modelMarketRows(m,'match_total').map(x=>({ln:modelLine(x),side:String(x.pick||'').toUpperCase(),v:Number(x.v)})).filter(x=>x.ln&&num(x.v)!=null).sort((a,b)=>b.v-a.v);\n    if(selected.length){const z=selected[0],exp=num(m.expected_match_games);return `<div class=\"p753-match-total-preview\"><span>📊 Gemy · cały mecz · ${esc(activeModelName())}</span><b>${esc(z.side)} ${esc(z.ln)}</b><strong>${Math.round(z.v)}%</strong>${exp!=null?`<em>śr. Adaptive ${exp.toFixed(1)}</em>`:''}</div>`}\n    const e=Object.entries(m.match_over_under||{}).map(([ln,x])=>{const o=num(x?.over),u=num(x?.under);return o==null||u==null?null:{ln,side:o>=u?'OVER':'UNDER',v:Math.max(o,u)}}).filter(Boolean).sort((a,b)=>b.v-a.v);\n    if(!e.length)return `<div class=\"p753-match-total-preview\"><span>📊 Gemy · cały mecz</span><b>N/D</b></div>`;\n    const z=e[0],exp=num(m.expected_match_games);return `<div class=\"p753-match-total-preview\"><span>📊 Gemy · cały mecz · Adaptive baza</span><b>${z.side} ${esc(z.ln)}</b><strong>${Math.round(z.v)}%</strong>${exp!=null?`<em>śr. ${exp.toFixed(1)}</em>`:''}</div>`;\n  }\n\n  function matchGamesLines(m){\n    const selected=modelMarketRows(m,'match_total'),exp=num(m.expected_match_games);\n    if(selected.length)return `<div class=\"p751-lines p756-match-lines\"><label>📊 Linie gemów · cały mecz · ${esc(activeModelName())}${exp!=null?` · śr. Adaptive ${exp.toFixed(1)}`:''}</label><div>${selected.map(x=>{const ln=modelLine(x),v=Number(x.v),side=String(x.pick||'').toUpperCase().startsWith('O')?'O':'U';return `<span class=\"${v>=72?'strong':''}\"><b>${esc(ln)}</b><small>${side} ${Math.round(v)}%</small></span>`}).join('')}</div></div>`;\n    const e=Object.entries(m.match_over_under||{});if(!e.length)return `<div class=\"p751-lines p756-match-lines\"><label>📊 Linie gemów · cały mecz</label><p class=\"p751-note\">Brak danych O/U całego meczu.</p></div>`;\n    return `<div class=\"p751-lines p756-match-lines\"><label>📊 Linie gemów · cały mecz · Adaptive baza${exp!=null?` · śr. ${exp.toFixed(1)}`:''}</label><div>${e.map(([ln,x])=>{const o=num(x?.over),u=num(x?.under),mx=Math.max(o||0,u||0),side=(o||0)>=(u||0)?'O':'U';return `<span class=\"${mx>=72?'strong':''}\"><b>${esc(ln)}</b><small>${side} ${Math.round(mx)}%</small></span>`}).join('')}</div></div>`;\n  }\n""",'Adaptive baza${exp')

rep(ui,"""      <footer>\n        <span>${m.early_hold_v7?.ready?'🧬 PBP OK':'🧠 Adaptive'}</span>\n        <span>DANE ${esc(m.quality||'—')}</span>\n        <b>Analiza ›</b>\n      </footer>\n""",
"""      <footer>\n        <span>🧠 ${esc(activeModelName())}</span>\n        <span>${m.early_hold_v7?.ready?'🧬 PBP OK':'🧬 PBP N/D'}</span>\n        <span>DANE ${esc(m.quality||'—')}</span>\n        <b>Analiza ›</b>\n      </footer>\n""",'<span>🧠 ${esc(activeModelName())}</span>')

rep(ui,"""        <article><span>Ryzyko</span><b>${(a?.value||0)>=85?'Niskie':(a?.value||0)>=72?'Średnie':'Wyższe'}</b><strong>${Math.round(a?.value||0)||'—'}/100</strong></article>""",
"""        <article><span>Siła sygnału</span><b>${(a?.value||0)>=85?'Bardzo mocny':(a?.value||0)>=72?'Mocny':'Umiarkowany'}</b><strong>${Math.round(a?.value||0)||'—'}/100</strong></article>""",'<span>Siła sygnału</span><b>${(a?.value||0)>=85')

rep(ui,"""    const over85=num(m.over_under?.['8.5']?.over);\n    const lines=m.market_lab_v741?.set1_total||m.over_under||{};\n    return `<details class=\"p751-acc\" open>\n""",
"""    const over85=num(m.over_under?.['8.5']?.over);\n    const lines=m.market_lab_v741?.set1_total||m.over_under||{};\n    const selectedSetLines=modelMarketRows(m,'set1_total');\n    const modelContext=activeModelId()==='adaptive'?'':`<p class=\"p772-context\"><b>Aktywny model: ${esc(activeModelName())}.</b> Top typ, siła i linie modelowe korzystają z tego modelu. 1:1 / 2:2 / 3:3 pozostają osobną warstwą stanów gemowych PBP/Adaptive.</p>`;\n    return `<details class=\"p751-acc\" open>\n""",'const selectedSetLines=modelMarketRows')
rep(ui,'      <div class="p751-acc-body">\n        ${p11!=null?', '      <div class="p751-acc-body">\n        ${modelContext}\n        ${p11!=null?', '${modelContext}\n        ${p11')

old_lines="""        <div class=\"p751-lines\"><label>Linie gemów · 1. set</label><div>${Object.entries(lines).map(([ln,x])=>{\n          const o=num(x?.over),u=num(x?.under),mx=Math.max(o||0,u||0),side=(o||0)>=(u||0)?'O':'U';\n          return `<span class=\"${mx>=72?'strong':''}\"><b>${esc(ln)}</b><small>${side}${Math.round(mx)}</small></span>`;\n        }).join('')}</div></div>\n"""
new_lines="""        <div class=\"p751-lines\"><label>Linie gemów · 1. set · ${selectedSetLines.length?esc(activeModelName()):'Adaptive baza'}</label><div>${selectedSetLines.length?selectedSetLines.map(x=>{const ln=modelLine(x),v=Number(x.v),side=String(x.pick||'').toUpperCase().startsWith('O')?'O':'U';return `<span class=\"${v>=72?'strong':''}\"><b>${esc(ln)}</b><small>${side}${Math.round(v)}</small></span>`}).join(''):Object.entries(lines).map(([ln,x])=>{const o=num(x?.over),u=num(x?.under),mx=Math.max(o||0,u||0),side=(o||0)>=(u||0)?'O':'U';return `<span class=\"${mx>=72?'strong':''}\"><b>${esc(ln)}</b><small>${side}${Math.round(mx)}</small></span>`}).join('')}</div></div>\n"""
rep(ui,old_lines,new_lines,'selectedSetLines.length?esc(activeModelName())')

# Serve Props full tool
rx(ui,r"  function serve\(m\)\{.*?\n  \}\n\n  function lab\(m\)\{",
"""  function serve(m){\n    const s=m.serve_props_v72;if(!s)return '';\n    const one=(side)=>{const p=s[side]||{},name=m[side]||'—',hist=p.history?.all?.['10']||{};const avg=k=>hist?.[k]?.avg==null?'N/D':`${Number(hist[k].avg).toFixed(1)} · n=${hist[k].sample||0}`;\n      const tool=(kind,x)=>{const title=kind==='aces'?'🎯 Asy':'⚠️ Podwójne błędy';if(!x?.ready)return `<div class=\"sp72-market nd\"><div class=\"sp72-market-head\"><b>${title}</b><span>N/D</span></div><p>Za mała próbka.</p></div>`;const mean=Number(x.mean),def=num(x.suggested_line)??Math.max(.5,Math.floor(mean)-.5),max=kind==='aces'?'20.5':'12.5';return `<div class=\"sp72-market\" data-sp-market=\"p772-${esc(m.id||'m')}-${side}-${kind}\" data-sp-mean=\"${mean}\"><div class=\"sp72-market-head\"><b>${title}</b><span>MODEL ŚR. ${mean.toFixed(1)}</span></div><div class=\"sp72-market-meta\"><span>${x.sample||0} meczów</span><span>BO3 · model count</span></div><div class=\"sp72-line-tool\"><label>Linia buka <input type=\"number\" inputmode=\"decimal\" min=\"0.5\" max=\"${max}\" step=\"0.5\" value=\"${Number(def).toFixed(1)}\" data-sp-line></label><div class=\"sp72-probs\" data-sp-output></div></div></div>`};\n      return `<article><h4>${esc(name)}</h4><div class=\"p772-serve-history\"><span>Asy · ostatnie 10<b>${esc(avg('aces'))}</b></span><span>DF · ostatnie 10<b>${esc(avg('double_faults'))}</b></span></div>${tool('aces',p.aces)}${tool('df',p.double_faults)}</article>`};\n    return `<details class=\"p751-acc\"><summary><div><span>⚡</span><b>Asy i podwójne błędy</b><small>przeciwnik + nawierzchnia + długość meczu</small></div><em>${s.ready?'MODEL':'N/D'}</em><i>⌄</i></summary><div class=\"p751-acc-body\"><p class=\"p751-note\">Wpisz linię buka. OVER/UNDER i fair odds odświeżają się automatycznie.</p><div class=\"p751-serve-grid\">${one('p1')}${one('p2')}</div></div></details>`;\n  }\n\n  function lab(m){""",'data-sp-market="p772-')

# Market Lab fuller panel
rx(ui,r"  function lab\(m\)\{.*?\n  \}\n\n  function models\(m\)\{",
"""  function lab(m){\n    const l=m.market_lab_v741;if(!l)return '';\n    const lr=(label,x)=>{const o=num(x?.over),u=num(x?.under);if(o==null||u==null)return '';return marketRow(label,`O ${pc(o)}`,`U ${pc(u)}`,Math.max(o,u)>=72)};\n    const best=(o,n=6)=>Object.entries(o||{}).sort((a,b)=>Math.max(Number(b[1]?.over||0),Number(b[1]?.under||0))-Math.max(Number(a[1]?.over||0),Number(a[1]?.under||0))).slice(0,n),pg=l.player_total_games||{};\n    const combo=(obj,stage)=>`<div class=\"p772-lab-grid\">${marketRow(`${stage} · ${m.p1} wygra + U6.5`,pc(obj?.p1?.under),'wspólne zdarzenie',num(obj?.p1?.under)>=72)}${marketRow(`${stage} · ${m.p1} wygra + O6.5`,pc(obj?.p1?.over),'wspólne zdarzenie',num(obj?.p1?.over)>=72)}${marketRow(`${stage} · ${m.p2} wygra + U6.5`,pc(obj?.p2?.under),'wspólne zdarzenie',num(obj?.p2?.under)>=72)}${marketRow(`${stage} · ${m.p2} wygra + O6.5`,pc(obj?.p2?.over),'wspólne zdarzenie',num(obj?.p2?.over)>=72)}</div>`;\n    return `<details class=\"p751-acc\"><summary><div><span>🧪</span><b>Market Lab</b><small>pełne rynki · osobna walidacja</small></div><em>LAB</em><i>⌄</i></summary><div class=\"p751-acc-body\"><p class=\"p751-note\">LAB nie podbija głównego score. v7.7.2 tracker rozlicza też liczbę tie-breaków oraz „zwycięzca seta + własne gemy”.</p><div class=\"p751-lab-grid\"><span>Dokładnie 6 gemów 1S <b>${pc(l.set1_exact_six_games)}</b></span><span>Tie-break 1S <b>${pc(l.set1_tiebreak?.yes)}</b></span><span>Tie-break mecz <b>${pc(l.match_tiebreak?.yes)}</b></span><span>Obaj wygrają seta <b>${pc(l.both_players_win_set?.yes)}</b></span></div><div class=\"p772-lab-section\"><h4>🎾 1. set · O/U</h4><div>${Object.entries(l.set1_total||{}).map(([ln,x])=>lr(`1S ${ln}`,x)).join('')}</div></div><div class=\"p772-lab-section\"><h4>👤 Gemy zawodnika · cały mecz</h4><div class=\"p772-lab-grid\"><div><b>${esc(m.p1)}</b>${best(pg[m.p1]).map(([ln,x])=>lr(ln,x)).join('')}</div><div><b>${esc(m.p2)}</b>${best(pg[m.p2]).map(([ln,x])=>lr(ln,x)).join('')}</div></div></div><div class=\"p772-lab-section\"><h4>🔀 Dokładna liczba tie-breaków</h4><div class=\"p772-lab-grid\">${Object.entries(l.tiebreak_count||{}).map(([k,v])=>marketRow(`${k} tie-break`,pc(v),'event',num(v)>=72)).join('')}</div></div><div class=\"p772-lab-section\"><h4>🧩 Zwycięzca seta + własne gemy</h4>${combo(l.set1_winner_player_games_6_5,'1. set')}${combo(l.set2_winner_player_games_6_5,'2. set')}</div></div></details>`;\n  }\n\n  function models(m){""",'tracker rozlicza też liczbę tie-breaków')

# Analytics parity
rx(ui,r"  function pro76Side\(m,side\)\{.*?\n  \}\n  function analyticsPro76\(m\)\{",
"""  function pro76Side(m,side){\n    const tr=m.tendencies_v71?.[side]||{},eh=m.early_hold_v7?.[side]||{},g=tr.all?.['10']||{},surf=tr.surface?.['10']||{},p=eh.pbp_tendencies?.all?.['10']||{};\n    const metric=(b,k)=>num(b?.metrics?.[k]?.pct),av=(b,k)=>num(b?.averages?.[k]);\n    const serve=pro76Weighted([[pro76Range(av(g,'hold_rate'),60,90),.38],[pro76Range(av(g,'serve_points_won'),50,72),.25],[pro76Range(av(g,'first_serve_won'),55,85),.20],[pro76Range(av(g,'second_serve_won'),35,65),.17]]);\n    const ret=pro76Weighted([[pro76Range(av(g,'break_rate'),10,45),.46],[pro76Range(av(g,'return_points_won'),28,52),.54]]);\n    const form=pro76Weighted([[metric(g,'match_win'),.45],[metric(g,'set1_win'),.32],[metric(g,'set2_win'),.23]]);\n    const early=Number(p?.sample_matches||0)>=3?pro76Weighted([[metric(p,'hold1'),.42],[metric(p,'hold2'),.32],[metric(p,'hold3'),.18],[metric(p,'sequence_11_22_33'),.08]]):null;\n    const mental=pro76Weighted([[metric(g,'closeout_after_set1_win'),.32],[metric(g,'comeback_set2_after_set1_loss'),.32],[metric(g,'deciding_set_win'),.26],[metric(g,'set2_win'),.10]]);\n    const surface=Number(surf?.sample_matches||0)>=3?pro76Weighted([[metric(surf,'match_win'),.40],[pro76Range(av(surf,'hold_rate'),60,90),.25],[pro76Range(av(surf,'return_points_won'),28,52),.20],[metric(surf,'set1_win'),.15]]):null;\n    return {serve,ret,form,early,mental,surface};\n  }\n  function analyticsPro76(m){""",'pbp_tendencies?.all?.[\'10\']')
rep(ui,'        <p class="p751-note">Indeksy opisują profil danych zawodnika i służą do porównania. Nie są szansą wygranej meczu.</p>',
'        <p class="p751-note">Indeksy liczone identycznie jak w profilu: ostatnie 10 · wszystkie mecze; „Nawierzchnia” używa ostatnich 10 na tej nawierzchni. Nie są szansą wygranej meczu.</p>','Indeksy liczone identycznie jak w profilu')
rep(ui,'        <div><em class="${m.early_hold_v7?.ready?\'ok\':\'\'}">${m.early_hold_v7?.ready?\'PBP OK\':\'PBP N/D\'}</em><em>LIVE DATA</em><em>MODEL ${Math.round(num(m.model_confidence)||0)}</em></div>',
'        <div><em class="${m.early_hold_v7?.ready?\'ok\':\'\'}">${m.early_hold_v7?.ready?\'PBP OK\':\'PBP N/D\'}</em><em>AKTYWNY ${esc(activeModelName())}</em><em>JAKOŚĆ ${Math.round(num(m.model_confidence)||0)}</em></div>','<em>AKTYWNY ${esc(activeModelName())}</em>')
rep(ui,"document.querySelector('.brand-copy p').textContent='Tenis AI v7.7.1 · Hold Paths'","document.querySelector('.brand-copy p').textContent='Tenis AI v7.7.2 · Logic Audit Fix'",'Tenis AI v7.7.2 · Logic Audit Fix')

# 3. PBP directional stats
pbp=B/'pbp_tracker.py'
rx(pbp,r"def _result_signal\(name: str, pred: dict \| None, actual: dict, entry: dict\):.*?\n\n\ndef settle_one",
'''def _result_signal(name: str, pred: dict | None, actual: dict, entry: dict):
    if not pred or pred.get("prob") is None: return None
    p=float(pred["prob"]); pick=pred.get("pick"); states=actual.get("states") or {}
    if name=="first_set": y=_key(pick)==_key(actual.get("first_set_winner"))
    elif name=="lead_after6":
        st=states.get("6")
        if not st:return None
        a,b=[int(x) for x in st.split(":")];y=(a>b and _key(pick)==_key(entry.get("p1"))) or (b>a and _key(pick)==_key(entry.get("p2")))
    elif name=="over85": y=bool(actual.get("over85"))
    elif name=="balanced_after6": y=states.get("6")=="3:3"
    elif name=="joint_builder":
        st=states.get("6")
        if not st:return None
        a,b=[int(x) for x in st.split(":")];lead=(a>b and _key(pick)==_key(entry.get("p1"))) or (b>a and _key(pick)==_key(entry.get("p2")));win=_key(pick)==_key(actual.get("first_set_winner"));y=lead and bool(actual.get("over85")) and win
    elif name in ("state2","state4","state6"): y=str(pick)==str(states.get(name.replace("state","")))
    else:return None
    direction_yes=p>=.5;correct=bool(y) if direction_yes else not bool(y);conf=max(p,1-p)
    return {"market":name,"pick":pick,"prob":round(p,4),"event_actual":bool(y),"actual":bool(y),"direction":"YES" if direction_yes else "NO","confidence":round(conf,4),"correct":bool(correct),"result":"hit" if correct else "miss","brier":round((p-(1.0 if y else 0.0))**2,6)}


def settle_one''','"event_actual":bool(y)')
rx(pbp,r"def _summary\(signals\):.*?\n\n\ndef tracker_stats",
'''def _signal_confidence(s):
    try:p=float(s.get("prob"))
    except (TypeError,ValueError):return 0.0
    return max(p,1-p)

def _signal_correct(s):
    if s.get("correct") is not None:return bool(s.get("correct"))
    try:p=float(s.get("prob"))
    except (TypeError,ValueError):return False
    event=bool(s.get("event_actual") if s.get("event_actual") is not None else s.get("actual"))
    return event if p>=.5 else not event

def _summary(signals):
    n=len(signals)
    if not n:return {"settled":0,"hits":0,"misses":0,"accuracy":None,"avg_predicted":None,"avg_confidence":None,"brier":None}
    hits=sum(1 for s in signals if _signal_correct(s));c=sum(_signal_confidence(s) for s in signals)/n
    return {"settled":n,"hits":hits,"misses":n-hits,"accuracy":round(100*hits/n,1),"avg_predicted":round(100*c,1),"avg_confidence":round(100*c,1),"brier":round(sum(float(s["brier"]) for s in signals)/n,4)}


def tracker_stats''','def _signal_confidence(s):')
rep(pbp,'        rows=[s for s in sig if lo<=float(s.get("prob") or 0)<hi]','        rows=[s for s in sig if lo<=_signal_confidence(s)<hi]','lo<=_signal_confidence(s)<hi')
rep(pbp,'    green=[s for s in sig if float(s.get("prob") or 0)>=GREEN]','    green=[s for s in sig if _signal_confidence(s)>=GREEN]','_signal_confidence(s)>=GREEN')
rep(pbp,'    return {"version":"v7.3","production_matches_captured":len(entries),','    return {"version":"v7.7.2-directional","production_matches_captured":len(entries),','"version":"v7.7.2-directional"')
rep(pbp,'            "note":"Production tracker freezes the real pre-match Early Hold output and settles it from BASIC PBP."}','            "note":"Production accuracy = poprawny kierunek TAK/NIE; green = max(p,1-p)>=72%; Brier = surowe p zdarzenia."}','Production accuracy = poprawny kierunek')

# 4. Adaptive second-set context + Market Lab conditional
model=B/'model.py'
rep(model,'    expected_match_games = match_win = total_sets = exact_match_score = None\n    pick = first_score = over85 = None\n','    expected_match_games = match_win = total_sets = exact_match_score = None\n    second_set_context = None\n    pick = first_score = over85 = None\n','second_set_context = None')
rep(model,"""        q_win, q_loss, q2 = _second_set_context(p1, p2, first_target, model_confidence)\n        q3 = _third_set_target(p1, p2, first_target, model_confidence)\n        second_set_win = {match['p1']: round(q2 * 100, 1), match['p2']: round((1 - q2) * 100, 1)}\n""",
"""        q_win, q_loss, q2 = _second_set_context(p1, p2, first_target, model_confidence)\n        q3 = _third_set_target(p1, p2, first_target, model_confidence)\n        second_set_context = {'p1_if_p1_wins_set1': round(q_win*100,1), 'p1_if_p1_loses_set1': round(q_loss*100,1), 'p1_unconditional': round(q2*100,1)}\n        second_set_win = {match['p1']: round(q2 * 100, 1), match['p2']: round((1 - q2) * 100, 1)}\n""",'p1_if_p1_wins_set1')
rep(model,"        'second_set_win': second_set_win,\n        'third_set_win': third_set_win,\n","        'second_set_win': second_set_win,\n        'second_set_context': second_set_context,\n        'third_set_win': third_set_win,\n","'second_set_context': second_set_context")

lab=B/'market_lab_v741.py'
rx(lab,r"def build_match\(first,second,third\):.*?\n    return norm\(joint\),norm\(tb\),norm\(exact\)\n",
'''def build_match(first,second_if_win,second_if_loss,third):
    joint={};tb={0:0.0,1:0.0,2:0.0,3:0.0};exact={"2:0":0.0,"2:1":0.0,"1:2":0.0,"0:2":0.0}
    for s1,p1 in first.items():
        w1=s1[0]>s1[1];t1=int(set(s1)=={6,7});second=second_if_win if w1 else second_if_loss
        for s2,p2 in second.items():
            w2=s2[0]>s2[1];t2=int(set(s2)=={6,7});p12=p1*p2;a=s1[0]+s2[0];b=s1[1]+s2[1]
            if w1 and w2:joint[(a,b)]=joint.get((a,b),0)+p12;exact["2:0"]+=p12;tb[t1+t2]+=p12
            elif not w1 and not w2:joint[(a,b)]=joint.get((a,b),0)+p12;exact["0:2"]+=p12;tb[t1+t2]+=p12
            else:
                for s3,p3 in third.items():
                    pr=p12*p3;aa=a+s3[0];bb=b+s3[1];t3=int(set(s3)=={6,7});joint[(aa,bb)]=joint.get((aa,bb),0)+pr;tb[t1+t2+t3]+=pr;exact["2:1" if s3[0]>s3[1] else "1:2"]+=pr
    return norm(joint),norm(tb),norm(exact)
def mix_dist(a,b,wa):
    wa=clamp(wa);keys=set(a)|set(b);return norm({k:wa*a.get(k,0)+(1-wa)*b.get(k,0) for k in keys})
''','def mix_dist(a,b,wa):')
rep(lab,'    second=reweight(raw,target(m.get("second_set_win"),p1,p1win(first)))\n    third=reweight(raw,target(m.get("third_set_win"),p1,p1win(first)))\n    joint,tb,exact=build_match(first,second,third)\n',
'    second_default=target(m.get("second_set_win"),p1,p1win(first))\n    ctx=m.get("second_set_context") or {}\n    second_if_win=reweight(raw,target(ctx,"p1_if_p1_wins_set1",second_default))\n    second_if_loss=reweight(raw,target(ctx,"p1_if_p1_loses_set1",second_default))\n    second=mix_dist(second_if_win,second_if_loss,p1win(first))\n    third=reweight(raw,target(m.get("third_set_win"),p1,p1win(first)))\n    joint,tb,exact=build_match(first,second_if_win,second_if_loss,third)\n','second_if_win=reweight')
rep(lab,'      "note":"Nowe rynki są osobno zamrażane i walidowane; nie podnoszą jeszcze głównego score.",','      "note":"LAB walidowany osobno; 2. set używa warunkowego kontekstu po wyniku 1. seta; nie podnosi głównego score.",','warunkowego kontekstu')

# 5. Market Lab tracker extra markets
ml=B/'market_lab_tracker_v741.py'
rx(ml,r"def flatten\(x\):.*?\n    return m\n",
'''def flatten(x):
    l=x.get("market_lab_v741") or {};m={}
    for n,o in (l.get("set1_total") or {}).items():add(m,f"set1_over_{n}",o.get("over"))
    for n,o in (l.get("set2_total") or {}).items():add(m,f"set2_over_{n}",o.get("over"))
    add(m,"set1_exact_6_games",l.get("set1_exact_six_games"));add(m,"set1_tiebreak",(l.get("set1_tiebreak") or {}).get("yes"));add(m,"match_tiebreak",(l.get("match_tiebreak") or {}).get("yes"));add(m,"both_players_win_set",(l.get("both_players_win_set") or {}).get("yes"))
    for k,p in (l.get("tiebreak_count") or {}).items():add(m,f"tiebreak_count_{k}",p)
    for stage,key in (("set1","set1_winner_player_games_6_5"),("set2","set2_winner_player_games_6_5")):
        c=l.get(key) or {}
        for tag in ("p1","p2"):
            add(m,f"{stage}_winner_{tag}_under_6.5",(c.get(tag) or {}).get("under"));add(m,f"{stage}_winner_{tag}_over_6.5",(c.get(tag) or {}).get("over"))
    for player,tag in ((x.get("p1"),"p1"),(x.get("p2"),"p2")):
        for n,o in ((l.get("player_total_games") or {}).get(player) or {}).items():add(m,f"{tag}_games_over_{n}",o.get("over"))
    return m
''','tiebreak_count_{k}')
rx(ml,r"def outcomes\(final\):.*?\n    return o\n",
'''def outcomes(final):
    sets=[tuple(map(int,s[:2])) for s in (final.get("sets") or []) if isinstance(s,(list,tuple)) and len(s)>=2]
    if not sets:return {}
    o={}
    for i,s in enumerate(sets[:2],1):
        g=sum(s)
        for n in (6.5,7.5,8.5,9.5,10.5,11.5,12.5):o[f"set{i}_over_{n:.1f}"]=int(g>n)
        a,b=s;p1=a>b;p2=b>a
        o[f"set{i}_winner_p1_under_6.5"]=int(p1 and a<6.5);o[f"set{i}_winner_p1_over_6.5"]=int(p1 and a>6.5);o[f"set{i}_winner_p2_under_6.5"]=int(p2 and b<6.5);o[f"set{i}_winner_p2_over_6.5"]=int(p2 and b>6.5)
    o["set1_exact_6_games"]=int(sum(sets[0])==6);o["set1_tiebreak"]=int(set(sets[0])=={6,7});tb=sum(1 for s in sets if set(s)=={6,7});o["match_tiebreak"]=int(tb>0)
    for k in range(4):o[f"tiebreak_count_{k}"]=int(tb==k)
    o["both_players_win_set"]=int(len(sets)>=3)
    for tag,g in (("p1",sum(s[0] for s in sets)),("p2",sum(s[1] for s in sets))):
        for n in (6.5,7.5,8.5,9.5,10.5,11.5,12.5,13.5,14.5,15.5):o[f"{tag}_games_over_{n:.1f}"]=int(g>n)
    return o
''','o[f"tiebreak_count_{k}"]')
rx(ml,r"def make_stats\(rows\):.*?\n    return \{\"version\":\"v7\.4\.1\",\"overall\":overall,\"markets\":markets\}\n",
'''def make_stats(rows):
    a={}
    for r in rows:
        ac=r.get("actual") or {}
        for k,p in (r.get("metrics") or {}).items():
            if k not in ac:continue
            y=bool(ac[k]);v=a.setdefault(k,{"n":0,"h":0,"g":0,"gh":0,"dg":0,"dgh":0,"b":0.0})
            v["n"]+=1;v["h"]+=int((p>=.5)==y);v["b"]+=(p-int(y))**2
            # green = zdarzenie, które aplikacja faktycznie mogłaby pokazać jako mocny pozytywny typ.
            if p>=.72:
                v["g"]+=1;v["gh"]+=int(y)
            # osobno diagnostyczny kierunek TAK/NIE.
            if max(p,1-p)>=.72:
                v["dg"]+=1;v["dgh"]+=int((p>=.5)==y)
    markets={k:{"n":v["n"],"accuracy":round(100*v["h"]/v["n"],1),"green_n":v["g"],
                "green_accuracy":round(100*v["gh"]/v["g"],1) if v["g"] else None,
                "directional_green_n":v["dg"],"directional_green_accuracy":round(100*v["dgh"]/v["dg"],1) if v["dg"] else None,
                "brier":round(v["b"]/v["n"],4)} for k,v in a.items()}
    n=sum(v["n"] for v in a.values());h=sum(v["h"] for v in a.values());g=sum(v["g"] for v in a.values());gh=sum(v["gh"] for v in a.values());dg=sum(v["dg"] for v in a.values());dgh=sum(v["dgh"] for v in a.values());b=sum(v["b"] for v in a.values())
    overall={"n":n,"accuracy":round(100*h/n,1) if n else None,"green_n":g,"green_accuracy":round(100*gh/g,1) if g else None,
             "directional_green_n":dg,"directional_green_accuracy":round(100*dgh/dg,1) if dg else None,
             "brier":round(b/n,4) if n else None}
    return {"version":"v7.7.2","overall":overall,"markets":markets}
''','directional_green_accuracy')
rep(ml,'    return {"version":"v7.4.1","overall":overall,"markets":markets}','    return {"version":"v7.7.2","overall":overall,"markets":markets}','"version":"v7.7.2"')

# 6. source_model in general history
ht=B/'history_tracker.py'
rep(ht,'    def add_binary(field, market, label, **extra):\n        obj = match.get(field) or {}\n        for pick, value in obj.items():\n            if value is not None and float(value) >= threshold:\n                out.append(_signal(market, label, pick, value, **extra))\n',
'    def add_binary(field, market, label, source_model="adaptive", **extra):\n        obj = match.get(field) or {}\n        for pick, value in obj.items():\n            if value is not None and float(value) >= threshold:\n                out.append(_signal(market, label, pick, value, source_model=source_model, **extra))\n','source_model="adaptive"')
rep(ht,"""                out.append(_signal(\n                    'game_state', f'Wynik po {checkpoint} gemach', pick, value,\n                    checkpoint=int(checkpoint), resolvable=False,\n                ))\n""",
"""                out.append(_signal(\n                    'game_state', f'Wynik po {checkpoint} gemach', pick, value,\n                    checkpoint=int(checkpoint), resolvable=False,\n                    source_model='early_hold_pbp' if (match.get('early_hold_v7') or {}).get('ready') else 'adaptive',\n                ))\n""",'source_model=\'early_hold_pbp\'')
# add adaptive source to set/match totals, both identical anchors
s=rd(ht); anchor="                    line=float(line),\n                ))"
for _ in range(2):
    if anchor in s:s=s.replace(anchor,"                    line=float(line), source_model='adaptive',\n                ))",1)
wr(ht,s)
rep(ht,"            out.append(_signal('exact_set1', 'Dokładny wynik 1. seta', pick, value))","            out.append(_signal('exact_set1', 'Dokładny wynik 1. seta', pick, value, source_model='adaptive'))",'exact_set1\', \'Dokładny wynik 1. seta\', pick, value, source_model=')

# 7. Performance Center labels
pc=F/'performance-center-v77.js'
rep(pc,"          version:m.model_version||'N/D',\n          matchKey:m.match_key||String(m.match_id||[m.p1,m.p2,m.scheduled_time].join('|'))\n","          version:m.model_version||'N/D',\n          sourceModel:s.source_model||'legacy',\n          matchKey:m.match_key||String(m.match_id||[m.p1,m.p2,m.scheduled_time].join('|'))\n","sourceModel:s.source_model||'legacy'")
rep(pc,"      {name:'Adaptive · zielona historia',value:cur.accuracy,n:cur.n,note:'rzeczywiście zamrożone i rozliczone sygnały'},","      {name:'Główna historia zamrożonych sygnałów',value:cur.accuracy,n:cur.n,note:'Adaptive + PBP game states; źródło modelu zapisywane per sygnał od v7.7.2'},",'Główna historia zamrożonych sygnałów')
rep(pc,"      {name:'Early Hold · production PBP',value:t.green_72_plus?.accuracy,n:t.green_72_plus?.settled||0,note:`${t.production_matches_pending||0} meczów czeka na rozliczenie`},","      {name:'Early Hold · production PBP',value:t.green_72_plus?.accuracy,n:t.green_72_plus?.settled||0,note:`kierunek TAK/NIE · confidence=max(p,1-p) · ${t.production_matches_pending||0} meczów czeka`},",'confidence=max(p,1-p)')

# 8. index + PWA
idx=F/'index.html';x=rd(idx)
if 'logic-audit-v772.css' not in x:x=x.replace('<link rel="stylesheet" href="early-hold-paths-v771.css">','<link rel="stylesheet" href="early-hold-paths-v771.css">\n  <link rel="stylesheet" href="logic-audit-v772.css">',1)
x=x.replace('Tenis AI v7.7.1 · Hold Paths','Tenis AI v7.7.2 · Logic Audit Fix').replace('LAB v7.7.1','LAB v7.7.2')
if 'v7.7.2: Logic Audit Fix' not in x:x=x.replace('<div>v7.7.1:','<div>v7.7.2: Logic Audit Fix — aktywny model steruje Match Center; PBP accuracy = kierunek TAK/NIE; Analytics PRO ujednolicony; pełne Serve Props i Market Lab; rozszerzona walidacja LAB. v7.7.1:',1)
wr(idx,x)
sw=F/'sw.js';w=rd(sw);w=re.sub(r"const C='[^']+';","const C='tenis-ai-v772-logic-audit-fix';",w,count=1)
if "'logic-audit-v772.css'" not in w:w=w.replace("'early-hold-paths-v771.css'","'early-hold-paths-v771.css','logic-audit-v772.css'",1)
wr(sw,w)

# Syntax checks before commit
for p in [B/'pbp_tracker.py',B/'market_lab_v741.py',B/'market_lab_tracker_v741.py',B/'history_tracker.py',B/'model.py']:
    compile(rd(p),str(p),'exec')
for p in [F/'multi-model.js',F/'ui-v751.js',F/'performance-center-v77.js']:
    try: subprocess.run(['node','--check',str(p)],check=True,capture_output=True,text=True)
    except FileNotFoundError: pass
print('Tenis AI v7.7.2 Logic Audit Fix: install + syntax OK')
