(()=>{
  'use strict';

  const VERSION='v8.4D.1';
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

  function signalRows(results){
    const rows=[];
    for(const match of Array.isArray(results)?results:[]){
      const auto=match?.autolearn_v84||{};
      for(const s of (auto.signals||[])){
        const dyn=s?.dynamic_weighting||{};
        rows.push({
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
    if(!row.dimensions.length) return 'brak aktywnego segmentu';
    return row.dimensions
      .map(x=>`${x.dimension||'?'}:${x.value||'N/D'}`)
      .join(' · ');
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
    if(!host) return false;

    const rows=signalRows(results);
    const active=rows.filter(x=>x.active);
    const global=rows.filter(x=>!x.active);
    const maxShift=active.length?Math.max(...active.map(x=>x.maxShift)):0;

    let root=document.getElementById(ROOT_ID);
    if(!root){
      root=document.createElement('section');
      root.id=ROOT_ID;
      root.className='dw84-audit';
      const telemetry=host.querySelector('.al84-telemetry');
      if(telemetry) telemetry.insertAdjacentElement('beforebegin',root);
      else host.appendChild(root);
    }

    const examples=(active.length?active:rows).slice(0,6);

    root.innerHTML=`
      <div class="dw84-head">
        <div>
          <span>DYNAMIC WEIGHTS ${VERSION}</span>
          <h4>Podgląd decyzji wag</h4>
          <p>Pokazuje, czy dany sygnał używa wag globalnych czy korekty v8.4D.</p>
        </div>
        <b class="${active.length?'active':'safe'}">${active.length?'DYNAMIC':'GLOBAL / SAFE'}</b>
      </div>

      <div class="dw84-summary">
        <div><small>Dynamiczne</small><strong>${active.length}</strong></div>
        <div><small>Global fallback</small><strong>${global.length}</strong></div>
        <div><small>Wszystkie sygnały</small><strong>${rows.length}</strong></div>
        <div><small>Max zmiana wagi</small><strong>${(maxShift*100).toFixed(1)} pp</strong></div>
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

            <div class="dw84-weights">
              ${weightsHtml(row.effective)}
            </div>

            <div class="dw84-meta">
              <span>${esc(dimsText(row))}</span>
              <span>shift ${(row.maxShift*100).toFixed(1)} pp</span>
              <span>score ${Number.isFinite(Number(row.score))?Number(row.score).toFixed(1):'—'}</span>
            </div>
          </article>
        `).join(''):`<p class="dw84-empty">Brak bieżących sygnałów AutoLearn do audytu.</p>`}
      </div>

      <p class="dw84-note">
        v8.4D nie może włączyć modelu wyłączonego przez globalny gate. Brak wystarczającej próbki = stare bezpieczne wagi.
      </p>
    `;
    return true;
  }

  async function load(){
    try{
      const res=await fetch(`${DATA_URL}?v=${Date.now()}`,{cache:'no-store'});
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
      const data=await res.json();
      render(data);
    }catch(err){
      const host=document.querySelector('.al84-performance');
      if(!host) return;
      let root=document.getElementById(ROOT_ID);
      if(!root){
        root=document.createElement('section');
        root.id=ROOT_ID;
        root.className='dw84-audit';
        host.appendChild(root);
      }
      root.innerHTML=`
        <div class="dw84-head">
          <div><span>DYNAMIC WEIGHTS ${VERSION}</span><h4>Podgląd decyzji wag</h4></div>
          <b class="safe">SAFE</b>
        </div>
        <p class="dw84-empty">Nie udało się odczytać bieżącego results.json — moduł obliczeń nie jest przez to zmieniany.</p>
      `;
    }
  }

  let timer=null;
  function schedule(ms=150){
    clearTimeout(timer);
    timer=setTimeout(load,ms);
  }

  document.addEventListener('DOMContentLoaded',()=>schedule(250));

  const observer=new MutationObserver(()=>{
    if(document.querySelector('.al84-performance') && !document.getElementById(ROOT_ID)){
      schedule(100);
    }
  });
  observer.observe(document.documentElement,{childList:true,subtree:true});

  document.addEventListener('click',(e)=>{
    if(e.target?.closest?.('#refresh')) schedule(1800);
  });

  setInterval(()=>schedule(0),60000);
})();
