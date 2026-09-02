(()=>{
  'use strict';

  const VERSION='v8.4D.4';
  const ROOT_ID='dynamic-weights-audit-v84d1';
  const DATA_URL='data/results.json';

  const esc=(v)=>String(v??'')
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;')
    .replaceAll('"','&quot;')
    .replaceAll("'","&#039;");

  const pct=(v)=>{
    const n=Number(v);
    return Number.isFinite(n)?`${Math.round(n*100)}%`:'—';
  };

  const matchKey=(m)=>String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|'));

  function signalRows(results){
    const rows=[];
    for(const match of Array.isArray(results)?results:[]){
      const auto=match?.autolearn_v84||{};
      for(const s of (auto.signals||[])){
        const dyn=s?.dynamic_weighting||{};
        rows.push({
          matchKey:matchKey(match),
          signalKey:String(s?.key||s?.signal_key||''),
          match:`${match?.p1||'—'} – ${match?.p2||'—'}`,
          label:s?.label||s?.key||'sygnał',
          market:s?.market||'—',
          score:s?.ensemble,
          active:!!dyn.active,
          status:dyn.status||'SAFE_FALLBACK',
          reason:dyn.reason||'—',
          maxShift:Number(dyn.max_shift||0),
          local:s?.local_weights||{},
          effective:dyn.effective_weights||s?.local_weights||{},
          dimensions:Array.isArray(dyn.dimensions)?dyn.dimensions:[],
        });
      }
    }
    return rows;
  }

  function dimsText(row){
    if(!row.dimensions.length)return 'brak aktywnego segmentu';
    return row.dimensions.map(x=>`${x.dimension||'?'}:${x.value||'N/D'}`).join(' · ');
  }

  function weightsHtml(w){
    return `
      <span><b>Current</b> ${pct(w?.current)}</span>
      <span><b>Cat</b> ${pct(w?.catboost)}</span>
      <span><b>TabPFN</b> ${pct(w?.tabpfn)}</span>
    `;
  }

  function render(results){
    const host=document.querySelector('.al84-performance');
    if(!host)return false;

    const poolRows=signalRows(results);
    const activePool=poolRows.filter(x=>x.active);
    const globalPool=poolRows.filter(x=>!x.active);
    const maxShift=poolRows.length?Math.max(...poolRows.map(x=>x.maxShift)):0;

    let root=document.getElementById(ROOT_ID);
    if(!root){
      root=document.createElement('section');
      root.id=ROOT_ID;
      root.className='dw84-audit';
      const telemetry=host.querySelector('.al84-telemetry');
      if(telemetry)telemetry.insertAdjacentElement('beforebegin',root);
      else host.appendChild(root);
    }

    const examples=(activePool.length?activePool:poolRows).slice(0,6);
    const mode=activePool.length?'DYNAMIC':'GLOBAL / SAFE';

    root.innerHTML=`
      <div class="dw84-head">
        <div>
          <span>DYNAMIC WEIGHTS ${VERSION}</span>
          <h4>Podgląd decyzji wag</h4>
          <p>Audyt pełnej puli MODEL/RAW. Symfonia 2.0 korzysta z własnego operator-first pipeline.</p>
        </div>
        <b class="${activePool.length?'active':'safe'}">${mode}</b>
      </div>

      <div class="dw84-summary">
        <div><small>Wszystkie sygnały</small><strong>${poolRows.length}</strong></div>
        <div><small>Dynamiczne</small><strong>${activePool.length}</strong></div>
        <div><small>Global / SAFE</small><strong>${globalPool.length}</strong></div>
        <div><small>Max shift</small><strong>${(maxShift*100).toFixed(1)} pp</strong></div>
      </div>

      <div class="dw84-examples">
        ${examples.length?examples.map(row=>`
          <article class="dw84-row ${row.active?'is-dynamic':'is-global'}">
            <header>
              <div>
                <b>${esc(row.label)}</b>
                <small>${esc(row.match)} · ${esc(row.market)}</small>
              </div>
              <em>${row.active?'DYNAMIC':'GLOBAL'}</em>
            </header>
            <div class="dw84-weights">${weightsHtml(row.effective)}</div>
            <div class="dw84-meta">
              <span>${esc(dimsText(row))}</span>
              <span>shift ${(row.maxShift*100).toFixed(1)} pp</span>
              <span>score ${Number.isFinite(Number(row.score))?Number(row.score).toFixed(1):'—'}</span>
            </div>
          </article>
        `).join(''):`<p class="dw84-empty">Brak bieżących sygnałów AutoLearn do audytu.</p>`}
      </div>

      <p class="dw84-note">
        v8.4D nie może włączyć modelu wyłączonego przez globalny gate. Ten moduł nie steruje PLAYABLE i nie tworzy kandydatów dla Symfonii 2.0.
      </p>
    `;
    return true;
  }

  function memoryResults(){
    try{return typeof all!=='undefined'&&Array.isArray(all)?all:null}catch{return null}
  }

  async function load(){
    try{
      const memory=memoryResults();
      if(memory){render(memory);return}
      const res=await fetch(`${DATA_URL}?v=${Date.now()}`,{cache:'no-store'});
      if(!res.ok)throw new Error(`HTTP ${res.status}`);
      render(await res.json());
    }catch{
      const host=document.querySelector('.al84-performance');
      if(!host)return;
      let root=document.getElementById(ROOT_ID);
      if(!root){root=document.createElement('section');root.id=ROOT_ID;root.className='dw84-audit';host.appendChild(root)}
      root.innerHTML=`<div class="dw84-head"><div><span>DYNAMIC WEIGHTS ${VERSION}</span><h4>Podgląd decyzji wag</h4></div><b class="safe">SAFE</b></div><p class="dw84-empty">Nie udało się odczytać bieżącego results.json — moduł obliczeń nie jest przez to zmieniany.</p>`;
    }
  }

  let timer=null;
  function schedule(ms=150){clearTimeout(timer);timer=setTimeout(load,ms)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>schedule(250),{once:true});else schedule(50);
  document.addEventListener('tenis-ai:stats-ready',()=>schedule(180));
  document.addEventListener('tenis-ai:stats-dashboard-ready',()=>schedule(180));
  document.addEventListener('click',(e)=>{if(e.target?.closest?.('#refresh'))schedule(1800)});
})();
