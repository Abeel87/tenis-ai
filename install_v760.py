from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent

# 1) backend/player_trends.py — more stats from existing data, no new API
p=ROOT/'backend/player_trends.py'
s=p.read_text(encoding='utf-8')

needle='''    if "first_set_won" in x:
        metrics["set1_win"] = _binary_metric(x["first_set_won"])
'''
insert='''    if "first_set_won" in x:
        metrics["set1_win"] = _binary_metric(x["first_set_won"])
    if "second_set_won" in x:
        metrics["set2_win"] = _binary_metric(x["second_set_won"])
    if "second_after_first_win" in x:
        metrics["closeout_after_set1_win"] = _binary_metric(x["second_after_first_win"])
    if "second_after_first_loss" in x:
        metrics["comeback_set2_after_set1_loss"] = _binary_metric(x["second_after_first_loss"])
    if "third_set_won" in x:
        metrics["deciding_set_win"] = _binary_metric(x["third_set_won"])
'''
if 'closeout_after_set1_win' not in s:
    if needle not in s:
        raise SystemExit('player_trends: set1 marker not found')
    s=s.replace(needle,insert,1)

needle='''    if "return_points_won" in x:
        averages["return_points_won"] = _avg_metric(x["return_points_won"], 100.0)
    if "first_set_games" in x:
'''
insert='''    if "return_points_won" in x:
        averages["return_points_won"] = _avg_metric(x["return_points_won"], 100.0)
    if "first_serve_won" in x:
        averages["first_serve_won"] = _avg_metric(x["first_serve_won"], 100.0)
    if "second_serve_won" in x:
        averages["second_serve_won"] = _avg_metric(x["second_serve_won"], 100.0)
    if "first_set_games" in x:
'''
if 'averages["first_serve_won"]' not in s:
    if needle not in s:
        raise SystemExit('player_trends: averages marker not found')
    s=s.replace(needle,insert,1)

if 'def _trend_pack(' not in s:
    marker='def build_player_tendencies('
    helper='''def _trend_pack(rows: pd.DataFrame) -> dict:
    # latest 5 minus previous 5, in percentage points; descriptive only
    if rows is None or rows.empty:
        return {}
    a=rows.head(5)
    b=rows.iloc[5:10]
    if len(a)<3 or len(b)<3:
        return {}
    out={}
    for col in (
        "won","first_set_won","second_set_won","hold_rate","break_rate",
        "serve_points_won","return_points_won","first_serve_won","second_serve_won"
    ):
        if col not in rows.columns:
            continue
        x=pd.to_numeric(a[col],errors="coerce").dropna()
        y=pd.to_numeric(b[col],errors="coerce").dropna()
        if len(x)<2 or len(y)<2:
            continue
        out[col]=round(100.0*(float(x.mean())-float(y.mean())),1)
    aliases={"won":"match_win","first_set_won":"set1_win","second_set_won":"set2_win"}
    for src,dst in aliases.items():
        if src in out:
            out[dst]=out[src]
    return out


'''
    if marker not in s:
        raise SystemExit('player_trends: build marker not found')
    s=s.replace(marker,helper+marker,1)

needle='''        "all": {str(n): _window(x, n) for n in WINDOWS},
        "surface": {str(n): _window(sx, n) for n in WINDOWS},
    }
'''
insert='''        "all": {str(n): _window(x, n) for n in WINDOWS},
        "surface": {str(n): _window(sx, n) for n in WINDOWS},
        "trend": {
            "all": _trend_pack(x),
            "surface": _trend_pack(sx),
        },
    }
'''
if '"trend": {' not in s:
    if needle not in s:
        raise SystemExit('player_trends: return marker not found')
    s=s.replace(needle,insert,1)

p.write_text(s,encoding='utf-8')

# 2) frontend assets
idx=ROOT/'frontend/index.html'
x=idx.read_text(encoding='utf-8')
if 'player-analytics-v76.css' not in x:
    x=x.replace(
      '<link rel="stylesheet" href="player-trends-v71.css">',
      '<link rel="stylesheet" href="player-trends-v71.css">\n  <link rel="stylesheet" href="player-analytics-v76.css">'
    )
if 'player-analytics-v76.js' not in x:
    x=x.replace(
      '<script src="player-trends-v71.js"></script>',
      '<script src="player-trends-v71.js"></script>\n  <script src="player-analytics-v76.js"></script>'
    )
x=x.replace('Tenis AI v7.5.6 · Gemy całego meczu','Tenis AI v7.6 · Player Analytics PRO')
x=x.replace('LAB v7.5.6','LAB v7.6')
if 'v7.6:' not in x:
    x=x.replace(
      '<div>v7.5.6:',
      '<div>v7.6: Player Analytics PRO — serwis, return, forma, Early Hold, mental, nawierzchnia i trendy 5/10/20. v7.5.6:'
    )
idx.write_text(x,encoding='utf-8')

# 3) direct comparison in match detail
ui=ROOT/'frontend/ui-v751.js'
u=ui.read_text(encoding='utf-8')
helper='''  function pro76Range(x,lo,hi){
    x=num(x);if(x==null)return null;
    return Math.max(0,Math.min(100,(x-lo)/(hi-lo)*100));
  }
  function pro76Weighted(pairs){
    const ok=pairs.filter(([v,w])=>num(v)!=null&&w>0);
    if(!ok.length)return null;
    const z=ok.reduce((s,[,w])=>s+w,0);
    return ok.reduce((s,[v,w])=>s+Number(v)*w,0)/z;
  }
  function pro76Side(m,side){
    const st=m[`${side}_stats`]||{};
    const eh=m.early_hold_v7?.[side]||{};
    const tr=m.tendencies_v71?.[side]||{};
    const surf=tr.surface?.['10']||{};
    const sm=surf.metrics||{},sa=surf.averages||{};
    const get=(k)=>num(st[k])==null?null:Number(st[k])*100;
    const serve=pro76Weighted([
      [pro76Range(get('hold_rate'),60,90),.38],
      [pro76Range(get('serve_points_won'),50,72),.25],
      [pro76Range(get('first_serve_won'),55,85),.20],
      [pro76Range(get('second_serve_won'),35,65),.17]
    ]);
    const ret=pro76Weighted([
      [pro76Range(get('break_rate'),10,45),.46],
      [pro76Range(get('return_points_won'),28,52),.54]
    ]);
    const form=pro76Weighted([[get('won'),.45],[get('first_set_won'),.32],[get('second_set_won'),.23]]);
    const early=eh.ready?num(eh.ehs):null;
    const mental=pro76Weighted([
      [get('second_after_first_win'),.32],
      [get('second_after_first_loss'),.32],
      [get('third_set_won'),.26],
      [get('second_set_won'),.10]
    ]);
    const surface=Number(surf.sample_matches||0)>=3?pro76Weighted([
      [sm.match_win?.pct,.42],
      [pro76Range(sa.hold_rate,60,90),.28],
      [pro76Range(sa.return_points_won,28,52),.18],
      [sm.set1_win?.pct,.12]
    ]):null;
    return {serve,ret,form,early,mental,surface};
  }
  function analyticsPro76(m){
    const a=pro76Side(m,'p1'),b=pro76Side(m,'p2');
    const row=(label,key)=>{
      const x=a[key],y=b[key];
      const best=x==null||y==null?'':x>y?'p1':y>x?'p2':'';
      return `<div class="pa76-compare-row">
        <span>${esc(label)}</span>
        <b class="${best==='p1'?'best':''}">${x==null?'N/D':Math.round(x)}</b>
        <b class="${best==='p2'?'best':''}">${y==null?'N/D':Math.round(y)}</b>
      </div>`;
    };
    return `<details class="p751-acc pa76-match-compare">
      <summary><div><span>🧠</span><b>Player Analytics PRO</b><small>profil 0–100 · nie prawdopodobieństwo</small></div><em>PRO</em><i>⌄</i></summary>
      <div class="p751-acc-body">
        <div class="pa76-compare-head"><span></span><b>${esc(m.p1)}</b><b>${esc(m.p2)}</b></div>
        ${row('🎾 Serwis','serve')}
        ${row('↩️ Return','ret')}
        ${row('🔥 Forma','form')}
        ${row('🧬 Early Hold','early')}
        ${row('🧠 Mental','mental')}
        ${row('🏟️ Nawierzchnia','surface')}
        <p class="p751-note">Indeksy opisują profil danych zawodnika i służą do porównania. Nie są szansą wygranej meczu.</p>
      </div>
    </details>`;
  }

'''
if 'function analyticsPro76(m)' not in u:
    marker='  function detailHtml(m){'
    if marker not in u:
        raise SystemExit('ui-v751: detailHtml marker not found')
    u=u.replace(marker,helper+marker,1)

if '${analyticsPro76(m)}' not in u:
    old='${coreMarkets(m)}${stats(m)}${pbp(m)}${serve(m)}${lab(m)}${models(m)}'
    new='${coreMarkets(m)}${stats(m)}${analyticsPro76(m)}${pbp(m)}${serve(m)}${lab(m)}${models(m)}'
    if old not in u:
        raise SystemExit('ui-v751: accordion list marker not found')
    u=u.replace(old,new,1)
ui.write_text(u,encoding='utf-8')

# 4) service worker
sw=ROOT/'frontend/sw.js'
w=sw.read_text(encoding='utf-8')
w=re.sub(r"const C='[^']+';","const C='tenis-ai-v760-player-analytics-pro';",w,count=1)
for asset,anchor in [
    ('player-analytics-v76.css','player-trends-v71.css'),
    ('player-analytics-v76.js','player-trends-v71.js')
]:
    if asset not in w:
        w=w.replace(f"'{anchor}'",f"'{anchor}','{asset}'")
sw.write_text(w,encoding='utf-8')

print('Tenis AI v7.6 Player Analytics PRO installer: OK')
