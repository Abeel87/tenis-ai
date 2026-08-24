/* Tenis AI v8.5 — Player Intelligence UI
   Cache-first backend data only. No extra fetch, no MutationObserver, no interval.
*/
(() => {
  'use strict';
  const VERSION='v8.5';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>Number.isFinite(Number(x))?Number(x):null;
  const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  const signed=x=>num(x)==null?'—':`${Number(x)>0?'+':''}${Number(x).toFixed(1)}`;
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const qualityClass=q=>String(q||'N/D').toLowerCase().replace('/','-');
  const rows=()=>{try{return typeof all!=='undefined'&&Array.isArray(all)?all:[]}catch{return []}};
  const mkey=m=>String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|'));

  function signalKey(s){return String(s?.key||s?.signal_key||`${s?.market||''}|${s?.pick||''}`)}
  function supportFor(m,s){
    const by=m?.autolearn_v84?.by_key||{};
    const row=by[signalKey(s)]||{};
    const pi=row?.player_intelligence_v85||null;
    return pi&&num(pi.probability)!=null?pi:null;
  }
  function matchForNames(text){
    const t=norm(text);
    return rows().find(m=>t.includes(norm(m?.p1))&&t.includes(norm(m?.p2)))||null;
  }
  function metric(profile,key,w='10'){
    const x=profile?.windows?.[String(w)]?.metrics?.[key]||{};
    const v=num(x.adjusted);return v==null?null:(v<=1?v*100:v);
  }
  function index(profile,key){return num(profile?.indexes?.[key])}
  function sample(profile,w){return Number(profile?.windows?.[String(w)]?.sample_matches||0)}

  function compact(m){
    const pi=m?.player_intelligence_v85||{},mu=pi.matchup||{};
    if(!pi.version)return '';
    const q=mu.quality||'N/D',edge=num(mu.edge_p1);
    const lead=edge==null?'profil N/D':Math.abs(edge)<2?'matchup równy':`${edge>0?esc(m.p1):esc(m.p2)} ${signed(Math.abs(edge))}`;
    return `<div class="pi85-compact q-${qualityClass(q)}"><span>🧬 Player Intelligence</span><b>${lead}</b><em>${esc(q)}</em></div>`;
  }

  function profileCol(name,p){
    const ix=p?.indexes||{};
    return `<article class="pi85-player"><header><b>${esc(name)}</b><em>${esc(p?.quality||'N/D')}</em></header>
      <div class="pi85-kpis">
        <span><small>Serwis</small><b>${index(p,'serve')==null?'—':Math.round(index(p,'serve'))}</b></span>
        <span><small>Return</small><b>${index(p,'return')==null?'—':Math.round(index(p,'return'))}</b></span>
        <span><small>Forma</small><b>${index(p,'form')==null?'—':Math.round(index(p,'form'))}</b></span>
        <span><small>Mental</small><b>${index(p,'mental')==null?'—':Math.round(index(p,'mental'))}</b></span>
      </div>
      <div class="pi85-window-row"><span>L5 <b>${sample(p,5)}</b></span><span>L10 <b>${sample(p,10)}</b></span><span>L20 <b>${sample(p,20)}</b></span></div>
      <small class="pi85-sub">Hold ${pct(metric(p,'hold_rate'))} · Return ${pct(metric(p,'return_points_won'))} · 1S ${pct(metric(p,'first_set_won'))}</small>
      <small class="pi85-sub">BO5 obserw. ${Number(p?.windows?.['20']?.bo5_observed||0)} · S4 ${pct((p?.windows?.['20']?.set4_win||{}).adjusted<=1?(p?.windows?.['20']?.set4_win||{}).adjusted*100:(p?.windows?.['20']?.set4_win||{}).adjusted)} · S5 ${pct((p?.windows?.['20']?.set5_win||{}).adjusted<=1?(p?.windows?.['20']?.set5_win||{}).adjusted*100:(p?.windows?.['20']?.set5_win||{}).adjusted)}</small>
    </article>`;
  }

  function details(m){
    const pi=m?.player_intelligence_v85||{},pr=pi.profiles||{},mu=pi.matchup||{};
    if(!pi.version)return '';
    const reasons=(mu.reasons||[]).map(r=>`<span>${esc(r.factor)}: ${Number(r.edge_p1)>0?esc(m.p1):esc(m.p2)} ${Math.abs(Number(r.edge_p1||0)).toFixed(1)}</span>`).join('');
    return `<section class="pi85-match-block">
      <header class="pi85-head"><div><b>🧬 Player Intelligence v8.5</b><small>${esc(String(pi.surface||m.surface||'').toUpperCase())} · L5/L10/L20 · dane przedmeczowe</small></div><em>SHADOW</em></header>
      <div class="pi85-matchup"><span>Jakość profilu <b>${esc(mu.quality||'N/D')}</b></span><span>Matchup P1 <b>${signed(mu.edge_p1)}</b></span><span>Format <b>${mu.best_of?`BO${mu.best_of}`:'N/D'}</b></span></div>
      <div class="pi85-players">${profileCol(m.p1,pr.p1)}${profileCol(m.p2,pr.p2)}</div>
      ${reasons?`<div class="pi85-reasons">${reasons}</div>`:''}
      <p class="pi85-note">Profile są liczone wyłącznie z tej samej nawierzchni. Zakres główny 12 miesięcy; do 24 miesięcy tylko fallback przy małej próbce. Player nie wykonuje własnych requestów API.</p>
    </section>`;
  }

  function decorateMatches(){
    document.querySelectorAll('.match-card').forEach(card=>{
      if(card.dataset.pi85==='1')return;
      const m=matchForNames(card.querySelector('.match-players')?.textContent||'');if(!m)return;
      const c=compact(m),d=details(m);if(!c&&!d)return;
      const main=card.querySelector('.match-main');if(c&&main)main.insertAdjacentHTML('beforeend',c);
      const detail=card.querySelector('.match-detail');if(d&&detail)detail.insertAdjacentHTML('afterbegin',d);
      card.dataset.pi85='1';
    });
  }

  function profileForName(name){
    const m=rows().find(x=>norm(x?.p1)===norm(name)||norm(x?.p2)===norm(name));
    if(!m)return null;
    const side=norm(m.p1)===norm(name)?'p1':'p2';
    return {match:m,side,profile:m?.player_intelligence_v85?.profiles?.[side]||null};
  }
  function injectPlayerPanel(name){
    const host=document.querySelector('#player-analytics-v76');if(!host||host.querySelector('.pi85-profile-addon'))return;
    const x=profileForName(name);if(!x?.profile)return;
    const p=x.profile;
    const html=`<details class="pa76-details pi85-profile-addon"><summary>🧬 Player Intelligence v8.5 · profil skorygowany <i>⌄</i></summary>
      <div class="pi85-profile-grid">
        <span><small>Jakość</small><b>${esc(p.quality||'N/D')}</b></span>
        <span><small>Serwis adj.</small><b>${index(p,'serve')==null?'—':Math.round(index(p,'serve'))}</b></span>
        <span><small>Return adj.</small><b>${index(p,'return')==null?'—':Math.round(index(p,'return'))}</b></span>
        <span><small>Forma adj.</small><b>${index(p,'form')==null?'—':Math.round(index(p,'form'))}</b></span>
        <span><small>L5/L10/L20</small><b>${sample(p,5)}/${sample(p,10)}/${sample(p,20)}</b></span>
        <span><small>Fallback 24m</small><b>${p.fallback_used?'TAK':'NIE'}</b></span>
      </div>
      <p class="pi85-note">Adjusted = świeżość + jakość rywali + shrinkage do średniej nawierzchni. Nie jest to prawdopodobieństwo wygranej.</p>
    </details>`;
    host.querySelector('#pa76-content')?.insertAdjacentHTML('beforeend',html);
  }

  function spark(series,cls){
    const vals=(Array.isArray(series)?series:[]).map(x=>num(x?.accuracy)).filter(x=>x!=null);
    if(vals.length<2)return '<div class="pi85-spark-empty">wykres po kolejnych rozliczeniach</div>';
    const W=260,H=60,P=5,lo=Math.max(0,Math.min(...vals)-5),hi=Math.min(100,Math.max(...vals)+5),den=Math.max(8,hi-lo);
    const pts=vals.map((v,i)=>`${(P+i*(W-2*P)/Math.max(1,vals.length-1)).toFixed(1)},${(H-P-(v-lo)/den*(H-2*P)).toFixed(1)}`).join(' ');
    return `<svg class="pi85-spark ${cls}" viewBox="0 0 ${W} ${H}"><polyline points="${pts}"/></svg>`;
  }
  function telCard(label,x,icon){
    return `<article class="pi85-tel-card"><header><span>${icon}</span><b>${esc(label)}</b></header>${spark(x?.series,label.toLowerCase().replace(/\W+/g,'-'))}
      <div><span><small>Accuracy ≥65</small><b>${pct(x?.accuracy)}</b></span><span><small>Brier</small><b>${num(x?.brier)==null?'—':Number(x.brier).toFixed(3)}</b></span><span><small>n</small><b>${Number(x?.selected_n||0)}</b></span></div></article>`;
  }
  async function injectStats(){
    const app=document.querySelector('#app');if(!app||document.querySelector('#pi85-stats'))return;
    const api=window.TENIS_AI_AUTOLEARN_V84;if(!api?.loadTelemetry)return;
    const tel=await api.loadTelemetry();const pi=tel?.player_intelligence_v85;if(!pi||document.querySelector('#pi85-stats'))return;
    const m=pi.models||{};
    const html=`<section id="pi85-stats" class="pi85-stats"><header class="pi85-head"><div><b>🧬 Player Intelligence v8.5</b><small>Player vs Ensemble vs Ensemble+Player</small></div><em>SHADOW</em></header>
      <div class="pi85-tel-grid">${telCard('Player',m.player,'🧬')}${telCard('Ensemble',m.ensemble,'🔗')}${telCard('Ensemble + Player',m.ensemble_player_shadow,'⚡')}</div>
      <div class="pi85-surface-stats">${Object.entries(pi.by_surface||{}).map(([s,v])=>`<span><b>${esc(s.toUpperCase())}</b> ${pct(v?.ensemble_player_shadow?.accuracy)} · n=${Number(v?.ensemble_player_shadow?.selected_n||0)}</span>`).join('')}</div>
      <p class="pi85-note">Monitoring, nie autopilot: Player nie zmienia wag produkcyjnych. Generator może dostać wyłącznie mały, ograniczony bonus/karę jakościową.</p></section>`;
    app.insertAdjacentHTML('afterbegin',html);
  }

  function wrapRenderers(){
    try{
      if(typeof renderMatches==='function'&&!renderMatches.__pi85){const base=renderMatches;renderMatches=function(){const v=base.apply(this,arguments);decorateMatches();return v};renderMatches.__pi85=true}
      if(typeof renderStats==='function'&&!renderStats.__pi85){const base=renderStats;renderStats=function(){const v=base.apply(this,arguments);injectStats();return v};renderStats.__pi85=true}
    }catch{}
    const pa=window.TENIS_AI_PLAYER_ANALYTICS_V801;
    if(pa?.mount&&!pa.mount.__pi85){const base=pa.mount;const f=function(name){const v=base.apply(this,arguments);injectPlayerPanel(name);return v};f.__pi85=true;pa.mount=f}
  }

  wrapRenderers();
  if(document.querySelector('.match-card'))decorateMatches();
  if(document.querySelector('#app')&&document.querySelector('.stats-hero'))injectStats();
  window.TENIS_AI_PLAYER_V85=Object.freeze({version:VERSION,supportFor,decorateMatches,injectStats});
})();
