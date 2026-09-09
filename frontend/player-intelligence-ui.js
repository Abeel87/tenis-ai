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
