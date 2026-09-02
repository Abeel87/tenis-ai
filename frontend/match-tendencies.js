/* Tenis AI v7.1.2 — szybkie tendencje bezpośrednio przy meczu */
(() => {
  if(typeof renderMatchDetail!=='function') return;
  const baseRender=renderMatchDetail;
  const escT=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim();
  const LABELS={
    match_win:'Wygrany mecz',set1_win:'Wygrany 1. set',
    'set1_over_8.5':'Over 8.5 · 1. set','set1_over_9.5':'Over 9.5 · 1. set','set1_over_10.5':'Over 10.5 · 1. set',
    hold1:'Utrzymany 1. gem serwisowy',hold2:'Utrzymany 2. gem serwisowy',hold3:'Utrzymany 3. gem serwisowy',
    after2_11:'1:1 po 2 gemach',after4_22:'2:2 po 4 gemach',after6_33:'3:3 po 6 gemach',sequence_11_22_33:'1:1 → 2:2 → 3:3'
  };
  const PBP_KEYS=new Set(['hold1','hold2','hold3','after2_11','after4_22','after6_33','sequence_11_22_33']);

  function matchKey(m){return String(m.id??`${m.p1}|${m.p2}|${m.scheduled_time||''}`)}
  function sourceFor(m,side){return {g:m.tendencies_v71?.[side]||null,p:m.early_hold_v7?.[side]?.pbp_tendencies||null}}
  function sample(src,scope,win){return Number(src?.[scope]?.[String(win)]?.sample_matches||0)}
  function rows(src,scope,win,kind){
    const b=src?.[scope]?.[String(win)];if(!b)return [];
    return Object.entries(b.metrics||{}).filter(([k,v])=>LABELS[k]&&v&&v.pct!=null&&Number(v.n)>=3)
      .map(([k,v])=>({key:k,label:LABELS[k],pct:Number(v.pct),hits:Number(v.hits),n:Number(v.n),kind}));
  }
  function chooseScope(g,surface){
    if(surface&&sample(g,'surface',10)>=5)return 'surface';
    return 'all';
  }
  function topFor(m,side){
    const {g,p}=sourceFor(m,side);const surface=String(m.surface||'').toLowerCase();const scope=chooseScope(g,surface);const win=10;
    const a=rows(g,scope,win,'HISTORIA');
    const b=rows(p,scope,win,'PBP').filter(x=>PBP_KEYS.has(x.key));
    const all=[...a,...b].sort((x,y)=>(y.pct*(y.n/(y.n+3)))-(x.pct*(x.n/(x.n+3)))||y.n-x.n).slice(0,3);
    return {rows:all,scope,surface,historyN:sample(g,scope,win),pbpN:sample(p,scope,win)};
  }
  function trendRows(x){
    if(!x.rows.length)return '<div class="mt-empty">N/D — za mała próbka w tym meczu.</div>';
    return x.rows.map(r=>`<div class="mt-row"><div><b>${escT(r.label)}</b><small>${r.kind} · ${r.hits}/${r.n}</small></div><strong>${Math.round(r.pct)}%</strong></div>`).join('');
  }
  function player(m,side){
    const name=m[side]||'—',x=topFor(m,side);const scopeLabel=x.scope==='surface'?(x.surface||'surface').toUpperCase():'WSZYSTKIE';
    return `<article class="mt-player"><div class="mt-name"><b>${escT(name)}</b><span>${escT(scopeLabel)} · 10</span></div><div class="mt-list">${trendRows(x)}</div><div class="mt-sample">Historia ${x.historyN} · PBP ${x.pbpN||0}</div><button type="button" class="mt-profile" data-mt-player="${escT(name)}">Pełny profil 5/10/20 →</button></article>`;
  }
  function box(m){
    if(!m.tendencies_v71)return '';
    return `<section class="match-tendencies" data-mt-match="${escT(matchKey(m))}"><div class="mt-head"><div><b>🧭 Szybkie tendencje zawodników</b><small>ostatnie 10 · bieżąca nawierzchnia, gdy próbka ≥5</small></div><span>HISTORIA + PBP</span></div><div class="mt-grid">${player(m,'p1')}${player(m,'p2')}</div><div class="mt-note">To częstość zdarzeń w poprzednich meczach, nie prognoza na dzisiejszy wynik.</div></section>`;
  }

  renderMatchDetail=function(m){
    const html=baseRender(m),panel=box(m);if(!panel)return html;
    return html.replace('<div class="match-detail">',`<div class="match-detail">${panel}`);
  };

  function openPlayer(name){
    const input=document.querySelector('#player-search-input');if(!input)return;
    input.value=name;
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true}));
    setTimeout(()=>document.querySelector('#player-profile-panel')?.scrollIntoView({behavior:'smooth',block:'start'}),120);
  }
  document.addEventListener('click',e=>{
    const b=e.target.closest?.('[data-mt-player]');if(!b)return;
    e.preventDefault();e.stopPropagation();openPlayer(b.dataset.mtPlayer||'');
  });
})();