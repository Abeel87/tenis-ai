/* Tenis AI v7.5.1 — PROJECT UI
   The visual layer follows the approved three-screen mockup:
   clean match list -> dedicated full-screen match detail -> compact history.
   Model/tracker calculations are not changed.
*/
(() => {
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>x==null||!Number.isFinite(Number(x))?null:Number(x);
  const pc=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const key=m=>String(m?.id ?? m?.match_id ?? [m?.p1,m?.p2,m?.scheduled_time].join('|'));
  const tm=m=>{const d=new Date(m?.scheduled_time||'');return Number.isFinite(d.getTime())?d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'}):'—'};
  const dt=m=>{const d=new Date(m?.scheduled_time||'');return Number.isFinite(d.getTime())?d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit',year:'numeric'}):''};
  const surf=m=>String(m?.surface||'').trim()||'—';
  const tour=m=>{
    const t=String(m?.tour||'').toLowerCase();
    if(t.includes('chall'))return 'CH';
    if(t.includes('itf'))return 'ITF';
    return t.toUpperCase()||'TENIS';
  };

  let focus='all';
  let route='matches';

  const UI_MODE_KEY='tenis-ai-clean-ui-mode';
  function uiRole(){
    return String(
      document.documentElement.dataset.tenisRole ||
      window.tenisAIAccount?.profile?.role ||
      window.tenisAICommunityHub?.profile?.role ||
      'user'
    ).toLowerCase();
  }
  function isUiAdmin(){return uiRole()==='admin'}
  function updateUiModeButton(){
    const button=document.querySelector('#tenis-ui-mode-toggle');
    if(!button)return;
    const technical=document.documentElement.dataset.tenisUiMode==='technical'&&isUiAdmin();
    const copy=button.querySelector('small');
    const icon=button.querySelector('span');
    if(icon)icon.textContent=technical?'🛠️':'👁️';
    if(copy)copy.textContent=technical?'Techniczny':'Prosty';
    button.setAttribute('aria-pressed',technical?'true':'false');
  }
  function setUiMode(mode,{persist=true}={}){
    const next=isUiAdmin()&&mode==='technical'?'technical':'simple';
    document.documentElement.dataset.tenisUiMode=next;
    document.documentElement.dataset.tenisStatsMode=next==='technical'?'pro':'simple';
    if(persist&&isUiAdmin()){
      try{localStorage.setItem(UI_MODE_KEY,next)}catch{}
    }
    updateUiModeButton();
    window.dispatchEvent(new CustomEvent('tenis-ai-ui-mode-change',{detail:{mode:next,role:uiRole(),admin:isUiAdmin()}}));
    return next;
  }
  function syncUiMode(){
    let requested='simple';
    if(isUiAdmin()){
      try{requested=localStorage.getItem(UI_MODE_KEY)==='technical'?'technical':'simple'}catch{}
    }
    return setUiMode(requested,{persist:false});
  }
  function bindUiMode(){
    const button=document.querySelector('#tenis-ui-mode-toggle');
    if(button&&button.dataset.cleanUiBound!=='1'){
      button.dataset.cleanUiBound='1';
      button.addEventListener('click',()=>{
        const current=document.documentElement.dataset.tenisUiMode||'simple';
        setUiMode(current==='technical'?'simple':'technical');
      });
    }
    syncUiMode();
  }

  const modelApi=()=>window.TENIS_AI_MODEL_API||null;
  const activeModelId=()=>modelApi()?.active||'adaptive';
  const activeModelName=()=>modelApi()?.activeName?.()||'🧠 Adaptive';

  // v7.8E2.3: cache expensive allSignals() per match + active model.
  const signalCache78e23=new WeakMap();
  function modelAllSignals(m){
    try{
      if(!m || typeof m!=='object') return modelApi()?.allSignals?.(m)||[];
      let byModel=signalCache78e23.get(m);
      if(!byModel){byModel=new Map();signalCache78e23.set(m,byModel)}
      const id=activeModelId();
      if(byModel.has(id)) return byModel.get(id);
      const rows=modelApi()?.allSignals?.(m)||[];
      byModel.set(id,rows);
      return rows;
    }catch{return []}
  }
  function modelMarketRows(m,market){return modelAllSignals(m).filter(x=>x&&x.market===market&&num(x.v)!=null)}
  function modelLine(x){const p=String(x?.key||'').split('|');return p.length>1?p[1]:''}
  const signalIsProbability=()=>activeModelId()==='adaptive';
  const signalText=v=>num(v)==null?'—':(signalIsProbability()?`${Math.round(Number(v))}%`:`${Math.round(Number(v))}/100`);

  function status(m){
    return window.TENIS_AI_MATCH_TIME?.cardStatus(m)||{txt:'STATUS N/D',cls:'unknown'};
  }

  function addBest(arr,label,obj,kind='model'){
    if(!obj)return;
    const best=Object.entries(obj).filter(([,v])=>num(v)!=null).sort((a,b)=>Number(b[1])-Number(a[1]))[0];
    if(best)arr.push({label:`${label}: ${best[0]}`,value:Number(best[1]),kind});
  }
  function signals(m){
    const api=modelApi();
    if(api?.signals){
      try{
        return (api.signals(m,40)||[]).map(x=>({label:x.label||x.key||'Sygnał',value:Number(x.v),kind:'selected-model',market:x.market,pick:x.pick,key:x.key,source_model:activeModelId()}))
          .filter(x=>num(x.value)!=null).sort((a,b)=>b.value-a.value);
      }catch{}
    }
    if(api?.allSignals){
      return modelAllSignals(m).map(x=>({label:x.label||x.key||'Sygnał',value:Number(x.v),kind:'selected-model',market:x.market,pick:x.pick,key:x.key,source_model:activeModelId()}))
        .filter(x=>num(x.value)!=null).sort((a,b)=>b.value-a.value);
    }
    const a=[];
    addBest(a,'Mecz',m.match_win);addBest(a,'1. set',m.first_set_win);addBest(a,'2. set',m.second_set_win);addBest(a,'Sety',m.total_sets);
    Object.entries(m.over_under||{}).forEach(([ln,v])=>{const o=num(v?.over),u=num(v?.under);if(o==null||u==null)return;a.push({label:`1S ${o>=u?'OVER':'UNDER'} ${ln}`,value:Math.max(o,u),kind:'set'})});
    Object.entries(m.match_over_under||{}).forEach(([ln,v])=>{const o=num(v?.over),u=num(v?.under);if(o==null||u==null)return;a.push({label:`Mecz ${o>=u?'OVER':'UNDER'} ${ln}`,value:Math.max(o,u),kind:'match'})});
    const seen=new Set();return a.filter(x=>!seen.has(x.label)&&seen.add(x.label)).sort((x,y)=>y.value-x.value);
  }
  const top=(m,n=1)=>signals(m).filter(x=>x.value>=55).slice(0,n);
  const strength=m=>top(m,1)[0]?.value ?? num(m.model_confidence) ?? 0;
  const greens=m=>signals(m).filter(x=>x.value>=72).length;

  function currentRows(){
    let rows=(typeof filteredReady==='function'?filteredReady():Array.isArray(all)?all:[]).filter(Boolean);
    if(typeof filter!=='undefined'&&filter!=='all'&&typeof tourKey==='function')rows=rows.filter(m=>tourKey(m)===filter);
    if(focus==='strong')rows=rows.filter(m=>{
      const signal=window.TENIS_AI_PLAYABLE_UI_V917?.playableSignals?.(m,1)?.[0];
      return num(signal?.v??signal?.final_score??signal?.score??signal?.current)>=80;
    });
    if(focus==='pbp')rows=rows.filter(m=>m.early_hold_v7?.ready);
    if(focus==='live')rows=rows.filter(m=>status(m).cls==='live');
    rows.sort((a,b)=>new Date(a.scheduled_time||0)-new Date(b.scheduled_time||0));
    return rows;
  }

  function signalBars(v){
    return `<span class="p751-bars">${[1,2,3,4,5].map(i=>`<i class="${v>=i*18?'on':''}"></i>`).join('')}</span>`;
  }

  function topStrip(rows){
    const picks=rows.map(m=>({m,s:top(m,1)[0]}))
      .filter(x=>x.s&&x.s.value>=72)
      .sort((a,b)=>b.s.value-a.s.value)
      .slice(0,3);
    if(!picks.length)return '';
    return `<section class="signal-spotlight">
      <header>
        <div><span>NAJMOCNIEJSZE TERAZ</span><b>Top sygnały</b></div>
        <small>${picks.length} wybrane z aktualnych meczów</small>
      </header>
      <div class="signal-spotlight-grid">${picks.map(({m,s},i)=>`<button class="signal-spotlight-card ${i===0?'primary':''}" data-p751-open="${encodeURIComponent(key(m))}">
        <span>${esc(tour(m))} · ${esc(tm(m))}</span>
        <b>${esc(m.p1)} <i>vs</i> ${esc(m.p2)}</b>
        <small>${esc(s.label)}</small>
        <strong>${signalText(s.value)}</strong>
      </button>`).join('')}</div>
    </section>`;
  }


  function sameMatchTotalAsTop(s,z){
    if(!s||!z)return false;

    const line=String(z.ln||'').trim();
    const side=String(z.side||'').toUpperCase().startsWith('O')?'O':'U';

    if(s.market==='match_total'){
      const sLine=String(modelLine(s)||'').trim();
      const sSide=String(s.pick||'').toUpperCase().startsWith('O')?'O':'U';
      return sLine===line && sSide===side;
    }

    const label=String(s.label||'')
      .toUpperCase()
      .replace(/OVER/g,'O')
      .replace(/UNDER/g,'U')
      .replace(/\s+/g,'');

    return label.includes('MECZ') && label.includes(`${side}${line}`);
  }

  function matchGamesPreview(m,topSignal=null){
    const selected=modelMarketRows(m,'match_total')
      .map(x=>({
        ln:modelLine(x),
        side:String(x.pick||'').toUpperCase(),
        v:Number(x.v)
      }))
      .filter(x=>x.ln&&num(x.v)!=null)
      .sort((a,b)=>b.v-a.v);

    if(selected.length){
      const z=selected[0];
      if(sameMatchTotalAsTop(topSignal,z))return '';

      const exp=num(m.expected_match_games);

      return `<div class="p753-match-total-preview">
        <span>📊 Gemy · cały mecz · ${esc(activeModelName())}</span>
        <b>${esc(z.side)} ${esc(z.ln)}</b>
        <strong>${signalText(z.v)}</strong>
        ${exp!=null?`<em>śr. Adaptive ${exp.toFixed(1)}</em>`:''}
      </div>`;
    }

    const e=Object.entries(m.match_over_under||{})
      .map(([ln,x])=>{
        const o=num(x?.over),u=num(x?.under);
        return o==null||u==null
          ?null
          :{ln,side:o>=u?'OVER':'UNDER',v:Math.max(o,u)};
      })
      .filter(Boolean)
      .sort((a,b)=>b.v-a.v);

    if(!e.length)return '';

    const z=e[0];
    if(sameMatchTotalAsTop(topSignal,z))return '';

    const exp=num(m.expected_match_games);

    return `<div class="p753-match-total-preview">
      <span>📊 Gemy · cały mecz · Adaptive baza</span>
      <b>${z.side} ${esc(z.ln)}</b>
      <strong>${Math.round(z.v)}%</strong>
      ${exp!=null?`<em>śr. ${exp.toFixed(1)}</em>`:''}
    </div>`;
  }

  function matchGamesLines(m){
    const selected=modelMarketRows(m,'match_total'),exp=num(m.expected_match_games);
    if(selected.length)return `<div class="p751-lines p756-match-lines"><label>📊 Linie gemów · cały mecz · ${esc(activeModelName())}${exp!=null?` · śr. Adaptive ${exp.toFixed(1)}`:''}</label><div>${selected.map(x=>{const ln=modelLine(x),v=Number(x.v),side=String(x.pick||'').toUpperCase().startsWith('O')?'O':'U';return `<span class="${v>=72?'strong':''}"><b>${esc(ln)}</b><small>${side} ${signalText(v)}</small></span>`}).join('')}</div></div>`;
    const e=Object.entries(m.match_over_under||{});if(!e.length)return `<div class="p751-lines p756-match-lines"><label>📊 Linie gemów · cały mecz</label><p class="p751-note">Brak danych O/U całego meczu.</p></div>`;
    return `<div class="p751-lines p756-match-lines"><label>📊 Linie gemów · cały mecz · Adaptive baza${exp!=null?` · śr. ${exp.toFixed(1)}`:''}</label><div>${e.map(([ln,x])=>{const o=num(x?.over),u=num(x?.under),mx=Math.max(o||0,u||0),side=(o||0)>=(u||0)?'O':'U';return `<span class="${mx>=72?'strong':''}"><b>${esc(ln)}</b><small>${side} ${Math.round(mx)}%</small></span>`}).join('')}</div></div>`;
  }

  function card(m){
    const s=top(m,1)[0],v=strength(m),st=status(m);
    const second=top(m,2)[1];
    const playable=window.TENIS_AI_PLAYABLE_UI_V917?.playableSignals?.(m,3)||[];
    const playableCount=Array.isArray(playable)?playable.length:0;
    return `<article class="p751-match-card match-tile" data-p751-open="${encodeURIComponent(key(m))}" role="button" tabindex="0">
      <header class="match-tile-head">
        <div>
          ${window.TENIS_AI_MATCH_TIME?.badgeHtml(m)||`<span class="match-status ${st.cls}">${esc(st.txt)}</span>`}
          <span class="match-tour">${esc(tour(m))}</span>
          <span class="match-time">${esc(tm(m))}</span>
        </div>
        <span class="match-surface">${esc(surf(m))}</span>
      </header>
      <div class="match-tile-main">
        <div class="match-tile-copy">
          <div class="match-tile-event">${esc(m.tournament||'Turniej')}</div>
          <div class="match-tile-players">
            <b class="v762-player-link" role="link" tabindex="0">${esc(m.p1)}</b>
            <span>vs</span>
            <b class="v762-player-link" role="link" tabindex="0">${esc(m.p2)}</b>
          </div>
          <div class="match-tile-pick">
            <span>Najlepszy typ</span>
            <b>${esc(s?.label||'Brak mocnego sygnału')}</b>
            ${second?`<small>Alternatywa: ${esc(second.label)} · ${signalText(second.value)}</small>`:''}
          </div>
        </div>
        <aside class="match-tile-score">
          <span>Siła</span>
          <strong>${v>0?signalText(v):'—'}</strong>
          <small>${playableCount?playableCount+' PLAYABLE':greens(m)+' mocnych'}</small>
        </aside>
      </div>
      <footer class="match-tile-foot">
        <span>${m.early_hold_v7?.ready?'PBP gotowe':'PBP N/D'}</span>
        <span class="phase11-technical">Dane ${esc(m.quality||'—')}</span>
        <b>Analiza meczu <i>→</i></b>
      </footer>
    </article>`;
  }

  function groupRows(rows){
    const groups=new Map();
    rows.forEach(m=>{
      const k=`${tour(m)}|${m.tournament||'Turniej'}`;
      if(!groups.has(k))groups.set(k,{tour:tour(m),name:m.tournament||'Turniej',rows:[]});
      groups.get(k).rows.push(m);
    });
    return [...groups.values()];
  }

  function focusBar(){
    return `<div class="match-filter-row">
      <button class="${focus==='all'?'active':''}" data-p751-focus="all">Wszystkie</button>
      <button class="${focus==='strong'?'active':''}" data-p751-focus="strong">Mocne 80+</button>
      <button class="${focus==='pbp'?'active':''}" data-p751-focus="pbp">PBP gotowe</button>
      <button class="${focus==='live'?'active':''}" data-p751-focus="live">Na żywo</button>
    </div>`;
  }

  renderMatches=function(){
    route='matches';
    navActive('matches');
    document.documentElement.dataset.tenisRoute='matches';
    const app=document.querySelector('#app');
    const rows=currentRows();
    if(!rows.length){
      app.innerHTML=`<section class="match-browser-head">${focusBar()}</section>
        <div class="empty-state"><b>Brak meczów dla tego filtra.</b><span>Zmień filtr albo wróć do wszystkich spotkań.</span></div>`;
      bindHome();
      return;
    }
    app.innerHTML=`<div class="match-browser">
      ${topStrip(rows)}
      <section class="match-browser-head">
        <div><span>LISTA MECZÓW</span><b>${rows.length} spotkań</b></div>
        ${focusBar()}
      </section>
      <div class="match-groups">${groupRows(rows).map(g=>`
        <section class="match-group">
          <header>
            <div><span>${esc(g.tour)}</span><b>${esc(g.name)}</b></div>
            <small>${g.rows.length} ${g.rows.length===1?'mecz':'meczów'} · ${esc([...new Set(g.rows.map(surf))].join('/')||'—')}</small>
          </header>
          <div class="match-grid">${g.rows.map(card).join('')}</div>
        </section>`).join('')}</div>
    </div>`;
    bindHome();
  };

  function bindHome(){
    document.querySelectorAll('[data-p751-focus]').forEach(b=>b.onclick=()=>{focus=b.dataset.p751Focus;renderMatches()});

    document.querySelectorAll('[data-p751-open]').forEach(b=>{
      const open=()=>openMatch(decodeURIComponent(b.dataset.p751Open));

      if(b.classList.contains('p751-match-card')){
        b.onclick=e=>{
          if(e.target.closest?.('.v762-player-link'))return;
          open();
        };

        b.onkeydown=e=>{
          if(e.target.closest?.('.v762-player-link'))return;
          if(e.key!=='Enter'&&e.key!==' ')return;
          e.preventDefault();
          open();
        };
      }else{
        b.onclick=open;
      }
    });
  }

  function binaryBest(obj){
    if(!obj)return null;
    const e=Object.entries(obj).filter(([,v])=>num(v)!=null).sort((a,b)=>Number(b[1])-Number(a[1]))[0];
    return e?{name:e[0],value:Number(e[1])}:null;
  }

  function verdict(m){
    const ss=top(m,3),a=ss[0],b=ss[1],trust=Math.round(Math.min(100,(num(m.model_confidence)||0)+(m.early_hold_v7?.ready?4:0)));
    return `<section class="p751-verdict">
      <header><span>⚡</span><b>Szybki werdykt</b></header>
      <div>
        <article><span>Najlepszy typ</span><b>${esc(a?.label||'—')}</b><strong>${a?signalText(a.value):'—'}</strong></article>
        <article><span>Alternatywa</span><b>${esc(b?.label||'—')}</b><strong>${b?signalText(b.value):'—'}</strong></article>
        <article><span>Ocena sygnału</span><b>${(a?.value||0)>=85?'Bardzo mocny':(a?.value||0)>=72?'Mocny':'Umiarkowany'}</b><strong>${a?signalText(a.value):'—'}</strong></article>
        <article><span>Zaufanie danych</span><b>${trust>=85?'Wysokie':trust>=65?'Średnie':'Niskie'}</b><strong>${trust||'—'}%</strong></article>
      </div>
    </section>`;
  }

  function marketRow(label,left,right='',hot=false,rightHot=false){
    return `<div class="p751-market-row"><span>${esc(label)}</span><b class="${hot?'hot':''}">${esc(left)}</b><em class="${rightHot?'hot':''}">${esc(right)}</em></div>`;
  }

  function coreMarkets(m){
    const gs=m.game_states||{},fs=binaryBest(m.first_set_win),mw=binaryBest(m.match_win);
    const p11=num(gs?.['2']?.['1:1']),p22=num(gs?.['4']?.['2:2']),p33=num(gs?.['6']?.['3:3']);
    const lead=num(m.score_lead_after6),leadName=m.pick_first_set_early||m.pick_first_set||fs?.name||'—';
    const over85=num(m.over_under?.['8.5']?.over);
    const lines=m.market_lab_v741?.set1_total||m.over_under||{};
    const selectedSetLines=modelMarketRows(m,'set1_total');
    const modelContext=activeModelId()==='adaptive'?'':`<p class="p772-context"><b>Aktywny model: ${esc(activeModelName())}.</b> Top typ, siła i linie modelowe korzystają z tego modelu. 1:1 / 2:2 / 3:3 pozostają osobną warstwą stanów gemowych PBP/Adaptive.</p>`;
    return `<details class="p751-acc" open>
      <summary><div><span>🎯</span><b>Typy meczowe</b><small>najważniejsze rynki</small></div><i>⌄</i></summary>
      <div class="p751-acc-body">
        ${modelContext}
        ${p11!=null?marketRow('1:1 po 2 gemach',pc(p11),`inny ${pc(100-p11)}`,p11>=72):''}
        ${p22!=null?marketRow('2:2 po 4 gemach',pc(p22),`inny ${pc(100-p22)}`,p22>=72):''}
        ${p33!=null?marketRow('3:3 po 6 gemach',pc(p33),`inny ${pc(100-p33)}`,p33>=72):''}
        ${lead!=null?marketRow('Prowadzi po 6',`${leadName} ${pc(lead)}`,`pozostałe ${pc(100-lead)}`,lead>=72):''}
        ${over85!=null?marketRow('OVER 8.5 · 1. set',pc(over85),`UNDER ${pc(100-over85)}`,over85>=72):''}
        ${fs?marketRow('Wygrany 1. set',`${fs.name} ${pc(fs.value)}`,`rywal ${pc(100-fs.value)}`,fs.value>=72):''}
        ${mw?marketRow('Wygrany mecz',`${mw.name} ${pc(mw.value)}`,`rywal ${pc(100-mw.value)}`,mw.value>=72):''}
        <div class="p751-lines"><label>Linie gemów · 1. set · ${selectedSetLines.length?esc(activeModelName()):'Adaptive baza'}</label><div>${selectedSetLines.length?selectedSetLines.map(x=>{const ln=modelLine(x),v=Number(x.v),side=String(x.pick||'').toUpperCase().startsWith('O')?'O':'U';return `<span class="${v>=72?'strong':''}"><b>${esc(ln)}</b><small>${side}${Math.round(v)}</small></span>`}).join(''):Object.entries(lines).map(([ln,x])=>{const o=num(x?.over),u=num(x?.under),mx=Math.max(o||0,u||0),side=(o||0)>=(u||0)?'O':'U';return `<span class="${mx>=72?'strong':''}"><b>${esc(ln)}</b><small>${side}${Math.round(mx)}</small></span>`}).join('')}</div></div>
        ${matchGamesLines(m)}
      </div>
    </details>`;
  }

  function jointBuilder78b(m){
    const j=m.joint_builder_v78b;
    if(!j){
      return `<details class="p751-acc"><summary><div><span>🧩</span><b>Joint Builder v7.8B</b><small>wspólna kombinacja 1. seta</small></div><em>N/D</em><i>⌄</i></summary><div class="p751-acc-body"><p class="p751-note">Brak jeszcze wyniku Joint Buildera w tym rekordzie. Po kolejnym przebiegu danych zostanie policzony automatycznie.</p></div></details>`;
    }
    if(j.status!=='READY'){
      const why=j.reason||((j.validation_errors||[]).join(' · '))||j.status||'N/D';
      return `<details class="p751-acc"><summary><div><span>🧩</span><b>Joint Builder v7.8B</b><small>wspólna kombinacja 1. seta</small></div><em>${esc(j.status||'N/D')}</em><i>⌄</i></summary><div class="p751-acc-body"><p class="p751-note">N/D: ${esc(why)}. Nie zgadujemy wyniku bez modelu serwisowego i pełnego rozkładu.</p></div></details>`;
    }
    const b=j.best||{},p=b.player||'—';
    const r=(j.p1?.player===p?j.p1:j.p2?.player===p?j.p2:null)||{};
    const dep=num(b.dependency_ratio),joint=num(b.joint_all_3),naive=num(b.naive_independent);
    return `<details class="p751-acc ready" open>
      <summary><div><span>🧩</span><b>Joint Builder v7.8B</b><small>3 zdarzenia liczone z tej samej ścieżki seta</small></div><em>${joint==null?'N/D':pc(joint)}</em><i>⌄</i></summary>
      <div class="p751-acc-body">
        <p class="p751-note"><b>${esc(p)}</b>: prowadzi po 6 gemach + OVER 8.5 w 1. secie + wygrywa 1. set. To jest wspólne prawdopodobieństwo, a nie iloczyn trzech niezależnych procentów.</p>
        ${marketRow('Kombinacja 3/3',joint==null?'N/D':pc(joint),naive==null?'':`naiwne mnożenie ${pc(naive)}`,false)}
        ${marketRow('1 · Prowadzi po 6 gemach',`${esc(p)} ${pc(r.lead_after_6)}`,'',num(r.lead_after_6)>=72)}
        ${marketRow('2 · OVER 8.5 · 1. set',pc(r.over_8_5_set1),'',num(r.over_8_5_set1)>=72)}
        ${marketRow('3 · Wygrywa 1. set',`${esc(p)} ${pc(r.win_set1)}`,'',num(r.win_set1)>=72)}
        ${dep!=null?marketRow('Wpływ zależności',`×${dep.toFixed(2)}`,dep>1?'zdarzenia wzajemnie się wzmacniają':'zależność nie podbija kombinacji',dep>=1.25):''}
        <p class="p751-note">Joint zawsze musi być ≤ każdej składowej. Integralność v7.8A sprawdza ten warunek automatycznie.</p>
      </div>
    </details>`;
  }

  function calibration78d(m){
    const c=m.calibration_v78d;
    const specialist=activeModelId()!=='adaptive';
    if(!c){
      return `<details class="p751-acc"><summary><div><span>🎚️</span><b>Calibration Guard v7.8D</b><small>realna skuteczność ≠ wynik modelu</small></div><em>N/D</em><i>⌄</i></summary><div class="p751-acc-body"><p class="p751-note">Kalibracja pojawi się po następnym automatycznym odświeżeniu danych.</p></div></details>`;
    }
    const rows=(c.signals||[]).slice(0,6);
    const one=x=>{
      const cur=x.current||{},leg=x.legacy_reference||{},n=Number(cur.settled||0);
      const acc=cur.display_accuracy;
      const ci=Array.isArray(cur.ci95)?` · CI ${cur.ci95[0]}–${cur.ci95[1]}%`:'';
      const legacy=Number(leg.settled||0)>0?`LEGACY ${leg.accuracy==null?'N/D':Number(leg.accuracy).toFixed(1)+'%'} · n=${leg.settled}`:'LEGACY N/D';
      return `<div class="p78d-cal-row"><div><b>${esc(x.label||x.market||'Sygnał')}</b><small>Wynik modelu ${Math.round(Number(x.score||0))}${specialist?'/100':'%'} · obecna wersja n=${n}${ci}</small><small class="p78d-legacy">${esc(legacy)} · tylko odniesienie</small></div><strong class="${acc==null?'nd':''}">${acc==null?'N/D':Number(acc).toFixed(1)+'%'}</strong></div>`;
    };
    return `<details class="p751-acc" open><summary><div><span>🎚️</span><b>Calibration Guard v7.8D</b><small>bieżąca wersja osobno od LEGACY</small></div><em>${esc(c.status||'N/D')}</em><i>⌄</i></summary><div class="p751-acc-body">
      <div class="p78d-cal-note"><b>${specialist?'Wynik /100 = siła modelu, nie prawdopodobieństwo.':'Estymacja modelu i historyczna trafność są pokazywane osobno.'}</b><span>Stare wersje mają etykietę LEGACY i nie wpływają na skuteczność bieżącej wersji. Minimum do publikacji historycznej accuracy: n=${Number(c.min_sample||10)}.</span></div>
      ${rows.length?`<div class="p78d-cal-grid">${rows.map(one).join('')}</div>`:'<p class="p751-note">Brak zielonych sygnałów Adaptive do kalibracji dla tego meczu.</p>'}
    </div></details>`;
  }

  function stats(m){
    const a=m.p1_stats||{},b=m.p2_stats||{};
    const pv=(v,ratio=false)=>num(v)==null?'—':ratio?Math.round(Number(v)*100)+'%':String(Math.round(Number(v)*10)/10);
    const row=(l,x,y)=>`<div class="p751-compare-row"><span>${esc(l)}</span><b>${esc(x)}</b><b>${esc(y)}</b></div>`;
    return `<details class="p751-acc">
      <summary><div><span>📊</span><b>Statystyki zawodników</b><small>porównanie obok siebie</small></div><i>⌄</i></summary>
      <div class="p751-acc-body">
        <div class="p751-compare-head"><span></span><b>${esc(m.p1)}</b><b>${esc(m.p2)}</b></div>
        ${row('Ranking',a.rank??'—',b.rank??'—')}
        ${row('Mecze próbki',a.matches??'—',b.matches??'—')}
        ${row('Ta nawierzchnia',a.surface_matches??'—',b.surface_matches??'—')}
        ${row('Win rate',pv(a.won,true),pv(b.won,true))}
        ${row('Hold',pv(a.hold_rate,true),pv(b.hold_rate,true))}
        ${row('Return points',pv(a.return_points_won,true),pv(b.return_points_won,true))}
        ${row('1. set win hist.',pv(a.first_set_won,true),pv(b.first_set_won,true))}
        ${m.service_model?row('Model hold',pc(m.service_model.p1_hold),pc(m.service_model.p2_hold)):''}
      </div>
    </details>`;
  }

  function pbp(m){
    const e=m.early_hold_v7;if(!e)return '';
    const player=x=>x?`<article class="p751-pbp-player"><header><b>${esc(x.player||'—')}</b><span class="${x.ready?'ok':''}">${x.ready?'PBP OK':'N/D'}</span></header><strong>EHS ${x.ehs==null?'N/D':Number(x.ehs).toFixed(1)+'/100'}</strong><div><span>1. hold <b>${pc(x.hold1)}</b></span><span>2. hold <b>${pc(x.hold2)}</b></span><span>3. hold <b>${pc(x.hold3)}</b></span><span>1:1/2 <b>${pc(x.after2_11)}</b></span><span>2:2/4 <b>${pc(x.after4_22)}</b></span><span>3:3/6 <b>${pc(x.after6_33)}</b></span></div><small>${x.matches||0} meczów PBP</small></article>`:'';
    return `<details class="p751-acc ${e.ready?'ready':''}">
      <summary><div><span>🧬</span><b>Early Hold · PBP</b><small>${e.ready?'prawdziwy początek seta':'brak pełnej próbki'}</small></div><em>${e.ready?'PBP OK':'N/D'}</em><i>⌄</i></summary>
      <div class="p751-acc-body">
        ${e.ready?`<div class="p751-pbp-top"><span>Pick 1S <b>${esc(m.pick_first_set_early||'—')} ${pc(m.score_first_set_early)}</b></span><span>Prowadzi po 6 <b>${pc(m.score_lead_after6)}</b></span><span>Joint Builder <b>${pc(m.score_joint_builder)}</b></span></div>`:`<p class="p751-note">Brak minimum 5 wiarygodnych PBP dla obu zawodników. Tutaj bazą pozostaje Adaptive.</p>`}
        <div class="p751-pbp-grid">${player(e.p1)}${player(e.p2)}</div>
      </div>
    </details>`;
  }

  function serve(m){
    const s=m.serve_props_v72;if(!s)return '';
    const one=(side)=>{const p=s[side]||{},name=m[side]||'—',hist=p.history?.all?.['10']||{};const avg=k=>hist?.[k]?.avg==null?'N/D':`${Number(hist[k].avg).toFixed(1)} · n=${hist[k].sample||0}`;
      const tool=(kind,x)=>{const title=kind==='aces'?'🎯 Asy':'⚠️ Podwójne błędy';if(!x?.ready)return `<div class="sp72-market nd"><div class="sp72-market-head"><b>${title}</b><span>N/D</span></div><p>Za mała próbka.</p></div>`;const mean=Number(x.mean),def=num(x.suggested_line)??Math.max(.5,Math.floor(mean)-.5),max=kind==='aces'?'20.5':'12.5';return `<div class="sp72-market" data-sp-market="p772-${esc(m.id||'m')}-${side}-${kind}" data-sp-mean="${mean}"><div class="sp72-market-head"><b>${title}</b><span>MODEL ŚR. ${mean.toFixed(1)}</span></div><div class="sp72-market-meta"><span>${x.sample||0} meczów</span><span>BO3 · model count</span></div><div class="sp72-line-tool"><label>Linia buka <input type="number" inputmode="decimal" min="0.5" max="${max}" step="0.5" value="${Number(def).toFixed(1)}" data-sp-line></label><div class="sp72-probs" data-sp-output></div></div></div>`};
      return `<article><h4>${esc(name)}</h4><div class="p772-serve-history"><span>Asy · ostatnie 10<b>${esc(avg('aces'))}</b></span><span>DF · ostatnie 10<b>${esc(avg('double_faults'))}</b></span></div>${tool('aces',p.aces)}${tool('df',p.double_faults)}</article>`};
    return `<details class="p751-acc"><summary><div><span>⚡</span><b>Asy i podwójne błędy</b><small>przeciwnik + nawierzchnia + długość meczu</small></div><em>${s.ready?'MODEL':'N/D'}</em><i>⌄</i></summary><div class="p751-acc-body"><p class="p751-note">Wpisz linię buka. OVER/UNDER i fair odds odświeżają się automatycznie.</p><div class="p751-serve-grid">${one('p1')}${one('p2')}</div></div></details>`;
  }

  function lab(m){
    const l=m.market_lab_v741;if(!l)return '';
    const lr=(label,x)=>{const o=num(x?.over),u=num(x?.under);if(o==null||u==null)return '';return marketRow(label,`O ${pc(o)}`,`U ${pc(u)}`,o>=72,u>=72)};
    const best=(o,n=6)=>Object.entries(o||{}).sort((a,b)=>Math.max(Number(b[1]?.over||0),Number(b[1]?.under||0))-Math.max(Number(a[1]?.over||0),Number(a[1]?.under||0))).slice(0,n),pg=l.player_total_games||{};
    const combo=(obj,stage)=>`<div class="p772-lab-grid">${marketRow(`${stage} · ${m.p1} wygra + U6.5`,pc(obj?.p1?.under),'wspólne zdarzenie',num(obj?.p1?.under)>=72)}${marketRow(`${stage} · ${m.p1} wygra + O6.5`,pc(obj?.p1?.over),'wspólne zdarzenie',num(obj?.p1?.over)>=72)}${marketRow(`${stage} · ${m.p2} wygra + U6.5`,pc(obj?.p2?.under),'wspólne zdarzenie',num(obj?.p2?.under)>=72)}${marketRow(`${stage} · ${m.p2} wygra + O6.5`,pc(obj?.p2?.over),'wspólne zdarzenie',num(obj?.p2?.over)>=72)}</div>`;
    return `<details class="p751-acc"><summary><div><span>🧪</span><b>Market Lab</b><small>pełne rynki · osobna walidacja</small></div><em>LAB</em><i>⌄</i></summary><div class="p751-acc-body"><p class="p751-note">LAB nie podbija głównego score. v7.7.2 tracker rozlicza też liczbę tie-breaków oraz „zwycięzca seta + własne gemy”.</p><div class="p751-lab-grid"><span>Dokładnie 6 gemów 1S <b>${pc(l.set1_exact_six_games)}</b></span><span>Tie-break 1S <b>${pc(l.set1_tiebreak?.yes)}</b></span><span>Tie-break mecz <b>${pc(l.match_tiebreak?.yes)}</b></span><span>Obaj wygrają seta <b>${pc(l.both_players_win_set?.yes)}</b></span></div><div class="p772-lab-section"><h4>🎾 1. set · O/U</h4><div>${Object.entries(l.set1_total||{}).map(([ln,x])=>lr(`1S ${ln}`,x)).join('')}</div></div><div class="p772-lab-section"><h4>👤 Gemy zawodnika · cały mecz</h4><div class="p772-lab-grid"><div><b>${esc(m.p1)}</b>${best(pg[m.p1]).map(([ln,x])=>lr(ln,x)).join('')}</div><div><b>${esc(m.p2)}</b>${best(pg[m.p2]).map(([ln,x])=>lr(ln,x)).join('')}</div></div></div><div class="p772-lab-section"><h4>🔀 Dokładna liczba tie-breaków</h4><div class="p772-lab-grid">${Object.entries(l.tiebreak_count||{}).map(([k,v])=>marketRow(`${k} tie-break`,pc(v),'event',num(v)>=72)).join('')}</div></div><div class="p772-lab-section"><h4>🧩 Zwycięzca seta + własne gemy</h4>${combo(l.set1_winner_player_games_6_5,'1. set')}${combo(l.set2_winner_player_games_6_5,'2. set')}</div></div></details>`;
  }

  function models(m){
    const block=(title,obj)=>obj?`<article><h4>${esc(title)}</h4>${Object.entries(obj).map(([n,v])=>`<span>${esc(n)} <b>${pc(v)}</b></span>`).join('')}</article>`:'';
    return `<details class="p751-acc"><summary><div><span>🧠</span><b>Modele</b><small>pełny mecz i dodatkowe prognozy</small></div><i>⌄</i></summary><div class="p751-acc-body"><div class="p751-model-grid">${block('Mecz',m.match_win)}${block('1. set',m.first_set_win)}${block('2. set',m.second_set_win)}${block('Liczba setów',m.total_sets)}${block('Dokładny wynik',m.exact_match_score)}</div></div></details>`;
  }

  function pro76Range(x,lo,hi){
    x=num(x);if(x==null)return null;
    return Math.max(0,Math.min(100,(x-lo)/(hi-lo)*100));
  }
  function pro76Weighted(pairs){
    const ok=pairs.filter(([v,w])=>num(v)!=null&&w>0);
    if(!ok.length)return null;
    const z=ok.reduce((s,[,w])=>s+w,0);
    return ok.reduce((s,[v,w])=>s+Number(v)*w,0)/z;
  }
  function pro76Side(m,side){
    const tr=m.tendencies_v71?.[side]||{},eh=m.early_hold_v7?.[side]||{},g=tr.all?.['10']||{},surf=tr.surface?.['10']||{},p=eh.pbp_tendencies?.all?.['10']||{};
    const metric=(b,k)=>num(b?.metrics?.[k]?.pct),av=(b,k)=>num(b?.averages?.[k]);
    const serve=pro76Weighted([[pro76Range(av(g,'hold_rate'),60,90),.38],[pro76Range(av(g,'serve_points_won'),50,72),.25],[pro76Range(av(g,'first_serve_won'),55,85),.20],[pro76Range(av(g,'second_serve_won'),35,65),.17]]);
    const ret=pro76Weighted([[pro76Range(av(g,'break_rate'),10,45),.46],[pro76Range(av(g,'return_points_won'),28,52),.54]]);
    const form=pro76Weighted([[metric(g,'match_win'),.45],[metric(g,'set1_win'),.32],[metric(g,'set2_win'),.23]]);
    const early=Number(p?.sample_matches||0)>=3?pro76Weighted([[metric(p,'hold1'),.42],[metric(p,'hold2'),.32],[metric(p,'hold3'),.18],[metric(p,'sequence_11_22_33'),.08]]):null;
    const mental=pro76Weighted([[metric(g,'closeout_after_set1_win'),.32],[metric(g,'comeback_set2_after_set1_loss'),.32],[metric(g,'deciding_set_win'),.26],[metric(g,'set2_win'),.10]]);
    const surface=Number(surf?.sample_matches||0)>=3?pro76Weighted([[metric(surf,'match_win'),.40],[pro76Range(av(surf,'hold_rate'),60,90),.25],[pro76Range(av(surf,'return_points_won'),28,52),.20],[metric(surf,'set1_win'),.15]]):null;
    return {serve,ret,form,early,mental,surface};
  }
  function analyticsPro76(m){
    const a=pro76Side(m,'p1'),b=pro76Side(m,'p2');
    const row=(label,key)=>{
      const x=a[key],y=b[key];
      const best=x==null||y==null?'':x>y?'p1':y>x?'p2':'';
      return `<div class="pa76-compare-row">
        <span>${esc(label)}</span>
        <b class="${best==='p1'?'best':''}">${x==null?'N/D':Math.round(x)}</b>
        <b class="${best==='p2'?'best':''}">${y==null?'N/D':Math.round(y)}</b>
      </div>`;
    };
    return `<details class="p751-acc pa76-match-compare">
      <summary><div><span>🧠</span><b>Player Analytics PRO</b><small>profil 0–100 · nie prawdopodobieństwo</small></div><em>PRO</em><i>⌄</i></summary>
      <div class="p751-acc-body">
        <div class="pa76-compare-head"><span></span><b>${esc(m.p1)}</b><b>${esc(m.p2)}</b></div>
        ${row('🎾 Serwis','serve')}
        ${row('↩️ Return','ret')}
        ${row('🔥 Forma','form')}
        ${row('🧬 Early Hold','early')}
        ${row('🧠 Mental','mental')}
        ${row('🏟️ Nawierzchnia','surface')}
        <p class="p751-note">Indeksy liczone identycznie jak w profilu: ostatnie 10 · wszystkie mecze; „Nawierzchnia” używa ostatnich 10 na tej nawierzchni. Nie są szansą wygranej meczu.</p>
      </div>
    </details>`;
  }

  function lazySection78e23(id,icon,title,small,badge=''){
    return `<details class="p751-acc" data-p751-lazy78e23="${id}">
      <summary><div><span>${icon}</span><b>${title}</b><small>${small}</small></div>${badge?`<em>${badge}</em>`:''}<i>⌄</i></summary>
    </details>`;
  }

  function lazySections78e23(m){
    const out=[
      lazySection78e23('stats','📊','Statystyki zawodników','porównanie obok siebie'),
      lazySection78e23('analytics','🧠','Player Analytics PRO','profil 0–100 · nie prawdopodobieństwo','PRO')
    ];
    if(m.early_hold_v7) out.push(lazySection78e23('pbp','🧬','Early Hold · PBP',m.early_hold_v7.ready?'prawdziwy początek seta':'brak pełnej próbki',m.early_hold_v7.ready?'PBP OK':'N/D'));
    if(m.serve_props_v72) out.push(lazySection78e23('serve','⚡','Asy i podwójne błędy','przeciwnik + nawierzchnia + długość meczu',m.serve_props_v72.ready?'MODEL':'N/D'));
    if(m.market_lab_v741) out.push(lazySection78e23('lab','🧪','Market Lab','pełne rynki · osobna walidacja','LAB'));
    out.push(lazySection78e23('models','🧠','Modele','pełny mecz i dodatkowe prognozy'));
    return out.join('');
  }

  function bindLazySections78e23(root,m){
    const renderers={stats,analytics:analyticsPro76,pbp,serve,lab,models};
    root.querySelectorAll('[data-p751-lazy78e23]').forEach(d=>{
      d.addEventListener('toggle',()=>{
        if(!d.open || d.dataset.loaded78e23==='1') return;
        const fn=renderers[d.dataset.p751Lazy78e23];
        if(typeof fn!=='function') return;
        const html=fn(m);
        d.dataset.loaded78e23='1';
        if(!html) return;
        const t=document.createElement('template');
        t.innerHTML=html.trim();
        const full=t.content.firstElementChild;
        if(!full) return;
        full.classList.forEach(c=>d.classList.add(c));
        const body=full.querySelector('.p751-acc-body');
        if(!body) return;
        d.appendChild(body);
        requestAnimationFrame(()=>{
          d.querySelectorAll('input[data-sp-line]').forEach(i=>i.dispatchEvent(new Event('input',{bubbles:true})));
        });
      },{passive:true});
    });
  }

  function detailHtml(m){
    const ss=top(m,3),best=ss[0],second=ss[1];
    const trust=Math.round(Math.min(100,(num(m.model_confidence)||0)+(m.early_hold_v7?.ready?4:0)));
    return `<div class="p751-detail-screen match-page">
      <header class="match-page-top">
        <button data-p751-close class="match-back" aria-label="Wróć">←</button>
        <div>
          <span>${esc(tour(m))} · ${esc(m.tournament||'Turniej')}</span>
          <b>Analiza meczu</b>
        </div>
        <time>${esc(dt(m))} · ${esc(tm(m))}</time>
      </header>
      <section class="match-hero">
        <div class="match-hero-meta">
          <span>${esc(surf(m))}</span>
          <span>${m.early_hold_v7?.ready?'PBP gotowe':'PBP N/D'}</span>
          <span class="phase11-technical">Jakość ${trust}/100</span>
        </div>
        <div class="match-hero-players">
          <b class="v762-player-link" role="link" tabindex="0">${esc(m.p1)}</b>
          <span>vs</span>
          <b class="v762-player-link" role="link" tabindex="0">${esc(m.p2)}</b>
        </div>
      </section>
      <section class="match-decision">
        <article class="match-decision-main">
          <span>NAJLEPSZY TYP</span>
          <b>${esc(best?.label||'Brak mocnego sygnału')}</b>
          <strong>${best?signalText(best.value):'—'}</strong>
          <small>${second?`Alternatywa: ${esc(second.label)} · ${signalText(second.value)}`:'Model nie wskazał mocnej alternatywy.'}</small>
        </article>
        <article>
          <span>OCENA</span>
          <b>${(best?.value||0)>=85?'Bardzo mocny':(best?.value||0)>=72?'Mocny':'Umiarkowany'}</b>
          <strong>${best?signalText(best.value):'—'}</strong>
        </article>
        <article>
          <span>DANE</span>
          <b>${trust>=85?'Wysokie zaufanie':trust>=65?'Średnie zaufanie':'Ostrożnie'}</b>
          <strong>${trust||'—'}%</strong>
        </article>
      </section>
      <div class="match-page-content">
        <section class="match-page-primary">
          <div class="section-heading"><span>RYNKI</span><b>Co warto sprawdzić</b></div>
          ${coreMarkets(m)}
          ${jointBuilder78b(m)}
          ${lazySections78e23(m)}
        </section>
        <aside class="match-page-side">
          <div class="section-heading"><span>KONTEKST</span><b>Kalibracja i jakość</b></div>
          ${calibration78d(m)}
          <p class="p751-disclaimer">Sygnały są estymacjami analitycznymi, nie gwarancją wyniku.</p>
        </aside>
      </div>
    </div>`;
  }

  let returnScroll=0;
  function findMatch(k){return (Array.isArray(all)?all:[]).find(m=>key(m)===k)}
  function openMatch(k){
    const m=findMatch(k);if(!m)return;
    const app=document.querySelector('#app');if(!app)return;
    returnScroll=window.scrollY||0;
    route='match';
    document.documentElement.dataset.tenisRoute='match';
    app.innerHTML=detailHtml(m);
    app.dataset.matchKey=String(k);
    bindLazySections78e23(app,m);
    window.TENIS_AI_DECISION_CENTER_V87?.tidy?.(m);
    window.TENIS_AI_PLAYER_UI_V851?.injectDetail?.(m);
    if(!app.querySelector('.dc87'))window.TENIS_AI_ADAPTIVE_V79?.injectProjectDetail?.();
    window.scrollTo({top:0,behavior:'auto'});
    app.querySelector('[data-p751-close]')?.addEventListener('click',closeMatch);
    document.dispatchEvent(new CustomEvent('tenis-ai:match-open',{detail:{matchKey:String(k)}}));
  }
  function closeMatch(){
    const app=document.querySelector('#app');
    if(app)delete app.dataset.matchKey;
    route='matches';
    document.documentElement.dataset.tenisRoute='matches';
    document.dispatchEvent(new CustomEvent('tenis-ai:match-close'));
    renderMatches();
    setTimeout(()=>window.scrollTo({top:returnScroll,behavior:'auto'}),0);
  }


  function signalPage(){
    route='signals';navActive('signals');
    const app=document.querySelector('#app');
    const rows=(typeof filteredReady==='function'?filteredReady():[]).flatMap(m=>signals(m).filter(s=>s.value>=68).map(s=>({m,s}))).sort((a,b)=>b.s.value-a.s.value).slice(0,40);
    app.innerHTML=`<section class="p751-signals-page"><header><div><b>⚡ Najmocniejsze sygnały</b><small>posortowane po sile modelu</small></div><button data-p751-validation>📊 Walidacja</button></header><div>${rows.map(({m,s})=>`<button data-p751-open="${encodeURIComponent(key(m))}"><div><b>${esc(m.p1)} <i>vs</i> ${esc(m.p2)}</b><small>${esc(tour(m))} · ${esc(m.tournament||'Turniej')} · ${esc(tm(m))}</small></div><span>${esc(s.label)}</span><strong>${signalText(s.value)}</strong></button>`).join('')}</div></section>`;
    document.querySelectorAll('[data-p751-open]').forEach(b=>b.onclick=()=>openMatch(decodeURIComponent(b.dataset.p751Open)));
    document.querySelector('[data-p751-validation]')?.addEventListener('click',()=>{
      document.querySelector('.main-tabs [data-view="stats"]')?.click();
      route='signals';navActive('signals');
    });
  }

  // History: v7.5's grouping/status logic is kept, but this styles it exactly like the project.
  const oldHistory=typeof renderHistory==='function'?renderHistory:null;
  renderHistory=function(){
    route='history';navActive('history');
    if(oldHistory)oldHistory();
  };

  function ensureBottomNav(){
    return document.querySelector('.main-tabs');
  }
  function navActive(which){
    const mapped=which==='history'?'history':which==='matches'?'matches':null;
    if(mapped){
      document.querySelectorAll('.main-tabs button[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===mapped));
    }
    document.documentElement.dataset.tenisRoute=which;
  }

  function simplifyShell(){
    window.TENIS_AI_APPLY_META?.();
    const symphony=document.querySelector('#symphony-open');
    if(symphony&&!symphony.dataset.boundProjectUi){
      symphony.dataset.boundProjectUi='1';
      symphony.addEventListener('click',()=>{
        window.TENIS_AI_SYMPHONY2?.open?.('home');
        route='symphony2';
        navActive('symphony2');
      });
    }
  }

  simplifyShell();
  bindUiMode();
  window.addEventListener('tenis-ai-auth-change',()=>setTimeout(bindUiMode,0));
  window.addEventListener('pageshow',()=>setTimeout(bindUiMode,0));
  if(typeof view!=='undefined'&&view==='matches')renderMatches();
  document.documentElement.dataset.tenisUiReady='1';

  window.TENIS_AI_PROJECT_UI = {
    openMatch,
    findMatch,
    renderMatches: () => renderMatches(),
    setUiMode,
    syncUiMode
  };

})();
