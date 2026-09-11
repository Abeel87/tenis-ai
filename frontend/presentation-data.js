/* Read-only presentation mapping. Values and availability are separate sources. */
(()=>{
'use strict';
const num=v=>v==null||v===''||!Number.isFinite(Number(v))?null:Number(v);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=v=>String(v??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const key=m=>String(m.id??m.match_id??m.match_key??[m.p1,m.p2,m.scheduled_time].join('|'));
const pct=v=>num(v)==null?'Brak danych':`${Number(v).toFixed(1).replace('.0','')}%`;
const score=v=>num(v)==null?'Brak danych':`${Number(v).toFixed(1).replace('.0','')}/100`;
const ratio=v=>pct(num(v)==null?null:Number(v)*100);
const best=o=>Object.entries(o||{}).filter(([,v])=>num(v)!=null).sort((a,b)=>b[1]-a[1])[0];
const LABELS={match_winner:'Zwycięzca meczu',match_win:'Zwycięzca meczu',set1_winner:'Zwycięzca 1. seta',set1_win:'Zwycięzca 1. seta',set2_win:'Zwycięzca 2. seta',set2_winner:'Zwycięzca 2. seta',set3_win:'Zwycięzca 3. seta',set3_winner:'Zwycięzca 3. seta',set1_total:'Liczba gemów w 1. secie',set2_total:'Liczba gemów w 2. secie',set3_total:'Liczba gemów w 3. secie',match_total:'Liczba gemów w meczu',total_sets:'Liczba setów',exact_match_score:'Dokładny wynik meczu',set1_exact_score:'Dokładny wynik 1. seta',set1_tiebreak:'Tie-break w 1. secie',match_tiebreak:'Tie-break w meczu',tiebreak_count:'Liczba tie-breaków',match_game_handicap:'Handicap gemów w meczu',match_handicap:'Handicap gemów w meczu',game_handicap:'Handicap gemów w meczu',set_handicap:'Handicap setów',set1_game_handicap:'Handicap gemów w 1. secie',player_total_games:'Gemy zawodnika',player_aces:'Asy zawodnika',match_total_aces:'Asy w meczu',player_double_faults:'Podwójne błędy',most_aces:'Najwięcej asów',most_double_faults:'Najwięcej podwójnych błędów',any_set_to_nil:'Set do zera',both_players_win_set:'Obaj zawodnicy wygrają seta',set1_exact_six_games:'Dokładnie 6 gemów w 1. secie',joint_3of3:'Prowadzenie po 6 gemach, ponad 8,5 gema i wygrany 1. set'};
function label(s,m){
const market=String(s.market||'');
if(/^state[246]$/.test(market)||market==='game_state')return `Wynik po ${s.checkpoint??market.slice(-1)} gemach`;
if(/^p[12]_exactly_1_?set$/.test(market))return `${market[1]==='1'?m.p1:m.p2} wygra dokładnie 1 set`;
if(/^p[12]_wins_a_set$/.test(market))return `${market[1]==='1'?m.p1:m.p2} wygra seta`;
return LABELS[market]||String(s.label||'Inne zdarzenie').replaceAll('_',' ');
}
function pick(s,m){let p=String(s.displayPick??s.pick??'—');p=({yes:'Tak',no:'Nie',over:'Powyżej',under:'Poniżej',p1:m.p1,p2:m.p2,p1_lead:m.p1+' prowadzi',p2_lead:m.p2+' prowadzi',draw:'Remis'})[p]||p;return `${p}${num(s.line)!=null?' '+Number(s.line):''}`;}
const cache=new Map();
async function json(path,force=false){if(force)cache.delete(path);if(!cache.has(path))cache.set(path,fetch(path,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Nie można pobrać danych ('+r.status+').');return r.json()}).catch(e=>{cache.delete(path);throw e}));return cache.get(path)}
function find(rows,m){const ids=[m.id,m.match_id,m.match_key].filter(v=>v!=null).map(String);return rows.find(r=>[r.id,r.match_id,r.match_key].some(v=>v!=null&&ids.includes(String(v))))||rows.find(r=>norm(r.p1)===norm(m.p1)&&norm(r.p2)===norm(m.p2)&&Math.abs(Date.parse(r.scheduled_time)-Date.parse(m.scheduled_time))<=600000)||null;}
function allEvents(m,sym){
const out=[];const add=(s,source,value,unit)=>{if(!s||!s.market)return;out.push({...s,source,value:num(value),unit,eventKey:source+'|'+window.TENIS_AI_PLAYABLE_UI_V917.signature(s)})};
for(const s of sym?.scored_selections||[])add(s,'Symfonia 2.0',s.operator_model_probability,'%');
for(const c of Object.values(sym?.compositions||{}))for(const s of c?.selection||[])if(!out.some(x=>x.eventKey==='Symfonia 2.0|'+window.TENIS_AI_PLAYABLE_UI_V917.signature(s)))add(s,'Symfonia 2.0',s.operator_model_probability,'%');
for(const s of m.autolearn_v84?.signals||[])add(s,'Ocena AI',s.final_score??s.adaptive_prod_score??s.adaptive_prod_v79?.final_score,'/100');
for(const s of window.TENIS_AI_DECISION_CENTER_V87.buildRows(m)){if(num(s.base)!=null)add(s,'Model bazowy',s.base,'%');if(num(s.lab)!=null)add(s,'Analiza eksperymentalna',s.lab,'%');if(num(s.joint)!=null)add(s,'Analiza łączna',s.joint,'%');}
for(const [field,market]of [['over_under','set1_total'],['match_over_under','match_total']])for(const [line,v]of Object.entries(m[field]||{}))for(const pick of ['over','under'])if(num(v[pick])!=null)add({market,pick,line:Number(line)},'Model bazowy',v[pick],'%');
for(const [p,v]of Object.entries(m.exact_first_set||{}))add({market:'set1_exact_score',pick:p},'Model bazowy',v,'%');
for(const [field,market]of [['early_first_set_win','set1_winner'],['early_exact_first_set','set1_exact_score']])for(const [p,v]of Object.entries(m[field]||{}))add({market,pick:p},'Początek seta',v,'%');
for(const [line,v]of Object.entries(m.early_over_under||{}))for(const p of ['over','under'])if(num(v[p])!=null)add({market:'set1_total',pick:p,line:Number(line)},'Początek seta',v[p],'%');
const seen=new Set();return out.filter(s=>{if(seen.has(s.eventKey))return false;seen.add(s.eventKey);return true});
}
function availability(m,s,sym,generatedAt){const api=window.TENIS_AI_PLAYABLE_UI_V917;const offer=api.active(m)&&m.superbet_market_v91?.operator==='superbet.pl'?api.availability(m).get(api.signature(s)):undefined;const layer=m.symphony2_playable;const selected=layer?.signals||[];const comp=sym?.compositions?.[String(sym?.recommended_leg_count)];const sameSnapshot=!!generatedAt&&layer?.source_generated_at===generatedAt;const matching=comp&&Number(sym.recommended_leg_count)>=2&&Number(layer?.recommended_leg_count)===Number(sym.recommended_leg_count)&&comp.selection?.length===Number(sym.recommended_leg_count)&&selected.length===comp.selection.length&&selected.map(api.signature).sort().join('|')===comp.selection.map(api.signature).sort().join('|');const final=!!offer&&sameSnapshot&&matching&&layer?.playable===true&&layer?.final_playable_authority===true&&api.compositionPlayable(m,comp)&&selected.some(x=>api.signature(x)===api.signature(s));return {available:!!offer,playable:!!final,odds:offer?num(offer.odds??offer.price??offer.decimal_odds):null,offer};}
function couponTotals(legs,stake){const grouped=new Map();for(const leg of legs){if(!grouped.has(leg.matchId))grouped.set(leg.matchId,[]);grouped.get(leg.matchId).push(leg)}const correlated=[...grouped.values()].some(x=>x.length>1);const complete=legs.length>0&&legs.every(x=>num(x.odds)!=null&&Number(x.odds)>1);const odds=complete&&!correlated?legs.reduce((v,l)=>v*Number(l.odds),1):null;return {odds,payout:odds!=null&&num(stake)!=null?odds*Number(stake):null,correlated};}
function filterRows(rows,f,{saved=new Set(),events=()=>[],playable=()=>false,now=Date.now()}={}){return rows.filter(m=>{const t=Date.parse(m.scheduled_time);if(f.tour&&f.tour!=='all'&&String(m.tour||'').toLowerCase()!==f.tour)return false;if(f.surface&&f.surface!=='all'&&m.surface!==f.surface)return false;if(f.query&&!norm(m.p1+' '+m.p2+' '+m.tournament).includes(norm(f.query)))return false;if(f.focus==='soon'&&!(t>now&&t<=now+7200000))return false;if(f.focus==='today'&&new Date(t).toLocaleDateString('en-CA',{timeZone:'Europe/Warsaw'})!==new Date(now).toLocaleDateString('en-CA',{timeZone:'Europe/Warsaw'}))return false;if(f.focus==='saved'&&!saved.has(key(m)))return false;if(f.focus==='playable'&&!playable(m))return false;if(f.focus==='data'&&!events(m).some(x=>x.value!=null))return false;return true}).sort((a,b)=>f.sort==='name'?String(a.p1).localeCompare(String(b.p1),'pl'):f.sort==='quality'||f.focus==='top'?(window.TENIS_AI_MODEL_API.signals(b,1)[0]?.v??-1)-(window.TENIS_AI_MODEL_API.signals(a,1)[0]?.v??-1):(Date.parse(a.scheduled_time)||Infinity)-(Date.parse(b.scheduled_time)||Infinity));}

// Price metadata is deliberately separate from the price-free PLAYABLE contract.
// This read-only join cannot grant availability or change a recommendation.
function operatorPrice(m,s,feed){
const api=window.TENIS_AI_PLAYABLE_UI_V917;
if(feed?.operator!=='superbet.pl'||feed.status!=='OK'||feed.prices_used!==false||!api?.signature||!api?.freshContext)return null;
const sig=api.signature(s),fresh={source_generated_at:feed.generated_at,source_max_age_hours:m?.superbet_market_v91?.source_max_age_hours??1.8};
if(!sig||!api.freshContext(fresh))return null;
const name=v=>norm(v).split(' ').sort().join(' ');
const rows=(Array.isArray(feed.matches)?feed.matches:[]).filter(r=>String(r.match_id)===key(m)&&r.direct_match_verified===true&&name(r.p1)===name(m.p1)&&name(r.p2)===name(m.p2));
if(rows.length!==1)return null;
const r=rows[0],start=Date.parse(r.operator_start_time),scheduled=Date.parse(m.scheduled_time);
// Match the existing backend fixture tolerance (MAX_MATCH_TIME_DELTA_HOURS=4).
// A verified ID does not authorize reusing a price for another day's fixture.
if(!Number.isFinite(start)||!Number.isFinite(scheduled)||start<=Date.now()||Math.abs(start-scheduled)>4*3600000)return null;
try{const url=new URL(r.event_url);if(url.protocol!=='https:'||url.hostname!=='superbet.pl')return null}catch{return null}
const matches=(Array.isArray(r.canonical_selections)?r.canonical_selections:[]).filter(x=>x.operator==='superbet.pl'&&x.operator_available===true&&x.operator_price_verified===true&&x.prices_used===false&&x.operator_selection_status!=='suspended'&&(!x.operator_selection_status||x.operator_selection_status==='active')&&api.signature(x)===sig&&num(x.set_no)===num(s.set_no??(/^set([123])_/.exec(api.canonicalMarket(s.market))?.[1])));
// Ambiguous duplicate prices fail closed; no nearest market/line or old-price fallback.
if(!matches.length||new Set(matches.map(x=>num(x.operator_price))).size!==1)return null;
const row=matches[0],odds=num(row.operator_price);
return odds!=null&&odds>1?{odds,generated_at:feed.generated_at,event_url:r.event_url}:null;
}
function marketGroup(s){const api=window.TENIS_AI_PLAYABLE_UI_V917,parts=api.signature(s).split('¦');parts[1]='';return JSON.stringify([s.source,parts.join('¦'),num(s.set_no),norm(s.player)]);}
function groupEvents(rows){const groups=new Map();rows.forEach((s,index)=>{const k=marketGroup(s);if(!groups.has(k))groups.set(k,[]);groups.get(k).push({s,index})});return [...groups.values()].map(items=>items.sort((a,b)=>(b.s.value??-Infinity)-(a.s.value??-Infinity)));}
function marketChoice(s){const api=window.TENIS_AI_PLAYABLE_UI_V917,market=api.canonicalMarket(s.market);if(market==='game_state'){const p=api.signature(s).split('¦');return market+':'+p[3]+(['1:1','2:2','3:3'].includes(p[1])?':draw':':lead')}return market;}
function marketChoiceLabel(s,m){const choice=marketChoice(s);if(choice.startsWith('game_state:')){const [,cp,kind]=choice.split(':');return kind==='draw'?`Remis ${Number(cp)/2}:${Number(cp)/2}`:`Prowadzenie po ${cp} gemach`;}if(/^p[12]_wins_a_set$/.test(choice))return `${choice[1]==='1'?'Pierwszy':'Drugi'} zawodnik wygra seta`;if(/^p[12]_exactly_1_?set$/.test(choice))return `${choice[1]==='1'?'Pierwszy':'Drugi'} zawodnik wygra dokładnie 1 set`;return label(s,m);}
function tournamentGroups(rows){const groups=new Map();for(const m of rows){const k=JSON.stringify([m.tour||'',m.tournament||'',m.surface||'']);if(!groups.has(k))groups.set(k,{key:k,tour:m.tour,tournament:m.tournament,surface:m.surface,matches:[]});groups.get(k).matches.push(m)}return [...groups.values()];}

window.TenisPresentation={operatorPrice,groupEvents,marketChoice,marketChoiceLabel,tournamentGroups,num,esc,norm,key,pct,ratio,score,best,label,pick,json,find,allEvents,availability,couponTotals,filterRows,clearCache:()=>cache.clear()};
})();