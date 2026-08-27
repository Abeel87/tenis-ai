/* Tenis AI v8.4E2 — Model Trend Monitor
   Read-only monitoring. Reuses existing telemetry promise: no extra fetch,
   no MutationObserver, no interval, and it never changes production weights.
*/
(() => {
  'use strict';
  const VERSION='v8.4E2';
  const PRIMARY=['adaptive_prod','current','catboost','tabpfn','ensemble','generator'];
  const SECONDARY=['adaptive','early','serve','form','surface','consensus','dynamic'];
  const LABELS={adaptive_prod:'FINAL Adaptive PROD',adaptive:'Adaptive',early:'Early Hold',serve:'Serve/Return',form:'Form',surface:'Surface',consensus:'Consensus',current:'Current Engine',catboost:'CatBoost',tabpfn:'TabPFN-2',ensemble:'Ensemble',dynamic:'Dynamic Ensemble',generator:'Ensemble selector proxy'};
  const ICONS={adaptive:'🧠',early:'🎯',serve:'🎾',form:'🔥',surface:'🏟️',consensus:'⚡',current:'🧠',catboost:'🐱',tabpfn:'🧬',ensemble:'🔗',dynamic:'🧭',generator:'🚀'};
  const STATUS={rising:['↗','ROŚNIE'],stable:['→','STABILNY'],watch:['◐','OBSERWUJ'],falling:['↘','OSTROŻNIE'],collecting:['…','ZA MAŁA PRÓBA']};
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>x==null||x===''||!Number.isFinite(Number(x))?null:Number(x);
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

  function qlLines(tel,id){
    const ql=tel?.trends_v84e2?.quality_lock_v852?.[id]||tel?.trends_v84e2?.quality_lock_v852?.models?.[id];
    if(!ql)return '';
    const bef=ql.before_v852||{};
    const sin=ql.since_v852||{};
    const befStr=`Przed v8.5.2: n=${Number(bef.selected_n||0)} · Trafność ${pct(bef.accuracy)} · Brier ${num(bef.brier)==null?'—':Number(bef.brier).toFixed(3)}`;
    const sinStr=Number(sin.selected_n||0)<8
      ?`Od v8.5.2: n=${Number(sin.selected_n||0)} · zbieramy próbę`
      :`Od v8.5.2: n=${Number(sin.selected_n||0)} · Trafność ${pct(sin.accuracy)} · Brier ${num(sin.brier)==null?'—':Number(sin.brier).toFixed(3)}`;
    return `<div class="mt84e2-ql-lines" style="margin-top:6px;padding-top:4px;border-top:1px dashed rgba(255,255,255,.1);font-size:0.62rem;line-height:1.35;opacity:0.82;"><div>${esc(befStr)}</div><div>${esc(sinStr)}</div></div>`;
  }

  function modelCard(tel,id){
    const t=tel?.trends_v84e2?.models?.[id]||{};
    const [arrow,label]=statusMeta(t.status);
    const bd=num(t.brier_delta),n=Number(t.selected_n||0),w=Number(t.compare_window||0);
    return `<article class="mt84e2-card status-${esc(t.status||'collecting')}">
      <header><div><span>${ICONS[id]||'📊'}</span><b>${esc(LABELS[id]||id)}</b></div><em>${arrow} ${esc(label)}</em></header>
      ${spark(t.series,t.status)}
      <div class="mt84e2-metrics">
        <span><small>Zmiana trafności</small><b>${signed(t.accuracy_delta_pp)}</b></span>
        <span><small>Zmiana Brier</small><b class="${bd!=null&&bd<0?'good':bd>0?'bad':''}">${bd==null?'—':`${bd>0?'+':''}${bd.toFixed(3)}`}</b></span>
      </div>
      ${PRIMARY.includes(id)?qlLines(tel,id):''}
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

  function html(tel,rootId='mt84e2'){
    if(!tel||tel?.trends_v84e2?.version!==VERSION){
      return `<section id="${esc(rootId)}" class="mt84e2"><header class="mt84e2-head"><div><b>📈 Model Trend Monitor v8.4E2</b><small>Kierunek jakości modeli</small></div><span>OCZEKUJE</span></header><p class="mt84e2-note">Wykresy pojawią się po pierwszym raporcie telemetryki v8.4E2.</p></section>`;
    }
    const gs=tel.game_state_progress_v84e2||{};
    return `<section id="${esc(rootId)}" class="mt84e2">
      <header class="mt84e2-head"><div><b>📈 Model Trend Monitor v8.4E2</b><small>Czy model rośnie, stoi czy się pogarsza</small></div><span>MONITORING</span></header>
      <div class="mt84e2-legend"><span class="rising">↗ rośnie</span><span class="stable">→ stabilny</span><span class="watch">◐ obserwuj</span><span class="falling">↘ ostrożnie</span></div>
      <div class="mt84e2-grid">${PRIMARY.map(id=>modelCard(tel,id)).join('')}</div>
      <details class="mt84e2-details"><summary><b>Modele bazowe i Dynamic</b><span>pokaż trendy</span></summary><div class="mt84e2-grid secondary">${SECONDARY.map(id=>modelCard(tel,id)).join('')}</div></details>
      <div class="mt84e2-state">
        <div class="mt84e2-subhead"><div><b>🎯 Po2 / Po4 / Po6 — postęp nowego E1</b><small>Prawdziwe rozliczenie wyłącznie z PBP</small></div><span>${Number(gs.total_settled||0)} rozliczonych</span></div>
        <div class="mt84e2-state-grid">${[2,4,6].map(cp=>gameStateCard(gs,cp)).join('')}</div>
      </div>
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
  let trendTimer=null;
  function schedule(ms=320){
    clearTimeout(trendTimer);
    trendTimer=setTimeout(inject,ms);
  }
  if(typeof renderStats==='function'){
    const base=renderStats;
    renderStats=function(){const v=base.apply(this,arguments);schedule();return v};
  }
  if(document.querySelector('#pc77'))schedule();
  window.TENIS_AI_MODEL_TRENDS_V84E2=Object.freeze({version:VERSION,inject,render:html});
})();
