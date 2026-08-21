
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent

ui=ROOT/'frontend/ui-v751.js'
s=ui.read_text(encoding='utf-8')

helper = """
  function matchGamesPreview(m){
    const entries=Object.entries(m.match_over_under||{}).map(([ln,x])=>{
      const o=num(x?.over),u=num(x?.under);
      if(o==null||u==null)return null;
      return {ln,o,u,side:o>=u?'OVER':'UNDER',v:Math.max(o,u)};
    }).filter(Boolean).sort((a,b)=>b.v-a.v);
    if(!entries.length){
      return `<div class="p753-match-total-preview"><span>📊 Gemy · cały mecz</span><b>N/D</b></div>`;
    }
    const z=entries[0],exp=num(m.expected_match_games);
    return `<div class="p753-match-total-preview">
      <span>📊 Gemy · cały mecz</span>
      <b>${z.side} ${esc(z.ln)}</b>
      <strong>${Math.round(z.v)}%</strong>
      ${exp!=null?`<em>śr. ${exp.toFixed(1)}</em>`:''}
    </div>`;
  }

  function matchGamesLines(m){
    const entries=Object.entries(m.match_over_under||{});
    const exp=num(m.expected_match_games);
    if(!entries.length){
      return `<div class="p751-lines p756-match-lines"><label>📊 Linie gemów · cały mecz</label><p class="p751-note">Brak danych O/U całego meczu.</p></div>`;
    }
    return `<div class="p751-lines p756-match-lines">
      <label>📊 Linie gemów · cały mecz${exp!=null?` · śr. ${exp.toFixed(1)}`:''}</label>
      <div>${entries.map(([ln,x])=>{
        const o=num(x?.over),u=num(x?.under),mx=Math.max(o||0,u||0),side=(o||0)>=(u||0)?'O':'U';
        return `<span class="${mx>=72?'strong':''}"><b>${esc(ln)}</b><small>${side} ${Math.round(mx)}%</small></span>`;
      }).join('')}</div>
    </div>`;
  }
"""

if 'function matchGamesPreview(m)' not in s:
    marker='  function card(m){'
    if marker not in s:
        raise SystemExit('Nie znaleziono funkcji card(m)')
    s=s.replace(marker, helper+'\n'+marker, 1)

if '${matchGamesPreview(m)}' not in s:
    marker='      <footer>\n        <span>${m.early_hold_v7?.ready?\'🧬 PBP OK\':\'🧠 Adaptive\'}</span>'
    replacement='      ${matchGamesPreview(m)}\n      <footer>\n        <span>${m.early_hold_v7?.ready?\'🧬 PBP OK\':\'🧠 Adaptive\'}</span>'
    if marker not in s:
        raise SystemExit('Nie znaleziono stopki karty')
    s=s.replace(marker,replacement,1)

if '${matchGamesLines(m)}' not in s:
    start_marker='<div class="p751-lines"><label>Linie gemów · 1. set</label><div>${Object.entries(lines).map(([ln,x])=>{'
    start=s.find(start_marker)
    if start<0:
        raise SystemExit('Nie znaleziono linii gemów 1. seta')
    end_marker="}).join('')}</div></div>"
    end=s.find(end_marker,start)
    if end<0:
        raise SystemExit('Nie znaleziono końca bloku gemów 1. seta')
    pos=end+len(end_marker)
    s=s[:pos]+'\n        ${matchGamesLines(m)}'+s[pos:]

ui.write_text(s,encoding='utf-8')

css=ROOT/'frontend/readability-v753.css'
c=css.read_text(encoding='utf-8')
block="""
/* v7.5.6 — whole-match games are a first-class market */
.p756-match-lines{
  margin-top:10px!important;
  padding:9px!important;
  border:1px solid rgba(185,255,0,.18)!important;
  border-radius:10px!important;
  background:rgba(185,255,0,.025)!important;
}
.p756-match-lines>label{
  display:block!important;
  font-size:11px!important;
  font-weight:900!important;
  color:#dff8ff!important;
  margin-bottom:6px!important;
}
.p756-match-lines>div span{min-width:62px!important}
.p756-match-lines>div span small{font-size:9px!important}
"""
if 'v7.5.6 — whole-match games' not in c:
    c += '\n'+block
css.write_text(c,encoding='utf-8')

idx=ROOT/'frontend/index.html'
x=idx.read_text(encoding='utf-8')
x=x.replace('Tenis AI v7.5.5 · Match games hotfix','Tenis AI v7.5.6 · Gemy całego meczu')
x=x.replace('LAB v7.5.5','LAB v7.5.6')
if 'v7.5.6:' not in x:
    x=x.replace('<div>v7.5.5:','<div>v7.5.6: gemy całego meczu są renderowane bezpośrednio na każdej karcie i w Typach meczowych. v7.5.5:')
idx.write_text(x,encoding='utf-8')

sw=ROOT/'frontend/sw.js'
w=sw.read_text(encoding='utf-8')
w=re.sub(r"const C='[^']+';","const C='tenis-ai-v756-direct-match-games';",w,count=1)
sw.write_text(w,encoding='utf-8')

print('Tenis AI v7.5.6 direct match games: OK')
