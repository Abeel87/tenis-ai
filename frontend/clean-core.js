/* Tenis AI v8.0.1 — Clean Core + Post-Match Center */
(() => {
  'use strict';

  const VERSION='v8.0.1';
  const DAY_KEY='tenis-ai-v80-history-days';
  const MODEL_NAMES={
    adaptive:'🧠 Adaptive', consensus:'⚡ Consensus', early:'🎯 Early Hold',
    serve:'🎾 Serve/Return', form:'🔥 Form', surface:'🏟️ Surface',
    early_hold_pbp:'🧬 Early Hold PBP'
  };

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>x==null||!Number.isFinite(Number(x))?null:Number(x);
  const score=x=>num(x)==null?'N/D':`${Number(x).toFixed(1).replace('.0','')}/100`;
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const norm=s=>String(s??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'');
  const readState=()=>{try{return JSON.parse(localStorage.getItem(DAY_KEY)||'{}')||{}}catch{return {}}};
  const saveState=x=>{try{localStorage.setItem(DAY_KEY,JSON.stringify(x))}catch{}};
  let dayState=readState();
  let openEntry=null;

  function entryKey(e){return String(e?.match_key||e?.match_id||e?.id||[e?.p1,e?.p2,e?.scheduled_time].join('|'))}
  function localDay(value){
    const d=new Date(value||''); if(!Number.isFinite(d.getTime()))return 'bez-daty';
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }
  function dayLabel(key){
    if(key==='bez-daty')return 'Bez daty';
    const [y,m,d]=key.split('-').map(Number), dt=new Date(y,m-1,d), now=new Date();
    const today=localDay(now), yesterday=localDay(new Date(now.getFullYear(),now.getMonth(),now.getDate()-1));
    const pretty=dt.toLocaleDateString('pl-PL',{weekday:'long',day:'2-digit',month:'2-digit'});
    if(key===today)return `Dzisiaj · ${pretty}`;
    if(key===yesterday)return `Wczoraj · ${pretty}`;
    return pretty.charAt(0).toUpperCase()+pretty.slice(1);
  }
  function dateTime(value){
    const d=new Date(value||'');
    return Number.isFinite(d.getTime())?d.toLocaleString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}):'—';
  }
  function statusInfo(e){
    if(e?.result?.status==='retired')return {text:'KRECZ · CZĘŚCIOWO',cls:'special',icon:'↩️'};
    if(e?.status==='settled')return {text:'ROZLICZONY',cls:'settled',icon:'✅'};
    if(e?.status==='void')return {text:'NIE LICZYMY',cls:'void',icon:'↩️'};
    const s=String(e?.live_status||'').toLowerCase();
    if(s.includes('interrupt'))return {text:'PRZERWANY',cls:'special',icon:'⏸️'};
    if(s.includes('suspend'))return {text:'ZAWIESZONY',cls:'special',icon:'⏸️'};
    if(s.includes('postpon'))return {text:'PRZEŁOŻONY',cls:'special',icon:'📅'};
    if(s.includes('progress')||s.includes('started')||s==='live')return {text:'W TRAKCIE',cls:'live',icon:'🔴'};
    return {text:'OCZEKUJE',cls:'pending',icon:'⏳'};
  }
  function finalScore(e){
    const r=e?.result;
    if(!r)return 'Oczekuje na wynik';
    if(r.status==='void')return r.reason?`Nierozliczany · ${r.reason}`:'Mecz nierozliczany';
    if(r.sets?.length)return r.sets.map(s=>s.join(':')).join(' · ');
    return r.score_text||'Zakończony';
  }
  function settledRows(){
    try{
      return (Array.isArray(historyRows)?historyRows:[]).filter(e=>{
        const has=(e?.signals||[]).length||(e?.learning_signals_v79b||[]).length||e?.adaptive_review_v79;
        if(!has)return false;
        if(e.status==='settled'||e.status==='void')return true;
        const t=new Date(e.scheduled_time||'').getTime();
        return Number.isFinite(t)&&t<=Date.now()+5*60*1000;
      }).sort((a,b)=>new Date(b.scheduled_time||0)-new Date(a.scheduled_time||0)).slice(0,240);
    }catch{return []}
  }

  function marketOutcome(e,s){
    const existing=String(s?.result||'').toLowerCase();
    if(['hit','miss','void','unverifiable'].includes(existing))return existing;
    if(e?.status!=='settled'||!e?.result)return existing||'pending';
    const r=e.result, market=String(s?.market||''), pick=String(s?.pick||''), line=num(s?.line);
    const p1=norm(e.p1), p2=norm(e.p2), wanted=norm(pick);
    const winnerForSet=i=>{
      const z=r.sets?.[i]; if(!Array.isArray(z)||z.length<2||z[0]===z[1])return null;
      return z[0]>z[1]?p1:p2;
    };
    if(market==='match_winner'&&r.winner)return norm(r.winner)===wanted?'hit':'miss';
    if(market==='set1_winner'){const w=winnerForSet(0);return w?w===wanted?'hit':'miss':'unverifiable'}
    if(market==='set2_winner'){const w=winnerForSet(1);return w?w===wanted?'hit':'miss':'void'}
    if(market==='set3_winner'){const w=winnerForSet(2);return w?w===wanted?'hit':'miss':'void'}
    if(market==='set1_total'&&line!=null&&Array.isArray(r.sets?.[0])){
      const total=Number(r.sets[0][0])+Number(r.sets[0][1]);
      if(wanted.startsWith('over'))return total>line?'hit':'miss';
      if(wanted.startsWith('under'))return total<line?'hit':'miss';
      return 'unverifiable';
    }
    if(market==='match_total'&&line!=null){
      const total=num(r.total_games) ?? (Array.isArray(r.sets)?r.sets.reduce((a,z)=>a+Number(z?.[0]||0)+Number(z?.[1]||0),0):null);
      if(total==null)return 'unverifiable';
      if(wanted.startsWith('over'))return total>line?'hit':'miss';
      if(wanted.startsWith('under'))return total<line?'hit':'miss';
      return 'unverifiable';
    }
    if(market==='total_sets'){
      const expected=parseInt(pick,10), actual=num(r.number_of_sets)??r.sets?.length;
      return Number.isFinite(expected)&&actual!=null?(Number(actual)===expected?'hit':'miss'):'unverifiable';
    }
    return existing||'unverifiable';
  }

  const resultText=r=>({hit:'TRAFIONY',miss:'NIETRAFIONY',pending:'OCZEKUJE',void:'NIE LICZYMY',unverifiable:'BRAK DANYCH'}[r]||'OCZEKUJE');
  const resultIcon=r=>({hit:'✅',miss:'❌',pending:'⏳',void:'↩️',unverifiable:'➖'}[r]||'⏳');
  function officialSignals(e){return (e?.signals||[]).map(s=>({...s,_result:marketOutcome(e,s)}))}
  function learningSignals(e){return (e?.learning_signals_v79b||[]).map(s=>({...s,_result:marketOutcome(e,s)}))}
  function counts(rows){
    return rows.reduce((a,s)=>{a[s._result]=(a[s._result]||0)+1;return a},{hit:0,miss:0,pending:0,void:0,unverifiable:0});
  }
  function analysisReady(e){return !!(e?.adaptive_review_v79&&Array.isArray(e.adaptive_review_v79.lessons))}

  function historyCard(e){
    const st=statusInfo(e), c=counts(officialSignals(e)), ready=analysisReady(e);
    return `<button type="button" class="v80-history-card" data-v80-history-open="${esc(entryKey(e))}">
      <div class="v80-history-top"><span>${esc((e.tour||'').toUpperCase())} · ${esc(e.tournament||'—')}</span><em class="${st.cls}">${st.icon} ${esc(st.text)}</em></div>
      <div class="v80-history-match"><b>${esc(e.p1)}</b><span>vs</span><b>${esc(e.p2)}</b></div>
      <div class="v80-history-result"><strong>${esc(finalScore(e))}</strong><small>${esc(e.surface||'—')} · ${esc(dateTime(e.scheduled_time))}</small></div>
      <div class="v80-history-chips">
        <span class="hit">✅ ${c.hit}</span><span class="miss">❌ ${c.miss}</span>
        ${ready?'<span class="learn">🧠 Analiza gotowa</span>':'<span class="muted">🧠 Zbieranie danych</span>'}
        <b>Raport ›</b>
      </div>
    </button>`;
  }

  function renderHistoryV80(){
    openEntry=null;
    const app=document.querySelector('#app'); if(!app)return;
    const rows=settledRows();
    if(!rows.length){app.innerHTML='<div class="empty"><b>Historia jest jeszcze pusta.</b><br><br>Po rozliczeniu meczu pojawi się tutaj raport modeli.</div>';return}
    const groups=new Map();
    rows.forEach(e=>{const k=localDay(e.scheduled_time);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(e)});
    const ordered=[...groups.entries()].sort((a,b)=>b[0].localeCompare(a[0]));
    const newest=ordered[0]?.[0];
    app.innerHTML=`<section class="v80-history-head"><div><b>🕘 Historia i raporty po meczu</b><span>${rows.length} meczów · kliknij mecz, żeby zobaczyć co zrobiły modele</span></div></section>
      <div class="v80-day-list">${ordered.map(([key,list])=>{
        const open=dayState[key]===true||(dayState[key]===undefined&&key===newest);
        const settled=list.filter(x=>x.status==='settled').length;
        return `<details class="v80-day" data-v80-day="${esc(key)}" ${open?'open':''}><summary><div><b>${esc(dayLabel(key))}</b><small>${list.length} meczów · ${settled} rozliczonych</small></div><i>⌄</i></summary><div class="v80-day-body">${list.map(historyCard).join('')}</div></details>`;
      }).join('')}</div>`;
    bindHistory();
  }

  function signalRow(s){
    const r=s._result||s.result||'pending';
    return `<div class="v80-signal ${esc(r)}"><span>${resultIcon(r)}</span><div><b>${esc(s.label||s.key||s.market||'Sygnał')}</b><small>${esc(s.pick||'')} · ${score(s.score)}</small></div><strong>${resultText(r)}</strong></div>`;
  }

  function modelGroups(e){
    const map=new Map();
    const official=officialSignals(e);
    if(official.length)map.set('adaptive',official);
    learningSignals(e).forEach(s=>{
      const id=String(s.source_model||'learning');
      if(!map.has(id))map.set(id,[]);
      const duplicate=id==='adaptive'&&official.some(o=>o.market===s.market&&String(o.pick)===String(s.pick)&&String(o.line??'')===String(s.line??''));
      if(!duplicate)map.get(id).push(s);
    });
    return map;
  }

  function modelPanel(id,rows){
    const c=counts(rows), settled=c.hit+c.miss;
    return `<details class="v80-model-panel" ${id==='adaptive'?'open':''}><summary><div><b>${esc(MODEL_NAMES[id]||id)}</b><small>${rows.length} sygnałów${id==='adaptive'?' · oficjalne':' · learning-only'}</small></div><span>✅ ${c.hit} · ❌ ${c.miss}</span><i>⌄</i></summary><div class="v80-model-body">
      ${rows.length?rows.map(signalRow).join(''):'<p>Brak zapisanych sygnałów.</p>'}
      ${id!=='adaptive'?'<small class="v80-learning-only">Te sygnały służą nauce modelu i nie są doliczane do oficjalnej skuteczności Adaptive.</small>':''}
    </div></details>`;
  }

  function lessonCard(x){
    const delta=num(x?.delta)||0, cls=delta<0?'down':delta>0?'up':'keep';
    return `<article class="v80-lesson ${cls}">
      <header><div><b>${esc(x.label||'Błąd modelu')}</b><small>${esc(MODEL_NAMES[x.source_model]||x.source_model||'Model')}</small></div><span>${delta>0?'+':''}${delta.toFixed(1)} pp</span></header>
      <p><strong>Dlaczego nie weszło:</strong> ${esc(x.why||'Brak dokładniejszych danych do diagnozy.')}</p>
      <div class="v80-score-flow"><span>PRZED <b>${score(x.raw_score)}</b></span><i>→</i><span>PO NAUCE <b>${score(x.learned_score)}</b></span></div>
      <div class="v80-lesson-meta"><span>podobne n=${num(x.similar_n)?.toFixed(1).replace('.0','')||'0'}</span><span>trafność ${pct(x.historical_accuracy)}</span><span>${esc(String(x.evidence||'ZBIERAMY'))}</span></div>
      <p class="v80-conclusion"><strong>Wniosek:</strong> ${esc(x.lesson||'System zapisuje ten przypadek do dalszej walidacji.')}</p>
    </article>`;
  }

  function postMatch(e){
    const app=document.querySelector('#app'); if(!app)return;
    openEntry=e;
    const official=officialSignals(e), c=counts(official), review=e.adaptive_review_v79||{}, lessons=Array.isArray(review.lessons)?review.lessons:[];
    const hits=official.filter(s=>s._result==='hit'), misses=official.filter(s=>s._result==='miss');
    const groups=modelGroups(e);
    app.innerHTML=`<section class="v80-postmatch">
      <header class="v80-post-head"><button type="button" data-v80-back>‹ Historia</button><div><span>RAPORT PO MECZU</span><b>${esc((e.tour||'').toUpperCase())} · ${esc(e.tournament||'—')}</b></div></header>
      <section class="v80-result-hero">
        <div class="v80-match-meta"><span>${esc(e.surface||'—')}</span><span>${esc(dateTime(e.scheduled_time))}</span><span>${esc(e.round||e.round_name||'')}</span></div>
        <div class="v80-matchup"><b>${esc(e.p1)}</b><strong>${esc(finalScore(e))}</strong><b>${esc(e.p2)}</b></div>
        <div class="v80-result-chips"><span class="hit">✅ Trafione ${c.hit}</span><span class="miss">❌ Nietrafione ${c.miss}</span><span>🧠 ${analysisReady(e)?'Analiza gotowa':'Zbieramy wnioski'}</span></div>
      </section>

      <section class="v80-section"><header><div><span>01</span><b>Co weszło</b></div><em>${hits.length}</em></header>${hits.length?`<div class="v80-signal-list">${hits.map(signalRow).join('')}</div>`:'<p class="v80-empty-note">Brak trafionych oficjalnych sygnałów.</p>'}</section>
      <section class="v80-section danger"><header><div><span>02</span><b>Co nie weszło</b></div><em>${misses.length}</em></header>${misses.length?`<div class="v80-signal-list">${misses.map(signalRow).join('')}</div>`:'<p class="v80-empty-note">Brak nietrafionych oficjalnych sygnałów.</p>'}</section>

      <section class="v80-section"><header><div><span>03</span><b>Modele — wynik tego meczu</b></div><em>${groups.size}</em></header>
        <div class="v80-models">${[...groups.entries()].map(([id,rows])=>modelPanel(id,rows)).join('')}</div>
      </section>

      <section class="v80-section learning"><header><div><span>04</span><b>🧠 Dlaczego model się pomylił i czego się uczy</b></div><em>${lessons.length}</em></header>
        ${lessons.length?`<div class="v80-lessons">${lessons.map(lessonCard).join('')}</div>`:'<p class="v80-empty-note">Dla tego meczu nie ma jeszcze zapisanej szczegółowej lekcji Adaptive. Nowsze mecze będą analizowane automatycznie.</p>'}
        <div class="v80-shadow-note"><b>SHADOW</b><span>Wnioski są zbierane i walidowane. Pojedynczy mecz nie może sam zmienić produkcyjnych typów.</span></div>
      </section>

      <details class="v80-technical"><summary>Dane techniczne <i>⌄</i></summary><div>
        <span>Model bazowy <b>${esc(e.model_version||'—')}</b></span>
        <span>Settlement <b>${esc(e.settlement_source||'—')}</b></span>
        <span>Adaptive <b>${esc(review.version||'—')}</b></span>
        <span>Status nauki <b>${esc(review.status||'—')}</b></span>
        <span>Zapis prognozy <b>${esc(dateTime(e.first_captured_at||e.captured_at))}</b></span>
      </div></details>
    </section>`;
    app.querySelector('[data-v80-back]')?.addEventListener('click',()=>renderHistoryV80());
    window.scrollTo({top:0,behavior:'smooth'});
  }

  function bindHistory(){
    const app=document.querySelector('#app'); if(!app)return;
    app.querySelectorAll('[data-v80-history-open]').forEach(b=>b.addEventListener('click',()=>{
      const e=settledRows().find(x=>entryKey(x)===b.dataset.v80HistoryOpen); if(e)postMatch(e);
    }));
    app.querySelectorAll('[data-v80-day]').forEach(d=>d.addEventListener('toggle',()=>{dayState[d.dataset.v80Day]=d.open;saveState(dayState)}));
  }

  function compactHealth(){
    const h=document.querySelector('#v79-health'); if(!h||h.dataset.v80Bound)return;
    h.dataset.v80Bound='1'; h.classList.add('v80-health-compact'); h.setAttribute('role','button'); h.tabIndex=0;
    const toggle=()=>h.classList.toggle('expanded');
    h.addEventListener('click',ev=>{if(ev.target.closest('a,button,input,select'))return;toggle()});
    h.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();toggle()}});
  }
  function compactModels(){
    const s=document.querySelector('#model-switcher'); if(!s||s.dataset.v80Bound)return;
    s.dataset.v80Bound='1';s.classList.add('v80-model-compact');
    const head=s.querySelector('.model-switcher-head'); if(!head)return;
    const b=document.createElement('button');b.type='button';b.className='v80-model-toggle';b.textContent='Modele ▾';
    b.addEventListener('click',ev=>{ev.stopPropagation();s.classList.toggle('expanded');b.textContent=s.classList.contains('expanded')?'Zwiń ▴':'Modele ▾'});
    head.appendChild(b);
  }
  function fixHeader(){
    window.TENIS_AI_APPLY_META?.();
  }
  function tidy(){fixHeader();compactHealth();compactModels()}

  // Canonical History renderer: this script is intentionally loaded last.
  renderHistory=function(){renderHistoryV80()};

  // v8.0.1: no document-wide observer.
  tidy();
  window.addEventListener('load',tidy,{once:true});
  setTimeout(tidy,350);

  window.TENIS_AI_CLEAN_CORE={version:VERSION,renderHistory:renderHistoryV80,openPostMatch:postMatch,tidy};
})();
