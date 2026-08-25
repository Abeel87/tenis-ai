/* Tenis AI v8.4E2 — Model Trend Monitor
   Read-only monitoring. Reuses existing telemetry promise: no extra fetch,
   no MutationObserver, no interval, and it never changes production weights.
*/
(() => {
  'use strict';
  const VERSION='v8.4E2';
  const CUTOVER_V852='2026-08-25T09:55:27Z';
  const PRIMARY=['current','catboost','tabpfn','ensemble','generator'];
  const SECONDARY=['adaptive','early','serve','form','surface','consensus','dynamic'];
  const LABELS={adaptive:'Adaptive',early:'Early Hold',serve:'Serve/Return',form:'Form',surface:'Surface',consensus:'Consensus',current:'Current Engine',catboost:'CatBoost',tabpfn:'TabPFN-2',ensemble:'Ensemble',dynamic:'Dynamic Ensemble',generator:'Ensemble selector proxy'};
  const ICONS={adaptive:'🧠',early:'🎯',serve:'🎾',form:'🔥',surface:'🏟️',consensus:'⚡',current:'🧠',catboost:'🐱',tabpfn:'🧬',ensemble:'🔗',dynamic:'🧭',generator:'🚀'};
  const STATUS={rising:['↗','ROŚNIE'],stable:['→','STABILNY'],watch:['◐','OBSERWUJ'],falling:['↘','OSTROŻNIE'],collecting:['…','ZA MAŁA PRÓBA']};
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>Number.isFinite(Number(x))?Number(x):null;
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const signed=x=>num(x)==null?'—':`${Number(x)>0?'+':''}${Number(x).toFixed(1)} pp`;
  const statusMeta=s=>STATUS[s]||STATUS.collecting;

  function spark(series,status){
    const rows=(Array.isArray(series)?series:[]).filter(x=>num(x?.accuracy)!=null);
    if(rows.length<2)return '<div class="mt84e2-spark-empty">wykres po kolejnych rozliczeniach</div>';
    const values=rows.map(x=>Number(x.accuracy)),W=220,H=54,P=5;
    let lo=Math.max(0,Math.min(...values)-6),hi=Math.min(100,Math.max(...values)+6);
    if(hi-lo<12){const mid=(hi+lo)/2;lo=Math.max(0,mid-6);hi=Math.min(100,mid+6)}
    const den=Math.max(1,hi-lo);
    const pts=values.map((v,i)=>{
      const x=P+i*(W-P*2)/Math.max(1,values.length-1);
      const y=H-P-(v-lo)/den*(H-P*2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    const last=pts.split(' ').at(-1)?.split(',')||[];
    return `<svg class="mt84e2-spark status-${esc(status)}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Trend skuteczności">
      <line x1="${P}" y1="${H-P}" x2="${W-P}" y2="${H-P}" class="axis"/>
      <polyline points="${pts}" class="trend"/>
      ${last.length===2?`<circle cx="${last[0]}" cy="${last[1]}" r="3.5" class="last"/>`:''}
    </svg>`;
  }

  function modelCard(tel,id){
    const t=tel?.trends_v84e2?.models?.[id]||{};
    const [arrow,label]=statusMeta(t.status);
    const bd=num(t.brier_delta),n=Number(t.selected_n||0),w=Number(t.compare_window||0);
    return `<article class="mt84e2-card status-${esc(t.status||'collecting')}">
      <header><div><span>${ICONS[id]||'📊'}</span><b>${esc(LABELS[id]||id)}</b></div><em>${arrow} ${esc(label)}</em></header>
      ${spark(t.series,t.status)}
      <div class="mt84e2-metrics">
        <span><small>Zmiana accuracy</small><b>${signed(t.accuracy_delta_pp)}</b></span>
        <span><small>Zmiana Brier</small><b class="${bd!=null&&bd<0?'good':bd>0?'bad':''}">${bd==null?'—':`${bd>0?'+':''}${bd.toFixed(3)}`}</b></span>
      </div>
      <footer><span>n=${n}</span><span>${w?`porównanie ${w}+${w}`:'czekamy na ≥16'}</span><span>${esc(t.sample_strength||'collecting')}</span></footer>
    </article>`;
  }

  function gameStateCard(data,cp){
    const x=data?.checkpoints?.[String(cp)]||{},t=x.trend||{};
    const [arrow,label]=statusMeta(t.status);
    return `<article class="mt84e2-state-card status-${esc(t.status||'collecting')}">
      <header><b>Po ${cp} gemach</b><em>${arrow} ${esc(label)}</em></header>
      ${spark(t.series,t.status)}
      <div class="mt84e2-state-kpis">
        <span><small>Śledzone</small><b>${Number(x.tracked||0)}</b></span>
        <span><small>Rozliczone PBP</small><b>${Number(x.settled||0)}</b></span>
        <span><small>HIT–MISS</small><b>${Number(x.hits||0)}–${Number(x.misses||0)}</b></span>
        <span><small>Accuracy</small><b>${pct(x.accuracy)}</b></span>
      </div>
      <footer>${Number(x.waiting_pbp||0)} czeka na PBP</footer>
    </article>`;
  }

  function v852Comparison(){
    const rows=(typeof historyRows!=='undefined'&&Array.isArray(historyRows))?historyRows:[];
    let preCount=0,postCount=0,preHits=0,preSettled=0,postHits=0,postSettled=0;
    for(const m of rows){
      const cap=m?.autolearn_captured_at||m?.captured_at||'';
      const isPost=cap>=CUTOVER_V852;
      if(isPost)postCount++;else preCount++;
      const sigs=m?.autolearn_signals_v84||m?.signals||[];
      for(const s of sigs){
        if(s?.result==='hit'){if(isPost){postHits++;postSettled++}else{preHits++;preSettled++}}
        else if(s?.result==='miss'){if(isPost)postSettled++;else preSettled++}
      }
    }
    const preAcc=preSettled>0?(preHits/preSettled*100):null;
    const postAcc=postSettled>0?(postHits/postSettled*100):null;
    return `<div class="mt84e2-state" style="margin-top:10px;padding-top:10px;">
      <div class="mt84e2-subhead"><div><b>⚖️ Porównanie Jakości: Przed v8.5.2 / Od v8.5.2</b><small>Cutover 2026-08-25T09:55:27Z (autolearn_captured_at)</small></div><span>READ-ONLY</span></div>
      <div class="mt84e2-state-kpis">
        <span><small>Przed v8.5.2 (n=${preSettled}/${preCount} meczów)</small><b>${pct(preAcc)}</b></span>
        <span><small>Od v8.5.2 (n=${postSettled}/${postCount} meczów)</small><b>${pct(postAcc)}</b></span>
      </div>
    </div>`;
  }

  function html(tel){
    if(!tel||tel?.trends_v84e2?.version!==VERSION){
      return `<section id="mt84e2" class="mt84e2"><header class="mt84e2-head"><div><b>📈 Model Trend Monitor v8.4E2</b><small>Kierunek jakości modeli</small></div><span>OCZEKUJE</span></header><p class="mt84e2-note">Wykresy pojawią się po pierwszym raporcie telemetryki v8.4E2.</p></section>`;
    }
    const gs=tel.game_state_progress_v84e2||{};
    return `<section id="mt84e2" class="mt84e2">
      <header class="mt84e2-head"><div><b>📈 Model Trend Monitor v8.4E2</b><small>Czy model rośnie, stoi czy się pogarsza</small></div><span>MONITORING</span></header>
      <div class="mt84e2-legend"><span class="rising">↗ rośnie</span><span class="stable">→ stabilny</span><span class="watch">◐ obserwuj</span><span class="falling">↘ ostrożnie</span></div>
      <div class="mt84e2-grid">${PRIMARY.map(id=>modelCard(tel,id)).join('')}</div>
      <details class="mt84e2-details"><summary><b>Modele bazowe i Dynamic</b><span>pokaż trendy</span></summary><div class="mt84e2-grid secondary">${SECONDARY.map(id=>modelCard(tel,id)).join('')}</div></details>
      <div class="mt84e2-state">
        <div class="mt84e2-subhead"><div><b>🎯 Po2 / Po4 / Po6 — postęp nowego E1</b><small>Prawdziwe rozliczenie wyłącznie z PBP</small></div><span>${Number(gs.total_settled||0)} rozliczonych</span></div>
        <div class="mt84e2-state-grid">${[2,4,6].map(cp=>gameStateCard(gs,cp)).join('')}</div>
      </div>
      ${v852Comparison()}
      <p class="mt84e2-note"><b>Monitoring, nie autopilot.</b> Trend nie zmienia sam wag produkcyjnych. „OSTROŻNIE” oznacza pogorszenie ostatniej serii względem poprzedniej przy kontroli Brier.</p>
    </section>`;
  }

  async function inject(){
    const host=document.querySelector('#al84-performance');if(!host)return;
    const api=window.TENIS_AI_AUTOLEARN_V84;if(!api?.loadTelemetry)return;
    const tel=await api.loadTelemetry();
    if(!document.querySelector('#al84-performance'))return;
    document.querySelector('#mt84e2')?.remove();
    const grid=host.querySelector('.al84-grid');
    if(grid)grid.insertAdjacentHTML('afterend',html(tel));else host.insertAdjacentHTML('afterbegin',html(tel));
  }
  function schedule(){[260,720,1400].forEach(ms=>setTimeout(inject,ms))}
  if(typeof renderStats==='function'){
    const base=renderStats;
    renderStats=function(){const v=base.apply(this,arguments);schedule();return v};
  }
  if(document.querySelector('#pc77'))schedule();
  window.TENIS_AI_MODEL_TRENDS_V84E2=Object.freeze({version:VERSION,inject,render:html});
})();
