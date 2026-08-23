/* Tenis AI v8.4A — AutoLearn bridge + model comparison UI */
(() => {
  'use strict';
  const VERSION='v8.4A';
  const REPORT='data/autolearn_v84.json';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const num=x=>Number.isFinite(Number(x))?Number(x):null;
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const brier=x=>num(x)==null?'—':Number(x).toFixed(3);
  const norm=s=>String(s??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'');
  let reportPromise=null;

  function lineOf(s){
    const direct=num(s?.line??s?.selected_line??s?.suggested_line);if(direct!=null)return direct;
    const p=String(s?.key||s?.signal_key||'').split('|');
    return p.length>1?num(p[1]):null;
  }
  function marketAlias(m){
    return ({match_win:'match_winner',set1_win:'set1_winner',set2_win:'set2_winner',set3_win:'set3_winner'})[String(m||'').toLowerCase()]||String(m||'').toLowerCase();
  }
  function scoreFor(match,signal){
    const a=match?.autolearn_v84;if(!a)return null;
    const key=String(signal?.key||signal?.signal_key||'');
    const direct=a?.by_key?.[key];
    if(direct)return {...direct,status:a.status,weights:a.weights};
    const market=marketAlias(signal?.market),pick=norm(signal?.pick),line=lineOf(signal);
    const row=(a?.signals||[]).find(x=>{
      if(marketAlias(x?.market)!==market||norm(x?.pick)!==pick)return false;
      const xl=lineOf(x);
      return line==null?xl==null:xl!=null&&Math.abs(xl-line)<0.001;
    });
    return row?{...row,status:a.status,weights:a.weights}:null;
  }

  async function loadReport(force=false){
    if(force)reportPromise=null;
    if(!reportPromise)reportPromise=fetch(`${REPORT}?v=84a1&ts=${Date.now()}`,{cache:'no-store'})
      .then(r=>r.ok?r.json():{}).catch(()=>({}));
    return reportPromise;
  }
  function metric(report,id){
    const track=report?.tracking?.[id]||{};
    const val=report?.validation?.[id]||{};
    const useTrack=Number(track?.selected_n||0)>=5;
    return {data:useTrack?track:val,scope:useTrack?'TRACKING':'WALK-FORWARD'};
  }
  function card(report,id,label,icon,status){
    const {data,scope}=metric(report,id);
    const st=String(status||'N/D').toUpperCase();
    return `<article class="al84-card">
      <header><span>${icon}</span><div><b>${esc(label)}</b><small>${esc(scope)}</small></div><em class="${st==='ACTIVE'||st==='OK'?'ok':st==='UNAVAILABLE'?'off':'shadow'}">${esc(st)}</em></header>
      <strong>${pct(data?.accuracy)}</strong>
      <div class="al84-meta"><span>wybrane n=${Number(data?.selected_n||0)}</span><span>Brier ${brier(data?.brier)}</span><span>log-loss ${num(data?.log_loss)==null?'—':Number(data.log_loss).toFixed(3)}</span></div>
    </article>`;
  }
  function html(report){
    const models=report?.models||{},w=report?.weights||{},tr=report?.training||{},gen=report?.generator||{};
    const tab=models.tabpfn||{};
    return `<section id="al84-performance" class="al84-performance">
      <div class="al84-head"><div><span>🤖 AUTOLEARN v8.4A</span><h3>Porównanie modeli AI</h3><p>Te same rozliczone sygnały, osobno mierzona jakość i finalny selector generatora.</p></div><b>${esc(report?.status||'COLLECTING')}</b></div>
      <div class="al84-grid">
        ${card(report,'current','Current Engine','🧠',models.current?.status||'active')}
        ${card(report,'catboost','CatBoost','🐱',models.catboost?.status||'collecting')}
        ${card(report,'tabpfn','TabPFN-2','🧬',tab.status||'unavailable')}
        ${card(report,'generator','Ensemble Generator','⚡',models.ensemble?.status||'fallback')}
      </div>
      <div class="al84-weights"><b>Wagi Ensemble</b><span>Engine ${Math.round(Number(w.current||0)*100)}%</span><span>CatBoost ${Math.round(Number(w.catboost||0)*100)}%</span><span>TabPFN ${Math.round(Number(w.tabpfn||0)*100)}%</span></div>
      <div class="al84-foot"><span>Trening: ${Number(tr.rows||0)} sygnałów · ${Number(tr.matches||0)} meczów</span><span>Generator próg: ${pct(gen.selection_threshold)}</span>${tab.reason?`<span>TabPFN: ${esc(tab.reason)}</span>`:''}</div>
      <p class="al84-note">Accuracy dotyczy wyborów modelu na rozliczonej próbce, nie jest gwarancją przyszłego wyniku. Brier: niżej = lepiej.</p>
    </section>`;
  }
  async function injectPerformance(){
    const host=document.querySelector('#pc77');if(!host)return;
    const report=await loadReport(true);if(!document.querySelector('#pc77'))return;
    document.querySelector('#al84-performance')?.remove();
    host.insertAdjacentHTML('afterbegin',html(report));
  }
  function scheduleInject(){[0,120,450,1000].forEach(ms=>setTimeout(injectPerformance,ms))}

  if(typeof renderStats==='function'){
    const base=renderStats;
    renderStats=function(){const r=base.apply(this,arguments);scheduleInject();return r};
  }

  window.TENIS_AI_AUTOLEARN_V84={version:VERSION,scoreFor,loadReport,injectPerformance};
})();
