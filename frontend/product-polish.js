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

  const STYLE=`
  /* role split */
  .legacy-stats-nav{display:none!important}
  .admin-nav-zone{margin:14px 0 0;padding:14px 0 0;border-top:1px solid var(--line-soft);display:none;gap:5px}
  .admin-nav-zone>small{padding:0 13px 7px;color:var(--mint);font-size:8px;font-weight:900;letter-spacing:.16em}
  .admin-nav-zone button{width:100%;display:flex;align-items:center;gap:12px;border:0;border-radius:13px;padding:11px 13px;background:transparent;color:var(--muted);text-align:left}
  .admin-nav-zone button span{width:24px;text-align:center}.admin-nav-zone button b{font-size:12px}.admin-nav-zone button:hover,.admin-nav-zone button.active{background:rgba(87,239,178,.08);color:var(--text)}
  html[data-tenis-role="admin"][data-tenis-ui-mode="technical"] .admin-nav-zone{display:grid}
  .admin-mode-pill{display:none;align-items:center;gap:5px;border:1px solid var(--line);border-radius:999px;background:#0b1923;padding:5px 7px;color:var(--muted);font-size:8px;font-weight:900;letter-spacing:.04em}
  .admin-mode-pill i{width:7px;height:7px;border-radius:50%;background:var(--muted-2)}.admin-mode-pill b{color:var(--muted-2)}
  .admin-mode-pill.active{border-color:rgba(87,239,178,.42);background:rgba(87,239,178,.08)}.admin-mode-pill.active i{background:var(--mint);box-shadow:0 0 10px rgba(87,239,178,.55)}.admin-mode-pill.active b{color:var(--mint)}.admin-mode-pill.active span{color:var(--muted-2)}
  .admin-mode-nav{display:none!important}
  html[data-tenis-role="admin"][data-tenis-ui-mode="technical"] .mobile-nav .user-mode-nav{display:none!important}
  html[data-tenis-role="admin"][data-tenis-ui-mode="technical"] .mobile-nav .admin-mode-nav{display:grid!important}
  html[data-tenis-role="admin"] .admin-mode-pill{display:flex}

  /* shared polish */
  .polish-root{width:100%}.product-footer{display:flex;justify-content:space-between;gap:16px;margin-top:28px;padding:18px 2px 0;border-top:1px solid var(--line-soft);color:var(--muted-2);font-size:10px}.product-footer span{font-weight:800;color:var(--muted)}
  .restricted-card{max-width:620px;margin:20px auto;padding:30px;border:1px solid var(--line);border-radius:24px;background:var(--panel);text-align:center}.restricted-card>span{font-size:30px}.restricted-card h2{margin:12px 0 8px;font-size:23px}.restricted-card p{margin:0 auto 20px;max-width:500px;color:var(--muted);line-height:1.6}.restricted-card button{border:0;border-radius:13px;padding:11px 14px;background:linear-gradient(135deg,var(--mint),var(--lime));color:#082118;font-weight:850}

  /* admin console */
  .admin-console{display:grid;gap:14px}.admin-banner{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;padding:25px;border:1px solid rgba(87,239,178,.22);border-radius:24px;background:linear-gradient(135deg,rgba(87,239,178,.09),rgba(12,26,37,.92))}
  .admin-banner span{color:var(--mint);font-size:9px;font-weight:900;letter-spacing:.16em}.admin-banner h2{margin:6px 0 7px;font-size:29px;letter-spacing:-.04em}.admin-banner p{max-width:700px;margin:0;color:var(--muted);font-size:12px;line-height:1.5}.admin-banner button{flex:0 0 auto;border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:10px 13px;font-size:11px;font-weight:800}
  .admin-metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}.admin-metric{min-width:0;display:flex;flex-direction:column;gap:5px;border:1px solid var(--line-soft);border-radius:17px;background:var(--panel);padding:14px}.admin-metric span{color:var(--muted);font-size:8px;text-transform:uppercase;letter-spacing:.08em}.admin-metric b{font-size:20px;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.admin-metric small{color:var(--muted-2);font-size:8px}.admin-metric.accent b,.admin-metric.good b{color:var(--lime)}.admin-metric.bad b{color:var(--danger)}
  .admin-section,.admin-card,.admin-raw,.model-stat-card,.stats-explainer{border:1px solid var(--line-soft);border-radius:20px;background:var(--panel)}.admin-section{padding:18px}.admin-section>header{margin-bottom:12px}.admin-section>header small{color:var(--mint);font-size:8px;font-weight:900;letter-spacing:.14em}.admin-section>header h3{margin:3px 0 0;font-size:18px}.admin-tools{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.admin-tool{display:grid;grid-template-columns:38px minmax(0,1fr) 18px;align-items:center;gap:10px;border:1px solid var(--line-soft);border-radius:15px;background:rgba(255,255,255,.02);padding:13px;text-align:left}.admin-tool:hover{border-color:#355866;background:rgba(87,239,178,.04)}.admin-tool>span{display:grid;place-items:center;width:38px;height:38px;border-radius:12px;background:rgba(87,239,178,.08);color:var(--mint);font-size:17px}.admin-tool div{display:grid;gap:2px}.admin-tool b{font-size:12px}.admin-tool small{color:var(--muted);font-size:9px}.admin-tool>i{font-style:normal;color:var(--muted-2);font-size:18px}
  .admin-system-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.admin-card{padding:18px}.admin-card header{display:grid;gap:2px;margin-bottom:12px}.admin-card header span{color:var(--mint);font-size:8px;font-weight:900;letter-spacing:.13em}.admin-card header b{font-size:15px}.admin-card dl{display:grid;gap:1px;margin:0;background:var(--line-soft)}.admin-card dl div{display:flex;justify-content:space-between;gap:14px;background:var(--panel);padding:9px 0}.admin-card dt{color:var(--muted);font-size:10px}.admin-card dd{margin:0;font-size:10px;font-weight:800;text-align:right}
  .admin-raw{overflow:hidden}.admin-raw summary{display:flex;justify-content:space-between;padding:14px 16px;cursor:pointer}.admin-raw summary span{font-size:11px;font-weight:800}.admin-raw summary b{font-size:9px;color:var(--muted)}.admin-raw pre{max-height:360px;overflow:auto;margin:0;padding:16px;border-top:1px solid var(--line-soft);background:#061019;color:#9fb7c0;font-size:9px;line-height:1.55;white-space:pre-wrap;word-break:break-word}
  .admin-loading{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.polish-skeleton{height:120px;border-radius:18px;background:linear-gradient(90deg,var(--panel),var(--panel-2),var(--panel));background-size:220% 100%;animation:polishPulse 1.3s linear infinite}@keyframes polishPulse{to{background-position:-220% 0}}

  /* model stats */
  .model-stats-console{display:grid;gap:12px}.stats-overview{display:grid;grid-template-columns:1.4fr repeat(3,1fr);gap:8px}.stats-main-number{display:flex;flex-direction:column;justify-content:center;border:1px solid rgba(87,239,178,.22);border-radius:19px;background:linear-gradient(135deg,rgba(87,239,178,.08),var(--panel));padding:18px}.stats-main-number span{color:var(--mint);font-size:8px;font-weight:900;letter-spacing:.13em}.stats-main-number b{margin:4px 0;font-size:38px;color:var(--lime);letter-spacing:-.05em}.stats-main-number small{color:var(--muted);font-size:9px}.admin-inline-actions{display:flex;gap:7px;overflow:auto;scrollbar-width:none}.admin-inline-actions button{flex:0 0 auto;border:1px solid var(--line-soft);border-radius:11px;background:var(--panel);padding:9px 11px;font-size:10px;font-weight:800}
  .model-stats-grid{display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px;align-items:start}.model-stat-card{overflow:hidden}.model-stat-card>header{display:flex;justify-content:space-between;align-items:center;padding:14px 15px;border-bottom:1px solid var(--line-soft)}.model-stat-card h3{margin:0;font-size:13px}.model-stat-card header span{color:var(--muted);font-size:8px}.model-stat-list{display:grid}.model-stat-row{display:grid;grid-template-columns:minmax(0,1fr) 54px;gap:9px;padding:11px 14px;border-bottom:1px solid var(--line-soft)}.model-stat-row:last-child{border-bottom:0}.model-stat-row div{display:grid;gap:2px}.model-stat-row b{font-size:10px;word-break:break-word}.model-stat-row small{color:var(--muted-2);font-size:8px}.model-stat-row strong{justify-self:end;color:var(--lime);font-size:12px}.model-stat-row>i{grid-column:1/-1;height:3px;border-radius:999px;background:#132733;overflow:hidden}.model-stat-row>i span{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,var(--mint),var(--lime))}.stats-explainer{padding:15px}.stats-explainer b{font-size:11px}.stats-explainer p{margin:5px 0 0;color:var(--muted);font-size:10px;line-height:1.5}

  /* clean history */
  .history-clean{display:grid;gap:12px}.history-summary{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:18px;border:1px solid var(--line-soft);border-radius:19px;background:var(--panel)}.history-summary>div{display:grid;grid-template-columns:auto auto;align-items:end;column-gap:8px}.history-summary span{grid-column:1/-1;color:var(--mint);font-size:8px;font-weight:900;letter-spacing:.12em}.history-summary b{font-size:30px}.history-summary small{color:var(--muted);font-size:9px;padding-bottom:5px}.history-summary p{max-width:480px;margin:0;color:var(--muted);font-size:10px;line-height:1.5}
  .history-clean-list{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}.history-clean-card{border:1px solid var(--line-soft);border-radius:18px;background:var(--panel);overflow:hidden}.history-clean-card>header{display:flex;justify-content:space-between;gap:12px;padding:15px 15px 10px}.history-clean-card header small{color:var(--muted-2);font-size:8px;text-transform:uppercase}.history-clean-card h3{margin:4px 0 0;font-size:12px}.history-clean-card h3 i{font-style:normal;color:var(--muted-2);font-weight:400}.history-clean-card header>span{height:max-content;border:1px solid var(--line);border-radius:999px;padding:4px 7px;font-size:7px;font-weight:850;text-transform:uppercase}.history-clean-card header>span.good{color:var(--good);border-color:rgba(116,239,155,.25)}.history-clean-card header>span.bad{color:var(--danger)}.history-final{display:flex;justify-content:space-between;align-items:center;margin:0 15px 12px;padding:10px 11px;border-radius:12px;background:rgba(255,255,255,.025)}.history-final span{color:var(--muted);font-size:9px}.history-final b{font-size:11px}.history-clean-card details{border-top:1px solid var(--line-soft)}.history-clean-card details summary{display:flex;justify-content:space-between;padding:11px 15px;cursor:pointer}.history-clean-card details summary span{font-size:9px;font-weight:750}.history-clean-card details summary b{color:var(--mint);font-size:10px}.history-clean-signals{display:grid;gap:1px;background:var(--line-soft)}.history-clean-signals>div{display:grid;grid-template-columns:20px minmax(0,1fr);gap:7px;background:var(--panel);padding:9px 14px}.history-clean-signals i{font-style:normal;font-weight:900}.history-clean-signals .hit i{color:var(--good)}.history-clean-signals .miss i{color:var(--danger)}.history-clean-signals span{display:grid;gap:1px}.history-clean-signals b{font-size:9px}.history-clean-signals small{color:var(--muted);font-size:8px}

  /* account */
  .account-head{padding-right:40px}.account-head h2{margin:0 0 5px;font-size:21px}.account-head p{margin:0 0 17px;color:var(--muted);font-size:11px;line-height:1.5}.account-profile-card{display:grid;gap:14px}.account-profile-main{display:flex;align-items:center;gap:14px;padding:15px;border:1px solid var(--line-soft);border-radius:17px;background:var(--panel)}.account-profile-avatar{flex:0 0 70px;width:70px;height:70px;display:grid;place-items:center;border-radius:20px;overflow:hidden;background:linear-gradient(135deg,var(--mint),var(--cyan));color:#062019;font-size:20px;font-weight:900}.account-profile-avatar img,.account-button-avatar img,.mobile-account img{width:100%!important;height:100%!important;object-fit:cover!important;border-radius:inherit!important}.account-profile-main h3{margin:0 0 3px;font-size:18px}.account-profile-main p{margin:0;color:var(--muted);font-size:10px;word-break:break-all}.account-profile-meta{display:grid;grid-template-columns:1fr 1fr;gap:8px}.account-profile-meta>div{display:grid;gap:3px;border:1px solid var(--line-soft);border-radius:14px;background:var(--panel);padding:12px}.account-profile-meta span{color:var(--muted);font-size:8px}.account-profile-meta b{font-size:11px}.account-coming{border:1px solid var(--line-soft);border-radius:14px;background:rgba(87,239,178,.035);padding:12px;color:var(--muted);font-size:9px;line-height:1.5}.account-secondary,.account-primary{width:100%;border-radius:12px!important;padding:11px!important;font-weight:800}.account-primary{background:linear-gradient(135deg,var(--mint),var(--lime))!important;color:#082118!important}.account-auth-tabs{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:12px}.account-auth-tabs button{padding:9px}.account-auth-tabs button.active{border-color:rgba(87,239,178,.35);background:rgba(87,239,178,.08)}.account-form{display:grid;gap:10px}.account-form label{display:grid;gap:5px;color:var(--muted);font-size:9px}.account-message{margin-top:10px;padding:10px;border-radius:11px;background:var(--panel);font-size:9px}.account-message.error{color:var(--danger)}.account-message.ok{color:var(--good)}

  /* Symphony 2.0 — canonical overlay */
  .s2-hub{position:fixed!important;z-index:4100!important;inset:0!important;overflow:auto!important;background:rgba(4,10,16,.96)!important;backdrop-filter:blur(18px)!important;padding:18px!important;color:var(--text)!important}.s2-hub[hidden]{display:none!important}.s2-hub-frame{width:min(1040px,100%)!important;margin:0 auto!important;min-height:calc(100vh - 36px)!important;border:1px solid var(--line)!important;border-radius:24px!important;background:#08151f!important;box-shadow:var(--shadow)!important;overflow:hidden!important}.s2-hub-top{position:sticky!important;top:0!important;z-index:3!important;display:flex!important;justify-content:space-between!important;align-items:center!important;padding:14px 17px!important;border-bottom:1px solid var(--line-soft)!important;background:rgba(8,21,31,.92)!important;backdrop-filter:blur(16px)!important}.s2-hub-top>div{display:grid!important;gap:2px!important}.s2-hub-top b{font-size:13px!important}.s2-hub-top small{color:var(--muted)!important;font-size:8px!important}.s2-hub-top button{width:36px!important;height:36px!important;border:1px solid var(--line)!important;border-radius:11px!important;background:var(--panel)!important;color:var(--text)!important}.s2-hub-body{padding:18px!important}.s2-shell{display:grid!important;gap:12px!important}.s2-hero{padding:19px!important;border:1px solid rgba(87,239,178,.18)!important;border-radius:19px!important;background:linear-gradient(135deg,rgba(87,239,178,.07),var(--panel))!important}.s2-kicker{color:var(--mint)!important;font-size:8px!important;font-weight:900!important;letter-spacing:.14em!important}.s2-hero h2{margin:5px 0 7px!important;font-size:26px!important}.s2-hero p{margin:0!important;max-width:820px!important;color:var(--muted)!important;font-size:10px!important;line-height:1.55!important}.s2-status{display:grid!important;grid-template-columns:repeat(3,1fr)!important;gap:7px!important}.s2-stat{display:grid!important;gap:4px!important;border:1px solid var(--line-soft)!important;border-radius:14px!important;background:var(--panel)!important;padding:12px!important}.s2-stat small{color:var(--muted)!important;font-size:8px!important}.s2-stat strong{font-size:13px!important}.s2-controls{display:grid!important;grid-template-columns:1fr 1fr auto!important;gap:7px!important;align-items:end!important;padding:12px!important;border:1px solid var(--line-soft)!important;border-radius:16px!important;background:var(--panel)!important}.s2-controls label{display:grid!important;gap:4px!important;color:var(--muted)!important;font-size:8px!important}.s2-controls select{border:1px solid var(--line)!important;border-radius:10px!important;background:#091722!important;color:var(--text)!important;padding:9px!important}.s2-generate{border:0!important;border-radius:11px!important;background:linear-gradient(135deg,var(--mint),var(--lime))!important;color:#072018!important;padding:10px 13px!important;font-weight:850!important}.s2-grid{display:grid!important;grid-template-columns:1fr 1fr!important;gap:9px!important}.s2-card{border:1px solid var(--line-soft)!important;border-radius:17px!important;background:var(--panel)!important;overflow:hidden!important}.s2-head{display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;gap:10px!important;padding:14px!important;border-bottom:1px solid var(--line-soft)!important}.s2-head small,.s2-muted{color:var(--muted)!important;font-size:8px!important}.s2-head h3{margin:4px 0!important;font-size:12px!important}.s2-head h3 span{color:var(--muted-2)!important;font-weight:400!important}.s2-score{text-align:right!important}.s2-score strong{display:block!important;color:var(--lime)!important;font-size:19px!important}.s2-leg{display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;gap:8px!important;padding:11px 14px!important;border-bottom:1px solid var(--line-soft)!important}.s2-leg>div:first-child{display:grid!important;gap:2px!important}.s2-leg strong{font-size:10px!important}.s2-leg small{color:var(--muted)!important;font-size:7px!important;line-height:1.4!important}.s2-prob{color:var(--lime)!important;font-size:11px!important;font-weight:850!important}.s2-joint{display:grid!important;grid-template-columns:1fr auto!important;gap:3px 8px!important;padding:11px 14px!important;background:rgba(87,239,178,.035)!important}.s2-joint span{color:var(--muted)!important;font-size:8px!important}.s2-joint strong{color:var(--mint)!important;font-size:12px!important}.s2-joint small{grid-column:1/-1;color:var(--muted-2)!important;font-size:7px!important}.s2-empty{padding:20px!important;border:1px dashed var(--line)!important;border-radius:15px!important;background:var(--panel)!important;color:var(--muted)!important;font-size:10px!important;line-height:1.5!important}html.s2-hub-open body{overflow:hidden!important}

  /* Shadow Lab inside admin */
  .sl78-inline-view{display:grid;gap:10px}.sl78-inline-summary{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;padding:16px;border:1px solid rgba(87,239,178,.16);border-radius:18px;background:var(--panel)}.sl78-inline-summary>div:first-child{display:grid;gap:3px}.sl78-inline-summary b{font-size:13px}.sl78-inline-summary span,.sl78-inline-summary small{color:var(--muted);font-size:9px}.sl78-inline-summary>small{grid-column:1/-1;line-height:1.5}.sl78-inline-numbers{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.sl78-inline-numbers span{border:1px solid var(--line-soft);border-radius:10px;padding:7px;background:rgba(255,255,255,.02)}.sl78-signal-section,.sl78-nd-wrap{border:1px solid var(--line-soft);border-radius:18px;background:var(--panel);padding:14px}.sl78-section-title{display:flex;justify-content:space-between;margin-bottom:10px}.sl78-section-title b{font-size:12px}.sl78-section-title span{color:var(--muted);font-size:9px}.p751-groups{display:grid;gap:8px}.p751-group{border:1px solid var(--line-soft);border-radius:15px;overflow:hidden;background:#0a1721}.p751-group>summary{display:flex;justify-content:space-between;align-items:center;padding:11px 13px}.p751-group>summary div{display:grid;gap:2px}.p751-group>summary span{color:var(--mint);font-size:8px}.p751-group>summary b{font-size:11px}.p751-group>summary small{color:var(--muted);font-size:8px}.p751-group-body{display:grid;gap:6px;padding:7px}.p751-match-card{display:grid;grid-template-columns:minmax(0,1fr) 110px;gap:8px;border:1px solid var(--line-soft);border-radius:13px;background:var(--panel)!important;padding:11px!important}.p751-match-meta,.p751-card-center,.p751-top-pick,.p751-strength,.p753-match-total-preview,.p751-match-card footer{min-width:0}.p751-match-meta{grid-column:1/-1;display:flex;gap:6px;flex-wrap:wrap;color:var(--muted);font-size:7px}.p751-card-center{display:grid;gap:7px}.p751-names{font-size:10px;font-weight:800}.p751-names>span{color:var(--muted-2);font-weight:400}.p751-top-pick{display:grid;gap:2px;padding:8px;border-radius:10px;background:rgba(255,255,255,.025)}.p751-top-pick span,.p751-top-pick em{color:var(--muted);font-size:7px}.p751-top-pick b{font-size:9px}.p751-strength{display:grid;align-content:center;justify-items:end}.p751-strength span,.p751-strength small{color:var(--muted);font-size:7px}.p751-strength b{color:var(--lime);font-size:20px}.p753-match-total-preview{grid-column:1/-1;display:grid;gap:2px;padding:8px;border-radius:10px;background:rgba(255,255,255,.02)}.p753-match-total-preview span,.p753-match-total-preview em{color:var(--muted);font-size:7px;font-style:normal}.p753-match-total-preview b{font-size:8px}.p751-match-card footer{grid-column:1/-1;display:flex;gap:6px;flex-wrap:wrap;color:var(--muted);font-size:7px}.p751-match-card footer b{margin-left:auto;color:var(--mint)}

  @media(max-width:1050px){.admin-metrics{grid-template-columns:repeat(3,1fr)}.admin-tools{grid-template-columns:1fr 1fr}.model-stats-grid{grid-template-columns:1fr 1fr}.model-stat-card:first-child{grid-column:1/-1}}
  @media(max-width:760px){
    .product-footer{display:grid;gap:3px;margin:18px 2px 0;padding-top:12px}.admin-banner{display:grid;gap:15px;padding:18px;border-radius:19px}.admin-banner h2{font-size:23px}.admin-banner button{width:max-content}.admin-metrics{grid-template-columns:1fr 1fr;gap:6px}.admin-metric{padding:11px;border-radius:14px}.admin-metric b{font-size:17px}.admin-section{padding:13px;border-radius:17px}.admin-tools{grid-template-columns:1fr 1fr;gap:6px}.admin-tool{grid-template-columns:31px minmax(0,1fr) 12px;padding:10px;gap:7px;border-radius:13px}.admin-tool>span{width:31px;height:31px;border-radius:9px}.admin-tool small{display:none}.admin-system-grid{grid-template-columns:1fr;gap:7px}.admin-card{padding:14px;border-radius:16px}.admin-raw{border-radius:16px}.stats-overview{grid-template-columns:1fr 1fr}.stats-main-number{grid-column:1/-1;padding:15px}.stats-main-number b{font-size:32px}.model-stats-grid{grid-template-columns:1fr;gap:7px}.model-stat-card:first-child{grid-column:auto}.history-summary{display:grid;gap:8px;padding:14px}.history-summary p{font-size:9px}.history-clean-list{grid-template-columns:1fr;gap:7px}.history-clean-card{border-radius:15px}.account-profile-avatar{width:62px;height:62px;flex-basis:62px;border-radius:17px}
    .s2-hub{padding:0!important}.s2-hub-frame{min-height:100vh!important;border-radius:0!important;border-left:0!important;border-right:0!important}.s2-hub-body{padding:12px!important}.s2-hub-top{padding:10px 12px!important}.s2-hero{padding:14px!important;border-radius:15px!important}.s2-hero h2{font-size:22px!important}.s2-status{grid-template-columns:1fr 1fr 1fr!important;gap:5px!important}.s2-stat{padding:9px!important;border-radius:11px!important}.s2-stat strong{font-size:10px!important}.s2-controls{grid-template-columns:1fr 1fr!important;padding:9px!important}.s2-generate{grid-column:1/-1!important}.s2-grid{grid-template-columns:1fr!important;gap:7px!important}.s2-card{border-radius:14px!important}.s2-head,.s2-leg,.s2-joint{padding-left:11px!important;padding-right:11px!important}
    .sl78-inline-summary{grid-template-columns:1fr;padding:12px}.sl78-inline-summary>small{grid-column:auto}.sl78-inline-numbers{justify-content:flex-start}.sl78-signal-section,.sl78-nd-wrap{padding:10px;border-radius:15px}.p751-match-card{grid-template-columns:1fr 70px!important;padding:9px!important}.p751-strength b{font-size:17px}
  }
  @media(max-width:390px){.admin-tools{grid-template-columns:1fr}.admin-metrics{grid-template-columns:1fr 1fr}.s2-status{grid-template-columns:1fr!important}}
  `;
  const style=document.createElement('style');style.id='tenis-product-polish';style.textContent=STYLE;document.head.appendChild(style);

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