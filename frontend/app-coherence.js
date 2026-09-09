/* Tenis AI v8.9.2 — Full App Coherence
   Read-only UI bridge for the newest SHADOW learning layers.
   v8.9.3 adds Surface Elo experiment visibility without production influence.
   Never changes model scores, Generator selection, Adaptive PROD or final_score.
*/
(() => {
  'use strict';
  if (window.TENIS_AI_COHERENCE_V892) return;

  const VERSION='v8.9.2';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>x==null||String(x).trim()===''||!Number.isFinite(Number(x))?null:Number(x);
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const brier=x=>num(x)==null?'—':Number(x).toFixed(5);

  function patchReleaseLabel(){
    window.TENIS_AI_APPLY_META?.();
    const release=window.TENIS_AI_META?.releaseVersion||VERSION;
    const foot=[...document.querySelectorAll('footer > div')].find(x=>/^v\d/i.test(String(x.textContent||'').trim()));
    if(foot)foot.textContent=`${release} · Player Intelligence i Player Learning działają w SHADOW. Modele nie gwarantują wygranej ani zysku.`;
  }

  function metricBlock(label,m){
    return `<div class="coh892-metric"><small>${esc(label)}</small><b>${pct(m?.accuracy)}</b><span>n=${Number(m?.n||0)} · wybrane ${Number(m?.selected_n||0)}</span><span>Brier ${brier(m?.brier)}</span></div>`;
  }

  function gateClass(status){
    const x=String(status||'collecting').toLowerCase();
    if(x==='promising'||x==='strong_candidate')return 'good';
    if(x==='watch')return 'watch';
    return 'collecting';
  }

  function experimentCard(kind,report){
    if(!report||typeof report!=='object')return '';
    const gate=report.gate||{};
    const isLearning=kind==='learning';
    const metric=isLearning
      ? report?.holdout?.ensemble_player_learning
      : report?.holdout?.player_catboost_shadow;
    const title=isLearning?'Ensemble + Player Learning':'CatBoost + Player Intelligence';
    const version=report.version|| (isLearning?'v8.9.1':'v8.9');
    const icon=isLearning?'🧠🧬':'🐱🧬';
    const detail=isLearning
      ? `Uczy udziału Player Intelligence zależnie od rynku, nawierzchni i jakości profilu.`
      : `Sprawdza, czy pełny zestaw cech Player Intelligence poprawia CatBoost.`;
    const alpha=isLearning?num(report?.holdout?.alpha_summary?.avg):null;
    return `<article class="coh892-card">
      <header><div><span>${icon}</span><div><b>${esc(title)}</b><small>${esc(version)} · SHADOW</small></div></div><em class="${gateClass(gate.status)}">${esc(String(gate.status||'collecting').toUpperCase())}</em></header>
      ${metricBlock('Holdout',metric)}
      <p>${esc(detail)}</p>
      ${alpha!=null?`<div class="coh892-alpha"><span>Średni udział Playera</span><b>${Math.round(alpha*100)}%</b></div>`:''}
      <footer><span>Rozliczone: ${Number(report?.training?.rows_total||0)}</span><span>Mecze: ${Number(report?.training?.matches_total||0)}</span><strong>🚫 bez wpływu na PROD</strong></footer>
    </article>`;
  }

  function eloCard(kind,report){
    if(!report||typeof report!=='object')return '';
    const cfg={
      catboost:{title:'CatBoost + Player + Surface Elo',icon:'🐱🧬🎾',base:'catboost_player',elo:'catboost_player_elo',gate:'catboost_player_elo',detail:'Elo ogólne i na bieżącej nawierzchni wchodzą jako dodatkowe cechy modelu.'},
      ensemble:{title:'Ensemble + Player + Surface Elo',icon:'🧠🧬🎾',base:'ensemble_player',elo:'ensemble_player_elo',gate:'ensemble_player_elo',detail:'Elo jest dokładane do uczącego połączenia Ensemble + Player tylko tam, gdzie ma sens.'},
      tabpfn:{title:'TabPFN + Surface Elo',icon:'🧬🎾',base:'tabpfn',elo:'tabpfn_elo',gate:'tabpfn_elo',detail:'Sprawdzamy, czy niezależny sygnał Elo poprawia challenger TabPFN.'},
    }[kind];
    if(!cfg)return '';
    const base=report?.holdout?.[cfg.base]||{};
    const metric=report?.holdout?.[cfg.elo]||{};
    const gate=report?.gates?.[cfg.gate]||{};
    const alpha=kind==='ensemble'?num(report?.learned?.ensemble_elo_alpha):(kind==='tabpfn'?num(report?.learned?.tabpfn_elo_alpha):null);
    const covered=Number(report?.elo?.rows_with_both_surface_history||0);
    const total=Number(report?.training?.rows_total||0);
    const accDelta=(num(metric?.accuracy)!=null&&num(base?.accuracy)!=null)?num(metric.accuracy)-num(base.accuracy):null;
    const brierDelta=(num(metric?.brier)!=null&&num(base?.brier)!=null)?num(base.brier)-num(metric.brier):null;
    const deltaText=accDelta==null?'—':`${accDelta>=0?'+':''}${accDelta.toFixed(1)} pp`;
    const brierText=brierDelta==null?'—':`${brierDelta>=0?'+':''}${brierDelta.toFixed(5)}`;
    return `<article class="coh892-card coh892-elo-card">
      <header><div><span>${cfg.icon}</span><div><b>${esc(cfg.title)}</b><small>v8.9.3 · SHADOW</small></div></div><em class="${gateClass(gate.status)}">${esc(String(gate.status||'collecting').toUpperCase())}</em></header>
      ${metricBlock('Z Surface Elo',metric)}
      <div class="coh892-compare"><span>Baza <b>${pct(base?.accuracy)}</b></span><span>Zmiana <b>${esc(deltaText)}</b></span><span>Δ Brier <b>${esc(brierText)}</b></span></div>
      <p>${esc(cfg.detail)}</p>
      ${alpha!=null?`<div class="coh892-alpha"><span>Nauczony maks. udział Elo</span><b>${Math.round(alpha*100)}%</b></div>`:''}
      <footer><span>Elo nawierzchni: ${covered}/${total}</span><span>Mecze historyczne Elo: ${Number(report?.elo?.events||0)}</span><strong>🚫 bez wpływu na PROD</strong></footer>
    </article>`;
  }

  async function loadTelemetry(){
    try{
      const api=window.TENIS_AI_AUTOLEARN_V84;
      if(api?.loadTelemetry)return await api.loadTelemetry(false);
      const r=await fetch('data/model_telemetry_v84c.json',{cache:'no-store'});
      return r.ok?await r.json():{};
    }catch{return {}}
  }

  async function renderShadowExperiments(){
    const host=document.querySelector('#pc77');
    if(!host)return false;
    const telemetry=await loadTelemetry();
    if(document.querySelector('#pc77')!==host)return false;
    const player=telemetry?.player_model_shadow_v89||null;
    const learning=telemetry?.ensemble_player_learning_v891||null;
    const elo=telemetry?.surface_elo_integration_v893||null;
    if(!player&&!learning&&!elo)return false;
    const existing=host.querySelector('#coh892-shadow');
    const section=existing||document.createElement('section');
    section.id='coh892-shadow';
    section.className='coh892-shadow';
    const eloCards=elo?`${eloCard('catboost',elo)}${eloCard('ensemble',elo)}${eloCard('tabpfn',elo)}`:'';
    const html=`<div class="coh892-head"><div><b>🧪 EKSPERYMENTY PLAYER + SURFACE ELO · SHADOW</b><small>Nowe warstwy uczące są porównywane na holdoucie. Nie mieszamy ich z rankingiem modeli produkcyjnych.</small></div><span>0% wpływu na PROD</span></div><div class="coh892-grid">${experimentCard('player',player)}${experimentCard('learning',learning)}${eloCards}</div>`;
    if(section.__coherenceHtml!==html){
      section.innerHTML=html;
      section.__coherenceHtml=html;
    }
    const anchor=host.querySelector('#pc882-dashboard');
    if(anchor?.parentNode===host){
      if(anchor.nextElementSibling!==section)anchor.insertAdjacentElement('afterend',section);
    }else if(!existing){
      host.append(section);
    }
    document.dispatchEvent(new CustomEvent('tenis-ai:shadow-experiments-ready'));
    return true;
  }

  let timer=null;
  function schedule(ms=180){
    clearTimeout(timer);
    timer=setTimeout(()=>{renderShadowExperiments();},ms);
  }

  patchReleaseLabel();
  document.addEventListener('tenis-ai:stats-dashboard-ready',()=>schedule(60));
  document.addEventListener('tenis-ai:stats-ready',()=>schedule(80));
  document.addEventListener('click',e=>{
    if(e.target?.closest?.('[data-view="stats"]')){
      schedule(180);
      setTimeout(()=>renderShadowExperiments(),650);
    }
    if(e.target?.closest?.('#refresh')){
      setTimeout(()=>renderShadowExperiments(),1700);
    }
  },true);

  window.TENIS_AI_COHERENCE_V892=Object.freeze({
    version:VERSION,
    surfaceEloVersion:'v8.9.3',
    productionInfluence:false,
    patchReleaseLabel,
    renderShadowExperiments
  });
})();
