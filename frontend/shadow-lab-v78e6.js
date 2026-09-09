/* Tenis AI Shadow Lab — canonical clean UI, SHADOW data only. */
(() => {
  'use strict';

  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
  const score=v=>v==null||!Number.isFinite(Number(v))
    ?'N/D'
    :`${Number(v).toFixed(1).replace('.0','')}/100`;
  const pct=v=>v==null||!Number.isFinite(Number(v))
    ?'—'
    :`${Number(v).toFixed(1).replace('.0','')}%`;

  let current=[];
  let stats={};
  let active=false;
  let shadowFilter='all';

  async function safeJson(url,fallback){
    try{
      const r=await fetch(url+'?v='+Date.now(),{cache:'no-store'});
      return r.ok?await r.json():fallback;
    }catch{
      return fallback;
    }
  }

  async function reload(){
    [current,stats]=await Promise.all([
      safeJson('data/shadow_current.json',[]),
      safeJson('data/shadow_stats.json',{})
    ]);
    if(!Array.isArray(current))current=[];
    if(!stats||typeof stats!=='object')stats={};
    return {current,stats};
  }

  function tour(x){
    const t=String(x?.tour||'').toLowerCase();
    if(t.includes('chall'))return 'CH';
    if(t.includes('itf'))return 'ITF';
    return t.toUpperCase()||'TENIS';
  }

  function tourKey(x){
    const t=String(x?.tour||'').toLowerCase();
    if(t.includes('chall'))return 'challenger';
    if(t.includes('itf'))return 'itf';
    if(t.includes('wta'))return 'wta';
    if(t.includes('atp'))return 'atp';
    return t||'other';
  }

  function surface(x){
    const raw=String(x?.surface||'').trim();
    if(!raw)return '—';
    const k=raw.toLowerCase();
    if(k==='hard')return 'Hard';
    if(k==='clay')return 'Clay';
    if(k==='grass')return 'Grass';
    return raw;
  }

  function matchTime(x){
    const d=new Date(x?.scheduled_time||'');
    return Number.isFinite(d.getTime())
      ?d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'})
      :'—';
  }

  function validSignals(x){
    return (Array.isArray(x?.signals)?x.signals:[])
      .filter(row=>Number.isFinite(Number(row?.score)))
      .filter(row=>Number(row.score)>=55&&Number(row.score)<72)
      .sort((a,b)=>Number(b.score)-Number(a.score));
  }

  function signalLabel(row){
    const label=String(row?.label||'Sygnał').trim();
    const pick=String(row?.pick||'').trim().toUpperCase();
    if(!pick||label.toUpperCase().includes(pick))return label;
    return `${label} · ${pick}`;
  }

  function filteredRows(){
    return current
      .filter(Boolean)
      .filter(x=>window.TENIS_AI_MATCH_TIME?.isCurrent?.(x)===true)
      .filter(x=>shadowFilter==='all'||tourKey(x)===shadowFilter)
      .sort((a,b)=>{
        const aSignal=validSignals(a).length?1:0;
        const bSignal=validSignals(b).length?1:0;
        if(aSignal!==bSignal)return bSignal-aSignal;
        return new Date(a.scheduled_time||0)-new Date(b.scheduled_time||0);
      });
  }

  function matchExists(x){
    try{
      return !!window.TENIS_AI_PROJECT_UI?.findMatch?.(String(x?.match_id??''));
    }catch{
      return false;
    }
  }

  function card(x){
    const rows=validSignals(x);
    const best=rows[0]||null;
    const canOpen=matchExists(x)&&!!x.model_ready;
    const reason=x.rejection_reason
      ||(best
        ?'Sygnał nie przekroczył progu zielonego 72/100.'
        :'Brak wystarczającej próbki do wiarygodnego sygnału.');

    return `
      <article class="match-tile shadow-match-tile ${best?'':'shadow-match-nodata'}"
        ${canOpen?`data-shadow-match="${esc(String(x.match_id))}"`:''}
        ${canOpen?'role="button" tabindex="0"':''}>
        <header class="match-tile-meta">
          <span class="shadow-chip">${best?'SHADOW 55–71':'N/D'}</span>
          <b>${esc(tour(x))}</b>
          <span>${esc(x.tournament||'Turniej')}</span>
          <time>${esc(matchTime(x))}</time>
        </header>

        <div class="match-tile-players">
          <b>${esc(x.p1)}</b>
          <span>vs</span>
          <b>${esc(x.p2)}</b>
        </div>

        <div class="match-tile-decision shadow-decision">
          <span>${best?'ODRZUCONY SYGNAŁ':'OBSERWACJA'}</span>
          <b>${esc(best?signalLabel(best):'Brak rozliczalnego sygnału')}</b>
          <strong>${best?score(best.score):'N/D'}</strong>
        </div>

        ${rows.length>1?`<div class="shadow-extra-signals">${rows.slice(1,4).map(row=>`
          <span><i>${esc(signalLabel(row))}</i><b>${score(row.score)}</b></span>
        `).join('')}</div>`:''}

        <div class="shadow-reason">
          <span>Dlaczego nie jest zielony</span>
          <b>${esc(reason)}</b>
          <small>${esc(x.p1)} n=${x.p1_matches??'—'} · ${esc(x.p2)} n=${x.p2_matches??'—'}</small>
        </div>

        <footer class="match-tile-foot">
          <span>🧪 Shadow Lab</span>
          <span>${esc(surface(x))}</span>
          <span>Dane ${esc(x.quality||'—')}</span>
          <b>${canOpen?'Analiza meczu →':best?'SHADOW':'N/D'}</b>
        </footer>
      </article>`;
  }

  function groupRows(rows){
    const groups=new Map();
    rows.forEach(x=>{
      const k=`${tour(x)}|${x.tournament||'Turniej'}`;
      if(!groups.has(k))groups.set(k,{tour:tour(x),name:x.tournament||'Turniej',rows:[]});
      groups.get(k).rows.push(x);
    });
    return [...groups.values()];
  }

  function summary(rows){
    const signalRows=rows.filter(x=>validSignals(x).length);
    const ndRows=rows.filter(x=>!validSignals(x).length);
    const signalCount=signalRows.reduce((n,x)=>n+validSignals(x).length,0);
    const overall=stats.overall||{};
    return `<section class="shadow-summary">
      <div>
        <span>SHADOW · DIAGNOSTYKA</span>
        <h2>Odrzucone sygnały</h2>
        <p>Zakres 55–71/100. Dane nie wpływają na PROD, PLAYABLE ani oficjalną skuteczność.</p>
      </div>
      <div class="shadow-summary-grid">
        <article><span>Sygnały</span><b>${signalCount}</b></article>
        <article><span>Mecze</span><b>${signalRows.length}</b></article>
        <article><span>N/D</span><b>${ndRows.length}</b></article>
        <article><span>Skuteczność</span><b>${overall.accuracy==null?'—':pct(overall.accuracy)}</b></article>
      </div>
    </section>`;
  }

  function filterBar(){
    const options=[['all','Wszystkie'],['atp','ATP'],['wta','WTA'],['challenger','CH'],['itf','ITF']];
    return `<div class="match-filter-row shadow-filter-row">${options.map(([id,label])=>`
      <button type="button" class="${shadowFilter===id?'active':''}" data-shadow-filter="${id}">${label}</button>
    `).join('')}</div>`;
  }

  function bindCards(){
    document.querySelectorAll('[data-shadow-match]').forEach(el=>{
      const open=()=>{
        const id=String(el.dataset.shadowMatch||'');
        const row=current.find(x=>String(x?.match_id??'')===id);
        window.TENIS_AI_PROJECT_UI?.openMatch?.(id);
        if(row)detailShadowInfo(row);
      };
      el.onclick=open;
      el.onkeydown=e=>{
        if(e.key!=='Enter'&&e.key!==' ')return;
        e.preventDefault();
        open();
      };
    });
  }

  function bindFilters(){
    document.querySelectorAll('[data-shadow-filter]').forEach(btn=>{
      btn.onclick=()=>{
        shadowFilter=btn.dataset.shadowFilter||'all';
        renderShadow();
      };
    });
  }

  function detailShadowInfo(x){
    const rows=validSignals(x);
    if(!rows.length)return;
    requestAnimationFrame(()=>{
      const root=document.querySelector('#app[data-match-key] .p751-detail-screen');
      if(!root)return;
      root.querySelector('.shadow-detail-note')?.remove();
      const anchor=root.querySelector('.match-hero')||root.querySelector('.match-decision')||root.firstElementChild;
      if(!anchor)return;
      const box=document.createElement('section');
      box.className='shadow-detail-note phase11-technical';
      box.innerHTML=`
        <header><div><span>SHADOW LAB</span><b>Odrzucone sygnały 55–71</b></div><strong>SHADOW</strong></header>
        <p>To diagnostyka. Te sygnały nie są zielonymi typami i nie wpływają na PLAYABLE.</p>
        <div>${rows.slice(0,5).map(row=>`
          <span><i>${esc(signalLabel(row))}</i><b>${score(row.score)}</b></span>
        `).join('')}</div>`;
      anchor.insertAdjacentElement('afterend',box);
    });
  }

  function syncTrigger(){
    const btn=document.querySelector('#shadow-open');
    if(btn)btn.classList.toggle('active',active);
  }

  function renderShadow(){
    const app=document.querySelector('#app');
    if(!app)return;
    active=true;
    document.documentElement.dataset.tenisRoute='shadow';
    syncTrigger();

    const rows=filteredRows();
    app.innerHTML=`<div class="match-browser shadow-browser">
      ${summary(rows)}
      <section class="match-browser-head shadow-browser-head">
        <div><span>SHADOW LAB</span><b>${rows.length} spotkań</b></div>
        ${filterBar()}
      </section>
      ${rows.length
        ?`<div class="match-groups">${groupRows(rows).map(group=>`
          <section class="match-group shadow-match-group">
            <header>
              <div><span>${esc(group.tour)}</span><b>${esc(group.name)}</b></div>
              <small>${group.rows.length} ${group.rows.length===1?'mecz':'meczów'} · ${esc([...new Set(group.rows.map(surface))].join('/')||'—')}</small>
            </header>
            <div class="match-grid">${group.rows.map(card).join('')}</div>
          </section>
        `).join('')}</div>`
        :'<div class="empty-state"><b>Brak danych SHADOW dla tego filtra.</b><span>Wybierz inny tour.</span></div>'}
    </div>`;

    bindFilters();
    bindCards();
  }

  async function openShadow(){
    await reload();
    renderShadow();
    window.scrollTo({top:0,behavior:'auto'});
    return true;
  }

  function bindTrigger(){
    const btn=document.querySelector('#shadow-open');
    if(!btn)return false;
    if(btn.dataset.shadowBound==='1')return true;
    btn.dataset.shadowBound='1';
    btn.addEventListener('click',e=>{
      e.preventDefault();
      openShadow();
    });
    return true;
  }

  document.addEventListener('click',e=>{
    if(e.target?.closest?.('.main-tabs button[data-view]')){
      active=false;
      syncTrigger();
    }
  },true);

  async function boot(){
    bindTrigger();
    await reload();
  }

  window.TENIS_AI_SHADOW_LAB={
    reload,
    open:openShadow,
    render:renderShadow,
    detail:detailShadowInfo,
    bindTrigger
  };

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
  else boot();
})();