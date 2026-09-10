/* Tenis AI — product polish + role split 2026-09-10 */
(()=>{
  'use strict';

  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const n=v=>v==null||v===''||!Number.isFinite(Number(v))?null:Number(v);
  const pct=v=>n(v)==null?'—':`${Number(v).toFixed(1).replace('.0','')}%`;
  const score=v=>n(v)==null?'—':`${Math.round(Number(v))}/100`;
  const root=document.documentElement;
  const app=()=>$('#app');
  let adminCache=null,adminCacheAt=0,renderLock=false;

  function role(){return String(root.dataset.tenisRole||window.tenisAIAccount?.profile?.role||'user').toLowerCase()}
  function isAdmin(){return role()==='admin'}
  function technical(){return isAdmin()&&root.dataset.tenisUiMode==='technical'}
  function currentView(){return String(root.dataset.tenisView||'home')}
  function setHeader(kicker,title,subtitle){
    const a=$('#page-kicker'),b=$('#page-title'),c=$('#page-subtitle'),d=$('#topbar-section');
    if(a)a.textContent=kicker;if(b)b.textContent=title;if(c)c.textContent=subtitle;if(d)d.textContent=title;
  }
  function setOwned(name){
    const el=app();if(!el)return null;
    el.dataset.polishOwned=name;
    return el;
  }
  function clearOwned(){const el=app();if(el)delete el.dataset.polishOwned}

  function mirrorAvatar(){
    const src=$('#account-button .account-button-avatar');
    const dst=$('.mobile-account');
    if(!src||!dst)return;
    const img=$('img',src);
    dst.innerHTML=img?`<img src="${esc(img.getAttribute('src')||'')}" alt="">`:esc(src.textContent||'A');
  }

  function installChrome(){
    $$('.rail-nav [data-view="stats"]').forEach(x=>x.classList.add('legacy-stats-nav'));
    $$('.mobile-nav [data-view="picks"],.mobile-nav [data-view="history"]').forEach(x=>x.classList.add('user-mode-nav'));

    if(!$('.admin-nav-zone')){
      const zone=document.createElement('div');
      zone.className='admin-nav-zone admin-only';
      zone.innerHTML=`<small>PANEL ADMINA</small>
        <button type="button" data-admin-route="admin"><span>⌘</span><b>Centrum modeli</b></button>
        <button type="button" data-admin-route="stats"><span>⌁</span><b>Statystyki modeli</b></button>
        <button type="button" data-admin-action="shadow"><span>◇</span><b>SHADOW Lab</b></button>
        <button type="button" data-admin-action="symphony"><span>♫</span><b>Symfonia 2.0</b></button>`;
      $('.rail-nav')?.insertAdjacentElement('afterend',zone);
    }

    if(!$('#admin-mode-pill')){
      const pill=document.createElement('button');
      pill.id='admin-mode-pill';
      pill.className='admin-mode-pill admin-only';
      pill.type='button';
      pill.innerHTML='<span>USER</span><i></i><b>ADMIN</b>';
      $('.mobile-top-actions')?.prepend(pill);
    }

    const mobile=$('.mobile-nav');
    if(mobile&&!$('.mobile-nav [data-admin-route="admin"]')){
      const account=$('.mobile-nav [data-account-proxy]');
      const admin=document.createElement('button');
      admin.type='button';admin.className='admin-mode-nav admin-only';admin.dataset.adminRoute='admin';
      admin.innerHTML='<span>⌘</span><b>Admin</b>';
      const stats=document.createElement('button');
      stats.type='button';stats.className='admin-mode-nav admin-only';stats.dataset.adminRoute='stats';
      stats.innerHTML='<span>⌁</span><b>Modele</b>';
      mobile.insertBefore(admin,account||null);
      mobile.insertBefore(stats,account||null);
    }

    syncChromeMode();
    mirrorAvatar();
  }

  function syncChromeMode(){
    const tech=technical();
    const desk=$('#tenis-ui-mode-toggle');
    if(desk){
      desk.classList.add('role-switch');
      const b=$('b',desk),s=$('small',desk);
      if(b)b.textContent='Tryb';
      if(s)s.textContent=tech?'ADMIN':'Użytkownik';
      desk.setAttribute('aria-label',tech?'Przełącz na widok użytkownika':'Przełącz na panel admina');
    }
    const pill=$('#admin-mode-pill');
    if(pill){
      pill.classList.toggle('active',tech);
      pill.setAttribute('aria-pressed',tech?'true':'false');
    }
    const start=$('.mobile-nav [data-view="home"] b');
    if(start)start.textContent=tech?'Admin':'Start';
    $$('.admin-nav-zone [data-admin-route]').forEach(b=>b.classList.toggle('active',currentView()===b.dataset.adminRoute));
  }

  function switchMode(){
    if(!isAdmin())return;
    const desktop=$('#tenis-ui-mode-toggle');
    if(desktop){desktop.click();setTimeout(()=>{syncChromeMode();if(technical())renderAdminHome();},0);return}
    const next=technical()?'simple':'technical';
    root.dataset.tenisUiMode=next;
    try{localStorage.setItem('tenis-ai-product-ui-mode',next)}catch{}
    syncChromeMode();
    if(next==='technical')renderAdminHome();else window.TENIS_AI_PROJECT_UI?.navigate?.('home');
  }

  async function safeJson(url,fallback={}){
    try{const r=await fetch(`${url}${url.includes('?')?'&':'?'}v=${Date.now()}`,{cache:'no-store'});return r.ok?await r.json():fallback}catch{return fallback}
  }
  async function loadAdminSnapshot(force=false){
    if(adminCache&&!force&&Date.now()-adminCacheAt<60000)return adminCache;
    const [meta,integrity,playable,symphony,shadow,neuro,dna]=await Promise.all([
      safeJson('data/meta.json',{}),
      safeJson('data/integrity_report_v78a.json',{}),
      safeJson('data/superbet_playable_stats_v912.json',{}),
      safeJson('data/symphony2_stats.json',{}),
      safeJson('data/shadow_stats.json',{}),
      safeJson('data/neuro_shadow_stats_v935.json',{}),
      safeJson('data/player_dna_profile_readiness.json',{})
    ]);
    adminCache={meta,integrity,playable,symphony,shadow,neuro,dna};
    adminCacheAt=Date.now();
    return adminCache;
  }

  function allRows(){try{return Array.isArray(all)?all:[]}catch{return []}}
  function playableCount(){
    const api=window.TENIS_AI_PLAYABLE_UI_V917;
    if(typeof api?.playableSignals!=='function')return 0;
    return allRows().reduce((sum,m)=>{try{return sum+(api.playableSignals(m,100)||[]).length}catch{return sum}},0);
  }
  function metaValue(obj,paths,fallback='—'){
    for(const path of paths){
      let cur=obj;
      for(const k of path.split('.'))cur=cur?.[k];
      if(cur!==undefined&&cur!==null&&cur!=='')return cur;
    }
    return fallback;
  }
  function statusClass(v){
    const s=String(v??'').toLowerCase();
    return /(pass|ok|active|fresh|green|success|prod)/.test(s)?'good':/(fail|error|red|stale|blocked)/.test(s)?'bad':'neutral';
  }

  function adminMetric(label,value,note='',cls=''){
    return `<article class="admin-metric ${cls}"><span>${esc(label)}</span><b>${esc(value)}</b>${note?`<small>${esc(note)}</small>`:''}</article>`;
  }
  function adminTool(icon,title,text,attr){
    return `<button class="admin-tool" type="button" ${attr}><span>${icon}</span><div><b>${esc(title)}</b><small>${esc(text)}</small></div><i>›</i></button>`;
  }

  async function renderAdminHome(){
    if(!technical())return;
    root.dataset.tenisView='admin';root.dataset.tenisRoute='admin';
    setHeader('ADMIN','Centrum modeli','Techniczny kokpit modeli, danych i jakości. Widok użytkownika pozostaje osobno.');
    syncChromeMode();
    const el=setOwned('admin');if(!el)return;
    el.innerHTML='<div class="polish-root admin-loading"><div class="polish-skeleton"></div><div class="polish-skeleton"></div><div class="polish-skeleton"></div></div>';
    const data=await loadAdminSnapshot();
    if(!technical()||currentView()!=='admin')return;
    const meta=data.meta||{};
    const rows=allRows();
    const playable=playableCount()||Number(metaValue(meta,['superbet_playable_v912.signals'],0))||0;
    const integrity=metaValue(meta,['integrity_v78a_status','integrity.status'],metaValue(data.integrity,['status','summary.status'],'—'));
    const profiles=metaValue(meta,['player_intelligence_v85_profiles_built','player_dna_profiles'],metaValue(data.dna,['profiles_ready','ready_profiles','profiles'], '—'));
    const sbMatches=metaValue(meta,['superbet_playable_v912.matches','superbet_matched_matches'],metaValue(data.playable,['matches','matched_matches'],'—'));
    const updated=metaValue(meta,['updated_at','generated_at'],'—');
    const shadowN=metaValue(meta,['shadow_signal_center_v894_matches'],metaValue(data.shadow,['matches','overall.matches'],'—'));
    const symN=metaValue(data.symphony,['matches','overall.matches','settled'],'—');
    const neuroState=metaValue(data.neuro,['status','mode','overall.status'],metaValue(meta,['neuro_shadow_v936_status'],'SHADOW'));

    const rootEl=document.createElement('div');
    rootEl.className='polish-root admin-console';
    rootEl.innerHTML=`
      <section class="admin-banner">
        <div><span>TRYB TECHNICZNY</span><h2>Panel administratora</h2><p>Tu siedzą modele, telemetria, SHADOW, Player DNA, Symfonia i status danych. Zwykły użytkownik tego nie widzi.</p></div>
        <button type="button" data-switch-user>← Widok użytkownika</button>
      </section>
      <div class="admin-metrics">
        ${adminMetric('Mecze w feedzie',String(rows.length),'results.json')}
        ${adminMetric('PLAYABLE',String(playable),'aktualna oferta Superbet','accent')}
        ${adminMetric('Superbet · mecze',String(sbMatches),'dopasowane do oferty')}
        ${adminMetric('Integrity',String(integrity),'kontrola spójności',statusClass(integrity))}
        ${adminMetric('Player Intelligence',String(profiles),'profile zawodników')}
        ${adminMetric('Ostatnia aktualizacja',String(updated).replace('T',' ').slice(0,16),'snapshot danych')}
      </div>
      <section class="admin-section">
        <header><div><small>NARZĘDZIA</small><h3>Silnik i analityka</h3></div></header>
        <div class="admin-tools">
          ${adminTool('⌁','Statystyki modeli','Skuteczność według rynku, touru i siły','data-admin-route="stats"')}
          ${adminTool('♫','Symfonia 2.0','Kompozycje exact-line z bieżącej oferty','data-admin-action="symphony"')}
          ${adminTool('◇','SHADOW Lab',`Odrzucone sygnały i nauka · ${shadowN} meczów`,'data-admin-action="shadow"')}
          ${adminTool('◈','NEURO SHADOW',`Stan warstwy: ${neuroState}`,'data-admin-action="neuro"')}
          ${adminTool('◎','Player DNA','Profile, serwis/return, trajektorie i readiness','data-view="players"')}
          ${adminTool('◷','Historia i settlement','Rozliczenia, raporty po meczach i błędy','data-view="history"')}
        </div>
      </section>
      <section class="admin-system-grid">
        <article class="admin-card"><header><span>SUPERBET</span><b>Warstwa PLAYABLE</b></header>
          <dl><div><dt>Mecze</dt><dd>${esc(sbMatches)}</dd></div><div><dt>Sygnały</dt><dd>${esc(playable)}</dd></div><div><dt>RAW zachowany</dt><dd>${esc(metaValue(meta,['superbet_playable_v912.raw_preserved'],'—'))}</dd></div><div><dt>Status odświeżenia</dt><dd>${esc(metaValue(meta,['superbet_context.refresh_status','superbet_refresh_status'],'—'))}</dd></div></dl>
        </article>
        <article class="admin-card"><header><span>MODELE</span><b>Warstwy eksperymentalne</b></header>
          <dl><div><dt>SHADOW</dt><dd>${esc(shadowN)}</dd></div><div><dt>NEURO</dt><dd>${esc(neuroState)}</dd></div><div><dt>Symfonia</dt><dd>${esc(symN)}</dd></div><div><dt>Produkcja</dt><dd>chroniona gate'ami</dd></div></dl>
        </article>
      </section>
      <details class="admin-raw">
        <summary><span>Surowe metadane systemu</span><b>rozwiń</b></summary>
        <pre>${esc(JSON.stringify({
          updated_at:meta.updated_at,
          fixtures_mode:meta.fixtures_mode,
          history_mode:meta.history_mode,
          integrity_v78a_status:meta.integrity_v78a_status,
          superbet_playable_v912:meta.superbet_playable_v912,
          player_intelligence_v85_profiles_built:meta.player_intelligence_v85_profiles_built,
          shadow_signal_center_v894_matches:meta.shadow_signal_center_v894_matches
        },null,2))}</pre>
      </details>`;
    el.replaceChildren(rootEl);
    bindPolishActions(rootEl);
  }

  function groupRows(obj){
    return Object.entries(obj||{}).sort((a,b)=>(Number(b[1]?.settled)||0)-(Number(a[1]?.settled)||0));
  }
  function statsGroup(title,obj){
    const rows=groupRows(obj);
    if(!rows.length)return '';
    return `<section class="model-stat-card"><header><h3>${esc(title)}</h3><span>${rows.length} pozycji</span></header><div class="model-stat-list">${rows.map(([k,v])=>{
      const acc=n(v?.accuracy),settled=Number(v?.settled||0),hits=Number(v?.hits||0);
      return `<div class="model-stat-row"><div><b>${esc(k)}</b><small>${hits} trafień · ${settled} rozliczonych</small></div><strong>${pct(acc)}</strong><i><span style="width:${acc==null?0:Math.max(0,Math.min(100,acc))}%"></span></i></div>`;
    }).join('')}</div></section>`;
  }

  async function renderAdminStats(){
    if(!technical()){renderRestricted();return}
    root.dataset.tenisView='stats';root.dataset.tenisRoute='stats';
    setHeader('ADMIN · MODELE','Statystyki modeli','Czytelny techniczny widok skuteczności. Bez ściany surowego tekstu.');
    syncChromeMode();
    const el=setOwned('stats');if(!el)return;
    el.innerHTML='<div class="polish-root admin-loading"><div class="polish-skeleton"></div><div class="polish-skeleton"></div></div>';
    try{if(typeof loadSecondaryData==='function')await loadSecondaryData()}catch{}
    if(!technical()||currentView()!=='stats')return;
    let s={};try{s=(typeof statsData!=='undefined'&&statsData)||{}}catch{}
    const o=s.overall||{};
    const rootEl=document.createElement('div');
    rootEl.className='polish-root model-stats-console';
    rootEl.innerHTML=`
      <div class="stats-overview">
        <article class="stats-main-number"><span>SKUTECZNOŚĆ</span><b>${o.accuracy==null?'—':pct(o.accuracy)}</b><small>${o.hits||0} trafień · ${o.settled||0} rozliczonych</small></article>
        ${adminMetric('Śledzone mecze',String(s.matches_tracked||0))}
        ${adminMetric('Oczekują',String(s.matches_pending||0))}
        ${adminMetric('Wyłączone z %',String(s.excluded_signals||0))}
      </div>
      <div class="admin-inline-actions">
        <button data-admin-route="admin">⌘ Centrum modeli</button>
        <button data-admin-action="shadow">◇ SHADOW</button>
        <button data-admin-action="symphony">♫ Symfonia</button>
        <button data-admin-action="neuro">◈ NEURO</button>
      </div>
      <div class="model-stats-grid">
        ${statsGroup('Według rynku',s.by_market)}
        ${statsGroup('Według touru',s.by_tour)}
        ${statsGroup('Według siły sygnału',s.by_score_band)}
      </div>
      <section class="stats-explainer"><b>Jak liczymy?</b><p>Do skuteczności wchodzą tylko sygnały, które można jednoznacznie rozliczyć z końcowego wyniku. Nieweryfikowalne rynki bez game-by-game nie są wciskane do procentu.</p></section>`;
    el.replaceChildren(rootEl);
    bindPolishActions(rootEl);
  }

  function resultIcon(r){return ({hit:'✓',miss:'×',pending:'…',unverifiable:'—',void:'↩'}[r]||'…')}
  function finalScore(e){
    const r=e?.result;if(!r)return 'Oczekuje na wynik';if(r.status==='void')return 'Nierozliczany';
    if(Array.isArray(r.sets)&&r.sets.length)return r.sets.map(s=>Array.isArray(s)?s.join(':'):s).join(' · ');
    return r.score_text||'Zakończony';
  }
  async function renderCleanHistory(){
    root.dataset.tenisView='history';root.dataset.tenisRoute='history';
    setHeader('ARCHIWUM','Historia','Rozliczone mecze i wcześniejsze sygnały w czytelnej formie.');
    clearOwned();
    try{if(typeof loadSecondaryData==='function')await loadSecondaryData()}catch{}
    if(currentView()!=='history')return;
    let rows=[];try{rows=Array.isArray(historyRows)?historyRows:[]}catch{}
    rows=rows.filter(e=>Array.isArray(e?.signals)&&e.signals.length).slice(0,80);
    const el=setOwned('history');if(!el)return;
    const rootEl=document.createElement('div');rootEl.className='polish-root history-clean';
    rootEl.innerHTML=rows.length?`
      <div class="history-summary"><div><span>OSTATNIE MECZE</span><b>${rows.length}</b><small>zapisanych wpisów z sygnałami</small></div><p>Każdy mecz jest osobną kartą. Szczegóły typów rozwijasz tylko wtedy, gdy ich potrzebujesz.</p></div>
      <div class="history-clean-list">${rows.map(e=>{
        const status=e.status==='settled'?'Rozliczony':e.status==='void'?'Nie liczymy':'Oczekuje';
        return `<article class="history-clean-card"><header><div><small>${esc(String(e.tour||'').toUpperCase())} · ${esc(e.tournament||'Turniej')}</small><h3>${esc(e.p1||'—')} <i>vs</i> ${esc(e.p2||'—')}</h3></div><span class="${statusClass(e.status)}">${esc(status)}</span></header>
          <div class="history-final"><span>Wynik</span><b>${esc(finalScore(e))}</b></div>
          <details><summary><span>Sygnały</span><b>${e.signals.length}</b></summary><div class="history-clean-signals">${e.signals.slice(0,20).map(s=>`<div class="${esc(s.result||'pending')}"><i>${resultIcon(s.result)}</i><span><b>${esc(s.label||'Sygnał')}</b><small>${esc(s.pick||'')} ${n(s.score)!=null?'· '+score(s.score):''}</small></span></div>`).join('')}</div></details>
        </article>`;
      }).join('')}</div>`:'<div class="product-empty">Historia nie ma jeszcze rozliczonych wpisów z sygnałami.</div>';
    el.replaceChildren(rootEl);
  }

  function renderRestricted(){
    const el=setOwned('restricted');if(!el)return;
    setHeader('TENIS AI','Statystyki','Techniczne statystyki modeli są dostępne tylko dla administratora.');
    const admin=isAdmin();
    el.innerHTML=`<div class="polish-root restricted-card"><span>🔒</span><h2>Panel techniczny jest oddzielony od aplikacji użytkownika</h2><p>${admin?'Masz konto administratora. Przełącz widok na ADMIN, aby wejść do modeli, SHADOW, telemetrii i statystyk.':'Ten widok nie jest częścią zwykłego interfejsu użytkownika.'}</p>${admin?'<button type="button" data-switch-admin>Przejdź do panelu ADMIN</button>':''}</div>`;
    bindPolishActions(el);
  }

  function polishHome(){
    clearOwned();
    const stat=$('.quick-card[data-view="stats"]');
    if(stat&&!technical()){
      stat.dataset.view='history';
      stat.innerHTML='<span>◷</span><div><b>Historia</b><small>wcześniejsze typy i wyniki</small></div>';
    }
  }

  function bindPolishActions(rootNode=document){
    $$('[data-admin-route]',rootNode).forEach(b=>{
      if(b.dataset.polishBound)return;b.dataset.polishBound='1';
      b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();const r=b.dataset.adminRoute;r==='stats'?renderAdminStats():renderAdminHome()});
    });
    $$('[data-admin-action]',rootNode).forEach(b=>{
      if(b.dataset.polishBound)return;b.dataset.polishBound='1';
      b.addEventListener('click',e=>{
        e.preventDefault();e.stopPropagation();
        const a=b.dataset.adminAction;
        if(a==='symphony')$('#symphony-open')?.click();
        else if(a==='shadow')window.TENIS_AI_SHADOW_LAB?.open?.();
        else if(a==='neuro')$('#neuro-open')?.click();
      });
    });
    $$('[data-switch-user]',rootNode).forEach(b=>b.addEventListener('click',switchMode));
    $$('[data-switch-admin]',rootNode).forEach(b=>b.addEventListener('click',switchMode));
  }

  function syncAfterRender(){
    installChrome();syncChromeMode();
    const v=currentView();
    if(technical()&&v==='home'){renderAdminHome();return}
    if(v==='stats'){technical()?renderAdminStats():renderRestricted();return}
    if(v==='history'){renderCleanHistory();return}
    if(v==='home')polishHome();else clearOwned();
  }

  document.addEventListener('click',e=>{
    if(e.target.closest('#admin-mode-pill')){e.preventDefault();e.stopPropagation();switchMode();return}
    const route=e.target.closest('[data-admin-route]');
    if(route){e.preventDefault();e.stopPropagation();route.dataset.adminRoute==='stats'?renderAdminStats():renderAdminHome();return}
    const action=e.target.closest('[data-admin-action]');
    if(action){
      e.preventDefault();e.stopPropagation();
      const a=action.dataset.adminAction;
      if(a==='symphony')$('#symphony-open')?.click();
      else if(a==='shadow')window.TENIS_AI_SHADOW_LAB?.open?.();
      else if(a==='neuro')$('#neuro-open')?.click();
    }
  },true);

  window.addEventListener('tenis-ai-product-render',()=>setTimeout(syncAfterRender,0));
  window.addEventListener('tenis-ai-auth-change',()=>setTimeout(()=>{installChrome();syncChromeMode();mirrorAvatar();if(technical()&&currentView()==='home')renderAdminHome()},0));

  const mo=new MutationObserver(()=>{
    if(renderLock)return;
    const el=app(),owned=el?.dataset.polishOwned;if(!owned)return;
    const ok=el.children.length===1&&el.firstElementChild?.classList.contains('polish-root');
    if(ok)return;
    renderLock=true;
    queueMicrotask(async()=>{
      try{
        if(owned==='history')await renderCleanHistory();
        else if(owned==='stats')await renderAdminStats();
        else if(owned==='admin')await renderAdminHome();
        else if(owned==='restricted')renderRestricted();
      }finally{renderLock=false}
    });
  });
  const appNode=app();if(appNode)mo.observe(appNode,{childList:true});

  installChrome();
  setTimeout(syncAfterRender,0);

  window.TENIS_AI_PRODUCT_POLISH=Object.freeze({
    version:'2026-09-10.1',
    renderAdmin:renderAdminHome,
    renderStats:renderAdminStats,
    renderHistory:renderCleanHistory,
    switchMode
  });
})();