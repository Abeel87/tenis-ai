/* Tenis AI · History UI
   Canonical history-only renderer extracted from the retired v7.5 match UI.
   It does not own match-list filtering, Top signals, model math or PLAYABLE logic.
*/
(()=>{
  'use strict';

  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const sched=e=>{
    const d=new Date(e?.scheduled_time||'');
    return Number.isFinite(d.getTime())?d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'}):'—';
  };
  const rows=()=>{
    try{return Array.isArray(historyRows)?historyRows:[]}catch{return[]}
  };

  function status(e){
    if(e?.status==='settled')return {t:'ROZLICZONY',c:'settled',icon:'✓'};
    if(e?.status==='void')return {t:'VOID',c:'void',icon:'↩'};
    const s=String(e?.live_status||'').toLowerCase();
    if(s.includes('interrupt'))return {t:'PRZERWANY',c:'interrupted',icon:'!'};
    if(s.includes('suspend'))return {t:'ZAWIESZONY',c:'suspended',icon:'‖'};
    if(s.includes('postpon'))return {t:'PRZEŁOŻONY',c:'postponed',icon:'↷'};
    if(s.includes('progress')||s==='live')return {t:'W TRAKCIE',c:'live',icon:'●'};
    return {t:'CZEKA',c:'pending',icon:'○'};
  }

  function score(e){
    const r=e?.result;
    if(!r)return '';
    if(Array.isArray(r.sets))return r.sets.map(s=>Array.isArray(s)?s.join(':'):'').filter(Boolean).join(' · ');
    return r.score_text||'';
  }

  function dayKey(v){
    const d=new Date(v||'');
    if(!Number.isFinite(d.getTime()))return 'bez-daty';
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }

  function dayLabel(k){
    if(k==='bez-daty')return 'Bez daty';
    const [y,m,d]=k.split('-').map(Number),x=new Date(y,m-1,d),today=dayKey(new Date());
    const yesterday=dayKey(new Date(new Date().setDate(new Date().getDate()-1)));
    if(k===today)return `Dzisiaj · ${x.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'})}`;
    if(k===yesterday)return `Wczoraj · ${x.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'})}`;
    return x.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric'});
  }

  function render(){
    const app=document.querySelector('#app');
    if(!app)return;
    const history=rows().filter(e=>(e.signals||[]).length).slice(0,220);
    if(!history.length){app.innerHTML='<div class="empty">Historia jest jeszcze pusta.</div>';return}

    const counts={all:history.length,settled:0,pending:0,special:0};
    history.forEach(e=>{
      const s=status(e);
      if(s.c==='settled')counts.settled++;
      else if(['interrupted','suspended','postponed','live'].includes(s.c))counts.special++;
      else counts.pending++;
    });

    const groups=new Map();
    history.forEach(e=>{
      const k=dayKey(e.scheduled_time);
      if(!groups.has(k))groups.set(k,[]);
      groups.get(k).push(e);
    });
    const ordered=[...groups.entries()].sort((a,b)=>b[0].localeCompare(a[0]));

    app.innerHTML=`<section class="v75-history-stats">
      <div><b>${counts.all}</b><span>Mecze</span></div><div><b>${counts.settled}</b><span>Rozliczone ✓</span></div><div><b>${counts.pending}</b><span>Czeka ○</span></div><div><b>${counts.special}</b><span>Specjalne !</span></div>
    </section>
    <div class="v75-history-days">${ordered.map(([k,list],idx)=>`<details class="v75-history-day" ${idx===0?'open':''}>
      <summary><div><b>${esc(dayLabel(k))}</b><small>${list.length} ${list.length===1?'mecz':'meczów'}</small></div><span>${list.length}</span><i>⌄</i></summary>
      <div class="v75-history-body">${list.map(e=>{
        const st=status(e),sc=score(e),hits=(e.signals||[]).filter(s=>s.result==='hit').length,miss=(e.signals||[]).filter(s=>s.result==='miss').length;
        return `<details class="v75-history-card ${st.c}"><summary>
          <div><b>${esc(e.p1)} <i>vs</i> ${esc(e.p2)}</b><small>${esc((e.tour||'').toUpperCase())} · ${esc(e.tournament||'Turniej')} · ${sched(e)}</small>${sc?`<em>${esc(sc)}</em>`:''}</div>
          <span class="v75-hstatus ${st.c}">${st.icon} ${st.t}</span><i>›</i>
        </summary><div class="v75-history-detail"><div class="v75-history-result"><span>✅ ${hits}</span><span>❌ ${miss}</span><span>🧾 ${(e.signals||[]).length} sygnałów</span></div>
          ${(e.signals||[]).map(s=>`<div class="v75-history-signal ${s.result||'pending'}"><span>${esc(s.label)}</span><b>${esc(s.pick)} · ${s.score==null?'—':Math.round(s.score)+'/100'}</b><em>${esc(s.result||'pending')}</em></div>`).join('')}
        </div></details>`;
      }).join('')}</div>
    </details>`).join('')}</div>`;
  }

  window.renderHistory=render;
  window.TENIS_AI_HISTORY_UI=Object.freeze({render});
})();
