/* Tenis AI v7.5 — UI Cleanup / Match Center
   UI-only: model/tracker logic stays unchanged.
*/
(() => {
  const esc75=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct75=x=>x==null||!Number.isFinite(Number(x))?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const num75=x=>x==null||!Number.isFinite(Number(x))?null:Number(x);
  const STORE='tenis-ai-v75-ui';
  let ui75=(()=>{try{return JSON.parse(localStorage.getItem(STORE)||'{}')||{}}catch{return {}}})();
  if(!ui75.focus) ui75.focus='all';
  const save75=()=>{try{localStorage.setItem(STORE,JSON.stringify(ui75))}catch{}};

  function status75(m){
    const raw=String(m.event_status||m.feed_status||m.status||'').toLowerCase();
    if(raw.includes('progress')||raw.includes('live')||raw.includes('started'))return {t:'LIVE',c:'live'};
    if(raw.includes('interrupt'))return {t:'PRZERWANY',c:'interrupted'};
    if(raw.includes('suspend'))return {t:'ZAWIESZONY',c:'suspended'};
    if(raw.includes('postpon'))return {t:'PRZEŁOŻONY',c:'postponed'};
    return {t:'PRZED MECZEM',c:'upcoming'};
  }

  function flattenSignals75(m){
    const out=[];
    const add=(label,v,kind='model')=>{
      v=num75(v); if(v==null)return;
      out.push({label,v,kind});
    };
    const bestBinary=(label,obj)=>{
      if(!obj)return;
      const e=Object.entries(obj).filter(([,v])=>num75(v)!=null).sort((a,b)=>Number(b[1])-Number(a[1]))[0];
      if(e)add(`${label}: ${e[0]}`,e[1]);
    };
    bestBinary('Mecz',m.match_win);
    bestBinary('1. set',m.first_set_win);
    bestBinary('2. set',m.second_set_win);
    bestBinary('Sety',m.total_sets);
    if(m.over_under) Object.entries(m.over_under).forEach(([ln,x])=>{
      const o=num75(x?.over),u=num75(x?.under);
      if(o!=null&&u!=null)add(`1S ${o>=u?'OVER':'UNDER'} ${ln}`,Math.max(o,u));
    });
    if(m.match_over_under) Object.entries(m.match_over_under).forEach(([ln,x])=>{
      const o=num75(x?.over),u=num75(x?.under);
      if(o!=null&&u!=null)add(`Mecz ${o>=u?'OVER':'UNDER'} ${ln}`,Math.max(o,u));
    });
    if(m.early_hold_v7?.ready){
      add(`Early Hold: ${m.pick_first_set_early||m.pick_first_set||'1. set'}`,m.score_first_set_early,'pbp');
      add('Prowadzi po 6',m.score_lead_after6,'pbp');
      add('Joint Builder',m.score_joint_builder,'pbp');
    }
    return out.sort((a,b)=>b.v-a.v);
  }

  function top75(m,n=2){return flattenSignals75(m).filter(x=>x.v>=60).slice(0,n)}
  function strength75(m){return top75(m,1)[0]?.v ?? num75(m.model_confidence) ?? 0}
  function greenCount75(m){
    const seen=new Set();
    return flattenSignals75(m).filter(x=>x.v>=72 && !seen.has(x.label) && seen.add(x.label)).length;
  }
  function strengthClass75(v){return v>=85?'elite':v>=72?'good':v>=60?'mid':'low'}
  function risk75(v){return v>=85?'Niskie':v>=72?'Średnie':'Podwyższone'}
  function dataTrust75(m){
    const c=num75(m.model_confidence)||0;
    const pbp=m.early_hold_v7?.ready;
    return Math.round(Math.min(100,c+(pbp?3:0)));
  }
  function sched75(m){
    const d=new Date(m.scheduled_time||'');
    return Number.isFinite(d.getTime())?d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'}):'—';
  }
  function date75(m){
    const d=new Date(m.scheduled_time||'');
    return Number.isFinite(d.getTime())?d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'}):'';
  }
  function surface75(m){return String(m.surface||'').trim()||'—'}
  function tour75(m){
    const t=String(m.tour||'').toLowerCase();
    if(t.includes('chall'))return 'CH';
    if(t.includes('itf'))return 'ITF';
    return t.toUpperCase()||'TENIS';
  }

  function quickVerdict75(m){
    const s=top75(m,3), best=s[0],alt=s[1],v=best?.v||0,trust=dataTrust75(m);
    return `<section class="v75-verdict">
      <div class="v75-section-title"><span>⚡</span><b>Szybki werdykt</b><small>najważniejsze w 3 sekundy</small></div>
      <div class="v75-verdict-grid">
        <div><span>Najlepszy sygnał</span><b>${esc75(best?.label||'Brak mocnego sygnału')}</b><strong>${best?pct75(best.v):'—'}</strong></div>
        <div><span>Alternatywa</span><b>${esc75(alt?.label||'—')}</b><strong>${alt?pct75(alt.v):'—'}</strong></div>
        <div><span>Ryzyko</span><b>${risk75(v)}</b><strong>${Math.round(v)||'—'}/100</strong></div>
        <div><span>Zaufanie danych</span><b>${trust>=85?'Wysokie':trust>=65?'Średnie':'Niskie'}</b><strong>${trust||'—'}%</strong></div>
      </div>
    </section>`;
  }

  function row75(label,left,right,leftCls=''){
    return `<div class="v75-market-row"><span>${esc75(label)}</span><b class="${leftCls}">${esc75(left)}</b><em>${esc75(right)}</em></div>`;
  }

  function coreMarkets75(m){
    const gs=m.game_states||{};
    const p11=num75(gs?.['2']?.['1:1']);
    const p22=num75(gs?.['4']?.['2:2']);
    const p33=num75(gs?.['6']?.['3:3']);
    const fs=m.first_set_win||{};
    const match=m.match_win||{};
    const bestFs=Object.entries(fs).sort((a,b)=>Number(b[1])-Number(a[1]))[0];
    const bestMatch=Object.entries(match).sort((a,b)=>Number(b[1])-Number(a[1]))[0];
    const leadPick=m.pick_first_set_early||m.pick_first_set||bestFs?.[0]||'—';
    const lead=num75(m.score_lead_after6);
    const over=num75(m.over_under?.['8.5']?.over);
    const lines=(m.market_lab_v741?.set1_total||m.over_under||{});
    const lineChips=Object.entries(lines).map(([ln,x])=>{
      const o=num75(x?.over),u=num75(x?.under),best=Math.max(o||0,u||0),side=(o||0)>=(u||0)?'O':'U';
      return `<span class="${best>=72?'strong':''}"><i>${esc75(ln)}</i><b>${side}${Math.round(best)}</b></span>`;
    }).join('');
    return `<details class="v75-accordion" open>
      <summary><div><span>🎯</span><b>Typy meczowe</b><small>najważniejsze rynki</small></div><i>⌄</i></summary>
      <div class="v75-acc-body">
        ${p11!=null?row75('1:1 po 2 gemach',pct75(p11),`inny wynik ${pct75(100-p11)}`,p11>=72?'hot':''):''}
        ${p22!=null?row75('2:2 po 4 gemach',pct75(p22),`inny wynik ${pct75(100-p22)}`,p22>=72?'hot':''):''}
        ${p33!=null?row75('3:3 po 6 gemach',pct75(p33),`inny wynik ${pct75(100-p33)}`,p33>=72?'hot':''):''}
        ${lead!=null?row75('Prowadzi po 6',`${leadPick} ${pct75(lead)}`,`pozostałe ${pct75(100-lead)}`,lead>=72?'hot':''):''}
        ${over!=null?row75('OVER 8.5 · 1. set',pct75(over),`UNDER ${pct75(100-over)}`,over>=72?'hot':''):''}
        ${bestFs?row75('Wygrany 1. set',`${bestFs[0]} ${pct75(bestFs[1])}`,`rywal ${pct75(100-Number(bestFs[1]))}`,Number(bestFs[1])>=72?'hot':''):''}
        ${bestMatch?row75('Wygrany mecz',`${bestMatch[0]} ${pct75(bestMatch[1])}`,`rywal ${pct75(100-Number(bestMatch[1]))}`,Number(bestMatch[1])>=72?'hot':''):''}
        ${lineChips?`<div class="v75-lines"><label>Linie gemów · 1. set</label><div>${lineChips}</div></div>`:''}
      </div>
    </details>`;
  }

  function statVal75(v,asPct=false){
    v=num75(v);if(v==null)return '—';
    return asPct?`${Math.round(v*100)}%`:String(Math.round(v*10)/10);
  }
  function stats75(m){
    const a=m.p1_stats||{},b=m.p2_stats||{};
    const r=(label,av,bv)=>`<div class="v75-compare-row"><span>${esc75(label)}</span><b>${esc75(av)}</b><b>${esc75(bv)}</b></div>`;
    return `<details class="v75-accordion">
      <summary><div><span>📊</span><b>Statystyki zawodników</b><small>porównanie obok siebie</small></div><i>⌄</i></summary>
      <div class="v75-acc-body">
        <div class="v75-compare-head"><span></span><b>${esc75(m.p1)}</b><b>${esc75(m.p2)}</b></div>
        ${r('Ranking',a.rank??'—',b.rank??'—')}
        ${r('Mecze próbki',a.matches??'—',b.matches??'—')}
        ${r('Ta nawierzchnia',a.surface_matches??'—',b.surface_matches??'—')}
        ${r('Win rate',statVal75(a.won,true),statVal75(b.won,true))}
        ${r('Hold',statVal75(a.hold_rate,true),statVal75(b.hold_rate,true))}
        ${r('Return points',statVal75(a.return_points_won,true),statVal75(b.return_points_won,true))}
        ${r('1. set win hist.',statVal75(a.first_set_won,true),statVal75(b.first_set_won,true))}
        ${r('Mecze / 7 dni',a.matches_7d??'—',b.matches_7d??'—')}
        ${m.service_model?r('Model hold',pct75(m.service_model.p1_hold),pct75(m.service_model.p2_hold)):''}
      </div>
    </details>`;
  }

  function pbpPlayer75(x){
    if(!x)return '<div class="v75-pbp-player nd">N/D</div>';
    const cell=(l,v)=>`<span>${esc75(l)} <b>${v==null?'N/D':pct75(v)}</b></span>`;
    return `<div class="v75-pbp-player">
      <div><b>${esc75(x.player||'—')}</b><em class="${x.ready?'ok':'nd'}">${x.ready?'PBP OK':'N/D'}</em></div>
      <strong>EHS ${x.ehs==null?'N/D':Number(x.ehs).toFixed(1)+'/100'}</strong>
      <div class="v75-pbp-kpi">${cell('1. hold',x.hold1)}${cell('2. hold',x.hold2)}${cell('3. hold',x.hold3)}${cell('1:1/2',x.after2_11)}${cell('2:2/4',x.after4_22)}${cell('3:3/6',x.after6_33)}</div>
      <small>${x.matches||0} meczów PBP · surface ${x.surface_matches||0}</small>
    </div>`;
  }
  function earlyHold75(m){
    const e=m.early_hold_v7;if(!e)return '';
    return `<details class="v75-accordion ${e.ready?'pbp-ready':''}">
      <summary><div><span>🧬</span><b>Early Hold · PBP</b><small>${e.ready?'prawdziwe początki setów':'brak pełnej próbki'}</small></div><em>${e.ready?'PBP OK':'N/D'}</em><i>⌄</i></summary>
      <div class="v75-acc-body">
        ${e.ready?`<div class="v75-pbp-top"><span>Pick 1. seta <b>${esc75(m.pick_first_set_early||'—')} · ${pct75(m.score_first_set_early)}</b></span><span>Prowadzi po 6 <b>${pct75(m.score_lead_after6)}</b></span><span>Joint Builder <b>${pct75(m.score_joint_builder)}</b></span></div>`:`<div class="v75-note">Za mało wiarygodnych PBP dla obu zawodników. W tym meczu początek seta opiera się na Adaptive.</div>`}
        <div class="v75-pbp-grid">${pbpPlayer75(e.p1)}${pbpPlayer75(e.p2)}</div>
      </div>
    </details>`;
  }

  function serveMini75(side,m){
    const s=m.serve_props_v72?.[side]||{}, name=m[side]||'—';
    const market=(title,k,icon)=>{
      const x=s[k];
      if(!x?.ready)return `<div class="v75-serve-market nd"><span>${icon} ${title}</span><b>N/D</b></div>`;
      const mean=num75(x.mean)||0,line=num75(x.suggested_line)??0.5,key=`v75-${m.id||'m'}-${side}-${k}`;
      return `<div class="v75-serve-market" data-sp-market="${key}" data-sp-mean="${mean}">
        <div><span>${icon} ${title}</span><b>śr. ${mean.toFixed(1)}</b></div>
        <label>Linia <input data-sp-line type="number" inputmode="decimal" step="0.5" min="0.5" value="${line.toFixed(1)}"></label>
        <div class="sp72-probs v75-sp-output" data-sp-output></div>
      </div>`;
    };
    return `<article class="v75-serve-player"><h4>${esc75(name)}</h4>${market('Asy','aces','🎯')}${market('Podwójne błędy','double_faults','⚠️')}</article>`;
  }
  function serve75(m){
    if(!m.serve_props_v72)return '';
    return `<details class="v75-accordion">
      <summary><div><span>⚡</span><b>Asy i podwójne błędy</b><small>linia buka + model</small></div><em>${m.serve_props_v72.ready?'MODEL':'N/D'}</em><i>⌄</i></summary>
      <div class="v75-acc-body"><div class="v75-serve-grid">${serveMini75('p1',m)}${serveMini75('p2',m)}</div></div>
    </details>`;
  }

  function lab75(m){
    const l=m.market_lab_v741;if(!l)return '';
    const setLines=Object.entries(l.set1_total||{}).map(([ln,x])=>`<div class="v75-lab-line"><b>${esc75(ln)}</b><span>O ${pct75(x.over)}</span><span>U ${pct75(x.under)}</span></div>`).join('');
    const player=(name)=>{
      const rows=Object.entries(l.player_total_games?.[name]||{}).sort((a,b)=>Math.abs(50-Math.max(Number(a[1].over),Number(a[1].under)))-Math.abs(50-Math.max(Number(b[1].over),Number(b[1].under)))).slice(0,5);
      return `<div><h4>${esc75(name)}</h4>${rows.map(([ln,x])=>`<div class="v75-lab-line"><b>${esc75(ln)}</b><span>O ${pct75(x.over)}</span><span>U ${pct75(x.under)}</span></div>`).join('')}</div>`;
    };
    return `<details class="v75-accordion">
      <summary><div><span>🧪</span><b>Market Lab</b><small>nowe rynki · osobna walidacja</small></div><em>LAB</em><i>⌄</i></summary>
      <div class="v75-acc-body">
        <div class="v75-note">Te rynki są zamrażane przed meczem i uczą się osobno. Nie podbijają jeszcze głównego score.</div>
        <h4 class="v75-sub">1. set · gemy 6.5–12.5</h4><div class="v75-lab-lines">${setLines}</div>
        <div class="v75-lab-kpi"><span>Dokładnie 6 gemów <b>${pct75(l.set1_exact_six_games)}</b></span><span>Tie-break 1S <b>${pct75(l.set1_tiebreak?.yes)}</b></span><span>Tie-break mecz <b>${pct75(l.match_tiebreak?.yes)}</b></span><span>Obaj wygrają seta <b>${pct75(l.both_players_win_set?.yes)}</b></span></div>
        <h4 class="v75-sub">Gemy zawodnika · mecz</h4><div class="v75-lab-players">${player(m.p1)}${player(m.p2)}</div>
      </div>
    </details>`;
  }

  function models75(m){
    const binary=(title,obj)=>{
      if(!obj)return '';
      return `<div class="v75-model-box"><h4>${esc75(title)}</h4>${Object.entries(obj).map(([k,v])=>`<span>${esc75(k)} <b>${pct75(v)}</b></span>`).join('')}</div>`;
    };
    return `<details class="v75-accordion">
      <summary><div><span>🧠</span><b>Modele i pełny mecz</b><small>Adaptive / BO3 / dokładne wyniki</small></div><i>⌄</i></summary>
      <div class="v75-acc-body"><div class="v75-model-grid">${binary('Zwycięzca meczu',m.match_win)}${binary('1. set',m.first_set_win)}${binary('2. set',m.second_set_win)}${binary('Liczba setów',m.total_sets)}${binary('Dokładny wynik meczu',m.exact_match_score)}</div></div>
    </details>`;
  }

  renderMatchDetail=function(m){
    const pbp=m.early_hold_v7?.ready;
    return `<div class="match-detail v75-detail">
      <div class="v75-detail-head">
        <div><span>${tour75(m)} · ${esc75(m.tournament||'Turniej')} · ${esc75(surface75(m))}</span><b>${esc75(m.p1)} <i>vs</i> ${esc75(m.p2)}</b><small>${date75(m)} · ${sched75(m)}</small></div>
        <div class="v75-head-badges"><em class="${pbp?'ok':'nd'}">${pbp?'PBP OK':'PBP N/D'}</em><em>MODEL ${Math.round(num75(m.model_confidence)||0)}</em></div>
      </div>
      ${quickVerdict75(m)}
      <div class="v75-accordions">${coreMarkets75(m)}${stats75(m)}${earlyHold75(m)}${serve75(m)}${lab75(m)}${models75(m)}</div>
      <div class="v75-model-note">Wyniki to sygnały modelu i estymacje, nie gwarancja wyniku ani skalibrowane kursy bukmacherskie.</div>
    </div>`;
  };

  renderMatchCard=function(m){
    const key=typeof matchKey==='function'?matchKey(m):`m:${m.id||m.p1+m.p2}`;
    const top=top75(m,1)[0],strength=strength75(m),greens=greenCount75(m),st=status75(m);
    const pbp=m.early_hold_v7?.ready;
    return `<details class="match-card v75-card" data-state-key="${esc75(key)}" ${(typeof detailOpen==='function'&&detailOpen(key,false))?'open':''}>
      <summary class="v75-summary">
        <div class="v75-card-meta"><span class="v75-status ${st.c}">${st.t}</span><b>${tour75(m)}</b><span>${esc75(m.tournament||'Turniej')}</span><span>• ${esc75(surface75(m))}</span><time>${sched75(m)}</time></div>
        <div class="v75-card-main">
          <div class="v75-players"><b>${esc75(m.p1)}</b><i>vs</i><b>${esc75(m.p2)}</b></div>
          <div class="v75-card-signal"><span>🎯 Top sygnał</span><b>${esc75(top?.label||'Brak mocnego sygnału')}</b><em>${top?pct75(top.v):'—'}</em></div>
        </div>
        <div class="v75-card-score ${strengthClass75(strength)}"><span>Siła sygnału</span><b>${Math.round(strength)||'—'}</b><div>${Array.from({length:5},(_,i)=>`<i class="${strength>=(i+1)*18?'on':''}"></i>`).join('')}</div><small>${greens} zielonych</small></div>
        <div class="v75-card-foot"><span>${pbp?'🧬 PBP OK':'🧠 Adaptive'}</span><span>Dane ${esc75(m.quality||'—')}</span><b>Pokaż analizę <i>⌄</i></b></div>
      </summary>
      ${renderMatchDetail(m)}
    </details>`;
  };

  function topStrip75(rows){
    const picks=rows.map(m=>({m,s:top75(m,1)[0]})).filter(x=>x.s&&x.s.v>=72).sort((a,b)=>b.s.v-a.s.v).slice(0,3);
    if(!picks.length)return '';
    return `<section class="v75-top-strip"><div class="v75-strip-title"><b>⚡ Najmocniejsze teraz</b><small>${picks.length} top sygnały</small></div><div class="v75-strip-grid">${picks.map(({m,s})=>`<button type="button" data-v75-open="${esc75(String(m.id??''))}"><span>${esc75(m.p1)} vs ${esc75(m.p2)}</span><b>${esc75(s.label)}</b><strong>${pct75(s.v)}</strong></button>`).join('')}</div></section>`;
  }

  renderMatches=function(){
    const app=document.querySelector('#app');
    let rows=(typeof filteredReady==='function'?filteredReady():[]).filter(m=>filter==='all'||tourKey(m)===filter);
    if(ui75.focus==='strong')rows=rows.filter(m=>strength75(m)>=80);
    if(ui75.focus==='pbp')rows=rows.filter(m=>m.early_hold_v7?.ready);
    rows.sort((a,b)=>new Date(a.scheduled_time||0)-new Date(b.scheduled_time||0));
    if(!rows.length){app.innerHTML='<div class="empty"><b>Brak meczów dla tego filtra.</b><br><br>Zmień filtr lub wróć do „Wszystkie”.</div>';return}

    const groups=new Map();
    rows.forEach(m=>{
      const k=typeof tournamentKey==='function'?tournamentKey(m):`${tour75(m)}:${m.tournament}`;
      if(!groups.has(k))groups.set(k,{key:k,name:m.tournament||'Turniej',tour:tour75(m),matches:[]});
      groups.get(k).matches.push(m);
    });

    app.innerHTML=`<div class="v75-focus">
      <button class="${ui75.focus==='all'?'active':''}" data-v75-focus="all">Wszystkie</button>
      <button class="${ui75.focus==='strong'?'active':''}" data-v75-focus="strong">⭐ 80+</button>
      <button class="${ui75.focus==='pbp'?'active':''}" data-v75-focus="pbp">🧬 PBP OK</button>
    </div>
    ${topStrip75(rows)}
    <div class="tournament-list v75-tournaments">${[...groups.values()].map(g=>{
      const key=g.key,open=typeof detailOpen==='function'?detailOpen(key,true):true;
      const surfaces=[...new Set(g.matches.map(x=>surface75(x)).filter(Boolean))];
      return `<details class="tournament-group v75-tournament" data-state-key="${esc75(key)}" ${open?'open':''}>
        <summary class="tournament-summary v75-tournament-summary"><div><span class="tour-badge">${esc75(g.tour)}</span><b>${esc75(g.name)}</b><small>${g.matches.length} ${g.matches.length===1?'mecz':'meczów'} · ${esc75(surfaces.join('/'))}</small></div><span class="group-chev">⌄</span></summary>
        <div class="tournament-body">${g.matches.map(renderMatchCard).join('')}</div>
      </details>`;
    }).join('')}</div>`;

    document.querySelectorAll('[data-v75-focus]').forEach(b=>b.onclick=()=>{ui75.focus=b.dataset.v75Focus;save75();renderMatches()});
    document.querySelectorAll('[data-v75-open]').forEach(b=>b.onclick=()=>{
      const id=b.dataset.v75Open;
      const card=[...document.querySelectorAll('.v75-card')].find(d=>d.querySelector('.v75-summary')?.innerHTML && String(d.dataset.stateKey||'').includes(id));
      if(card){card.open=true;card.scrollIntoView({behavior:'smooth',block:'start'})}
    });
    if(typeof bindCollapseState==='function')bindCollapseState();
  };

  function histStatus75(e){
    if(e.status==='settled')return {t:'ROZLICZONY',c:'settled',icon:'✓'};
    if(e.status==='void')return {t:'VOID',c:'void',icon:'↩'};
    const s=String(e.live_status||'').toLowerCase();
    if(s.includes('interrupt'))return {t:'PRZERWANY',c:'interrupted',icon:'!'};
    if(s.includes('suspend'))return {t:'ZAWIESZONY',c:'suspended',icon:'‖'};
    if(s.includes('postpon'))return {t:'PRZEŁOŻONY',c:'postponed',icon:'↷'};
    if(s.includes('progress')||s==='live')return {t:'W TRAKCIE',c:'live',icon:'●'};
    return {t:'CZEKA',c:'pending',icon:'○'};
  }
  function histScore75(e){
    const r=e.result;
    if(!r)return '';
    if(Array.isArray(r.sets))return r.sets.map(s=>Array.isArray(s)?s.join(':'):'').filter(Boolean).join(' · ');
    return r.score_text||'';
  }
  function histDayKey75(v){
    const d=new Date(v||'');if(!Number.isFinite(d.getTime()))return 'bez-daty';
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }
  function histDayLabel75(k){
    if(k==='bez-daty')return 'Bez daty';
    const [y,m,d]=k.split('-').map(Number),x=new Date(y,m-1,d),today=histDayKey75(new Date());
    const yesterday=histDayKey75(new Date(new Date().setDate(new Date().getDate()-1)));
    if(k===today)return `Dzisiaj · ${x.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'})}`;
    if(k===yesterday)return `Wczoraj · ${x.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'})}`;
    return x.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric'});
  }

  renderHistory=function(){
    const app=document.querySelector('#app');
    const rows=(Array.isArray(historyRows)?historyRows:[]).filter(e=>(e.signals||[]).length).slice(0,220);
    if(!rows.length){app.innerHTML='<div class="empty">Historia jest jeszcze pusta.</div>';return}
    const counts={all:rows.length,settled:0,pending:0,special:0};
    rows.forEach(e=>{const s=histStatus75(e);if(s.c==='settled')counts.settled++;else if(['interrupted','suspended','postponed','live'].includes(s.c))counts.special++;else counts.pending++});
    const groups=new Map();rows.forEach(e=>{const k=histDayKey75(e.scheduled_time);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(e)});
    const ordered=[...groups.entries()].sort((a,b)=>b[0].localeCompare(a[0]));
    app.innerHTML=`<section class="v75-history-stats">
      <div><b>${counts.all}</b><span>Mecze</span></div><div><b>${counts.settled}</b><span>Rozliczone ✓</span></div><div><b>${counts.pending}</b><span>Czeka ○</span></div><div><b>${counts.special}</b><span>Specjalne !</span></div>
    </section>
    <div class="v75-history-days">${ordered.map(([k,list],idx)=>`<details class="v75-history-day" ${idx===0?'open':''}>
      <summary><div><b>${esc75(histDayLabel75(k))}</b><small>${list.length} ${list.length===1?'mecz':'meczów'}</small></div><span>${list.length}</span><i>⌄</i></summary>
      <div class="v75-history-body">${list.map(e=>{
        const st=histStatus75(e),sc=histScore75(e),hits=(e.signals||[]).filter(s=>s.result==='hit').length,miss=(e.signals||[]).filter(s=>s.result==='miss').length;
        return `<details class="v75-history-card ${st.c}"><summary>
          <div><b>${esc75(e.p1)} <i>vs</i> ${esc75(e.p2)}</b><small>${esc75((e.tour||'').toUpperCase())} · ${esc75(e.tournament||'Turniej')} · ${sched75(e)}</small>${sc?`<em>${esc75(sc)}</em>`:''}</div>
          <span class="v75-hstatus ${st.c}">${st.icon} ${st.t}</span><i>›</i>
        </summary><div class="v75-history-detail"><div class="v75-history-result"><span>✅ ${hits}</span><span>❌ ${miss}</span><span>🧾 ${(e.signals||[]).length} sygnałów</span></div>
          ${(e.signals||[]).map(s=>`<div class="v75-history-signal ${s.result||'pending'}"><span>${esc75(s.label)}</span><b>${esc75(s.pick)} · ${s.score==null?'—':Math.round(s.score)+'/100'}</b><em>${esc75(s.result||'pending')}</em></div>`).join('')}
        </div></details>`;
      }).join('')}</div>
    </details>`).join('')}</div>`;
  };

  // Make the large community block a compact launcher. It remains fully clickable.
  function compactCommunity75(){
    const c=document.querySelector('#community-live-stats');
    if(c)c.classList.add('v75-community-compact');
  }

  // Bottom nav labels: keep existing functions/events, only styling changes in CSS.
  function reRender75(){
    try{
      if(typeof view!=='undefined'&&view==='matches')renderMatches();
      else if(typeof view!=='undefined'&&view==='history')renderHistory();
    }catch(e){console.warn('Tenis AI v7.5 rerender',e)}
  }

  compactCommunity75();
  setTimeout(()=>{compactCommunity75();reRender75()},350);
  window.addEventListener('tenis-ai-auth-change',()=>setTimeout(compactCommunity75,50));
})();