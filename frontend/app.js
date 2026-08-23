let all=[];
let historyRows=[];
let statsData=null;
let filter='all';
let view='matches';

const COLLAPSE_KEY='tenis-ai-v6-collapse';
const FEEDBACK_KEY='tenis-ai-v6-feedback';
const COUPON_KEY='tenis-ai-v6-coupons';
let collapseState=readLocal(COLLAPSE_KEY,{});
let feedbackRows=readLocal(FEEDBACK_KEY,[]);
let couponRows=readLocal(COUPON_KEY,[]);

const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const score=x=>x==null?'':`${Math.round(x)} / 100`;
const pct=x=>x==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
const slug=s=>String(s??'').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');

function readLocal(key,fallback){try{const v=JSON.parse(localStorage.getItem(key));return v??fallback}catch{return fallback}}
function writeLocal(key,value){try{localStorage.setItem(key,JSON.stringify(value));return true}catch{return false}}
function cls(x){return x==null?'':x>=80?'elite':x>=72?'good':x<55?'warn':''}
function pill(label,x,extra=''){if(x==null)return '';return `<div class="market ${cls(x)}"><span>${esc(label)}</span><b>${score(x)}</b>${extra?`<em>${esc(extra)}</em>`:''}</div>`}
function marketBox(title,content,tag='MODEL',extraClass=''){if(!content)return '';return `<details class="marketbox ${extraClass}"><summary><span class="summary-title">${title}</span><span class="tag">${esc(tag)}</span><span class="chev">⌄</span></summary><div class="marketbody">${content}</div></details>`}
function statTable(a={},b={}){return `<table><tr><td></td><td>${esc(a.player||'—')}</td><td>${esc(b.player||'—')}</td></tr><tr><td>Mecze próbki</td><td>${a.matches??'—'}</td><td>${b.matches??'—'}</td></tr><tr><td>Ta nawierzchnia</td><td>${a.surface_matches??'—'}</td><td>${b.surface_matches??'—'}</td></tr><tr><td>Ranking</td><td>${a.rank??'—'}</td><td>${b.rank??'—'}</td></tr><tr><td>Win rate</td><td>${a.won==null?'—':Math.round(a.won*100)+'%'}</td><td>${b.won==null?'—':Math.round(b.won*100)+'%'}</td></tr><tr><td>Hold</td><td>${a.hold_rate==null?'—':Math.round(a.hold_rate*100)+'%'}</td><td>${b.hold_rate==null?'—':Math.round(b.hold_rate*100)+'%'}</td></tr><tr><td>Return points</td><td>${a.return_points_won==null?'—':Math.round(a.return_points_won*100)+'%'}</td><td>${b.return_points_won==null?'—':Math.round(b.return_points_won*100)+'%'}</td></tr><tr><td>1. set win hist.</td><td>${a.first_set_won==null?'—':Math.round(a.first_set_won*100)+'%'}</td><td>${b.first_set_won==null?'—':Math.round(b.first_set_won*100)+'%'}</td></tr><tr><td>2. set win hist.</td><td>${a.second_set_won==null?'—':Math.round(a.second_set_won*100)+'%'}</td><td>${b.second_set_won==null?'—':Math.round(b.second_set_won*100)+'%'}</td></tr><tr><td>Mecze / 7 dni</td><td>${a.matches_7d??'—'}</td><td>${b.matches_7d??'—'}</td></tr><tr><td>Dni od meczu</td><td>${a.days_since_last??'—'}</td><td>${b.days_since_last??'—'}</td></tr><tr><td>Śr. gemy 1 seta</td><td>${a.first_set_games==null?'—':Number(a.first_set_games).toFixed(1)}</td><td>${b.first_set_games==null?'—':Number(b.first_set_games).toFixed(1)}</td></tr></table>`}
function binary(title,data,tag='MODEL'){if(!data)return '';return marketBox(title,`<div class="twocol">${Object.entries(data).map(([name,v])=>pill(name,v)).join('')}</div>`,tag)}
function gameStates(m){if(!m.game_states)return '';const body=['1','2','4','6'].map(n=>{const states=m.game_states[n];if(!states)return '';return `<div class="checkpoint"><h4>Po ${n} ${n==='1'?'gemie':'gemach'}</h4><div class="pillgrid">${Object.entries(states).map(([s,v])=>pill(s,v)).join('')}</div></div>`}).join('');return marketBox('🎮 Wynik po gemach',body)}
function overUnder(m){if(!m.over_under)return '';const body=Object.entries(m.over_under).map(([line,v])=>`<div class="line"><h4>Linia ${line}</h4><div class="twocol">${pill(`Over ${line}`,v.over)}${pill(`Under ${line}`,v.under)}</div></div>`).join('');return marketBox('📏 Liczba gemów · 1. set',body)}
function matchOverUnder(m){if(!m.match_over_under)return '';const exp=m.expected_match_games==null?'':` · śr. ${m.expected_match_games}`;const body=Object.entries(m.match_over_under).map(([line,v])=>`<div class="line"><h4>Linia ${line}</h4><div class="twocol">${pill(`Over ${line}`,v.over)}${pill(`Under ${line}`,v.under)}</div></div>`).join('');return marketBox('📊 Liczba gemów · cały mecz',body,`MODEL BO3${exp}`)}
function exactSet(m){if(!m.exact_first_set)return '';const entries=Object.entries(m.exact_first_set).filter(([,v])=>v>=1).slice(0,14);return marketBox('🎯 Dokładny wynik 1. seta',`<div class="pillgrid exact">${entries.map(([s,v])=>pill(s,v)).join('')}</div>`)}
function exactMatch(m){if(!m.exact_match_score)return '';return marketBox('🎯 Dokładny wynik meczu',`<div class="pillgrid exact four">${Object.entries(m.exact_match_score).map(([s,v])=>pill(s,v)).join('')}</div>`,'MODEL BO3')}
function statsBox(m){const body=`${statTable(m.p1_stats,m.p2_stats)}${m.service_model?`<p class="modelnote">Model hold: ${esc(m.p1)} ${m.service_model.p1_hold}% · ${esc(m.p2)} ${m.service_model.p2_hold}%</p>`:''}`;return marketBox('📚 Statystyki zawodników',body,'DANE')}

function scheduled(m){if(!m.scheduled_time)return '';const d=new Date(m.scheduled_time);return isNaN(d)?'':d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'})}
function dateLabel(m){if(!m.scheduled_time)return '';const d=new Date(m.scheduled_time);return isNaN(d)?'':d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'})}
function roundLabel(m){return m.round||m.round_name||m.stage||m.event_round||''}
function tourKey(m){const t=(m.tour||'').toLowerCase();if(t.includes('chall'))return 'challenger';if(t==='itf'||t.includes('itf'))return 'itf';if(t==='wta')return 'wta';if(t==='atp')return 'atp';return t}
function clientCurrent(m){if(!m.scheduled_time)return true;const t=new Date(m.scheduled_time).getTime();return !Number.isFinite(t)||t>=Date.now()-30*60*1000}
function filteredReady(){return all.filter(m=>m.model_ready&&m.first_set_win&&clientCurrent(m))}
function matchKey(m){return `m:${m.id??[m.p1,m.p2,m.scheduled_time].join('|')}`}
function tournamentKey(m){return `t:${tourKey(m)}:${slug(m.tournament||'bez-turnieju')}`}

function bestSignalsData(m,limit=3){
  const c=[];
  const addBinary=(prefix,obj)=>{if(!obj)return;const e=Object.entries(obj).filter(([,v])=>v!=null).sort((a,b)=>b[1]-a[1])[0];if(e)c.push({label:`${prefix}: ${e[0]}`,v:e[1]})};
  addBinary('Mecz',m.match_win);addBinary('1. set',m.first_set_win);addBinary('2. set',m.second_set_win);addBinary('3. set*',m.third_set_win);addBinary('Sety',m.total_sets);
  if(m.over_under)Object.entries(m.over_under).forEach(([line,v])=>c.push(v.over>=v.under?{label:`1S O${line}`,v:v.over}:{label:`1S U${line}`,v:v.under}));
  if(m.match_over_under)Object.entries(m.match_over_under).forEach(([line,v])=>c.push(v.over>=v.under?{label:`M O${line}`,v:v.over}:{label:`M U${line}`,v:v.under}));
  return c.filter(x=>x.v>=68).sort((a,b)=>b.v-a.v).slice(0,limit);
}
function bestSignals(m){const top=bestSignalsData(m,3);if(!top.length)return '';return `<div class="signals"><div class="signals-title">🔥 Najmocniejsze sygnały modelu</div><div class="signals-grid">${top.map(x=>pill(x.label,x.v)).join('')}</div></div>`}
function compactSignals(m){const top=bestSignalsData(m,2);if(!top.length)return '';return `<div class="compact-signals">${top.map(x=>`<span class="compact-signal ${cls(x.v)}">${esc(x.label)} <b>${Math.round(x.v)}</b></span>`).join('')}</div>`}

function updateCounts(){const ready=filteredReady();const counts={all:ready.length,atp:0,wta:0,challenger:0,itf:0};ready.forEach(m=>{const k=tourKey(m);if(k in counts&&k!=='all')counts[k]++});document.querySelectorAll('#tour-nav button').forEach(b=>{const n=counts[b.dataset.filter]??0;const c=b.querySelector('.count');if(c)c.textContent=n});const el=document.querySelector('#matched');if(el)el.textContent=`Dopasowane: ${ready.length} / ${all.length}`}

function detailOpen(key,defaultOpen=false){return collapseState[key]===true || (collapseState[key]===undefined&&defaultOpen)}
function bindCollapseState(){document.querySelectorAll('details[data-state-key]').forEach(d=>{d.addEventListener('toggle',()=>{collapseState[d.dataset.stateKey]=d.open;writeLocal(COLLAPSE_KEY,collapseState)})})}
function setAllDetails(open){document.querySelectorAll('#app details[data-state-key]').forEach(d=>{d.open=open;collapseState[d.dataset.stateKey]=open});writeLocal(COLLAPSE_KEY,collapseState)}

function renderMatchDetail(m){return `<div class="match-detail">${bestSignals(m)}<div class="markets">${binary('🏆 Zwycięzca meczu',m.match_win,'MODEL BO3')}${binary('🥇 Zwycięzca 1. seta',m.first_set_win)}${binary('🥈 Zwycięzca 2. seta',m.second_set_win)}${binary('🥉 Zwycięzca 3. seta · jeśli będzie',m.third_set_win,'MODEL BO3')}${binary('🔢 Liczba setów w meczu',m.total_sets,'MODEL BO3')}${exactMatch(m)}${gameStates(m)}${overUnder(m)}${matchOverUnder(m)}${exactSet(m)}${statsBox(m)}</div><div class="pick"><b>🎯 Model 1. seta: ${esc(m.pick_first_set||'—')}</b>${m.note?`<br><small>${esc(m.note)}</small>`:''}</div></div>`}

function renderMatchCard(m){
  const key=matchKey(m);
  const meta=[m.surface||'',roundLabel(m)||''].filter(Boolean).map(esc).join(' · ');
  const conf=m.model_confidence==null?'':`MODEL ${Math.round(m.model_confidence)}`;
  return `<details class="match-card" data-state-key="${esc(key)}" ${detailOpen(key,false)?'open':''}>
    <summary class="match-summary">
      <div class="match-time"><b>${esc(scheduled(m)||'—')}</b><small>${esc(dateLabel(m))}</small></div>
      <div class="match-main">
        <div class="match-players">${esc(m.p1)} <span>vs</span> ${esc(m.p2)}</div>
        <div class="match-meta">${meta||'Dane meczu'}${m.tournament?` · ${esc(m.tournament)}`:''}</div>
        ${compactSignals(m)}
      </div>
      <div class="match-score"><span>${esc(conf)}</span><small>DANE ${esc(m.quality||'—')}</small><i>⌄</i></div>
    </summary>
    ${renderMatchDetail(m)}
  </details>`
}

function renderMatches(){
  const app=document.querySelector('#app');
  let rows=filteredReady().filter(m=>filter==='all'||tourKey(m)===filter);
  rows.sort((a,b)=>new Date(a.scheduled_time||0)-new Date(b.scheduled_time||0));
  if(!rows.length){app.innerHTML='<div class="empty"><b>Brak aktualnych meczów z wystarczającymi danymi.</b><br><br>Stare/rozpoczęte mecze są automatycznie zdejmowane z głównej listy.</div>';return}
  const groups=new Map();
  for(const m of rows){const key=tournamentKey(m);if(!groups.has(key))groups.set(key,{key,tour:tourKey(m),name:m.tournament||'Turniej',matches:[]});groups.get(key).matches.push(m)}
  app.innerHTML=`<div class="tournament-list">${[...groups.values()].map(g=>{
    const surfaces=[...new Set(g.matches.map(x=>x.surface).filter(Boolean))];
    const key=g.key;
    return `<details class="tournament-group" data-state-key="${esc(key)}" ${detailOpen(key,true)?'open':''}>
      <summary class="tournament-summary"><div><span class="tour-badge">${esc(g.tour.toUpperCase())}</span><b>${esc(g.name)}</b><small>${g.matches.length} ${g.matches.length===1?'mecz':'mecze'}${surfaces.length?` · ${esc(surfaces.join('/'))}`:''}</small></div><span class="group-chev">⌄</span></summary>
      <div class="tournament-body">${g.matches.map(renderMatchCard).join('')}</div>
    </details>`
  }).join('')}</div>`;
  bindCollapseState();
}

function summaryCard(title,data){const a=data?.accuracy;return `<div class="stat-card"><span>${esc(title)}</span><b>${a==null?'—':pct(a)}</b><small>${data?.hits||0} ✅ · ${data?.misses||0} ❌ · ${data?.settled||0} rozliczonych</small></div>`}
function renderGroup(title,obj){const rows=Object.entries(obj||{}).sort((a,b)=>(b[1].settled||0)-(a[1].settled||0));if(!rows.length)return '';return `<section class="stats-section"><h3>${title}</h3><div class="stats-list">${rows.map(([k,v])=>`<div class="stats-row"><span>${esc(k)}</span><b>${v.accuracy==null?'—':pct(v.accuracy)}</b><small>${v.hits} / ${v.settled}</small></div>`).join('')}</div></section>`}
function renderStats(){const app=document.querySelector('#app');const s=statsData||{};const o=s.overall||{};app.innerHTML=`<section class="stats-hero"><div><span>📊 Skuteczność modelu · zielone sygnały</span><b>${o.accuracy==null?'—':pct(o.accuracy)}</b><small>Próg zielonego: ${s.green_threshold??72}/100</small></div><div class="stats-mini"><span>Śledzone mecze <b>${s.matches_tracked||0}</b></span><span>Oczekują <b>${s.matches_pending||0}</b></span><span>Wyłączone z % <b>${s.excluded_signals||0}</b></span></div></section><div class="stat-grid">${summaryCard('Wszystkie rozliczone',o)}</div>${renderGroup('Według rynku',s.by_market)}${renderGroup('Według touru',s.by_tour)}${renderGroup('Według siły sygnału',s.by_score_band)}<p class="stats-note">Do skuteczności liczymy tylko sygnały, które da się jednoznacznie rozliczyć z wyniku końcowego. Typy „wynik po 2/4/6 gemach” pozostają nieweryfikowalne bez danych game-by-game.</p>`}

const resultIcon=r=>({hit:'✅',miss:'❌',pending:'⏳',unverifiable:'➖',void:'↩️'}[r]||'⏳');
const resultText=r=>({hit:'WESZŁO',miss:'NIE WESZŁO',pending:'OCZEKUJE',unverifiable:'BRAK GAME-BY-GAME',void:'NIE LICZYMY'}[r]||'OCZEKUJE');
function finalScore(e){const r=e.result;if(!r)return 'Oczekuje na wynik';if(r.status==='void')return 'Mecz nierozliczany';if(r.sets?.length)return r.sets.map(s=>s.join(':')).join(' · ');return r.score_text||'Zakończony'}
function renderHistory(){const app=document.querySelector('#app');const rows=historyRows.filter(e=>{if(!(e.signals||[]).length)return false;if(e.status==='settled'||e.status==='void')return true;const t=new Date(e.scheduled_time||'').getTime();return Number.isFinite(t)&&t<=Date.now()+5*60*1000}).slice(0,150);if(!rows.length){app.innerHTML='<div class="empty"><b>Historia jest jeszcze pusta.</b><br><br>Zielone sygnały będą tu zapisywane po starcie spotkania.</div>';return}app.innerHTML=`<div class="history-head"><b>🕘 Historia zielonych sygnałów</b><span>${rows.length} ostatnich meczów</span></div>${rows.map(e=>`<article class="history-card"><div class="top"><span>${esc((e.tour||'').toUpperCase())} · ${esc(e.tournament||'—')}</span><span class="history-status ${e.status}">${e.status==='settled'?'ROZLICZONY':e.status==='void'?'NIE LICZYMY':'OCZEKUJE'}</span></div><div class="history-match">${esc(e.p1)} <span>vs</span> ${esc(e.p2)}</div><div class="history-score">${esc(finalScore(e))}</div><details><summary>Zielone typy (${e.signals.length}) <span class="chev">⌄</span></summary><div class="history-signals">${e.signals.map(s=>`<div class="history-signal ${s.result||'pending'}"><div><b>${resultIcon(s.result)} ${esc(s.label)}</b><span>${esc(s.pick)} · ${score(s.score)}</span></div><strong>${resultText(s.result)}</strong></div>`).join('')}</div></details></article>`).join('')}`}

function feedbackCard(x){return `<article class="community-card"><div class="community-top"><span>${esc(x.type||'Pomysł')}</span><small>${new Date(x.createdAt).toLocaleString('pl-PL')}</small></div><p>${esc(x.text)}</p><div class="community-actions"><span class="status-chip">${esc(x.status||'Nowe')}</span><button data-like-feedback="${esc(x.id)}">👍 ${x.likes||0}</button></div></article>`}
function renderFeedback(){const app=document.querySelector('#app');app.innerHTML=`<section class="community-hero"><h2>💡 Pomysły i poprawki</h2><p>Napisz co poprawić, jaki błąd znalazłeś albo czego brakuje w Tenis AI.</p><div class="local-note">Na razie wpisy zapisują się lokalnie na tym urządzeniu. Wspólna baza dla wszystkich użytkowników będzie wymagała osobnego backendu.</div></section><form id="feedback-form" class="community-form"><label>Typ<select name="type"><option>Pomysł</option><option>Poprawka</option><option>Błąd</option><option>Inne</option></select></label><label>Treść<textarea name="text" maxlength="800" required placeholder="Np. dodaj filtr nawierzchni albo popraw widok..." ></textarea></label><button type="submit" class="primary-btn">Dodaj zgłoszenie</button></form><div class="community-list">${feedbackRows.length?feedbackRows.slice().reverse().map(feedbackCard).join(''):'<div class="empty small"><b>Brak zgłoszeń.</b><br>Dodaj pierwsze.</div>'}</div>`;document.querySelector('#feedback-form').onsubmit=e=>{e.preventDefault();const fd=new FormData(e.currentTarget);const text=String(fd.get('text')||'').trim();if(!text)return;feedbackRows.push({id:crypto.randomUUID?crypto.randomUUID():String(Date.now()),type:String(fd.get('type')||'Pomysł'),text,status:'Nowe',likes:0,createdAt:new Date().toISOString()});writeLocal(FEEDBACK_KEY,feedbackRows);renderFeedback()};document.querySelectorAll('[data-like-feedback]').forEach(b=>b.onclick=()=>{const x=feedbackRows.find(v=>v.id===b.dataset.likeFeedback);if(x){x.likes=(x.likes||0)+1;writeLocal(FEEDBACK_KEY,feedbackRows);renderFeedback()}})}

function couponCard(x){return `<article class="coupon-card">${x.image?`<img src="${esc(x.image)}" alt="Kupon użytkownika">`:''}<div class="coupon-body"><div class="community-top"><span>${esc(x.bookmaker||'Kupon')}</span><small>${new Date(x.createdAt).toLocaleString('pl-PL')}</small></div><h3>${esc(x.title||'Kupon')}</h3>${x.description?`<p>${esc(x.description)}</p>`:''}<div class="coupon-meta">${x.odds?`<span>Kurs <b>${esc(x.odds)}</b></span>`:''}<span>Status <b>${esc(x.status||'Grany')}</b></span></div><div class="community-actions"><button data-like-coupon="${esc(x.id)}">❤️ ${x.likes||0}</button></div><div class="coupon-comments">${(x.comments||[]).map(c=>`<div><b>💬</b> ${esc(c)}</div>`).join('')}<form data-comment-form="${esc(x.id)}"><input maxlength="180" placeholder="Dodaj komentarz"><button>Wyślij</button></form></div></div></article>`}
async function compressImage(file){if(!file)return '';const img=await createImageBitmap(file);const max=1200;const scale=Math.min(1,max/Math.max(img.width,img.height));const w=Math.max(1,Math.round(img.width*scale));const h=Math.max(1,Math.round(img.height*scale));const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;canvas.getContext('2d').drawImage(img,0,0,w,h);return canvas.toDataURL('image/jpeg',.72)}
function renderCoupons(){const app=document.querySelector('#app');app.innerHTML=`<section class="community-hero"><h2>🧾 Kupony społeczności</h2><p>Wrzuć swój kupon, dopisz kurs, bukmachera i status. Reakcje i komentarze są już w widoku.</p><div class="local-note">Na razie kupony są zapisywane lokalnie na tym urządzeniu. Nie udajemy wspólnej bazy, dopóki nie podłączymy backendu.</div></section><form id="coupon-form" class="community-form coupon-form"><label>Tytuł<input name="title" maxlength="80" required placeholder="Np. Kupon na wieczór"></label><label>Bukmacher<input name="bookmaker" maxlength="50" placeholder="Np. Superbet"></label><label>Kurs<input name="odds" maxlength="20" placeholder="Np. 8.45"></label><label>Status<select name="status"><option>Grany</option><option>Wygrany</option><option>Przegrany</option><option>Cashout</option></select></label><label class="wide">Opis<textarea name="description" maxlength="600" placeholder="Co zagrałeś?"></textarea></label><label class="wide">Screen kuponu<input name="image" type="file" accept="image/*"></label><button type="submit" class="primary-btn wide">Dodaj kupon</button></form><div class="coupon-list">${couponRows.length?couponRows.slice().reverse().map(couponCard).join(''):'<div class="empty small"><b>Brak kuponów.</b><br>Dodaj pierwszy.</div>'}</div>`;document.querySelector('#coupon-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);const file=form.elements.image.files?.[0];let image='';try{image=await compressImage(file)}catch{}const row={id:crypto.randomUUID?crypto.randomUUID():String(Date.now()),title:String(fd.get('title')||'').trim(),bookmaker:String(fd.get('bookmaker')||'').trim(),odds:String(fd.get('odds')||'').trim(),status:String(fd.get('status')||'Grany'),description:String(fd.get('description')||'').trim(),image,likes:0,comments:[],createdAt:new Date().toISOString()};couponRows.push(row);if(!writeLocal(COUPON_KEY,couponRows)){couponRows.pop();alert('Brak miejsca na urządzeniu. Spróbuj mniejszego screena lub usuń starszy kupon.');return}renderCoupons()};document.querySelectorAll('[data-like-coupon]').forEach(b=>b.onclick=()=>{const x=couponRows.find(v=>v.id===b.dataset.likeCoupon);if(x){x.likes=(x.likes||0)+1;writeLocal(COUPON_KEY,couponRows);renderCoupons()}});document.querySelectorAll('[data-comment-form]').forEach(f=>f.onsubmit=e=>{e.preventDefault();const x=couponRows.find(v=>v.id===f.dataset.commentForm);const input=f.querySelector('input');const text=input.value.trim();if(x&&text){x.comments=x.comments||[];x.comments.push(text);writeLocal(COUPON_KEY,couponRows);renderCoupons()}})}

function render(){
  const matchControls=document.querySelector('#match-controls');
  const matched=document.querySelector('#matched');
  if(matchControls)matchControls.style.display=view==='matches'?'block':'none';
  if(matched)matched.style.display=view==='matches'?'inline-block':'none';
  if(view==='matches')renderMatches();
  else if(view==='stats')renderStats();
  else if(view==='history')renderHistory();
  else if(view==='feedback')renderFeedback();
  else renderCoupons();
}

async function safeJson(url,fallback){try{const r=await fetch(url+'?'+Date.now());if(!r.ok)return fallback;return await r.json()}catch{return fallback}}
async function load(){try{const [results,meta,hist,stat]=await Promise.all([safeJson('data/results.json',[]),safeJson('data/meta.json',{}),safeJson('data/history.json',[]),safeJson('data/history_stats.json',{})]);all=results;historyRows=hist;statsData=stat;document.querySelector('#updated').textContent=meta.updated_at?'Aktualizacja: '+new Date(meta.updated_at).toLocaleString('pl-PL'):'Aktualizacja: —';document.querySelector('#mode').textContent='Źródło: '+(meta.fixtures_mode||'—');const hm=document.querySelector('#history-mode');if(hm){const x=meta.history_mode||'—';hm.textContent=x==='degraded-previous'?'Historia: awaria źródła · poprzednie dane':x==='cache'?'Historia: cache':x==='fresh'?'Historia: świeża':x==='fresh+cache'?'Historia: cache + świeże':'Historia: '+x}updateCounts();render()}catch(e){document.querySelector('#app').innerHTML='<div class="empty">Nie udało się wczytać danych.</div>'}}

document.querySelectorAll('#tour-nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('#tour-nav button').forEach(x=>x.classList.remove('active'));b.classList.add('active');filter=b.dataset.filter;renderMatches()});
document.querySelectorAll('.main-tabs button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.main-tabs button').forEach(x=>x.classList.remove('active'));b.classList.add('active');view=b.dataset.view;render()});
document.querySelector('#collapse-all').onclick=()=>setAllDetails(false);
document.querySelector('#expand-all').onclick=()=>setAllDetails(true);
document.querySelector('#refresh').onclick=load;
if('serviceWorker'in navigator)navigator.serviceWorker.register('sw.js?v=801');
load();
// v7.8E2.3: nie przebudowuj całej listy co minutę podczas dotyku/przewijania.
setInterval(()=>{if(view==='matches')updateCounts()},60000);
