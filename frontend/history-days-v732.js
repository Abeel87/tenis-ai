/* Tenis AI v7.3.2 — Historia: dni + czytelne statusy */
(() => {
  if (typeof renderHistory !== 'function') return;

  const DAY_KEY='tenis-ai-v732-history-days';
  const read=()=>{try{return JSON.parse(localStorage.getItem(DAY_KEY)||'{}')||{}}catch{return {}}};
  const save=x=>{try{localStorage.setItem(DAY_KEY,JSON.stringify(x))}catch{}};
  let dayState=read();

  const localKey=value=>{
    const d=new Date(value||''); if(isNaN(d)) return 'bez-daty';
    const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${day}`;
  };
  const dayLabel=key=>{
    if(key==='bez-daty') return 'Bez daty';
    const [y,m,d]=key.split('-').map(Number); const dt=new Date(y,m-1,d);
    const now=new Date(); const today=localKey(now); const yesterday=localKey(new Date(now.getFullYear(),now.getMonth(),now.getDate()-1));
    const pretty=dt.toLocaleDateString('pl-PL',{weekday:'long',day:'2-digit',month:'2-digit'});
    if(key===today) return `Dzisiaj · ${pretty}`;
    if(key===yesterday) return `Wczoraj · ${pretty}`;
    return pretty.charAt(0).toUpperCase()+pretty.slice(1);
  };

  function statusInfo(e){
    if(e.status==='settled') return {text:'ROZLICZONY',cls:'settled',icon:'✅'};
    if(e.status==='void'){
      const why=String(e.result?.reason||e.result?.score_text||'').toLowerCase();
      if(why.includes('retir')) return {text:'KRETCZ / VOID',cls:'retired',icon:'↩️'};
      if(why.includes('walk')) return {text:'WALKOWER / VOID',cls:'walkover',icon:'↩️'};
      if(why.includes('cancel')) return {text:'ANULOWANY / VOID',cls:'cancelled',icon:'⛔'};
      return {text:'NIE LICZYMY',cls:'void',icon:'↩️'};
    }
    const s=String(e.live_status||'').trim().toLowerCase();
    if(s.includes('interrupt')) return {text:'PRZERWANY',cls:'interrupted',icon:'⏸️'};
    if(s.includes('suspend')) return {text:'ZAWIESZONY',cls:'suspended',icon:'⏸️'};
    if(s.includes('postpon')) return {text:'PRZEŁOŻONY',cls:'postponed',icon:'📅'};
    if(s.includes('delay')) return {text:'OPÓŹNIONY',cls:'delayed',icon:'🕒'};
    if(s.includes('progress')||s.includes('started')||s==='live') return {text:'W TRAKCIE',cls:'live',icon:'🔴'};
    return {text:'OCZEKUJE',cls:'pending',icon:'⏳'};
  }

  function finalText(e){
    const r=e.result;
    if(!r){
      const st=statusInfo(e);
      if(st.cls==='interrupted') return 'Mecz przerwany — czekamy na wznowienie';
      if(st.cls==='suspended') return 'Mecz zawieszony — czekamy na wznowienie';
      if(st.cls==='postponed') return 'Mecz przełożony — czekamy na nowy termin';
      if(st.cls==='delayed') return 'Start/opóźnienie — czekamy na aktualizację';
      if(st.cls==='live') return 'Mecz nadal trwa';
      return 'Oczekuje na wynik';
    }
    if(r.status==='void') return r.reason?`Nierozliczany · ${r.reason}`:'Mecz nierozliczany';
    if(r.sets?.length) return r.sets.map(s=>s.join(':')).join(' · ');
    return r.score_text||'Zakończony';
  }

  function card(e){
    const st=statusInfo(e);
    return `<article class="history-card v732-history-card">
      <div class="top"><span>${esc((e.tour||'').toUpperCase())} · ${esc(e.tournament||'—')}</span><span class="history-status v732-status ${st.cls}">${st.icon} ${st.text}</span></div>
      <div class="history-match">${esc(e.p1)} <span>vs</span> ${esc(e.p2)}</div>
      <div class="history-score">${esc(finalText(e))}</div>
      <details><summary>Zielone typy (${e.signals.length}) <span class="chev">⌄</span></summary><div class="history-signals">${e.signals.map(s=>`<div class="history-signal ${s.result||'pending'}"><div><b>${resultIcon(s.result)} ${esc(s.label)}</b><span>${esc(s.pick)} · ${score(s.score)}</span></div><strong>${resultText(s.result)}</strong></div>`).join('')}</div></details>
    </article>`;
  }

  function groupCounts(rows){
    const x={settled:0,pending:0,special:0};
    rows.forEach(e=>{const st=statusInfo(e);if(st.cls==='settled')x.settled++;else if(['interrupted','suspended','postponed','delayed','live'].includes(st.cls))x.special++;else x.pending++});
    return x;
  }

  renderHistory=function(){
    const app=document.querySelector('#app');
    const rows=historyRows.filter(e=>{
      if(!(e.signals||[]).length)return false;
      if(e.status==='settled'||e.status==='void')return true;
      const t=new Date(e.scheduled_time||'').getTime();
      return Number.isFinite(t)&&t<=Date.now()+5*60*1000;
    }).slice(0,220);
    if(!rows.length){app.innerHTML='<div class="empty"><b>Historia jest jeszcze pusta.</b><br><br>Zielone sygnały będą tu zapisywane po starcie spotkania.</div>';return}

    const groups=new Map();
    rows.forEach(e=>{const k=localKey(e.scheduled_time);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(e)});
    const ordered=[...groups.entries()].sort((a,b)=>b[0].localeCompare(a[0]));
    const newest=ordered[0]?.[0];

    app.innerHTML=`<div class="history-head v732-history-head"><div><b>🕘 Historia zielonych sygnałów</b><span>${rows.length} ostatnich meczów · ${ordered.length} dni</span></div><div class="v732-day-actions"><button data-v732-days="close">Zwiń dni</button><button data-v732-days="open">Rozwiń dni</button></div></div>
      <div class="v732-day-list">${ordered.map(([key,list])=>{
        const c=groupCounts(list); const open=dayState[key]===true||(dayState[key]===undefined&&key===newest);
        const extras=c.special?` · ${c.special} status specjalny`:'';
        return `<details class="v732-day" data-v732-day="${esc(key)}" ${open?'open':''}><summary><div><b>${esc(dayLabel(key))}</b><small>${list.length} ${list.length===1?'mecz':'meczów'} · ${c.settled} rozliczonych${c.pending?` · ${c.pending} czeka`:''}${extras}</small></div><span class="v732-day-chevron">⌄</span></summary><div class="v732-day-body">${list.map(card).join('')}</div></details>`;
      }).join('')}</div>`;

    app.querySelectorAll('[data-v732-day]').forEach(d=>d.addEventListener('toggle',()=>{dayState[d.dataset.v732Day]=d.open;save(dayState)}));
    app.querySelector('[data-v732-days="close"]')?.addEventListener('click',()=>{app.querySelectorAll('[data-v732-day]').forEach(d=>{d.open=false;dayState[d.dataset.v732Day]=false});save(dayState)});
    app.querySelector('[data-v732-days="open"]')?.addEventListener('click',()=>{app.querySelectorAll('[data-v732-day]').forEach(d=>{d.open=true;dayState[d.dataset.v732Day]=true});save(dayState)});
  };
})();