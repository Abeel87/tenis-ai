/* Tenis AI v7.8E6 — Shadow Lab / Odrzucone */
(() => {
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pc=x=>x==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const sc=x=>x==null?'—':`${Math.round(Number(x))}/100`;
  let current=[],stats={},hist=[];

  async function safeJson(url,fallback){
    try{const r=await fetch(url+'?v='+Date.now());return r.ok?await r.json():fallback}catch{return fallback}
  }
  async function reload(){
    [current,stats,hist]=await Promise.all([
      safeJson('data/shadow_current.json',[]),
      safeJson('data/shadow_stats.json',{}),
      safeJson('data/history.json',[])
    ]);
  }

  const ri=r=>({hit:'✅',miss:'❌',pending:'⏳',void:'↩️',unverifiable:'➖'}[r]||'⏳');
  const rt=r=>({hit:'WESZŁO',miss:'NIE WESZŁO',pending:'OCZEKUJE',void:'VOID',unverifiable:'NIEWERYF.'}[r]||'OCZEKUJE');

  function statCard(label,data){
    const d=data||{};
    return `<article class="sl78-stat"><span>${esc(label)}</span><b>${d.accuracy==null?'—':pc(d.accuracy)}</b><small>${d.hits||0} ✅ · ${d.misses||0} ❌ · n=${d.settled||0}</small></article>`;
  }

  function currentCard(x){
    const weak=x.signals||[],noData=!x.model_ready;
    return `<article class="sl78-card ${noData?'nodata':''}">
      <header><span>${esc((x.tour||'').toUpperCase())} · ${esc(x.tournament||'—')}</span><b>${noData?'BRAK DANYCH':'SHADOW'}</b></header>
      <h3>${esc(x.p1)} <i>vs</i> ${esc(x.p2)}</h3>
      <p>${esc(x.rejection_reason||'Odrzucone przez filtr.')}</p>
      ${noData?`<div class="sl78-samples"><span>${esc(x.p1)} <b>n=${x.p1_matches??'—'} · ${esc(x.p1_quality||'LOW')}</b></span><span>${esc(x.p2)} <b>n=${x.p2_matches??'—'} · ${esc(x.p2_quality||'LOW')}</b></span></div>`:
      `<div class="sl78-signals">${weak.slice(0,8).map(s=>`<div><span>${esc(s.label)}</span><b>${esc(s.pick)} · ${sc(s.score)}</b></div>`).join('')}</div>`}
      <footer>${x.scheduled_time?new Date(x.scheduled_time).toLocaleString('pl-PL'):''}</footer>
    </article>`;
  }

  function histCard(e){
    const rows=e.shadow_signals||[];
    const final=e.result?.status==='retired'?'KRECZ':e.status==='settled'?'ROZLICZONY':e.status==='void'?'VOID':'OCZEKUJE';
    return `<article class="sl78-card history">
      <header><span>${esc((e.tour||'').toUpperCase())} · ${esc(e.tournament||'—')}</span><b>${final}</b></header>
      <h3>${esc(e.p1)} <i>vs</i> ${esc(e.p2)}</h3>
      <div class="sl78-signals">${rows.map(s=>`<div class="${esc(s.result||'pending')}"><span>${ri(s.result)} ${esc(s.label)}</span><b>${esc(s.pick)} · ${sc(s.score)} · ${rt(s.result)}</b></div>`).join('')}</div>
    </article>`;
  }

  function grouped(obj){
    const rows=Object.entries(obj||{});
    if(!rows.length)return '';
    return `<div class="sl78-groups">${rows.map(([k,v])=>`<div><span>${esc(k)}</span><b>${v.accuracy==null?'—':pc(v.accuracy)}</b><small>${v.hits||0}/${v.settled||0}</small></div>`).join('')}</div>`;
  }

  function renderShadow(){
    try{view='shadow'}catch{}
    const mc=document.querySelector('#match-controls');if(mc)mc.style.display='none';
    const app=document.querySelector('#app');if(!app)return;
    const o=stats.overall||{},history=hist.filter(e=>(e.shadow_signals||[]).length).slice(0,60);
    app.innerHTML=`<section class="sl78-hero">
      <div><span>🧪 SHADOW LAB v7.8E6</span><b>Odrzucone sygnały też pracują</b><p>Zakres 55–71/100 jest śledzony osobno. Nigdy nie miesza się z oficjalną skutecznością zielonych typów.</p></div>
      <div class="sl78-badges"><span>Śledzone mecze <b>${stats.matches_tracked||0}</b></span><span>Czeka <b>${stats.matches_pending||0}</b></span><span>Cel nauki <b>${o.settled||0}/${stats.learning_target_sample||300}</b></span></div>
    </section>
    <div class="sl78-stat-grid">${statCard('Odrzucone · rozliczone',o)}${statCard('68–71',stats.by_score_band?.['68–71'])}${statCard('65–67',stats.by_score_band?.['65–67'])}</div>
    <section class="sl78-note ${stats.learning_ready?'ready':''}"><b>${stats.learning_ready?'✅ Próbka gotowa pod etap Adaptive Learning':'📥 Na razie zbieramy dane'}</b><span>${stats.learning_ready?'Mamy minimalną próbkę do testowania zmian progów i wag.':'Logika samouczenia nie zmienia jeszcze modelu. Najpierw chcemy zebrać min. 300 rozliczalnych sygnałów.'}</span></section>
    <section class="sl78-section"><header><div><b>🎯 Odrzucone teraz</b><small>Słabszy sygnał albo brak wystarczających danych</small></div><span>${current.length}</span></header>
      <div class="sl78-list">${current.length?current.slice(0,120).map(currentCard).join(''):'<div class="sl78-empty">Brak aktualnych odrzuconych meczów.</div>'}</div>
    </section>
    <section class="sl78-section"><header><div><b>📈 Co odrzuciliśmy — jak wyszło</b><small>osobna kalibracja Shadow Lab</small></div><span>${o.settled||0} sygnałów</span></header>
      ${grouped(stats.by_score_band)}
      <details class="sl78-history"><summary>Ostatnie mecze Shadow (${history.length})</summary><div class="sl78-list">${history.map(histCard).join('')}</div></details>
    </section>`;
    activateNav();
  }

  function activateNav(){
    document.querySelectorAll('#p751-bottom-nav [data-p751-nav]').forEach(b=>b.classList.toggle('active',b.dataset.p751Nav==='shadow'));
  }

  function restoreShell(target='matches'){
    const mc=document.querySelector('#match-controls');
    if(mc)mc.style.display='';

    const p=document.querySelector('.brand-copy p');
    if(p)p.textContent='Tenis AI v7.8D · Calibration Guard';

    try{
      view=target==='history'?'history':'matches';
    }catch{}
  }

  async function openShadow(){
    try{view='shadow'}catch{}
    await reload();
    renderShadow();
  }

  function ensureNav(){
    const nav=document.querySelector('#p751-bottom-nav');
    if(!nav)return;

    if(!nav.dataset.shadowLeaveBound){
      nav.dataset.shadowLeaveBound='1';

      nav.addEventListener('click',e=>{
        const b=e.target.closest('[data-p751-nav]');
        if(!b||b.dataset.p751Nav==='shadow')return;
        restoreShell(b.dataset.p751Nav);
      },true);
    }

    if(nav.querySelector('[data-p751-nav="shadow"]'))return;

    const b=document.createElement('button');
    b.dataset.p751Nav='shadow';
    b.innerHTML='<span>🧪</span><b>Odrzucone</b>';

    const h=nav.querySelector('[data-p751-nav="history"]');
    nav.insertBefore(b,h||null);

    b.onclick=openShadow;
  }

  const oldRender=typeof render==='function'?render:null;
  if(oldRender){
    render=function(){
      if(typeof view!=='undefined'&&view==='shadow'){renderShadow();return}
      return oldRender();
    };
  }

  window.TENIS_AI_SHADOW_LAB={reload,render:renderShadow,open:openShadow};
  reload();
  setTimeout(ensureNav,50);setTimeout(ensureNav,350);setTimeout(ensureNav,1200);
  setInterval(ensureNav,5000);
})();
