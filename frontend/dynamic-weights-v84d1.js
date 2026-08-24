(()=>{
  'use strict';

  const VERSION='v8.4D.2';
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

  const matchKey=(m)=>String(
    m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|')
  );

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

  function currentDraft(){
    try{
      const api=window.TENIS_AI_SCENARIOS;
      const draft=api?.draft?.();
      return draft&&Array.isArray(draft.items)?draft:{items:[]};
    }catch{
      return {items:[]};
    }
  }

  function currentScenarioRows(allRows){
    const draft=currentDraft();
    if(!draft.items.length)return [];

    const wanted=new Set(
      draft.items.map(x=>`${String(x?.match_key||'')}::${String(x?.signal_key||'')}`)
    );

    return allRows.filter(
      row=>wanted.has(`${row.matchKey}::${row.signalKey}`)
    );
  }

  function currentScenarioMeta(){
    const draft=currentDraft();
    const matches=new Set(
      draft.items.map(x=>String(x?.match_key||'')).filter(Boolean)
    );
    return {
      signalCount:draft.items.length,
      matchCount:matches.size,
      mode:String(draft?.mode||'manual'),
      profile:String(draft?.profile||'manual'),
    };
  }

  function dimsText(row){
    if(!row.dimensions.length)return 'brak aktywnego segmentu';
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
    if(!host)return false;

    const poolRows=signalRows(results);
    const scenarioRows=currentScenarioRows(poolRows);
    const scenarioMeta=currentScenarioMeta();

    const activePool=poolRows.filter(x=>x.active);
    const globalPool=poolRows.filter(x=>!x.active);
    const activeScenario=scenarioRows.filter(x=>x.active);
    const globalScenario=scenarioRows.filter(x=>!x.active);

    const scopeRows=scenarioRows.length?scenarioRows:poolRows;
    const maxShift=scopeRows.length
      ?Math.max(...scopeRows.map(x=>x.maxShift))
      :0;

    let root=document.getElementById(ROOT_ID);
    if(!root){
      root=document.createElement('section');
      root.id=ROOT_ID;
      root.className='dw84-audit';
      const telemetry=host.querySelector('.al84-telemetry');
      if(telemetry)telemetry.insertAdjacentElement('beforebegin',root);
      else host.appendChild(root);
    }

    const examples=(scenarioRows.length
      ?scenarioRows
      :(activePool.length?activePool:poolRows)
    ).slice(0,6);

    const scenarioMode=scenarioRows.length
      ?(activeScenario.length?'DYNAMIC':'GLOBAL / SAFE')
      :'BRAK SCENARIUSZA';

    root.innerHTML=`
      <div class="dw84-head">
        <div>
          <span>DYNAMIC WEIGHTS ${VERSION}</span>
          <h4>Podgląd decyzji wag</h4>
          <p>Aktualny scenariusz jest liczony osobno od całej puli results.json.</p>
        </div>
        <b class="${activeScenario.length?'active':'safe'}">${scenarioMode}</b>
      </div>

      <div class="dw84-summary">
        <div><small>Aktualny scenariusz</small><strong>${scenarioMeta.signalCount}</strong><small>${scenarioMeta.matchCount} spotk.</small></div>
        <div><small>Dynamiczne w scenariuszu</small><strong>${activeScenario.length}</strong></div>
        <div><small>Global w scenariuszu</small><strong>${globalScenario.length}</strong></div>
        <div><small>Cała pula</small><strong>${poolRows.length}</strong><small>${activePool.length} dynamic · ${globalPool.length} global</small></div>
      </div>

      ${scenarioMeta.signalCount?`
        <p class="dw84-scope-note">
          Bieżący draft: ${scenarioMeta.matchCount} spotk. · ${scenarioMeta.signalCount} sygnałów ·
          ${esc(scenarioMeta.mode)} / ${esc(scenarioMeta.profile)} ·
          max shift ${(maxShift*100).toFixed(1)} pp
        </p>
      `:''}

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
        v8.4D nie może włączyć modelu wyłączonego przez globalny gate.
        „Cała pula” to pełny results.json, a „Aktualny scenariusz” to dokładnie draft z Scenariuszy AI.
      </p>
    `;
    return true;
  }

  async function load(){
    try{
      const res=await fetch(`${DATA_URL}?v=${Date.now()}`,{cache:'no-store'});
      if(!res.ok)throw new Error(`HTTP ${res.status}`);
      const data=await res.json();
      render(data);
    }catch(err){
      const host=document.querySelector('.al84-performance');
      if(!host)return;
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
    if(document.querySelector('.al84-performance')&&!document.getElementById(ROOT_ID)){
      schedule(100);
    }
  });
  observer.observe(document.documentElement,{childList:true,subtree:true});

  document.addEventListener('click',(e)=>{
    if(e.target?.closest?.('#refresh'))schedule(1800);
    if(e.target?.closest?.('[data-sc-generate],[data-sc-add],[data-sc-remove],[data-sc-clear],[data-sc-line-pick]')){
      schedule(250);
    }
  });

  window.addEventListener('storage',(e)=>{
    if(e.key==='tenis-ai-v82a-scenario-draft')schedule(100);
  });

  setInterval(()=>schedule(0),60000);
})();
