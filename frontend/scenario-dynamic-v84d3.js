/* Tenis AI v8.4D.3 — per-signal Dynamic Weights audit inside Scenario draft.
   UI-only. Reads results.json + current draft. Does not change model calculations.
*/
(()=>{
  'use strict';

  const VERSION='v8.4D.3';
  const DATA_URL='data/results.json';
  const PANEL='#scenario-v82a-panel';
  const ENTRY='.sc82-draft-entry';
  const AUDIT_CLASS='sc84d3-audit';
  const SUMMARY_ID='sc84d3-summary';

  let resultsPromise=null;
  let lookupCache=null;
  let refreshTimer=null;

  const esc=(v)=>String(v??'')
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;')
    .replaceAll('"','&quot;')
    .replaceAll("'","&#039;");

  const num=(v)=>{
    const n=Number(v);
    return Number.isFinite(n)?n:null;
  };

  const pct=(v)=>{
    const n=num(v);
    return n==null?'—':`${Math.round(n*100)}%`;
  };

  const decode=(v)=>{
    try{return decodeURIComponent(String(v??''))}
    catch{return String(v??'')}
  };

  const matchKey=(m)=>String(
    m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|')
  );

  function dynamicInfo(signal){
    const dyn=signal?.dynamic_weighting||{};
    const weights=dyn?.effective_weights||signal?.local_weights||{};
    const dimensions=Array.isArray(dyn?.dimensions)?dyn.dimensions:[];
    return {
      active:!!dyn.active,
      status:String(dyn.status||'SAFE_FALLBACK'),
      reason:String(dyn.reason||'—'),
      maxShift:num(dyn.max_shift)||0,
      weights,
      dimensions,
      score:num(signal?.ensemble),
    };
  }

  function buildLookup(results){
    const map=new Map();
    for(const match of Array.isArray(results)?results:[]){
      const mk=matchKey(match);
      for(const signal of (match?.autolearn_v84?.signals||[])){
        const sk=String(signal?.key||signal?.signal_key||'');
        if(!sk)continue;
        map.set(`${mk}::${sk}`,{
          matchKey:mk,
          signalKey:sk,
          label:String(signal?.label||sk),
          market:String(signal?.market||'—'),
          ...dynamicInfo(signal),
        });
      }
    }
    return map;
  }

  async function resultLookup(force=false){
    if(force){
      resultsPromise=null;
      lookupCache=null;
    }
    if(lookupCache)return lookupCache;
    if(!resultsPromise){
      resultsPromise=fetch(`${DATA_URL}?v=84d3`,{cache:'no-store'})
        .then(r=>{
          if(!r.ok)throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .catch(err=>{
          console.warn('v8.4D.3 results load:',err);
          return [];
        });
    }
    lookupCache=buildLookup(await resultsPromise);
    return lookupCache;
  }

  function currentDraft(){
    try{
      const draft=window.TENIS_AI_SCENARIOS?.draft?.();
      return draft&&Array.isArray(draft.items)?draft:{items:[]};
    }catch{
      return {items:[]};
    }
  }

  function dimsText(info){
    if(!info?.dimensions?.length)return 'globalne / brak segmentu';
    return info.dimensions
      .map(x=>`${String(x?.dimension||'?')}:${String(x?.value||'N/D')}`)
      .join(' · ');
  }

  function compactWeights(info){
    const w=info?.weights||{};
    return [
      `<span><b>Current</b> ${pct(w.current)}</span>`,
      `<span><b>Cat</b> ${pct(w.catboost)}</span>`,
      `<span><b>TabPFN</b> ${pct(w.tabpfn)}</span>`,
    ].join('');
  }

  function auditHtml(info){
    if(!info){
      return `
        <div class="${AUDIT_CLASS} is-missing" data-sc84d3-audit>
          <span class="sc84d3-mode">N/D</span>
          <span class="sc84d3-copy">Brak dopasowanego wpisu AutoLearn dla tego sygnału.</span>
        </div>
      `;
    }

    const shift=(info.maxShift*100).toFixed(1);
    const score=info.score==null?'—':info.score.toFixed(1);
    return `
      <div class="${AUDIT_CLASS} ${info.active?'is-dynamic':'is-global'}" data-sc84d3-audit>
        <div class="sc84d3-top">
          <span class="sc84d3-mode">${info.active?'DYNAMIC':'GLOBAL'}</span>
          <div class="sc84d3-weights">${compactWeights(info)}</div>
        </div>
        <div class="sc84d3-meta">
          <span>${esc(dimsText(info))}</span>
          <span>shift ${shift} pp</span>
          <span>ensemble ${score}</span>
        </div>
      </div>
    `;
  }

  function entryKey(entry){
    const btn=entry.querySelector('[data-sc-remove][data-sc-sig]');
    if(!btn)return null;
    const mk=decode(btn.dataset.scRemove);
    const sk=decode(btn.dataset.scSig);
    if(!mk||!sk)return null;
    return `${mk}::${sk}`;
  }

  function renderSummary(rows,totalDraft){
    const panel=document.querySelector(PANEL);
    if(!panel)return;

    const score=panel.querySelector('.sc82-score');
    if(!score)return;

    let summary=panel.querySelector(`#${SUMMARY_ID}`);
    if(!summary){
      summary=document.createElement('div');
      summary.id=SUMMARY_ID;
      summary.className='sc84d3-summary';
      score.insertAdjacentElement('afterend',summary);
    }

    const found=rows.filter(x=>x.info);
    const dynamic=found.filter(x=>x.info.active).length;
    const global=found.filter(x=>!x.info.active).length;
    const missing=Math.max(0,totalDraft-found.length);
    const shifts=found.map(x=>x.info.maxShift||0);
    const maxShift=shifts.length?Math.max(...shifts):0;

    summary.innerHTML=`
      <div><span>DYNAMIC</span><b>${dynamic}</b></div>
      <div><span>GLOBAL</span><b>${global}</b></div>
      <div><span>N/D</span><b>${missing}</b></div>
      <div><span>MAX SHIFT</span><b>${(maxShift*100).toFixed(1)} pp</b></div>
      <small>${VERSION} · audyt bieżącego scenariusza · logika modeli bez zmian</small>
    `;
  }

  async function render(){
    const panel=document.querySelector(PANEL);
    if(!panel||panel.hidden)return;

    const entries=[...panel.querySelectorAll(ENTRY)];
    if(!entries.length){
      panel.querySelector(`#${SUMMARY_ID}`)?.remove();
      return;
    }

    const draft=currentDraft();
    const lookup=await resultLookup(false);
    const rows=[];

    for(const entry of entries){
      const key=entryKey(entry);
      const info=key?lookup.get(key)||null:null;
      rows.push({key,info});

      const old=entry.querySelector('[data-sc84d3-audit]');
      const html=auditHtml(info);

      if(old){
        const wrap=document.createElement('div');
        wrap.innerHTML=html.trim();
        old.replaceWith(wrap.firstElementChild);
      }else{
        const row=entry.querySelector('.sc82-draft-row');
        if(row)row.insertAdjacentHTML('afterend',html);
        else entry.insertAdjacentHTML('beforeend',html);
      }
    }

    renderSummary(rows,draft.items.length);
  }

  function schedule(ms=80){
    clearTimeout(refreshTimer);
    refreshTimer=setTimeout(()=>render(),ms);
  }

  document.addEventListener('DOMContentLoaded',()=>schedule(300),{once:true});

  const observer=new MutationObserver((mutations)=>{
    if(!document.querySelector(PANEL))return;
    const relevant=mutations.some(m=>
      [...m.addedNodes].some(n=>
        n?.nodeType===1 && (
          n.matches?.(ENTRY) ||
          n.querySelector?.(ENTRY) ||
          n.matches?.('.sc82-score') ||
          n.querySelector?.('.sc82-score')
        )
      )
    );
    if(relevant)schedule(60);
  });
  observer.observe(document.documentElement,{childList:true,subtree:true});

  document.addEventListener('click',(e)=>{
    if(e.target?.closest?.(
      '[data-sc-generate],[data-sc-add],[data-sc-remove],[data-sc-clear],[data-sc-line-pick],[data-sc-go="draft"]'
    )){
      schedule(120);
    }
  });

  window.addEventListener('storage',(e)=>{
    if(e.key==='tenis-ai-v82a-scenario-draft')schedule(80);
  });

  window.TENIS_AI_SCENARIO_DYNAMIC_AUDIT={
    version:VERSION,
    refresh:()=>resultLookup(true).then(()=>render()),
  };
})();
