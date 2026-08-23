/* Tenis AI v7.9A — Adaptive Learning UI */
(() => {
  const VERSION='v7.9A';

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));

  const score=x=>Number.isFinite(Number(x))?`${Number(x).toFixed(1).replace('.0','')}/100`:'N/D';
  const pct=x=>Number.isFinite(Number(x))?`${Number(x).toFixed(1).replace('.0','')}%`:'—';
  const n=x=>Number.isFinite(Number(x))?Number(x).toFixed(1).replace('.0',''):'0';

  function tone(x){
    const d=Number(x?.delta||0);
    if(d<=-2)return 'down';
    if(d>=2)return 'up';
    return 'keep';
  }

  function actionText(x){
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

  function livePanel(m){
    const a=m?.adaptive_learning_v79;
    if(!a||!Array.isArray(a.signals)||!a.signals.length)return '';

    const trained=a.signals
      .filter(x=>x&&Number.isFinite(Number(x.learned_score)))
      .sort((x,y)=>{
        const xe=x.evidence==='COLLECTING'?1:0;
        const ye=y.evidence==='COLLECTING'?1:0;
        if(xe!==ye)return xe-ye;
        return Number(y.learned_score)-Number(x.learned_score);
      })
      .slice(0,6);

    return `
      <section class="v79-live-panel">
        <header>
          <div>
            <b>🧠 Adaptive Learning ${VERSION}</b>
            <small>Bayesian Online Meta‑Learner · uczy się błędów każdego rynku osobno</small>
          </div>
          <span class="v79-shadow-chip">SHADOW</span>
        </header>

        <div class="v79-live-note">
          Nie nadpisuje jeszcze oficjalnego score. Pokazuje, jak historia podobnych przypadków
          skorygowałaby ocenę modelu.
        </div>

        <div class="v79-live-grid">
          ${trained.map(x=>`
            <article class="v79-learning-row ${tone(x)}">
              <div class="v79-learning-title">
                <b>${esc(x.label||x.market||'Sygnał')}</b>
                <span>${esc(String(x.pick||''))}</span>
              </div>
              <div class="v79-score-flow">
                <span>MODEL <b>${score(x.raw_score)}</b></span>
                <i>→</i>
                <span>PO NAUCE <b>${score(x.learned_score)}</b></span>
                <em>${Number(x.delta||0)>0?'+':''}${Number(x.delta||0).toFixed(1)} pp</em>
              </div>
              <div class="v79-learning-meta">
                <span>${actionText(x)}</span>
                <span>${evidenceText(x)}</span>
                <span>podobne n=${n(x.similar_n)}</span>
                <span>trafność ${pct(x.historical_accuracy)}</span>
              </div>
              <p>${esc(x.lesson||'')}</p>
            </article>
          `).join('')}
        </div>
      </section>
    `;
  }

  function reviewHtml(review){
    if(!review||!Array.isArray(review.lessons))return '';
    const misses=Number(review.misses||0);
    const hits=Number(review.hits||0);
    if(!misses&&!hits)return '';

    const mistakes=review.lessons.slice(0,5);
    return `
      <details class="v79-review" ${misses?'open':''}>
        <summary>
          <span>🧠 Analiza po meczu</span>
          <b>${misses?`${misses} błąd/błędy modelu`:'bez wykrytych błędów'}</b>
          <i>⌄</i>
        </summary>
        <div class="v79-review-body">
          <div class="v79-review-summary">
            <span>✅ trafione ${hits}</span>
            <span>❌ nietrafione ${misses}</span>
            <span>TRYB SHADOW</span>
          </div>

          ${mistakes.length?mistakes.map(x=>`
            <article class="v79-mistake ${tone(x)}">
              <header>
                <b>${esc(x.label||'Nietrafiony sygnał')}</b>
                <span>${esc(String(x.pick||''))}</span>
              </header>
              <p class="v79-why"><strong>Dlaczego nie weszło:</strong> ${esc(x.why||'Brak pełnych danych do dokładniejszej diagnozy.')}</p>
              <div class="v79-score-flow">
                <span>PRZED <b>${score(x.raw_score)}</b></span>
                <i>→</i>
                <span>PO NAUCE <b>${score(x.learned_score)}</b></span>
                <em>${Number(x.delta||0)>0?'+':''}${Number(x.delta||0).toFixed(1)} pp</em>
              </div>
              <div class="v79-learning-meta">
                <span>${actionText(x)}</span>
                <span>${evidenceText(x)}</span>
                <span>podobne n=${n(x.similar_n)}</span>
                <span>trafność ${pct(x.historical_accuracy)}</span>
              </div>
              <p class="v79-lesson"><strong>Wniosek:</strong> ${esc(x.lesson||'')}</p>
            </article>
          `).join(''):'<p class="v79-no-mistakes">Ten mecz nie dodał nowego błędu do analizy.</p>'}

          <small class="v79-review-foot">
            System zapisuje wzorzec błędu, ale pojedynczy mecz nie może sam zmienić produkcyjnego modelu.
          </small>
        </div>
      </details>
    `;
  }

  function orderedHistoryRows(){
    let rows=[];
    try{
      rows=(Array.isArray(historyRows)?historyRows:[]).filter(e=>{
        if(!(e?.signals||[]).length)return false;
        if(e.status==='settled'||e.status==='void')return true;
        const t=new Date(e.scheduled_time||'').getTime();
        return Number.isFinite(t)&&t<=Date.now()+5*60*1000;
      }).slice(0,220);
    }catch{return []}

    const localKey=value=>{
      const d=new Date(value||'');
      if(isNaN(d))return 'bez-daty';
      return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    };
    const groups=new Map();
    rows.forEach(e=>{
      const k=localKey(e.scheduled_time);
      if(!groups.has(k))groups.set(k,[]);
      groups.get(k).push(e);
    });
    return [...groups.entries()]
      .sort((a,b)=>b[0].localeCompare(a[0]))
      .flatMap(([,list])=>list);
  }

  function injectHistoryReviews(){
    const app=document.querySelector('#app');
    if(!app)return;
    const cards=[...app.querySelectorAll('.v732-history-card')];
    if(!cards.length)return;
    const rows=orderedHistoryRows();
    cards.forEach((card,i)=>{
      if(card.querySelector('.v79-review'))return;
      const e=rows[i];
      const html=reviewHtml(e?.adaptive_review_v79);
      if(!html)return;
      const scoreEl=card.querySelector('.history-score');
      if(scoreEl)scoreEl.insertAdjacentHTML('afterend',html);
      else card.insertAdjacentHTML('beforeend',html);
    });
  }

  if(typeof renderMatchDetail==='function'){
    const baseRenderMatchDetail=renderMatchDetail;
    renderMatchDetail=function(m){
      return `${baseRenderMatchDetail(m)}${livePanel(m)}`;
    };
  }

  if(typeof renderHistory==='function'){
    const baseRenderHistory=renderHistory;
    renderHistory=function(){
      const value=baseRenderHistory.apply(this,arguments);
      injectHistoryReviews();
      return value;
    };
  }

  window.TENIS_AI_ADAPTIVE_V79={
    version:VERSION,
    livePanel,
    injectHistoryReviews
  };

  if(typeof view!=='undefined'&&view==='history')injectHistoryReviews();
})();
