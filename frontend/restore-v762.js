/* Tenis AI v7.6.2 — UI restore + player click hotfix
   v8.8.24 runtime cleanup: explicit render/stats hooks replace app observer.
*/
(() => {
  const RUNTIME_FIX='v8.8.24';
  const WRAP_KEY='__v762RestoreWrapped';
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];

  function openPlayer(name){
    name=String(name||'').trim();
    if(!name)return;

    const overlay=$('#p751-match-overlay');
    window.TENIS_AI_PLAYER_PROFILE_RETURN_KEY = overlay && !overlay.hidden ? String(overlay.dataset.matchKey||'') : '';
    const close=$('#p751-match-overlay [data-p751-close]');
    if(close) close.click();

    if(typeof window.tenisAIPlayerProfileOpen==='function'){
      window.tenisAIPlayerProfileOpen(name);
    }else{
      const inp=$('#player-search-input');
      if(!inp)return;
      inp.value=name;
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
    }

    setTimeout(()=>{
      const pro=$('#player-analytics-v76');
      (pro||$('#player-profile-panel'))?.scrollIntoView({behavior:'smooth',block:'start'});
    },220);
  }

  document.addEventListener('click',e=>{
    const el=e.target.closest?.('.v762-player-link');
    if(!el)return;
    e.preventDefault();
    e.stopPropagation();
    if(typeof e.stopImmediatePropagation==='function')e.stopImmediatePropagation();
    openPlayer(el.textContent);
  },true);

  document.addEventListener('keydown',e=>{
    if(e.key!=='Enter'&&e.key!==' ')return;
    const el=e.target.closest?.('.v762-player-link');
    if(!el)return;
    e.preventDefault();
    e.stopPropagation();
    openPlayer(el.textContent);
  },true);

  function ensureStatsBack(){
    const app=$('#app');
    if(!app||$('#v762-stats-back',app))return;
    const statsReady=$('#pc77',app)||$('#pc882-dashboard',app);
    if(!statsReady)return;
    const head=document.createElement('div');
    head.id='v762-stats-back';
    head.className='v762-stats-head';
    head.innerHTML='<button type="button">‹ Mecze</button><div><b>📊 Statystyki / skuteczność modelu</b><small>zielone sygnały + walidacja PBP</small></div>';
    app.prepend(head);
    $('button',head).onclick=backMatches;
  }

  function openStats(){
    const b=$('.main-tabs [data-view="stats"]');
    if(!b)return;
    b.click();
    $$('#p751-bottom-nav button').forEach(x=>x.classList.remove('active'));
  }

  function backMatches(){
    const b=$('.main-tabs [data-view="matches"]');
    if(b)b.click();
  }

  function collapseAll(open){
    $$('.p751-group').forEach(d=>d.open=open);
  }

  function decorateHome(){
    const app=$('#app');
    if(!app||$('#v762-home-tools',app))return;
    const groups=$('.p751-groups',app);
    const focus=$('.p751-focus',app);
    const empty=$('.p751-empty',app);
    if(!groups&&!focus&&!empty)return;

    const bar=document.createElement('div');
    bar.id='v762-home-tools';
    bar.className='v762-home-tools';
    bar.innerHTML=`
      <button type="button" data-v762="collapse" ${groups?'':'disabled'}>− Zwiń wszystko</button>
      <button type="button" data-v762="expand" ${groups?'':'disabled'}>+ Rozwiń wszystko</button>
      <button type="button" class="stats" data-v762="stats">📊 Statystyki / skuteczność</button>`;

    const anchor=groups||empty;
    if(anchor)anchor.insertAdjacentElement('beforebegin',bar);
    else if(focus)focus.insertAdjacentElement('afterend',bar);
    else app.prepend(bar);

    $('[data-v762="collapse"]',bar).onclick=()=>collapseAll(false);
    $('[data-v762="expand"]',bar).onclick=()=>collapseAll(true);
    $('[data-v762="stats"]',bar).onclick=openStats;
  }

  function decoratePlayerNames(){
    $$('.p751-names > b, .p751-matchup > b').forEach(el=>{
      el.classList.add('v762-player-link');
      el.setAttribute('role','link');
      el.setAttribute('tabindex','0');
      el.setAttribute('title','Otwórz profil zawodnika');
    });
  }

  let busy=false;
  function refresh(){
    if(busy)return;
    busy=true;
    try{
      decorateHome();
      decoratePlayerNames();
    }finally{busy=false}
  }

  function wrapRenderMatches(){
    const current=window.renderMatches;
    if(typeof current!=='function'||current[WRAP_KEY])return false;
    const wrapped=function(...args){
      const result=current.apply(this,args);
      refresh();
      return result;
    };
    Object.defineProperty(wrapped,WRAP_KEY,{value:true});
    window.renderMatches=wrapped;
    return true;
  }

  wrapRenderMatches();
  requestAnimationFrame(refresh);
  document.addEventListener('tenis-ai:stats-ready',()=>requestAnimationFrame(ensureStatsBack));
  document.addEventListener('tenis-ai:stats-dashboard-ready',()=>requestAnimationFrame(ensureStatsBack));

  window.TENIS_AI_RESTORE_V762=Object.freeze({
    runtimeFix:RUNTIME_FIX,
    refresh,
    decorateHome,
    ensureStatsBack,
    wrapRenderMatches
  });
})();