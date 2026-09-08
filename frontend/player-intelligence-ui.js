/* Tenis AI v8.5.1 — Player Intelligence UI bridge
UI-only. No direct fetch, no MutationObserver, no interval.
*/
(() => {
  'use strict';
  const VERSION='v8.5.1';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>x==null||x===''||!Number.isFinite(Number(x))?null:Number(x);
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const signed=x=>num(x)==null?'—':`${Number(x)>0?'+':''}${Number(x).toFixed(1)}`;
  const rows=()=>{try{return typeof all!=='undefined'&&Array.isArray(all)?all:[]}catch{return []}};
  const key=m=>String(m?.id ?? m?.match_id ?? [m?.p1,m?.p2,m?.scheduled_time].join('|'));
  const qclass=q=>String(q||'N/D').toLowerCase().replace(/[^a-z0-9]+/g,'-');
  let telemetryPromise=null;

  const STYLE=`
  .pi851-card-strip{margin:.6rem .8rem .2rem;padding:.62rem .72rem;border:1px solid rgba(73,211,245,.22);border-radius:13px;background:linear-gradient(135deg,rgba(5,31,44,.94),rgba(4,20,31,.96))}
  .pi851-card-title{display:flex;align-items:center;gap:.45rem}.pi851-card-title span{font-size:.68rem;font-weight:800;letter-spacing:.08em;color:#67e6ff}.pi851-card-title b{font-size:.82rem;color:#f1fbff}.pi851-card-title em{margin-left:auto;padding:.15rem .38rem;border-radius:999px;font-size:.62rem;font-style:normal;color:#b9ff67;background:rgba(163,255,74,.09);border:1px solid rgba(163,255,74,.16)}
  .pi851-card-strip.q-low .pi851-card-title em,.pi851-card-strip.q-n-d .pi851-card-title em{color:#ffb38f}
  .pi851-card-compare{display:grid;grid-template-columns:1fr auto 1fr;gap:.45rem;align-items:center;margin-top:.45rem}.pi851-card-compare span{font-size:.7rem;color:#91aebb}.pi851-card-compare span:last-child{text-align:right}.pi851-card-compare b{color:#dff8ff}.pi851-card-compare i{font-style:normal;font-size:.62rem;color:#607d89}.pi851-card-strip>small{display:block;margin-top:.35rem;color:#6f8d99;font-size:.64rem}
  .pi851-detail{margin:.8rem 1rem 1rem;padding:.9rem;border:1px solid rgba(68,216,248,.26);border-radius:18px;background:linear-gradient(180deg,rgba(3,27,40,.98),rgba(2,15,25,.98))}
  .pi851-detail-head{display:flex;justify-content:space-between;gap:.8rem;align-items:flex-start;padding-bottom:.7rem;border-bottom:1px solid rgba(91,196,220,.12)}.pi851-detail-head div{display:flex;flex-direction:column;gap:.15rem}.pi851-detail-head span{font-size:.7rem;font-weight:800;letter-spacing:.08em;color:#62e5ff}.pi851-detail-head b{font-size:1.05rem;color:#f2fbff}.pi851-detail-head small{color:#86a2af}.pi851-detail-head em{font-style:normal;white-space:nowrap;padding:.22rem .5rem;border-radius:999px;font-size:.65rem;color:#b9ff66;border:1px solid rgba(168,255,80,.20)}
  .pi851-verdict-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.45rem;margin:.7rem 0}.pi851-verdict-grid span{padding:.5rem;border-radius:10px;border:1px solid rgba(68,185,211,.12);background:rgba(3,18,27,.72)}.pi851-verdict-grid small{display:block;font-size:.6rem;color:#6f8996}.pi851-verdict-grid b{display:block;margin-top:.1rem;color:#e9fbff}
  .pi851-player-heads{display:grid;grid-template-columns:1fr 1fr;gap:.55rem}.pi851-player-meta{padding:.62rem;border-radius:12px;background:rgba(4,20,30,.72);border:1px solid rgba(66,198,227,.14)}.pi851-player-meta>div{display:flex;justify-content:space-between;gap:.4rem}.pi851-player-meta b{color:#eefbff}.pi851-player-meta em{font-style:normal;font-size:.62rem;color:#b8ff62}.pi851-player-meta span,.pi851-player-meta small{display:block;margin-top:.28rem;color:#829eaa;font-size:.66rem;line-height:1.35}
  .pi851-compare{margin-top:.65rem;border:1px solid rgba(67,194,221,.13);border-radius:12px;overflow:hidden}.pi851-compare-labels,.pi851-compare-row{display:grid;grid-template-columns:1.35fr .75fr auto .75fr;gap:.4rem;align-items:center;padding:.46rem .58rem}.pi851-compare-labels{grid-template-columns:1fr auto 1fr;background:rgba(60,185,212,.07);color:#dff9ff}.pi851-compare-labels b:last-child{text-align:right}.pi851-compare-labels span{text-align:center;color:#688491;font-size:.62rem}.pi851-compare-row:nth-child(odd){background:rgba(255,255,255,.012)}.pi851-compare-row>span{color:#78939f;font-size:.68rem}.pi851-compare-row>b{color:#dceff5;text-align:center}.pi851-compare-row>b.win{color:#baff61}.pi851-compare-row>i{font-style:normal;color:#56727e;font-size:.62rem}
  .pi851-reasons{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.65rem}.pi851-reasons span{padding:.3rem .48rem;border-radius:999px;background:rgba(66,202,232,.08);color:#a9d9e5;font-size:.66rem}.pi851-reasons b{color:#e7fbff}.pi851-note{margin:.65rem 0 0;color:#718a96;font-size:.66rem;line-height:1.45}
  .pi85-stats.pi851-enhanced>.pi85-tel-grid,.pi85-stats.pi851-enhanced>.pi85-surface-stats,.pi85-stats.pi851-enhanced>.pi85-note{display:none}.pi851-stats-extra{display:grid;gap:.75rem;margin-top:.8rem}.pi851-learning,.pi851-metrics,.pi851-surfaces{padding:.78rem;border:1px solid rgba(64,202,232,.16);border-radius:14px;background:rgba(3,19,29,.78)}
  .pi851-learning-title{display:flex;justify-content:space-between;gap:.6rem}.pi851-learning-title div{display:flex;flex-direction:column;gap:.1rem}.pi851-learning-title span{font-size:.67rem;color:#70e6ff}.pi851-learning-title b{color:#effbff}.pi851-learning-title em{font-style:normal;font-size:.62rem;color:#baff66}.pi851-learning-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.4rem;margin-top:.6rem}.pi851-learning-grid span{padding:.48rem;border-radius:9px;background:rgba(54,172,199,.06);text-align:center}.pi851-learning-grid small{display:block;color:#718b97;font-size:.58rem}.pi851-learning-grid b{display:block;margin-top:.12rem;color:#e6faff}
  .pi851-progress{height:5px;margin:.58rem 0;border-radius:999px;background:rgba(85,117,128,.18);overflow:hidden}.pi851-progress i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#49dfff,#b9ff61)}.pi851-learning p{margin:0;color:#849ca7;font-size:.67rem;line-height:1.45}.pi851-learning p b{color:#ffcf8c}
  .pi851-metrics header,.pi851-surfaces header{display:flex;justify-content:space-between;gap:.5rem;align-items:center;margin-bottom:.5rem}.pi851-metrics header b,.pi851-surfaces header b{color:#eafaff}.pi851-metrics header span,.pi851-surfaces header span{font-size:.61rem;color:#6f8996}.pi851-metrics-table{display:grid;gap:.32rem}.pi851-metrics-table>div{display:grid;grid-template-columns:1.3fr repeat(5,.72fr);gap:.32rem;align-items:center;padding:.42rem .48rem;border-radius:8px;background:rgba(50,163,188,.045)}.pi851-metrics-table b{color:#def8ff;font-size:.68rem}.pi851-metrics-table span{color:#8da7b2;font-size:.62rem;text-align:right}
  .pi851-surfaces>div{display:flex;flex-wrap:wrap;gap:.4rem}.pi851-surfaces>div>span{display:flex;gap:.35rem;align-items:center;padding:.38rem .5rem;border-radius:9px;background:rgba(52,171,198,.055)}.pi851-surfaces b{color:#dff7ff}.pi851-surfaces em{font-style:normal;color:#baff61}.pi851-surfaces small{color:#718b97}.pi851-surfaces p{margin:0;color:#758f9b;font-size:.67rem}
  .pi851-reasons-wrap{margin-top:.7rem;padding:.62rem;border:1px solid rgba(66,202,232,.12);border-radius:12px;background:rgba(54,172,199,.035)}.pi851-reasons-wrap>header{display:flex;justify-content:space-between;gap:.5rem;margin-bottom:.45rem}.pi851-reasons-wrap>header b{color:#e8fbff}.pi851-reasons-wrap>header small{color:#7895a1;font-size:.62rem}
  .pi851-confidence{display:grid;grid-template-columns:1fr 1fr;gap:.45rem;margin-top:.65rem}.pi851-confidence>div{padding:.55rem;border-radius:11px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.065)}.pi851-confidence b{display:block;color:#eafaff}.pi851-confidence span,.pi851-confidence small{display:block;margin-top:.2rem;color:#809aa6;font-size:.64rem;line-height:1.35}
  .pi851-tech-panel{margin-top:.75rem;padding:.65rem;border:1px solid rgba(85,185,255,.18);border-radius:13px;background:rgba(5,18,32,.84)}.pi851-tech-panel>summary{cursor:pointer;color:#9fdcff;font-size:.7rem;font-weight:800}.pi851-tech-note{margin:.5rem 0;color:#7f9aa8;font-size:.64rem;line-height:1.45}
  .pi851-tech-grid{display:grid;grid-template-columns:1fr 1fr;gap:.55rem}.pi851-tech-player{padding:.55rem;border-radius:10px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.055)}.pi851-tech-player>header{display:flex;justify-content:space-between;gap:.4rem;margin-bottom:.4rem}.pi851-tech-player>header b{color:#eefbff}.pi851-tech-player>header small{color:#7e98a4}.pi851-tech-metric{display:grid;grid-template-columns:1.1fr .75fr auto .75fr;gap:.35rem;align-items:center;padding:.36rem 0;border-top:1px solid rgba(255,255,255,.045)}.pi851-tech-metric:first-of-type{border-top:0}.pi851-tech-metric span{color:#7f98a3;font-size:.62rem}.pi851-tech-metric b{color:#def6ff;text-align:center;font-size:.68rem}.pi851-tech-metric i{font-style:normal;color:#5c7a87;font-size:.62rem}.pi851-tech-metric small{grid-column:1/-1;color:#6f8995;font-size:.58rem}
  .pi851-matchup-tech{display:grid;grid-template-columns:repeat(4,1fr);gap:.4rem;margin-top:.55rem}.pi851-matchup-tech span{padding:.45rem;border-radius:9px;background:rgba(76,163,255,.05);border:1px solid rgba(76,163,255,.11)}.pi851-matchup-tech small{display:block;color:#718d9b;font-size:.58rem}.pi851-matchup-tech b{display:block;margin-top:.1rem;color:#e7f7ff}
  @media(max-width:720px){.pi851-card-strip{margin:.5rem .55rem .15rem}.pi851-card-compare span{font-size:.64rem}.pi851-detail{margin:.65rem .55rem .9rem;padding:.72rem}.pi851-detail-head{flex-direction:column}.pi851-verdict-grid{grid-template-columns:1fr 1fr}.pi851-player-heads,.pi851-tech-grid{grid-template-columns:1fr}.pi851-confidence{grid-template-columns:1fr}.pi851-matchup-tech{grid-template-columns:1fr 1fr}.pi851-learning-grid{grid-template-columns:1fr 1fr}.pi851-metrics-table>div{grid-template-columns:1.2fr repeat(2,.7fr)}.pi851-metrics-table>div span:nth-of-type(n+3){display:none}}
  `;
  if(!document.querySelector('#pi851-style')){const st=document.createElement('style');st.id='pi851-style';st.textContent=STYLE;document.head.appendChild(st)}

  function profile(m,side){return m?.player_intelligence_v85?.profiles?.[side]||{}}
  function ix(p,k){return num(p?.indexes?.[k])}
  function sample(p,w){return Number(p?.windows?.[String(w)]?.sample_matches||0)}
  function pack(p,k,w='10'){return p?.windows?.[String(w)]?.metrics?.[k]||{}}
  function asPct(v){const x=num(v);return x==null?null:(Math.abs(x)<=1?x*100:x)}
  function metric(p,k,w='10'){return asPct(pack(p,k,w)?.adjusted)}
  function rawMetric(p,k,w='10'){return asPct(pack(p,k,w)?.raw)}
  function volatility(p,k,w='10'){return asPct(pack(p,k,w)?.volatility)}
  function metricN(p,k,w='10'){return Number(pack(p,k,w)?.n||0)}
  function trend(p,k){const v=num(p?.trend?.[k]);return v==null?null:v}
  function qualityText(q){
    const key=String(q||'N/D').toUpperCase();
    if(key==='HIGH')return 'wysoka';
    if(key==='MEDIUM')return 'średnia';
    if(key==='LOW')return 'niska';
    return 'brak oceny';
  }
  function coverageText(p){const x=num(p?.coverage);return x==null?'N/D':pct(Math.abs(x)<=1?x*100:x)}
  function matchFromEncoded(raw){let wanted=String(raw||'');try{wanted=decodeURIComponent(wanted)}catch{}return rows().find(m=>key(m)===wanted)||null}
  function verdict(m){const mu=m?.player_intelligence_v85?.matchup||{},edge=num(mu.edge_p1),q=mu.quality||'N/D';if(edge==null)return{lead:'Profil N/D',sub:'Za mało porównywalnych danych',q};if(Math.abs(edge)<2)return{lead:'Matchup równy',sub:`różnica ${signed(edge)}`,q};const name=edge>0?m.p1:m.p2;return{lead:`${name} ma przewagę`,sub:`profil ${signed(Math.abs(edge))}`,q}}

  function cardStrip(m){const pi=m?.player_intelligence_v85;if(!pi?.version)return'';const p1=profile(m,'p1'),p2=profile(m,'p2'),v=verdict(m);return `<section class="pi851-card-strip q-${qclass(v.q)}"><div class="pi851-card-title"><span>🧬 PLAYER</span><b>${esc(v.lead)}</b><em>${esc(v.q)}</em></div><div class="pi851-card-compare"><span>${esc(m.p1)} <b>S ${ix(p1,'serve')==null?'—':Math.round(ix(p1,'serve'))}</b> · R ${ix(p1,'return')==null?'—':Math.round(ix(p1,'return'))}</span><i>VS</i><span>${esc(m.p2)} <b>S ${ix(p2,'serve')==null?'—':Math.round(ix(p2,'serve'))}</b> · R ${ix(p2,'return')==null?'—':Math.round(ix(p2,'return'))}</span></div><small>${esc(v.sub)} · ${esc(String(pi.surface||m.surface||'').toUpperCase())} · L5/L10/L20</small></section>`}

  function trendText(p){const a=[['forma',trend(p,'won')],['hold',trend(p,'hold_rate')],['return',trend(p,'return_points_won')]].filter(([,v])=>v!=null);return a.length?`Trend L5 vs poprzednie 5: ${a.map(([k,v])=>`${k} ${v>0?'+':''}${v.toFixed(1)} pp`).join(' · ')}`:'Trend L5 vs poprzednie 5: N/D'}
  function row(label,a,b,pc=false){const f=x=>num(x)==null?'—':pc?pct(x):String(Math.round(x)),av=num(a),bv=num(b);return `<div class="pi851-compare-row"><span>${esc(label)}</span><b class="${av!=null&&bv!=null&&av>bv?'win':''}">${f(a)}</b><i>↔</i><b class="${av!=null&&bv!=null&&bv>av?'win':''}">${f(b)}</b></div>`}
  function playerMeta(name,p){const rank=p?.windows?.['10']?.latest_rank??p?.windows?.['5']?.latest_rank;return `<div class="pi851-player-meta"><div><b>${esc(name)}</b><em>${esc(qualityText(p?.quality))}</em></div><span>Ranking ${rank??'—'} · próbka L20: ${sample(p,20)}</span><span>L5/L10/L20: ${sample(p,5)}/${sample(p,10)}/${sample(p,20)} · pokrycie ${coverageText(p)}</span><small>${esc(trendText(p))}</small></div>`}

  function techMetric(label,p,key){
    const raw=rawMetric(p,key),adj=metric(p,key),vol=volatility(p,key),n=metricN(p,key);
    return `<div class="pi851-tech-metric"><span>${esc(label)}</span><b>${raw==null?'—':pct(raw)}</b><i>→</i><b>${adj==null?'—':pct(adj)}</b><small>RAW → korekta rywal/świeżość/shrinkage · n=${n} · zmienność ${vol==null?'—':pct(vol)}</small></div>`;
  }

  function techProfile(name,p){
    return `<section class="pi851-tech-player"><header><b>${esc(name)}</b><small>jakość ${esc(qualityText(p?.quality))} · coverage ${coverageText(p)}</small></header>${techMetric('Hold',p,'hold_rate')}${techMetric('Pkt return',p,'return_points_won')}${techMetric('Win rate',p,'won')}${techMetric('1. set',p,'first_set_won')}</section>`;
  }

  function matchupTech(mu,m){
    return `<div class="pi851-matchup-tech"><span><small>Profil łączny P1</small><b>${signed(mu?.edge_p1)}</b></span><span><small>Serwis P1 ↔ return P2</small><b>${signed(mu?.serve_edge_p1)}</b></span><span><small>Return P1 ↔ serwis P2</small><b>${signed(mu?.return_edge_p1)}</b></span><span><small>Forma P1 ↔ P2</small><b>${signed(mu?.form_edge_p1)}</b></span></div>`;
  }

  function confidenceBox(name,p){
    return `<div><b>${esc(name)}</b><span>Jakość danych: ${esc(qualityText(p?.quality))}</span><span>Próbka L20: ${sample(p,20)} · pokrycie: ${coverageText(p)}</span><small>Zmienność hold: ${volatility(p,'hold_rate')==null?'—':pct(volatility(p,'hold_rate'))} · return: ${volatility(p,'return_points_won')==null?'—':pct(volatility(p,'return_points_won'))}</small></div>`;
  }

  function details(m){
    const pi=m?.player_intelligence_v85||{},mu=pi.matchup||{},p1=profile(m,'p1'),p2=profile(m,'p2');
    if(!pi.version)return'';
    const v=verdict(m);
    const reasons=(mu.reasons||[]).slice(0,3).map(r=>{const e=num(r.edge_p1);if(e==null)return'';return `<span>${esc(r.factor||'czynnik')}: <b>${esc(e>0?m.p1:m.p2)}</b> ${signed(Math.abs(e))}</span>`}).join('');
    return `<section class="pi851-detail" data-pi851-detail>
      <header class="pi851-detail-head">
        <div>
          <span class="phase11-simple-only">🧬 Analiza zawodników</span>
          <span class="phase11-technical">🧬 PLAYER INTELLIGENCE v8.5</span>
          <b>${esc(v.lead)}</b>
          <small class="phase11-simple-only">Wniosek z profilu na tej nawierzchni; to nie jest kurs ani gwarancja wyniku.</small>
          <small class="phase11-technical">${esc(v.sub)} · SHADOW diagnostic only</small>
        </div>
        <em><span class="phase11-simple-only">TRYB TESTOWY</span><span class="phase11-technical">SHADOW</span> · ${esc(qualityText(v.q))}</em>
      </header>
      <div class="pi851-verdict-grid">
        <span><small>Nawierzchnia</small><b>${esc(String(pi.surface||m.surface||'—').toUpperCase())}</b></span>
        <span><small>Format</small><b>${mu.best_of?`BO${mu.best_of}`:'N/D'}</b></span>
        <span><small>Jakość danych</small><b>${esc(qualityText(v.q))}</b></span>
        <span class="phase11-technical"><small>Matchup edge P1</small><b>${signed(mu.edge_p1)}</b></span>
      </div>
      <div class="pi851-player-heads">${playerMeta(m.p1,p1)}${playerMeta(m.p2,p2)}</div>
      <div class="pi851-confidence">${confidenceBox(m.p1,p1)}${confidenceBox(m.p2,p2)}</div>
      <div class="pi851-compare">
        <div class="pi851-compare-labels"><b>${esc(m.p1)}</b><span>vs</span><b>${esc(m.p2)}</b></div>
        ${row('Siła profilu',ix(p1,'overall'),ix(p2,'overall'))}
        ${row('Serwis',ix(p1,'serve'),ix(p2,'serve'))}
        ${row('Return',ix(p1,'return'),ix(p2,'return'))}
        ${row('Forma',ix(p1,'form'),ix(p2,'form'))}
        ${row('Mental',ix(p1,'mental'),ix(p2,'mental'))}
        ${row('Hold',metric(p1,'hold_rate'),metric(p2,'hold_rate'),true)}
        ${row('Pkt return',metric(p1,'return_points_won'),metric(p2,'return_points_won'),true)}
        ${row('Wygrany 1. set',metric(p1,'first_set_won'),metric(p2,'first_set_won'),true)}
      </div>
      ${reasons?`<section class="pi851-reasons-wrap"><header><b>Dlaczego?</b><small>największe różnice w matchupie</small></header><div class="pi851-reasons">${reasons}</div></section>`:''}
      <details class="phase11-technical pi851-tech-panel">
        <summary>Dane techniczne · RAW → korekta profilu → matchup</summary>
        <p class="pi851-tech-note">Adjusted pochodzi z backendu: recency weighting + siła rywali + shrinkage do priory nawierzchni. Volatility, n i coverage są dowodem niepewności; UI nie tworzy własnego confidence score.</p>
        <div class="pi851-tech-grid">${techProfile(m.p1,p1)}${techProfile(m.p2,p2)}</div>
        ${matchupTech(mu,m)}
      </details>
      <p class="pi851-note phase11-simple-only">Profil bierze pod uwagę tę samą nawierzchnię, świeżość wyników i jakość rywali. Im mniejsza próbka lub większa zmienność, tym ostrożniej czytaj przewagę.</p>
      <p class="pi851-note phase11-technical">L5/L10/L20 · same-surface only · 12m primary / 24m fallback · indeksy 0–100 nie są P(win).</p>
    </section>`;
  }

  function decorateCards(){document.querySelectorAll('.p751-match-card').forEach(c=>{if(c.querySelector('.pi851-card-strip'))return;const m=matchFromEncoded(c.getAttribute('data-p751-open'));if(!m)return;const h=cardStrip(m),f=c.querySelector('footer');if(h)(f?f.insertAdjacentHTML('beforebegin',h):c.insertAdjacentHTML('beforeend',h))})}
  function injectDetail(m){const h=document.querySelector('.p751-detail-screen');if(!m||!h||h.querySelector('[data-pi851-detail]'))return;const x=details(m),head=h.querySelector('.dc87')||h.querySelector('.p751-matchup')||h.querySelector('.p751-detail-header');if(x)(head?head.insertAdjacentHTML('afterend',x):h.insertAdjacentHTML('afterbegin',x))}

  function telemetry(){if(telemetryPromise)return telemetryPromise;const api=window.TENIS_AI_AUTOLEARN_V84;telemetryPromise=api?.loadTelemetry?Promise.resolve(api.loadTelemetry()).catch(()=>null):Promise.resolve(null);return telemetryPromise}
  function activeProfiles(){const s=new Set();rows().forEach(m=>{const p=m?.player_intelligence_v85?.profiles||{};[p.p1,p.p2].forEach(x=>{if(x?.player_key||x?.player)s.add(String(x.player_key||x.player))})});return s.size}
  function val(x,k,f){const v=num(x?.[k]);return v==null?'—':f==='pct'?pct(v):f==='dec'?v.toFixed(3):String(Math.round(v))}
  async function enhanceStats(){const host=document.querySelector('#pi85-stats');if(!host||host.querySelector('.pi851-stats-extra'))return;const t=await telemetry(),pi=t?.player_intelligence_v85;if(!pi)return;host.classList.add('pi851-enhanced');const n=Number(pi.settled_rows||0),m=pi.models||{},progress=Math.min(100,n/5*100),models=[['Player',m.player],['Ensemble',m.ensemble],['Ensemble + Player',m.ensemble_player_shadow],['Generator proxy + Player',m.generator_player_shadow]].filter(([,x])=>x);host.insertAdjacentHTML('beforeend',`<div class="pi851-stats-extra"><section class="pi851-learning"><div class="pi851-learning-title"><div><span>🧬 Stan danych Player Intelligence</span><b>${n?`${n} meczów z wynikiem`:'Czeka na pierwsze rozliczenia'}</b></div><em><span class="phase11-simple-only">TRYB TESTOWY</span><span class="phase11-technical">SHADOW</span></em></div><div class="pi851-learning-grid"><span><small>Profile aktywne teraz</small><b>${activeProfiles()}</b></span><span><small>Mecze z wynikiem</small><b>${n}</b></span><span class="phase11-technical"><small>Próg śledzenia</small><b>65+</b></span><span class="phase11-technical"><small>Wykres trendu</small><b>od 5</b></span></div><div class="pi851-progress"><i style="width:${progress}%"></i></div><p class="phase11-simple-only">${n?'Model testowy zbiera wyniki i nie zmienia głównej rekomendacji.':'Nie ma jeszcze wystarczającej liczby rozliczonych meczów do oceny.'}</p><p class="phase11-technical">${n?'Liczymy wyłącznie prognozy zamrożone przed meczem.':'<b>0 nie oznacza 0% skuteczności.</b> Nie ma jeszcze rozliczonego sygnału v8.5.'}</p></section><section class="pi851-metrics phase11-technical"><header><b>Dokładne metryki</b><span>n · ≥65 · ACC · Brier · LogLoss</span></header><div class="pi851-metrics-table">${models.map(([name,x])=>`<div><b>${esc(name)}</b><span>n ${Number(x.n||0)}</span><span>≥65 ${Number(x.selected_n||0)}</span><span>ACC ${val(x,'accuracy','pct')}</span><span>B ${val(x,'brier','dec')}</span><span>LL ${val(x,'log_loss','dec')}</span></div>`).join('')}</div></section><section class="pi851-surfaces"><header><b>Nawierzchnie</b><span>Ensemble + Player</span></header><div>${Object.keys(pi.by_surface||{}).length?Object.entries(pi.by_surface).map(([s,x])=>{const z=x?.ensemble_player_shadow||{};return `<span><b>${esc(s.toUpperCase())}</b><em>${val(z,'accuracy','pct')}</em><small>n=${Number(z.selected_n||0)} · B ${val(z,'brier','dec')}</small></span>`}).join(''):'<p>Pojawią się po pierwszych rozliczeniach.</p>'}</div></section></div>`)}

  function scheduleStats(){requestAnimationFrame(()=>requestAnimationFrame(()=>enhanceStats()));setTimeout(enhanceStats,180);setTimeout(enhanceStats,650)}
  try{if(typeof renderMatches==='function'&&!renderMatches.__pi851){const b=renderMatches;renderMatches=function(){const v=b.apply(this,arguments);decorateCards();return v};renderMatches.__pi851=true}if(typeof renderStats==='function'&&!renderStats.__pi851){const b=renderStats;renderStats=function(){const v=b.apply(this,arguments);scheduleStats();return v};renderStats.__pi851=true}}catch{}
  document.addEventListener('click',e=>{if(e.target.closest('.v762-player-link'))return;const o=e.target.closest('[data-p751-open]');if(o){const m=matchFromEncoded(o.getAttribute('data-p751-open'));injectDetail(m)}if(e.target.closest('[data-view="stats"]'))scheduleStats()});
  decorateCards();if(document.querySelector('#pi85-stats'))scheduleStats();
  window.TENIS_AI_PLAYER_UI_V851=Object.freeze({version:VERSION,decorateCards,injectDetail,enhanceStats});
})();
