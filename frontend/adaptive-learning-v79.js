/* Tenis AI v7.9B — Adaptive Learning UI + end-to-end health */
(() => {
  const VERSION='v7.9B';
  const REPORT_URL='data/adaptive_learning_v79.json';

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
  const score=x=>Number.isFinite(Number(x))?`${Number(x).toFixed(1).replace('.0','')}/100`:'N/D';
  const pct=x=>Number.isFinite(Number(x))?`${Number(x).toFixed(1).replace('.0','')}%`:'—';
  const n=x=>Number.isFinite(Number(x))?Number(x).toFixed(1).replace('.0',''):'0';
  const first=(...values)=>values.find(value=>value!==undefined&&value!==null);

  async function safeJson(url,fallback){
    try{
      const r=await fetch(`${url}?v=${Date.now()}`,{cache:'no-store'});
      return r.ok?await r.json():fallback;
    }catch{return fallback}
  }

  function signalView(x){
    const prod=x?.adaptive_prod_v79||{};
    const status=String(first(prod.status,x?.status,prod.evidence,x?.evidence,'COLLECTING')).toUpperCase();
    const evidence=String(first(prod.evidence,x?.evidence,status)).toUpperCase();
    const raw=first(prod.raw_score,x?.raw_score,x?.ensemble_raw);
    const final=first(prod.final_score,x?.final_score,x?.learned_score,raw);
    const delta=first(prod.delta_pp,x?.adaptive_delta_pp,x?.delta,0);
    return {
      ...x,...prod,status,evidence,
      raw_score:raw,final_score:final,learned_score:final,delta,
      cap_pp:first(prod.cap_pp,x?.cap_pp,status==='COLLECTING'?0:undefined),
      applied:first(prod.applied,x?.applied,status!=='COLLECTING'&&Math.abs(Number(delta||0))>0)
    };
  }
  function tone(x){
    const d=Number(x?.delta||0);
    if(d<=-2)return 'down';
    if(d>=2)return 'up';
    return 'keep';
  }
  function actionText(x){
    if(x?.status==='COLLECTING')return 'BEZ WPŁYWU';
    if(x?.action==='downgrade')return 'OBNIŻA';
    if(x?.action==='upgrade')return 'PODNOSI';
    if(x?.action==='keep')return 'UTRZYMUJE';
    return 'ZBIERA DANE';
  }
  function evidenceText(x){
    const e=String(x?.evidence||'COLLECTING').toUpperCase();
    if(e==='STRONG')return 'MOCNA PRÓBKA';
    if(e==='EARLY')return 'WCZESNA PRÓBKA';
    return 'ZBIERAMY';
  }
  function effectText(x){
    if(x?.status==='COLLECTING')return 'RAW ZACHOWANY';
    return x?.applied?'WPŁYW PROD':'BEZ ZMIANY';
  }
  function capText(x){
    return Number.isFinite(Number(x?.cap_pp))?`limit ±${n(x.cap_pp)} pp`:'';
  }
  function policyCap(value,fallback){
    const raw=value&&typeof value==='object'?value.cap_pp:value;
    return Number.isFinite(Number(raw))?Number(raw):fallback;
  }
  function timeText(value){
    const d=new Date(value||'');
    return Number.isFinite(d.getTime())
      ? d.toLocaleString('pl-PL',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})
      : 'brak';
  }

  function livePanel(m){
    const a=m?.adaptive_learning_v79;
    if(!a){
      return `<section class="v79-live-panel v79-live-missing">
        <header><div><b>🧠 Adaptive Learning ${VERSION}</b><small>Brak dekoracji v7.9 dla tego meczu</small></div><span class="v79-state-chip bad">BRAK DANYCH</span></header>
        <div class="v79-live-note">Ten rekord nie ma jeszcze danych Adaptive Learning. Do czasu odświeżenia zachowujemy wynik RAW bez korekty.</div>
      </section>`;
    }

    const trained=(Array.isArray(a.signals)?a.signals:[])
      .map(signalView)
      .filter(x=>x&&Number.isFinite(Number(x.final_score)))
      .sort((x,y)=>{
        const xe=x.status==='COLLECTING'?1:0, ye=y.status==='COLLECTING'?1:0;
        if(xe!==ye)return xe-ye;
        return Number(y.final_score)-Number(x.final_score);
      }).slice(0,6);
    const controlledProd=String(a.mode||trained.find(x=>x.mode)?.mode||'').toUpperCase()==='PROD';
    const policy={
      COLLECTING:policyCap(a.policy?.COLLECTING,0),
      EARLY:policyCap(a.policy?.EARLY,4),
      STRONG:policyCap(a.policy?.STRONG,8)
    };

    return `
      <section class="v79-live-panel">
        <header>
          <div>
            <b>🧠 Adaptive Learning ${VERSION}</b>
            <small>Bayesian Online Meta‑Learner · warstwa ucząca nad modelami</small>
          </div>
          <span class="v79-state-chip ${controlledProd?'prod':'warn'}">${controlledProd?'KONTROLOWANY PROD':'OCZEKUJE NA PROD'}</span>
        </header>

        <div class="v79-live-note">
          ${controlledProd
            ?'<b>STATUS: KONTROLOWANY PROD.</b> Zachowujemy RAW i pokazujemy wynik po Adaptive. Korekta działa wyłącznie w limicie właściwym dla siły próbki.'
            :'<b>STATUS: OCZEKUJE NA ODŚWIEŻENIE PROD.</b> Ten rekord pochodzi ze starszego trybu; wynik RAW pozostaje bez wpływu Adaptive.'}
        </div>

        <div class="v79-policy" aria-label="Limity wpływu Adaptive Learning">
          <span>COLLECTING <b>bez wpływu · ${n(policy.COLLECTING)} pp</b></span>
          <span>EARLY <b>ograniczona korekta · do ±${n(policy.EARLY)} pp</b></span>
          <span>STRONG <b>większa korekta · do ±${n(policy.STRONG)} pp</b></span>
        </div>

        ${trained.length?`<div class="v79-live-grid">
          ${trained.map(x=>`
            <article class="v79-learning-row ${tone(x)}">
              <div class="v79-learning-title">
                <b>${esc(x.label||x.market||'Sygnał')}</b>
                <span>${esc(String(x.pick||''))}</span>
              </div>
              <div class="v79-score-flow">
                <span>RAW <b>${score(x.raw_score)}</b></span>
                <i>→</i>
                <span>PO ADAPTIVE <b>${score(x.final_score)}</b></span>
                <em>${Number(x.delta||0)>0?'+':''}${Number(x.delta||0).toFixed(1)} pp</em>
              </div>
              <div class="v79-learning-meta">
                <span>${actionText(x)}</span>
                <span>${evidenceText(x)}</span>
                <span>${effectText(x)}</span>
                ${capText(x)?`<span>${capText(x)}</span>`:''}
                <span>podobne n=${n(x.similar_n)}</span>
                <span>trafność ${pct(x.historical_accuracy)}</span>
              </div>
              <p>${esc(x.lesson||'')}</p>
            </article>
          `).join('')}
        </div>`:`<div class="v79-live-note">Status COLLECTING: nie ma jeszcze wystarczającej próbki, więc Adaptive nie wpływa na wynik RAW.</div>`}
      </section>
    `;
  }

  function reviewHtml(review){
    if(!review||!Array.isArray(review.lessons))return '';
    const misses=Number(review.misses||0), hits=Number(review.hits||0);
    if(!misses&&!hits)return '';
    const mistakes=review.lessons.slice(0,8).map(signalView);
    return `
      <details class="v79-review" ${misses?'open':''}>
        <summary><span>🧠 Analiza po meczu</span><b>${misses?`${misses} błędów modeli`:'bez wykrytych błędów'}</b><i>⌄</i></summary>
        <div class="v79-review-body">
          <div class="v79-review-summary">
            <span>✅ trafione ${hits}</span><span>❌ nietrafione ${misses}</span><span>ADAPTIVE PROD · LIMITOWANY</span>
          </div>
          ${mistakes.length?mistakes.map(x=>`
            <article class="v79-mistake ${tone(x)}">
              <header><b>${esc(x.label||'Nietrafiony sygnał')}</b><span>${esc(String(x.pick||''))}</span></header>
              <p class="v79-why"><strong>Dlaczego nie weszło:</strong> ${esc(x.why||'Brak pełnych danych do dokładniejszej diagnozy.')}</p>
              <div class="v79-score-flow">
                <span>RAW <b>${score(x.raw_score)}</b></span><i>→</i>
                <span>PO ADAPTIVE <b>${score(x.final_score)}</b></span>
                <em>${Number(x.delta||0)>0?'+':''}${Number(x.delta||0).toFixed(1)} pp</em>
              </div>
              <div class="v79-learning-meta">
                <span>${actionText(x)}</span><span>${evidenceText(x)}</span>
                <span>${effectText(x)}</span>${capText(x)?`<span>${capText(x)}</span>`:''}
                <span>podobne n=${n(x.similar_n)}</span><span>trafność ${pct(x.historical_accuracy)}</span>
              </div>
              <p class="v79-lesson"><strong>Wniosek:</strong> ${esc(x.lesson||'')}</p>
            </article>`).join(''):'<p class="v79-no-mistakes">Ten mecz nie dodał nowego błędu do analizy.</p>'}
          <small class="v79-review-foot">Adaptive stosuje wyłącznie ograniczoną korektę zależną od próbki. Player SH i Accuracy Lab pozostają w SHADOW i nie zmieniają wyniku produkcyjnego.</small>
        </div>
      </details>`;
  }

  function orderedHistoryRows(){
    let rows=[];
    try{
      rows=(Array.isArray(historyRows)?historyRows:[]).filter(e=>{
        const hasSignals=(e?.signals||[]).length||(e?.learning_signals_v79b||[]).length;
        if(!hasSignals)return false;
        if(e.status==='settled'||e.status==='void')return true;
        const t=new Date(e.scheduled_time||'').getTime();
        return Number.isFinite(t)&&t<=Date.now()+5*60*1000;
      }).slice(0,220);
    }catch{return []}
    const localKey=value=>{
      const d=new Date(value||''); if(isNaN(d))return 'bez-daty';
      return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    };
    const groups=new Map();
    rows.forEach(e=>{const k=localKey(e.scheduled_time);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(e)});
    return [...groups.entries()].sort((a,b)=>b[0].localeCompare(a[0])).flatMap(([,list])=>list);
  }

  function injectHistoryReviews(){
    const app=document.querySelector('#app'); if(!app)return;
    const cards=[...app.querySelectorAll('.v732-history-card')]; if(!cards.length)return;
    const rows=orderedHistoryRows();
    cards.forEach((card,i)=>{
      if(card.querySelector('.v79-review'))return;
      const html=reviewHtml(rows[i]?.adaptive_review_v79); if(!html)return;
      const scoreEl=card.querySelector('.history-score');
      if(scoreEl)scoreEl.insertAdjacentHTML('afterend',html); else card.insertAdjacentHTML('beforeend',html);
    });
  }

  // PROJECT UI v7.5+ renders its own detailHtml() and bypasses renderMatchDetail().
  // Remember the clicked match id/key, then inject the adaptive panel into that screen.
  let lastOpenKey=null;
  function rememberOpen(ev){
    const el=ev.target?.closest?.('[data-p751-open]');
    if(el?.dataset?.p751Open){
      try{lastOpenKey=decodeURIComponent(el.dataset.p751Open)}catch{lastOpenKey=el.dataset.p751Open}
    }
  }
  document.addEventListener('click',rememberOpen,true);
  document.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' ')rememberOpen(ev)},true);

  function currentProjectMatch(){
    const bridge=window.TENIS_AI_PROJECT_UI;
    if(lastOpenKey&&bridge?.findMatch){
      try{const m=bridge.findMatch(lastOpenKey);if(m)return m}catch{}
    }
    try{
      const names=[...document.querySelectorAll('.p751-detail-screen .p751-matchup .v762-player-link')]
        .map(x=>String(x.textContent||'').trim()).filter(Boolean);
      if(names.length>=2&&Array.isArray(all)){
        return all.find(m=>String(m?.p1||'').trim()===names[0]&&String(m?.p2||'').trim()===names[1])||null;
      }
    }catch{}
    return null;
  }

  function injectProjectDetail(){
    const screen=document.querySelector('.p751-detail-screen');
    if(!screen||screen.querySelector('.dc87')||screen.querySelector('.v79-live-panel'))return;
    const m=currentProjectMatch(); if(!m)return;
    const html=livePanel(m); if(!html)return;
    const matchup=screen.querySelector('.p751-matchup');
    if(matchup)matchup.insertAdjacentHTML('afterend',html);
    else screen.insertAdjacentHTML('afterbegin',html);
  }

  function healthHtml(meta,report){
    const updated=meta?.adaptive_learning_updated_at||report?.generated_at;
    const hasReport=String(report?.version||'').startsWith('v7.9')&&!!updated;
    const controlledProd=String(report?.mode||'').toUpperCase()==='PROD';
    const ts=new Date(updated||'');
    const ageMin=Number.isFinite(ts.getTime())?(Date.now()-ts.getTime())/60000:null;
    const stale=ageMin!=null&&ageMin>150;
    const state=!hasReport?'BŁĄD':stale?'NIEAKTUALNE':!controlledProd?'OCZEKUJE NA PROD':'AKTYWNY';
    const cls=!hasReport||stale?'bad':controlledProd?'ok':'warn';
    const panelCls=!hasReport||stale?'bad':'';
    const training=report?.training||{};
    const gate=report?.promotion_gate||{};
    const models=Array.isArray(meta?.specialist_learning_models)?meta.specialist_learning_models:[];
    const pending=Number(meta?.specialist_learning_pending_signals||0);
    const repeated=Array.isArray(report?.repeated_errors)?report.repeated_errors.length:Number(meta?.adaptive_learning_repeated_errors||0);
    const current=Number(first(gate.current_official_effective,training.official_effective_rows,0));
    const required=Number(first(gate.required_official_settled,300));
    const settledSources=Object.keys(training.by_source||{});
    const connected=[...new Set([...models,...settledSources])];
    const modelList=connected.length
      ?connected.map(model=>`<i>${esc(model)}</i>`).join('')
      :'<i>oczekują</i>';

    return `<section id="v79-health" class="v79-health ${panelCls}">
      <div class="v79-health-main">
        <div><b>🧠 Adaptive Learning ${VERSION}</b><small>kontrola działania end‑to‑end</small></div>
        <span class="v79-state-chip ${cls}">${state}</span>
        <span class="v79-state-chip ${controlledProd?'prod':'warn'}">${controlledProd?'KONTROLOWANY PROD':'TRYB NIEAKTYWNY'}</span>
      </div>
      <div class="v79-health-grid">
        <span>Ostatnia nauka <b>${esc(timeText(updated))}</b></span>
        <span>Rekordy uczące <b>${n(training.rows)}</b></span>
        <span>Efektywna próbka <b>${n(training.effective_rows)}</b></span>
        <span>Oficjalne <b>${n(current)}/${n(required)}</b></span>
        <span>Wzorce błędów <b>${n(repeated)}</b></span>
        <span class="v79-health-models">Modele podpięte <b class="v79-model-list">${modelList}</b></span>
        <span>Sygnały specjalistów czekające na wynik <b>${n(pending)}</b></span>
      </div>
      <p>${hasReport&&controlledProd&&!stale
        ?'✅ Adaptive działa w kontrolowanym PROD: COLLECTING nie ma wpływu, a EARLY i STRONG stosują tylko ograniczoną korektę. Player SH i Accuracy Lab pozostają w SHADOW.'
        :'⚠️ Brak świeżego raportu w trybie PROD. Do czasu odświeżenia wynik RAW pozostaje bez korekty Adaptive. Player SH i Accuracy Lab nadal działają wyłącznie w SHADOW.'}</p>
    </section>`;
  }

  async function mountHealth(){
    const [meta,report]=await Promise.all([
      safeJson('data/meta.json',{}),
      safeJson(REPORT_URL,{})
    ]);
    document.querySelector('#v79-health')?.remove();
    const anchor=document.querySelector('.status');
    if(anchor)anchor.insertAdjacentHTML('afterend',healthHtml(meta,report));
    requestAnimationFrame(()=>window.TENIS_AI_CLEAN_CORE?.tidy?.());
  }

  if(typeof renderMatchDetail==='function'){
    const baseRenderMatchDetail=renderMatchDetail;
    renderMatchDetail=function(m){return `${baseRenderMatchDetail(m)}${livePanel(m)}`};
  }
  // v8.0.1: v8 History reads adaptive_review_v79 directly.
  // Match Center calls injectProjectDetail explicitly.

  window.TENIS_AI_ADAPTIVE_V79={
    version:VERSION, livePanel, reviewHtml, injectHistoryReviews,
    injectProjectDetail, mountHealth
  };

  mountHealth();
  setTimeout(injectProjectDetail,0);
  if(typeof view!=='undefined'&&view==='history')injectHistoryReviews();
})();
