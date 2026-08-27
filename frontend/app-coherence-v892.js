/* Tenis AI v8.9.2 — Full App Coherence
   Read-only UI bridge for the newest SHADOW learning layers.
   It also keeps the visible release label consistent with central metadata.
   Never changes model scores, Generator selection, Adaptive PROD or final_score.
*/
(() => {
  'use strict';
  if (window.TENIS_AI_COHERENCE_V892) return;

  const VERSION='v8.9.2';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>Number.isFinite(Number(x))?Number(x):null;
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const brier=x=>num(x)==null?'—':Number(x).toFixed(5);

  function patchReleaseLabel(){
    document.documentElement.dataset.tenisAiVersion=VERSION;
    document.title=`Tenis AI · ${VERSION}`;
    const brand=document.querySelector('.brand-copy p');
    if(brand)brand.textContent=`Tenis AI ${VERSION} · Adaptive PROD + Player Learning SHADOW`;
    const foot=[...document.querySelectorAll('footer > div')].find(x=>/^v\d/i.test(String(x.textContent||'').trim()));
    if(foot)foot.textContent=`${VERSION} Full App Coherence · Quality Lock · Player Intelligence i Player Learning działają w SHADOW. Modele nie gwarantują wygranej ani zysku.`;
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

  function ensureStyle(){
    if(document.getElementById('coh892-style'))return;
    const style=document.createElement('style');
    style.id='coh892-style';
    style.textContent=`
      .coh892-shadow{margin:12px 0;padding:12px;border:1px solid rgba(123,229,255,.16);border-radius:16px;background:rgba(6,18,31,.78)}
      .coh892-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:10px}.coh892-head b{display:block;font-size:.82rem}.coh892-head small{display:block;color:#8ea7b2;font-size:.66rem;margin-top:3px}.coh892-head>span{font-size:.62rem;padding:5px 8px;border-radius:999px;border:1px solid rgba(123,229,255,.2);color:#8be8ff;white-space:nowrap}
      .coh892-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.coh892-card{border:1px solid rgba(255,255,255,.08);border-radius:13px;padding:10px;background:rgba(255,255,255,.025)}
      .coh892-card header{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.coh892-card header>div{display:flex;gap:7px;align-items:flex-start}.coh892-card header b{display:block;font-size:.75rem}.coh892-card header small{display:block;color:#8ca4af;font-size:.61rem;margin-top:2px}.coh892-card header em{font-style:normal;font-size:.58rem;padding:4px 6px;border-radius:999px}.coh892-card header em.good{color:#baff76;background:rgba(153,255,83,.08);border:1px solid rgba(153,255,83,.18)}.coh892-card header em.watch{color:#ffd28f;background:rgba(255,184,76,.08);border:1px solid rgba(255,184,76,.18)}.coh892-card header em.collecting{color:#a9bec8;background:rgba(169,190,200,.07);border:1px solid rgba(169,190,200,.16)}
      .coh892-metric{display:grid;grid-template-columns:auto 1fr;gap:2px 8px;margin:10px 0 7px}.coh892-metric small{color:#8ca4af;font-size:.6rem}.coh892-metric b{font-size:1.05rem;grid-row:1/3;grid-column:2;text-align:right}.coh892-metric span{font-size:.59rem;color:#9fb2bb}.coh892-card p{font-size:.64rem;line-height:1.45;color:#a9bbc3;margin:6px 0}.coh892-alpha{display:flex;justify-content:space-between;font-size:.62rem;padding-top:6px;border-top:1px dashed rgba(255,255,255,.08)}.coh892-card footer{display:flex;flex-wrap:wrap;gap:5px 9px;margin-top:8px;font-size:.57rem;color:#899fa9}.coh892-card footer strong{color:#ffca87;font-weight:600}
      @media(max-width:720px){.coh892-grid{grid-template-columns:1fr}.coh892-head{align-items:center}}
    `;
    document.head.appendChild(style);
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
    if(!document.querySelector('#pc77'))return false;
    const player=telemetry?.player_model_shadow_v89||null;
    const learning=telemetry?.ensemble_player_learning_v891||null;
    if(!player&&!learning)return false;
    ensureStyle();
    document.querySelector('#coh892-shadow')?.remove();
    const section=document.createElement('section');
    section.id='coh892-shadow';
    section.className='coh892-shadow';
    section.innerHTML=`<div class="coh892-head"><div><b>🧪 EKSPERYMENTY PLAYER · SHADOW</b><small>Tu widać nowe warstwy uczące. Nie mieszamy ich z rankingiem modeli produkcyjnych.</small></div><span>0% wpływu na PROD</span></div><div class="coh892-grid">${experimentCard('player',player)}${experimentCard('learning',learning)}</div>`;
    const anchor=document.querySelector('#al84-performance');
    if(anchor?.parentNode===host)anchor.insertAdjacentElement('afterend',section);
    else host.insertAdjacentElement('afterbegin',section);
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
    productionInfluence:false,
    patchReleaseLabel,
    renderShadowExperiments
  });
})();
