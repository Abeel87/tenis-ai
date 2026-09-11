import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const read=n=>fs.readFileSync('frontend/'+n,'utf8');
const fixtureDir=process.env.TENIS_UI_FIXTURES||'frontend/data';
const feed=n=>fs.existsSync(fixtureDir+'/'+n)?JSON.parse(fs.readFileSync(fixtureDir+'/'+n)):null;
const matches=feed('results.json')||[{id:1,p1:'Alpha',p2:'Beta',scheduled_time:new Date(Date.now()+3600000).toISOString(),first_set_win:{Alpha:60,Beta:40},game_states:{2:{'1:1':65}}},{id:2,p1:'Gamma',p2:'Delta',scheduled_time:new Date(Date.now()+3600000).toISOString(),first_set_win:{Gamma:60,Delta:40}}];
const symphony=feed('symphony2_current.json')||{matches};
const handlers={},elements=new Map(),writes=[];
function node(){return {innerHTML:'',textContent:'',hidden:false,disabled:false,dataset:{},classList:{toggle(){}},setAttribute(){},removeAttribute(){},querySelectorAll(){return[]},querySelector(s){return element(s)}}}
function element(s){if(!elements.has(s))elements.set(s,node());return elements.get(s)}
const storage=new Map();
let role='user';
const account={authenticated:true,user:{id:'owner'},profile:{username:'Tester'},get role(){return role},client:{from(table){const q={select(){return q},eq(){return q},order(){return q},upsert(row){writes.push({table,row});q.row=row;return q},single(){return Promise.resolve({data:q.row})},then(resolve){return Promise.resolve({data:[]}).then(resolve)}};return q},rpc(){return Promise.resolve({data:[]})}},signOut(){account.authenticated=false;handlers['tenis-auth']()}};
const ctx={console,URL,Date,Map,Set,JSON,Math,Promise,Number,Object,Array,String,structuredClone,crypto:{randomUUID:()=> 'coupon-1'},navigator:{},location:{hash:'#start',href:'https://example.test/',origin:'https://example.test',pathname:'/'},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},document:{hidden:false,querySelector:element,querySelectorAll:()=>[],addEventListener:(k,f)=>handlers[k]=f},addEventListener:(k,f)=>handlers[k]=f,scrollY:0,scrollTo(x,y){ctx.scrollY=y},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,requestAnimationFrame:f=>f(),queueMicrotask,fetch:async path=>({ok:true,json:async()=>path.includes('symphony2_current')?symphony:path.includes('results')?matches:path.includes('match_detail_history')?{matches:[]}:path.includes('history')?(feed('history.json')||[]):path.includes('simulation')?(feed('player_dna_current_simulation.json')||{matches:[]}):{}})};
ctx.window=ctx;ctx.globalThis=ctx;vm.createContext(ctx);
const scripts=[...read('index.html').matchAll(/<script src="([^"]+)"/g)].map(x=>x[1]).filter(x=>!x.startsWith('https:')&&x!=='account.js');ctx.TenisAccount=account;
for(const name of scripts)vm.runInContext(read(name),ctx,{filename:name});
const flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve()};await flush();
const route=async hash=>{ctx.location.hash=hash;handlers.hashchange();await flush();return element('#app').innerHTML};
assert((await route('#symphony')).includes('Symfonia 2.0'));
assert.equal((element('#app').innerHTML.match(/data-events=/g)||[]).length,symphony.matches.length,'All Symphony matches must render');
const candidates=symphony.matches.filter(s=>ctx.TenisPresentation.allEvents(ctx.TenisPresentation.find(matches,s)||s,s).length).slice(0,2);
for(const m of candidates){const id=ctx.TenisPresentation.key(m),box=node();const detail={open:true,dataset:{events:id},matches:()=>true,querySelector:()=>box};handlers.toggle({target:detail});assert(box.innerHTML.includes('data-leg='),'Expanded events');const el={dataset:{leg:'0',match:id},checked:true,hasAttribute:k=>k==='data-leg',matches:()=>false,parentElement:{lastChild:{textContent:''}}};handlers.change({target:el});}
assert(element('#coupon-bar').innerHTML.includes(candidates.length+' zdarzeń'));
assert((await route('#coupons')).includes('slip-stake'));
const click=async attrs=>{const b={dataset:{},matches:()=>false,hasAttribute:k=>k in attrs,...attrs};await handlers.click({target:{closest:()=>b}});await flush()};
// Stage 1: selectors and navigation retain their presentation state.
await route('#symphony');
const scored=symphony.matches.flatMap(m=>ctx.TenisPresentation.allEvents(ctx.TenisPresentation.find(matches,m)||m,m)).filter(s=>s.source==='Symfonia 2.0');
if(scored.length){
 const cards=()=> (element('#app').innerHTML.match(/class="recommendation-card"/g)||[]).length;
 assert(cards()>0&&cards()<=3,'Default TOP 3');
 await click({dataset:{sLimit:'5'}});assert(cards()<=5,'TOP 5 limit');
 const choice=ctx.TenisPresentation.marketChoice(scored[0]);
 handlers.change({target:{id:'symphony-market',value:choice}});
 assert(element('#symphony-results').innerHTML.includes('recommendation-card'),'Existing market has recommendations');
 await route('#symphony');assert(element('#app').innerHTML.includes(`value="${choice}" selected`),'Market choice survives routing');
}
await route('#matches');
await click({dataset:{focus:'all'},closest:()=>({dataset:{filterScope:'matches'}})});
assert.equal((element('#app').innerHTML.match(/class="match-card"/g)||[]).length,matches.length,'Tournament sections preserve every fixture');
const tournament=ctx.TenisPresentation.tournamentGroups(matches)[0].key;
handlers.toggle({target:{dataset:{tournament},open:true}});
ctx.scrollY=640;handlers.scroll();
await route('#match/'+encodeURIComponent(ctx.TenisPresentation.key(matches[0]))+'/summary');
await route('#matches');assert.equal(ctx.scrollY,640,'Hash navigation restores list position');
assert(element('#app').innerHTML.includes(`data-tournament="${ctx.TenisPresentation.esc(tournament)}" open`),'Expanded tournament survives return');
await route('#coupons');
console.log('PASS: TOP controls, market state, tournament fixture retention, expanded section and scroll restoration');
handlers.input({target:{id:'slip-title',value:'Weekend',matches:()=>false}});
handlers.input({target:{id:'slip-stake',value:'25',matches:()=>false}});
await click({'data-save-slip':true});assert.equal(writes[0].table,'ui_coupons');assert.equal(writes[0].row.user_id,'owner');assert.equal(writes[0].row.title,'Weekend');assert.equal(writes[0].row.stake,25);assert.equal(writes[0].row.legs.length,candidates.length);
assert((await route('#coupons/saved')).includes('Weekend'));
assert((await route('#admin/dashboard')).includes('Brak uprawnień'));assert((await route('#moderator')).includes('Brak uprawnień'));
role='moderator';assert((await route('#moderator')).includes('Panel moderatora'));assert((await route('#admin/dashboard')).includes('Brak uprawnień'));
role='admin';for(const tab of ['dashboard','models','data','superbet','system','users','diagnostics'])assert((await route('#admin/'+tab)).includes('Admin Control Center'));
const id=encodeURIComponent(ctx.TenisPresentation.key(matches[0]));for(const tab of ['summary','trajectory','stats','h2h'])assert((await route('#match/'+id+'/'+tab)).includes('detail-body'));
assert((await route('#player/'+id+'/p1')).includes(matches[0].p1));assert((await route('#players')).includes('player-query'));await route('#history');
const rich=matches.find(m=>m.match_win&&m.player_intelligence_v85?.profiles?.p1?.windows?.['10']?.metrics?.won?.adjusted!=null);
if(rich){const key=encodeURIComponent(ctx.TenisPresentation.key(rich));const summary=await route('#match/'+key+'/summary');assert(summary.includes('SZYBKA OCENA'));assert(summary.includes('Porównanie zawodników'));assert(summary.includes('Przewaga'));assert((await route('#match/'+key+'/stats')).includes('Trend:'));}
const realHistory=feed('history.json')||[];
const existingH2H=matches.find(m=>ctx.TenisMatchDetail.historyRows(realHistory,m,'p1',true).length);
if(existingH2H){const html=await route('#match/'+encodeURIComponent(ctx.TenisPresentation.key(existingH2H))+'/h2h');assert(html.includes('h2h-bar'));assert(html.includes('Zwycięzca:'));}
console.log('PASS Stage 2: real comparison, form and H2H route rendering');
account.authenticated=false;handlers['tenis-auth']();assert.equal(element('#app').innerHTML,'');assert(element('#coupon-bar').hidden);
console.log('PASS: route runtime, all Symphony cards, expansion, cross-match selection, coupon persistence contract, role isolation, logout cleanup');
// Exercise the real authentication owner against a controlled Supabase boundary.
const authElements=new Map(),authEvents=[];let serverUser=null,serverProfile=null;
const authNode=s=>{if(!authElements.has(s))authElements.set(s,{...node(),querySelector:authNode});return authElements.get(s)};
const authClient={auth:{getUser:async()=>({data:{user:serverUser}}),onAuthStateChange(){},signOut:async()=>({})},from(){const q={select:()=>q,eq:()=>q,single:async()=>({data:serverProfile})};return q}};
const authContext={console,document:{querySelector:authNode},location:{},CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail}},setTimeout:()=>0,TENIS_AI_SUPABASE:{url:'https://example.test',publishableKey:'test'},supabase:{createClient:()=>authClient},dispatchEvent:e=>authEvents.push(e)};authContext.window=authContext;vm.createContext(authContext);vm.runInContext(read('account.js'),authContext);await flush();
assert(!authContext.TenisAccount.authenticated);assert(authNode('#product-shell').hidden);
serverUser={id:'owner',user_metadata:{role:'admin'}};serverProfile={id:'owner',role:'user',username:'Tester'};await authContext.TenisAccount.sync();assert.equal(authContext.TenisAccount.role,'user');assert(authContext.TenisAccount.authenticated);
for(const r of ['moderator','admin']){serverProfile={...serverProfile,role:r};await authContext.TenisAccount.sync();assert.equal(authContext.TenisAccount.role,r)}
serverProfile.banned_at='2026-09-10';await authContext.TenisAccount.sync();assert(!authContext.TenisAccount.authenticated);assert(authNode('#product-shell').hidden);
serverProfile=null;await authContext.TenisAccount.sync();assert(!authContext.TenisAccount.authenticated);
console.log('PASS: real auth controller rejects guests, missing/banned profiles and metadata role escalation');
