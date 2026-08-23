/* Tenis AI v7.1 — Profil Tendencji Zawodnika */
(() => {
  const panel=document.querySelector('#player-profile-panel');
  const input=document.querySelector('#player-search-input');
  if(!panel||!input)return;

  const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim();
  const same=(a,b)=>norm(a)===norm(b);
  const esc71=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const STORE='tenis-ai-v71-trend-ui';
  const LABELS={
    match_win:'Wygrany mecz',
    set1_win:'Wygrany 1. set',
    'set1_over_8.5':'Over 8.5 gema · 1. set',
    'set1_over_9.5':'Over 9.5 gema · 1. set',
    'set1_over_10.5':'Over 10.5 gema · 1. set',
    'set1_over_11.5':'Over 11.5 gema · 1. set',
    'set1_over_12.5':'Over 12.5 gema · 1. set',
    match_2_sets:'Mecz zakończony w 2 setach',
    match_3_sets:'Mecz miał 3 sety',
    hold1:'Utrzymany 1. własny gem serwisowy',
    hold2:'Utrzymany 2. własny gem serwisowy',
    hold3:'Utrzymany 3. własny gem serwisowy',
    after2_11:'1:1 po 2 gemach',
    after4_22:'2:2 po 4 gemach',
    after6_33:'3:3 po 6 gemach',
    sequence_11_22_33:'Sekwencja 1:1 → 2:2 → 3:3'
  };
  const AVG_LABELS={
    hold_rate:'Śr. hold w meczu',
    break_rate:'Śr. break rate',
    serve_points_won:'Śr. punkty wygrane przy serwisie',
    return_points_won:'Śr. punkty wygrane na returnie',
    first_set_games:'Śr. liczba gemów 1. seta'
  };

  function allRows(){try{return Array.isArray(all)?all:[]}catch{return []}}
  function dataFor(name){
    const rows=allRows().filter(m=>same(m.p1,name)||same(m.p2,name));
    const withTrend=rows.find(m=>m.tendencies_v71)||rows[0];
    if(!withTrend)return null;
    const side=same(withTrend.p1,name)?'p1':'p2';
    return {
      match:withTrend,
      general:withTrend.tendencies_v71?.[side]||null,
      pbp:withTrend.early_hold_v7?.[side]?.pbp_tendencies||null,
      pbpProfile:withTrend.early_hold_v7?.[side]||null,
      surface:String(withTrend.surface||'').toLowerCase()
    };
  }

  function loadUi(){
    try{return {...{window:'10',scope:'all'},...(JSON.parse(localStorage.getItem(STORE))||{})}}catch{return {window:'10',scope:'all'}}
  }
  function saveUi(x){try{localStorage.setItem(STORE,JSON.stringify(x))}catch{}}

  function wilsonish(m){
    if(!m||m.pct==null||!m.n)return -1;
    return (Number(m.pct)/100)*(Number(m.n)/(Number(m.n)+3));
  }
  function metricRows(source,scope,win,kind){
    const block=source?.[scope]?.[win];
    if(!block)return [];
    return Object.entries(block.metrics||{})
      .filter(([k,m])=>LABELS[k]&&m&&m.pct!=null&&m.n>0)
      .map(([k,m])=>({key:k,label:LABELS[k],...m,kind}))
  }
  function sourceSample(source,scope,win){return Number(source?.[scope]?.[win]?.sample_matches||0)}

  function strongRows(g,p,scope,win){
    const general=metricRows(g,scope,win,'Historia');
    // PBP contributes the game-by-game markets only; avoid duplicate set1 winner / over lines.
    const pbp=metricRows(p,scope,win,'BASIC PBP').filter(x=>['hold1','hold2','hold3','after2_11','after4_22','after6_33','sequence_11_22_33'].includes(x.key));
    return [...general,...pbp]
      .filter(x=>x.n>=3)
      .sort((a,b)=>wilsonish(b)-wilsonish(a)||b.n-a.n)
      .slice(0,5);
  }

  function rowHtml(x){
    const cls=Number(x.pct)>=80?'hot':Number(x.pct)>=70?'good':'';
    return `<div class="pt71-row ${cls}">
      <div><b>${esc71(x.label)}</b><small>${esc71(x.kind)} · ${x.hits}/${x.n} meczów</small></div>
      <strong>${Number(x.pct).toFixed(0)}%</strong>
    </div>`;
  }

  function avgHtml(g,scope,win){
    const a=g?.[scope]?.[win]?.averages||{};
    const rows=Object.entries(AVG_LABELS).filter(([k])=>a[k]!=null);
    if(!rows.length)return '';
    return `<div class="pt71-averages">${rows.map(([k,l])=>`<div><span>${esc71(l)}</span><b>${k==='first_set_games'?Number(a[k]).toFixed(1):Number(a[k]).toFixed(1)+'%'}</b></div>`).join('')}</div>`;
  }

  function renderContent(host,name,d,ui){
    if(!d?.general){
      host.innerHTML='<div class="player-empty">N/D — profil 5/10/20 powstaje dla zawodników z aktualnych spotkań i będzie uzupełniany automatycznie.</div>';
      return;
    }
    const win=ui.window,scope=ui.scope;
    const gs=sourceSample(d.general,scope,win), ps=sourceSample(d.pbp,scope,win);
    const strongest=strongRows(d.general,d.pbp,scope,win);
    const general=metricRows(d.general,scope,win,'Historia wyników');
    const pbp=metricRows(d.pbp,scope,win,'BASIC PBP').filter(x=>['hold1','hold2','hold3','after2_11','after4_22','after6_33','sequence_11_22_33'].includes(x.key));
    const surf=d.surface?d.surface.toUpperCase():'NAWIERZCHNIA';

    host.innerHTML=`
      <div class="pt71-explain">
        <b>Co tu mierzymy?</b>
        <span><strong>Częstość historyczna</strong> = ile razy dane zdarzenie naprawdę wystąpiło. To nie jest prognoza na kolejny mecz. <strong>Skuteczność AI</strong> niżej w profilu to osobno wynik naszych wcześniejszych typów.</span>
      </div>
      <div class="pt71-controls">
        <div class="pt71-seg">${['5','10','20'].map(n=>`<button data-pt-window="${n}" class="${win===n?'active':''}">Ostatnie ${n}</button>`).join('')}</div>
        <div class="pt71-seg"><button data-pt-scope="all" class="${scope==='all'?'active':''}">Wszystkie</button><button data-pt-scope="surface" class="${scope==='surface'?'active':''}">${esc71(surf)}</button></div>
      </div>
      <div class="pt71-samples"><span>📚 Historia: <b>${gs}</b> meczów</span><span>🧬 PBP: <b>${ps||0}</b> meczów</span></div>
      <div class="pt71-subtitle"><b>🔥 Najmocniejsze tendencje</b><small>minimum 3 obserwacje · zawsze pokazujemy liczebność próbki</small></div>
      <div class="pt71-strong">${strongest.length?strongest.map(rowHtml).join(''):'<div class="player-empty">Za mała próbka dla mocnych tendencji w tym filtrze.</div>'}</div>
      <details class="pt71-details">
        <summary>Pełne statystyki tendencji ▾</summary>
        <div class="pt71-detail-head"><b>📚 Wyniki historyczne</b><small>zwycięstwa, sety, overy</small></div>
        <div class="pt71-list">${general.length?general.map(rowHtml).join(''):'<div class="player-empty">Brak danych.</div>'}</div>
        ${avgHtml(d.general,scope,win)}
        <div class="pt71-detail-head"><b>🧬 BASIC point-by-point</b><small>realne pierwsze gemy i stany po 2/4/6</small></div>
        <div class="pt71-list">${pbp.length?pbp.map(rowHtml).join(''):'<div class="player-empty">PBP N/D dla tego filtra. Cache jest uzupełniany stopniowo.</div>'}</div>
      </details>
      <div class="pt71-note">💡 100% z 3/3 to nadal mała próbka. Dlatego aplikacja pokazuje jednocześnie procent i liczbę meczów, a model nie traktuje samej tendencji jako gwarancji.</div>
    `;

    host.querySelectorAll('[data-pt-window]').forEach(b=>b.onclick=()=>{ui.window=b.dataset.ptWindow;saveUi(ui);renderContent(host,name,d,ui)});
    host.querySelectorAll('[data-pt-scope]').forEach(b=>b.onclick=()=>{ui.scope=b.dataset.ptScope;saveUi(ui);renderContent(host,name,d,ui)});
  }

  let injecting=false;
  function inject(){
    if(injecting||panel.hidden||panel.querySelector('#player-tendencies-v71'))return;
    const name=input.value.trim();
    if(!name)return;
    const d=dataFor(name);
    injecting=true;
    try{
      const section=document.createElement('section');
      section.className='player-section pt71-section';
      section.id='player-tendencies-v71';
      section.innerHTML=`<div class="player-section-title"><b>🧭 Profil Tendencji Zawodnika</b><small>realne mecze · 5 / 10 / 20 · nawierzchnia</small></div><div id="pt71-content"></div>`;
      const sections=[...panel.querySelectorAll('.player-section')];
      const stats=sections.find(s=>s.querySelector('.player-section-title b')?.textContent.includes('Statystyki zawodnika'));
      if(stats)stats.insertAdjacentElement('afterend',section);else panel.appendChild(section);
      const ui=loadUi();
      // If surface sample is tiny, don't surprise a new user with an empty default filter.
      if(ui.scope==='surface' && sourceSample(d?.general,'surface',ui.window)<3)ui.scope='all';
      renderContent(section.querySelector('#pt71-content'),name,d,ui);
    }finally{injecting=false}
  }

  function mount(name){
    const wanted=String(name||input.value||'').trim();
    if(!wanted||panel.hidden)return;
    const old=panel.querySelector('#player-tendencies-v71');
    if(old)old.remove();
    inject();
  }

  // v8.1: profil montuje Trends jawnie. Zero subtree observera.
  window.TENIS_AI_PLAYER_TRENDS_V81={mount,inject};
  setTimeout(()=>{if(!panel.hidden)mount(input.value)},120);
})();