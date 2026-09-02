/* Tenis AI v7.6 — Player Analytics PRO
   Descriptive analytics only. 0–100 profile indexes are NOT win probabilities.
*/
(() => {
  const panel=document.querySelector('#player-profile-panel');
  const input=document.querySelector('#player-search-input');
  if(!panel||!input)return;

  const STORE='tenis-ai-v76-player-pro-ui';
  const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim();
  const same=(a,b)=>norm(a)===norm(b);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>x==null||!Number.isFinite(Number(x))?null:Number(x);
  const clamp=(x,a=0,b=100)=>Math.max(a,Math.min(b,Number(x)));
  const scoreRange=(x,lo,hi)=>num(x)==null?null:clamp((Number(x)-lo)/(hi-lo)*100);
  const weighted=(pairs)=>{
    const ok=pairs.filter(([v,w])=>num(v)!=null&&w>0);
    if(!ok.length)return null;
    const z=ok.reduce((s,[,w])=>s+w,0);
    return ok.reduce((s,[v,w])=>s+Number(v)*w,0)/z;
  };
  const fmt=x=>num(x)==null?'N/D':`${Math.round(Number(x))}`;
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const pp=x=>num(x)==null?'—':`${Number(x)>=0?'+':''}${Number(x).toFixed(1)} pp`;
  const safeAll=()=>{try{return Array.isArray(all)?all:[]}catch{return []}};

  function state(){
    try{return {...{window:'10',scope:'all'},...(JSON.parse(localStorage.getItem(STORE))||{})}}catch{return {window:'10',scope:'all'}}
  }
  function save(x){try{localStorage.setItem(STORE,JSON.stringify(x))}catch{}}

  function dataFor(name){
    const rows=safeAll().filter(m=>same(m.p1,name)||same(m.p2,name));
    const m=rows.find(x=>x.tendencies_v71||x.early_hold_v7||x.serve_props_v72)||rows[0];
    if(!m)return null;
    const side=same(m.p1,name)?'p1':'p2';
    return {
      m,side,
      stats:m[`${side}_stats`]||null,
      trends:m.tendencies_v71?.[side]||null,
      early:m.early_hold_v7?.[side]||null,
      serve:m.serve_props_v72?.[side]||null,
      surface:String(m.surface||'').toLowerCase()
    };
  }

  const metric=(block,key)=>block?.metrics?.[key]?.pct ?? null;
  const av=(block,key)=>block?.averages?.[key] ?? null;

  function indexes(d,ui){
    const g=d?.trends?.[ui.scope]?.[ui.window]||null;
    const surf=d?.trends?.surface?.[ui.window]||null;
    const p=d?.early?.pbp_tendencies?.[ui.scope]?.[ui.window]||null;
    const ps=d?.early?.pbp_tendencies?.surface?.[ui.window]||null;

    const serve=weighted([
      [scoreRange(av(g,'hold_rate'),60,90),.38],
      [scoreRange(av(g,'serve_points_won'),50,72),.25],
      [scoreRange(av(g,'first_serve_won'),55,85),.20],
      [scoreRange(av(g,'second_serve_won'),35,65),.17]
    ]);
    const ret=weighted([
      [scoreRange(av(g,'break_rate'),10,45),.46],
      [scoreRange(av(g,'return_points_won'),28,52),.54]
    ]);
    const form=weighted([
      [metric(g,'match_win'),.45],
      [metric(g,'set1_win'),.32],
      [metric(g,'set2_win'),.23]
    ]);
    const early=Number(p?.sample_matches||0)>=3?weighted([
      [metric(p,'hold1'),.42],
      [metric(p,'hold2'),.32],
      [metric(p,'hold3'),.18],
      [metric(p,'sequence_11_22_33'),.08]
    ]):null;
    const mental=weighted([
      [metric(g,'closeout_after_set1_win'),.32],
      [metric(g,'comeback_set2_after_set1_loss'),.32],
      [metric(g,'deciding_set_win'),.26],
      [metric(g,'set2_win'),.10]
    ]);
    const surface=Number(surf?.sample_matches||0)>=3?weighted([
      [metric(surf,'match_win'),.40],
      [scoreRange(av(surf,'hold_rate'),60,90),.25],
      [scoreRange(av(surf,'return_points_won'),28,52),.20],
      [metric(surf,'set1_win'),.15]
    ]):null;

    return {serve,ret,form,early,mental,surface,g,p,surf,ps};
  }

  function indexCard(label,v,icon,sub='indeks profilu'){
    const cls=num(v)==null?'nd':v>=80?'elite':v>=70?'good':v<50?'warn':'';
    return `<article class="pa76-index ${cls}">
      <span>${icon} ${esc(label)}</span><b>${fmt(v)}</b><small>${num(v)==null?'N/D':sub}</small>
    </article>`;
  }

  function tags(ix,d,ui){
    const g=ix.g||{};
    const t=[];
    const add=(x,cls='')=>{if(!t.some(y=>y.x===x))t.push({x,cls})};
    if(num(ix.serve)>=78)add('MOCNY SERWIS','good');
    if(num(ix.ret)>=75)add('MOCNY RETURN','good');
    if(num(ix.early)>=80)add('STABILNY START','good');
    if(num(ix.early)!=null&&ix.early<58)add('NIEPEWNY START','warn');
    if(num(ix.mental)>=72)add('DOBRY POD PRESJĄ','good');
    if(num(metric(g,'comeback_set2_after_set1_loss'))>=60)add('COMEBACK','good');
    if(num(metric(g,'closeout_after_set1_win'))>=70)add('DOMYKA SETY','good');
    if(num(av(g,'second_serve_won'))!=null&&av(g,'second_serve_won')<45)add('SŁABSZY 2. SERWIS','warn');
    const sh=d?.serve?.history?.[ui.scope]?.[ui.window];
    const df=num(sh?.double_faults?.avg);
    const ac=num(sh?.aces?.avg);
    if(df!=null&&df>=4.0)add('DUŻO DF','warn');
    if(ac!=null&&ac>=7.0)add('DUŻO ASÓW','good');
    if(!t.length)add('PROFIL ZRÓWNOWAŻONY');
    return t.slice(0,6);
  }

  function stat(label,value,note=''){
    return `<div class="pa76-stat"><span>${esc(label)}</span><b>${esc(value)}</b>${note?`<small>${esc(note)}</small>`:''}</div>`;
  }

  function trendLine(d,ui){
    const tr=d?.trends?.trend?.[ui.scope]||{};
    const f=num(tr.match_win);
    const h=num(tr.hold_rate);
    const r=num(tr.return_points_won);
    const dir=f==null?'→':f>=4?'↑':f<=-4?'↓':'→';
    const cls=f==null?'':f>=4?'up':f<=-4?'down':'flat';
    return `<div class="pa76-trend ${cls}">
      <b>${dir} Trend ostatnie 5 vs poprzednie 5</b>
      <span>Forma ${pp(f)}</span><span>Hold ${pp(h)}</span><span>Return ${pp(r)}</span>
    </div>`;
  }

  function serveBlock(d,ix,ui){
    const g=ix.g||{},pbp=ix.p||{};
    const sh=d?.serve?.history?.[ui.scope]?.[ui.window]||{};
    return `<div class="pa76-statgrid">
      ${stat('Hold',pct(av(g,'hold_rate')))}
      ${stat('Punkty przy serwisie',pct(av(g,'serve_points_won')))}
      ${stat('1. serwis wygrany',pct(av(g,'first_serve_won')))}
      ${stat('2. serwis wygrany',pct(av(g,'second_serve_won')))}
      ${stat('Asy / mecz',num(sh?.aces?.avg)==null?'—':Number(sh.aces.avg).toFixed(1),`${sh?.aces?.sample||0} meczów`)}
      ${stat('DF / mecz',num(sh?.double_faults?.avg)==null?'—':Number(sh.double_faults.avg).toFixed(1),`${sh?.double_faults?.sample||0} meczów`)}
      ${stat('Hold 1. własnego gema',pct(metric(pbp,'hold1')),`${pbp?.metrics?.hold1?.n||0} PBP`)}
      ${stat('Hold 2. własnego gema',pct(metric(pbp,'hold2')))}
      ${stat('Hold 3. własnego gema',pct(metric(pbp,'hold3')))}
    </div>`;
  }

  function returnBlock(ix){
    const g=ix.g||{};
    return `<div class="pa76-statgrid">
      ${stat('Return points won',pct(av(g,'return_points_won')))}
      ${stat('Break rate',pct(av(g,'break_rate')))}
      ${stat('Wygrany mecz',pct(metric(g,'match_win')))}
      ${stat('Wygrany 1. set',pct(metric(g,'set1_win')))}
    </div>`;
  }

  function mentalBlock(ix){
    const g=ix.g||{};
    return `<div class="pa76-statgrid">
      ${stat('2. set po wygranym 1.',pct(metric(g,'closeout_after_set1_win')))}
      ${stat('2. set po przegranym 1.',pct(metric(g,'comeback_set2_after_set1_loss')))}
      ${stat('Decydujący set',pct(metric(g,'deciding_set_win')))}
      ${stat('Wygrany 2. set',pct(metric(g,'set2_win')))}
    </div>`;
  }

  function gamesBlock(ix){
    const g=ix.g||{};
    const keys=['set1_over_8.5','set1_over_9.5','set1_over_10.5','set1_over_11.5','set1_over_12.5'];
    return `<div class="pa76-statgrid">
      ${keys.map(k=>stat(k.replace('set1_over_','Over ')+' · 1. set',pct(metric(g,k)))).join('')}
      ${stat('Mecz w 2 setach',pct(metric(g,'match_2_sets')))}
      ${stat('Mecz w 3 setach',pct(metric(g,'match_3_sets')))}
      ${stat('Śr. gemy 1. seta',num(av(g,'first_set_games'))==null?'—':Number(av(g,'first_set_games')).toFixed(1))}
    </div>`;
  }

  function sourceMatchesBlock(d,ui){
    const rows=(ui.scope==='surface'?d?.trends?.recent_surface_matches:d?.trends?.recent_matches)||[];
    const take=rows.slice(0,Number(ui.window)||10);
    if(!take.length)return '<div class="player-empty">Brak szczegółowej listy meczów źródłowych w obecnym pakiecie. Agregaty 5/10/20 pozostają dostępne.</div>';
    const one=x=>{
      const when=x?.date?new Date(x.date):null;
      const date=when&&Number.isFinite(when.getTime())?when.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'2-digit'}):'—';
      const wl=x?.won===true?'WYGRANA':x?.won===false?'PORAŻKA':'WYNIK N/D';
      const cls=x?.won===true?'win':x?.won===false?'loss':'nd';
      const fs=num(x?.first_set_games),hold=num(x?.hold_rate),ret=num(x?.return_points_won);
      const holdTxt=hold==null?'':` · hold ${(hold<=1?hold*100:hold).toFixed(0)}%`;
      const retTxt=ret==null?'':` · return ${(ret<=1?ret*100:ret).toFixed(0)}%`;
      return `<div class="pa801-source-row"><div><b>${esc(x?.opponent||'Przeciwnik N/D')}</b><small>${esc(date)}${x?.surface?` · ${esc(String(x.surface).toUpperCase())}`:''}${x?.tournament?` · ${esc(x.tournament)}`:''}</small></div><span class="${cls}">${wl}</span><small>${x?.score?`wynik ${esc(x.score)} · `:''}${fs==null?'':`1S ${fs.toFixed(0)} gemów`}${holdTxt}${retTxt}</small></div>`;
    };
    return `<div class="pa801-source-list">${take.map(one).join('')}</div><p class="pa801-source-note">To są mecze źródłowe użyte do statystyk 5/10/20. Nie oznaczają, że Tenis AI wystawił wtedy typ.</p>`;
  }

  function surfaceBlock(d,ix,ui){
    const s=ix.surf||{};
    const n=Number(s?.sample_matches||0);
    if(n<3)return `<div class="player-empty">Za mała próbka na ${esc(String(d.surface||'tej nawierzchni').toUpperCase())}. Potrzeba co najmniej 3 meczów.</div>`;
    return `<div class="pa76-surface">
      <div><b>${esc(String(d.surface||'').toUpperCase())}</b><span>${n} meczów z filtra ostatnie ${ui.window}</span></div>
      <div class="pa76-statgrid">
        ${stat('Win rate',pct(metric(s,'match_win')))}
        ${stat('1. set win',pct(metric(s,'set1_win')))}
        ${stat('Hold',pct(av(s,'hold_rate')))}
        ${stat('Return',pct(av(s,'return_points_won')))}
        ${stat('1. serwis',pct(av(s,'first_serve_won')))}
        ${stat('2. serwis',pct(av(s,'second_serve_won')))}
      </div>
    </div>`;
  }

  function render(host,name,d,ui){
    if(!d?.trends){
      host.innerHTML='<div class="player-empty">Analytics PRO: N/D — profil pojawi się po kolejnym odświeżeniu danych.</div>';
      return;
    }
    const ix=indexes(d,ui);
    const tagRows=tags(ix,d,ui);
    const surf=String(d.surface||'nawierzchnia').toUpperCase();

    host.innerHTML=`
      <div class="pa76-head">
        <div><b>🧠 Player Analytics PRO</b><span>serwis · return · forma · Early Hold · mental · nawierzchnia</span></div>
        <em>v7.6</em>
      </div>

      <div class="pa76-controls">
        <div>${['5','10','20'].map(n=>`<button data-pa-window="${n}" class="${ui.window===n?'active':''}">Ostatnie ${n}</button>`).join('')}</div>
        <div><button data-pa-scope="all" class="${ui.scope==='all'?'active':''}">Wszystkie</button><button data-pa-scope="surface" class="${ui.scope==='surface'?'active':''}">${esc(surf)}</button></div>
      </div>

      <div class="pa76-tags">${tagRows.map(t=>`<span class="${t.cls||''}">${esc(t.x)}</span>`).join('')}</div>

      <div class="pa76-index-grid">
        ${indexCard('SERWIS',ix.serve,'🎾')}
        ${indexCard('RETURN',ix.ret,'↩️')}
        ${indexCard('FORMA',ix.form,'🔥')}
        ${indexCard('EARLY',ix.early,'🧬')}
        ${indexCard('MENTAL',ix.mental,'🧠')}
        ${indexCard('NAWIERZCHNIA',ix.surface,'🏟️')}
      </div>

      <div class="pa76-note"><b>Ważne:</b> indeksy 0–100 opisują profil/statystyki zawodnika. <b>Nie są prawdopodobieństwem wygranej</b> ani kursem bukmacherskim.</div>

      ${trendLine(d,ui)}

      <details class="pa76-details" open><summary>🎾 Serwis i pierwsze gemy <i>⌄</i></summary>${serveBlock(d,ix,ui)}</details>
      <details class="pa76-details"><summary>↩️ Return i forma <i>⌄</i></summary>${returnBlock(ix)}</details>
      <details class="pa76-details"><summary>🧠 Mental / reakcja po secie <i>⌄</i></summary>${mentalBlock(ix)}</details>
      <details class="pa76-details"><summary>📏 Sety i linie gemów <i>⌄</i></summary>${gamesBlock(ix)}</details>
      <details class="pa76-details"><summary>🕘 Ostatnie mecze źródłowe · ${ui.window} <i>⌄</i></summary>${sourceMatchesBlock(d,ui)}</details>
      <details class="pa76-details"><summary>🏟️ ${esc(surf)} <i>⌄</i></summary>${surfaceBlock(d,ix,ui)}</details>
    `;

    const redraw=()=>requestAnimationFrame(()=>render(host,name,d,ui));
    host.querySelectorAll('[data-pa-window]').forEach(b=>b.onclick=()=>{if(ui.window===b.dataset.paWindow)return;ui.window=b.dataset.paWindow;save(ui);redraw()});
    host.querySelectorAll('[data-pa-scope]').forEach(b=>b.onclick=()=>{if(ui.scope===b.dataset.paScope)return;ui.scope=b.dataset.paScope;save(ui);redraw()});
  }

  let injecting=false;
  function inject(){
    if(injecting||panel.hidden||panel.querySelector('#player-analytics-v76'))return;
    const name=input.value.trim(); if(!name)return;
    const d=dataFor(name);
    injecting=true;
    try{
      const section=document.createElement('section');
      section.id='player-analytics-v76';
      section.className='player-section pa76-section';
      section.innerHTML='<div id="pa76-content"></div>';
      const kpis=panel.querySelector('.player-profile-kpis');
      const historyQuick=panel.querySelector('.player-ai-history-quick');
      const currentSection=panel.querySelector('.player-current-section');
      const pt=panel.querySelector('#player-tendencies-v71');
      if(currentSection)currentSection.insertAdjacentElement('afterend',section);
      else if(historyQuick)historyQuick.insertAdjacentElement('afterend',section);
      else if(kpis)kpis.insertAdjacentElement('afterend',section);
      else if(pt)pt.insertAdjacentElement('afterend',section);
      else{
        const sections=[...panel.querySelectorAll('.player-section')];
        const stats=sections.find(s=>s.textContent.includes('Statystyki zawodnika'));
        if(stats)stats.insertAdjacentElement('afterend',section);else panel.appendChild(section);
      }
      if(!d){
        section.querySelector('#pa76-content').innerHTML=
          '<div class="pa76-head"><div><b>🧠 Player Analytics PRO</b><span>profil 5/10/20</span></div><em>N/D</em></div>'+
          '<div class="player-empty">Ten zawodnik jest obecnie dostępny tylko w historii Tenis AI. Rozszerzony profil PRO powstaje z bieżącego pakietu tendencies/PBP i pojawi się, gdy zawodnik znajdzie się w aktualnych spotkaniach.</div>';
        return;
      }
      const ui=state();
      const surfSample=Number(d.trends?.surface?.[ui.window]?.sample_matches||0);
      if(ui.scope==='surface'&&surfSample<3)ui.scope='all';
      render(section.querySelector('#pa76-content'),name,d,ui);
    }finally{injecting=false}
  }

  function mount(name){
    const wanted=String(name||input.value||'').trim();
    if(!wanted||panel.hidden)return;
    const old=panel.querySelector('#player-analytics-v76');
    if(old)old.remove();
    inject();
  }

  // v8.0.1: explicit bridge. No polling and no subtree MutationObserver.
  window.TENIS_AI_PLAYER_ANALYTICS_V801={mount,inject};
  setTimeout(()=>{if(!panel.hidden)mount(input.value)},200);
})();