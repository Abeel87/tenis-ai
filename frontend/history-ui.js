/* Rich read-only history for Tenis AI. Uses frozen pre-match snapshots only. */
(()=>{
'use strict';
if(typeof document==='undefined'||typeof location==='undefined'||typeof MutationObserver==='undefined')return;
const D=window.TenisPresentation,A=window.TenisAccount;
if(!D)return;
const E=D.esc;
const ui={filter:'settled',query:'',dayLimit:14,data:null,model:null,loading:null,renderToken:0,searchTimer:null};
const FILTERS=[['settled','Rozliczone'],['all','Wszystkie'],['hit','Trafione'],['miss','Nietrafione'],['playable','PLAYABLE'],['symphony','Symfonia 2.0'],['pending','Oczekujące']];
const STATUS={
 hit:{label:'✅ TRAFIONY',className:'ok'},
 miss:{label:'❌ NIETRAFIONY',className:'bad'},
 void:{label:'➖ VOID',className:'warn'},
 pending:{label:'⏳ OCZEKUJE',className:''},
 unverifiable:{label:'⚪ NIEROZLICZALNE',className:'warn'},
 conflict:{label:'⚠ NIESPÓJNE',className:'bad'},
 unknown:{label:'⚪ BRAK ROZLICZENIA',className:''}
};
const LAYERS={
 signals:{source:'Model bazowy',unit:'score'},
 autolearn_signals_v84:{source:'AutoLearn',unit:'score'},
 superbet_candidate_signals_v925:{source:'Superbet · kandydat',unit:'score'}
};
const PLAYABLE_LAYERS={playable_signals_v912:'signals',playable_autolearn_signals_v912:'autolearn_signals_v84'};
function active(){return location.hash==='#history'&&!!A?.authenticated;}
function app(){return document.querySelector('#app');}
function number(v){const n=Number(v);return v==null||v===''||!Number.isFinite(n)?null:n;}
function pct(v){const n=number(v);if(n==null)return 'Brak danych';const x=Math.abs(n)<=1?n*100:n;return `${x.toFixed(1).replace('.0','')}%`;}
function score(v){const n=number(v);return n==null?'Brak danych':`${n.toFixed(1).replace('.0','')}/100`;}
function time(v){const t=Date.parse(v);return Number.isFinite(t)?new Date(t).toLocaleString('pl-PL',{timeZone:'Europe/Warsaw',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}):'N/D';}
function dayKey(v){const t=Date.parse(v);return Number.isFinite(t)?new Date(t).toLocaleDateString('en-CA',{timeZone:'Europe/Warsaw'}):'bez-daty';}
function dayLabel(v){const t=Date.parse(v);if(!Number.isFinite(t))return 'Bez potwierdzonej daty';const s=new Date(t).toLocaleDateString('pl-PL',{timeZone:'Europe/Warsaw',weekday:'long',day:'2-digit',month:'long',year:'numeric'});return s.charAt(0).toUpperCase()+s.slice(1);}
function matchKey(r){const id=r?.match_id??r?.id;if(id!=null&&String(id)!=='')return 'id:'+String(id);return 'nm:'+D.norm(r?.p1)+'|'+D.norm(r?.p2)+'|'+dayKey(r?.scheduled_time);}
function sig(s){return [String(s?.market||''),String(s?.pick??''),String(s?.line??''),String(s?.checkpoint??''),D.norm(s?.player||'')].join('|');}
function status(v){const x=String(v||'').toLowerCase();return STATUS[x]?x:x?'unknown':'pending';}
function settledStatus(v){return ['hit','miss','void'].includes(status(v));}
function resultBadge(v){const s=status(v),m=STATUS[s]||STATUS.unknown;return `<span class="badge ${m.className}">${m.label}</span>`;}
function oddsOf(s){for(const k of ['odds','operator_odds','operator_price','price','decimal_odds','superbet_odds']){const n=number(s?.[k]);if(n!=null&&n>1)return n}return null;}
function valueOf(s){for(const k of ['score','final_score','adaptive_prod_score','probability','operator_model_probability','model_probability']){const n=number(s?.[k]);if(n!=null)return n}return null;}
function mergeResult(a,b){const x=status(a),y=status(b);if(x===y)return x;const sx=settledStatus(x),sy=settledStatus(y);if(sx&&sy)return 'conflict';if(sy)return y;if(sx)return x;if(y==='unverifiable')return y;return x||y||'pending';}
function basePredictions(entry){
 const out=[];
 const byLayerSig=new Map();
 for(const [layer,meta] of Object.entries(LAYERS)){
   const rows=Array.isArray(entry?.[layer])?entry[layer]:[];
   for(const s of rows){if(!s||!s.market)continue;const rec={signal:s,source:meta.source,unit:meta.unit,value:valueOf(s),result:status(s.result),playable:false,odds:oddsOf(s),capturedAt:entry.captured_at||entry.first_captured_at||null,kind:'model'};out.push(rec);byLayerSig.set(layer+'|'+sig(s),rec)}
 }
 for(const [layer,targetLayer] of Object.entries(PLAYABLE_LAYERS)){
   const rows=Array.isArray(entry?.[layer])?entry[layer]:[];
   for(const s of rows){if(!s||!s.market)continue;const key=targetLayer+'|'+sig(s);let rec=byLayerSig.get(key);if(!rec){rec={signal:s,source:layer.includes('autolearn')?'AutoLearn':'Model bazowy',unit:'score',value:valueOf(s),result:status(s.result),playable:true,odds:oddsOf(s),capturedAt:entry.captured_at||entry.first_captured_at||null,kind:'model'};out.push(rec);byLayerSig.set(key,rec)}else{rec.playable=true;rec.result=mergeResult(rec.result,s.result);rec.odds=rec.odds??oddsOf(s);if(rec.value==null)rec.value=valueOf(s)}}
 }
 return out;
}
function latestSym(entries){return [...entries].sort((a,b)=>(Date.parse(b?.captured_at)||0)-(Date.parse(a?.captured_at)||0))[0]||null;}
function symPredictions(entries){const entry=latestSym(entries);if(!entry)return [];return (entry.selection||[]).filter(s=>s&&s.market).map(s=>({signal:s,source:'Symfonia 2.0',unit:'%',value:number(s.probability??s.operator_model_probability),result:status(s.result),playable:false,verified:s.fixture_line_verified===true,odds:oddsOf(s),capturedAt:entry.captured_at||null,kind:'symphony',predictionId:entry.prediction_id,jointProbability:number(entry.joint_probability),compositionResult:status(entry.result)}));}
function finalResult(entry){const r=entry?.result;return r&&typeof r==='object'?r:null;}
function resultText(entry){const r=finalResult(entry);if(!r)return 'Wynik: N/D';if(r.score_text)return String(r.score_text);if(Array.isArray(r.sets))return r.sets.map(x=>Array.isArray(x)?x.join(':'):String(x)).join(' · ');return r.match_score?String(r.match_score):'Wynik: N/D';}
function buildModel(data){
 const map=new Map();
 const ensure=r=>{const k=matchKey(r);if(!map.has(k))map.set(k,{key:k,p1:r?.p1||'',p2:r?.p2||'',scheduled_time:r?.scheduled_time||null,tournament:r?.tournament||'',surface:r?.surface||'',tour:r?.tour||'',base:null,sym:[]});const m=map.get(k);for(const f of ['p1','p2','scheduled_time','tournament','surface','tour'])if(!m[f]&&r?.[f])m[f]=r[f];return m};
 for(const r of data.history)if(r&&typeof r==='object'){const m=ensure(r);if(!m.base||Date.parse(r.captured_at||0)>=Date.parse(m.base.captured_at||0))m.base=r}
 for(const r of data.symphonyEntries)if(r&&typeof r==='object')ensure(r).sym.push(r);
 const matches=[...map.values()];
 for(const m of matches){m.predictions=[...basePredictions(m.base),...symPredictions(m.sym)];m.final=finalResult(m.base);m.day=dayKey(m.scheduled_time);m.time=Date.parse(m.scheduled_time)||0;m.search=D.norm([m.p1,m.p2,m.tournament,m.tour,m.surface].join(' '));}
 return matches.sort((a,b)=>b.time-a.time);
}
async function load(force=false){
 if(force){ui.data=null;ui.model=null;ui.loading=null;D.clearCache?.()}
 if(ui.data)return ui.data;
 if(ui.loading)return ui.loading;
 const paths=['data/history.json','data/symphony2_history.json','data/history_stats.json','data/symphony2_stats.json'];
 ui.loading=Promise.allSettled(paths.map(p=>D.json(p))).then(rows=>{
   const errors=[];rows.forEach((r,i)=>{if(r.status==='rejected')errors.push(paths[i])});
   const history=rows[0].status==='fulfilled'?(Array.isArray(rows[0].value)?rows[0].value:rows[0].value?.matches||[]):[];
   const symDoc=rows[1].status==='fulfilled'&&rows[1].value&&typeof rows[1].value==='object'?rows[1].value:{};
   const data={history,symphonyEntries:Array.isArray(symDoc.entries)?symDoc.entries:[],historyStats:rows[2].status==='fulfilled'?rows[2].value||{}:{},symphonyStats:rows[3].status==='fulfilled'?rows[3].value||{}:{},errors};
   ui.data=data;ui.model=buildModel(data);return data;
 }).finally(()=>{ui.loading=null});
 return ui.loading;
}
function matchSettled(m){return !!m.final||m.predictions.some(p=>settledStatus(p.result));}
function predVisible(p){if(ui.filter==='hit'||ui.filter==='miss')return status(p.result)===ui.filter;if(ui.filter==='playable')return p.playable;if(ui.filter==='symphony')return p.kind==='symphony';if(ui.filter==='pending')return ['pending','unverifiable','unknown'].includes(status(p.result));return true;}
function matchVisible(m){if(ui.query&&!m.search.includes(D.norm(ui.query)))return false;if(ui.filter==='settled')return matchSettled(m);if(ui.filter==='all')return true;return m.predictions.some(predVisible);}
function counts(predictions){const c={hit:0,miss:0,void:0,pending:0,unverifiable:0,unknown:0,playable:0,symphony:0};for(const p of predictions){const s=status(p.result);c[s]=(c[s]||0)+1;if(p.playable)c.playable++;if(p.kind==='symphony')c.symphony++}c.settled=c.hit+c.miss;c.accuracy=c.settled?100*c.hit/c.settled:null;return c;}
function header(){return `<header class="page-header"><div><p class="eyebrow">TENIS AI</p><h1>Historia</h1><p class="muted">Dzień → mecz → każda zapisana prognoza i jej rozliczenie.</p></div></header>`;}
function kpis(matches){const p=matches.flatMap(m=>m.predictions),c=counts(p);return `<div class="kpis"><div class="kpi"><small>Mecze w historii</small><b>${matches.length}</b></div><div class="kpi"><small>Rozliczone typy</small><b>${c.settled}</b></div><div class="kpi"><small>Trafione</small><b>${c.hit}</b></div><div class="kpi"><small>Nietrafione</small><b>${c.miss}</b></div><div class="kpi"><small>Skuteczność</small><b>${c.accuracy==null?'—':c.accuracy.toFixed(1)+'%'}</b></div></div>`;}
function controls(){return `<section class="panel"><div class="filters">${FILTERS.map(([v,l])=>`<button class="history-filter ${ui.filter===v?'active':''}" data-history-filter="${v}" aria-pressed="${ui.filter===v}">${l}</button>`).join('')}</div><label>Szukaj meczu<input id="history-query" type="search" value="${E(ui.query)}" placeholder="Zawodnik lub turniej"></label><p class="footer-note">Historia korzysta wyłącznie z zapisanych snapshotów przedmeczowych i istniejącego settlementu. Nic nie jest przeliczane po fakcie.</p></section>`;}
function sourceBadge(p){return `<span class="badge ${p.kind==='symphony'?'ok':''}">${E(p.source)}</span>${p.playable?'<span class="badge ok">PLAYABLE</span>':''}${p.verified?'<span class="badge">Linia Superbet zweryfikowana</span>':''}`;}
function predictionHtml(p,m){const value=p.value==null?'Brak zapisanej wartości':p.unit==='%'?pct(p.value):score(p.value);const odds=p.odds!=null?`<small>Kurs zapisany: ${p.odds.toFixed(2)}</small>`:'';return `<article class="event"><div><small class="event-source">${E(p.source)}</small><strong>${E(D.label(p.signal,m))}</strong><span>${E(D.pick(p.signal,m))}</span><small>${sourceBadge(p)}</small>${p.capturedAt?`<small>Snapshot: ${E(time(p.capturedAt))}</small>`:''}${odds}</div><div class="event-values"><b>${E(value)}</b>${resultBadge(p.result)}</div></article>`;}
function matchHtml(m){const allPred=m.predictions,shown=allPred.filter(predVisible),c=counts(allPred),final=m.final,latest=latestSym(m.sym),result=resultText(m.base),winner=final?.winner||null;const statusLine=matchSettled(m)?`${c.hit} traf. · ${c.miss} nietraf. · ${c.void} void`:`${c.pending+c.unverifiable+c.unknown} oczekuje`;return `<details class="symphony-card history-match"><summary><span class="symphony-title">${E(m.p1)} · ${E(m.p2)}</span><span class="symphony-sub">${resultBadge(matchSettled(m)?(c.miss?'miss':c.hit?'hit':'void'):'pending')}<span>${E(result)}</span><span>${E(statusLine)}</span></span></summary><div class="events"><section class="panel"><div class="summary-metrics"><div><small>Wynik</small><b>${E(result)}</b></div><div><small>Zwycięzca</small><b>${E(winner||'N/D')}</b></div><div><small>Nawierzchnia</small><b>${E(m.surface?({hard:'Twarda',clay:'Mączka',grass:'Trawa',carpet:'Dywan'}[m.surface]||m.surface):'N/D')}</b></div></div><p class="footer-note">${E(m.tournament||'Turniej N/D')} · ${E(time(m.scheduled_time))}${latest?.captured_at?' · Symfonia snapshot '+E(time(latest.captured_at)):''}</p></section>${shown.length?shown.map(p=>predictionHtml(p,m)).join(''):`<div class="empty">Brak prognoz pasujących do wybranego filtra.</div>`}</div></details>`;}
function dayHtml(day,matches,index){const preds=matches.flatMap(m=>m.predictions),c=counts(preds);return `<details class="symphony-card history-day" ${index===0?'open':''}><summary><span class="symphony-title">📅 ${E(dayLabel(matches[0]?.scheduled_time))}</span><span class="symphony-sub"><span>${matches.length} meczów</span><span>✅ ${c.hit}</span><span>❌ ${c.miss}</span><span>${c.accuracy==null?'—':c.accuracy.toFixed(1)+'%'}</span></span></summary><div class="events">${matches.map(matchHtml).join('')}</div></details>`;}
function renderBody(){const all=ui.model||[],visible=all.filter(matchVisible);const groups=new Map();for(const m of visible){if(!groups.has(m.day))groups.set(m.day,[]);groups.get(m.day).push(m)}const days=[...groups.entries()].slice(0,ui.dayLimit);const warning=ui.data?.errors?.length?`<p class="footer-note danger">Nie udało się wczytać: ${E(ui.data.errors.join(', '))}. Pokazuję dostępne źródła.</p>`:'';return `<section data-rich-history-root>${header()}${kpis(all)}${controls()}${warning}<div class="section-title"><h2>${visible.length} meczów</h2><small>${groups.size} dni</small></div>${days.length?days.map(([day,rows],i)=>dayHtml(day,rows,i)).join(''):'<div class="empty">Brak historii dla wybranego filtra.</div>'}${groups.size>ui.dayLimit?`<div class="toolbar"><button data-history-more>Pokaż starsze dni</button></div>`:''}</section>`;}
async function render(force=false){
 if(!active())return;
 const root=app();if(!root)return;
 const token=++ui.renderToken;
 root.innerHTML='<section data-rich-history-root><div class="empty">Wczytuję pełną historię prognoz i rozliczeń…</div></section>';
 try{await load(force);if(token!==ui.renderToken||!active())return;root.innerHTML=renderBody();}
 catch(e){if(token!==ui.renderToken||!active())return;root.innerHTML=`<section data-rich-history-root>${header()}<div class="empty">Nie udało się wczytać historii: ${E(e?.message||e)}</div></section>`;}
}
function schedule(force=false){queueMicrotask(()=>{if(!active())return;const root=app();if(root?.querySelector('[data-rich-history-root]')&&!force)return;render(force)});}
document.addEventListener('click',e=>{const filter=e.target.closest?.('[data-history-filter]');if(filter){ui.filter=filter.dataset.historyFilter;ui.dayLimit=14;app().innerHTML=renderBody();return}if(e.target.closest?.('[data-history-more]')){ui.dayLimit+=14;app().innerHTML=renderBody();return}if(e.target.closest?.('#refresh')){ui.data=null;ui.model=null;ui.loading=null;setTimeout(()=>schedule(true),0)}},true);
document.addEventListener('input',e=>{if(e.target?.id!=='history-query')return;ui.query=e.target.value;ui.dayLimit=14;clearTimeout(ui.searchTimer);ui.searchTimer=setTimeout(()=>{if(active()&&ui.model)app().innerHTML=renderBody()},120)});
window.addEventListener('hashchange',()=>schedule(false));
window.addEventListener('tenis-auth',()=>schedule(false));
const startObserver=()=>{const root=app();if(!root)return;new MutationObserver(()=>{if(active()&&!root.querySelector('[data-rich-history-root]'))schedule(false)}).observe(root,{childList:true})};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{startObserver();schedule(false)});else{startObserver();schedule(false)}
})();
