// Real Chromium UI tests with an isolated fake auth transport; never uses production credentials.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
let chromium;try{({chromium}=await import('playwright'))}catch{({chromium}=require(path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES,'playwright')))}
const root=path.resolve('frontend');
const server=http.createServer((req,res)=>{const file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));if(!file.startsWith(root+path.sep)&&file!==root){res.writeHead(403).end();return}const target=file===root||file===root+'/'?path.join(root,'index.html'):file;try{const data=fs.readFileSync(target);res.writeHead(200,{'content-type':target.endsWith('.js')?'text/javascript':target.endsWith('.json')?'application/json':target.endsWith('.css')?'text/css':target.endsWith('.html')?'text/html':'application/octet-stream','cache-control':'no-store'}).end(data)}catch{res.writeHead(404).end()}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({headless:true,executablePath:process.env.TENIS_CHROMIUM_EXECUTABLE||undefined,args:process.env.TENIS_CHROMIUM_EXECUTABLE?["--no-sandbox","--disable-dev-shm-usage"]:[]});
const index=JSON.parse(fs.readFileSync(root+'/data/delivery/index.json'));
const first=index.matches[0], hash='#match/'+encodeURIComponent(String(first.id))+'/summary';
const results=[];
try{
 for(const role of ['user','moderator','admin']){
  const context=await browser.newContext({viewport:{width:412,height:915},isMobile:true,hasTouch:true,serviceWorkers:'block'});
  const page=await context.newPage(),requests=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().includes('/data/'))requests.push(r.url().slice(origin.length+1))});
  await page.route('https://cdn.jsdelivr.net/**',route=>route.fulfill({contentType:'text/javascript',body:`
window.supabase={createClient(){let logged=false;const q={select(){return this},eq(){return this},is(){return this},in(){return this},order(){return this},limit(){return this},maybeSingle(){return Promise.resolve({data:null})},single(){return Promise.resolve({data:{id:'test-user',username:'Browser test',role:'${role}',banned_at:null}})},upsert(rows){window.testPreferences=Object.assign(window.testPreferences||{},Object.fromEntries(rows.map(r=>[r.setting_key,r.value])));return Promise.resolve({})},then(resolve){return Promise.resolve({data:this.table==='ui_preferences'?Object.entries(window.testPreferences||{}).map(([setting_key,value])=>({setting_key,value})):[]}).then(resolve)}};return {auth:{async getSession(){return {data:{session:{access_token:'isolated-test-token'}}}},async getUser(){return {data:{user:logged?{id:'test-user'}:null}}},async signInWithPassword(){logged=true;return {data:{}}},async signUp(){return {data:{}}},async resetPasswordForEmail(){return {}},onAuthStateChange(){},async signOut(){logged=false;return {}}},from(table){return Object.assign(Object.create(q),{table})},async rpc(){return {data:[]}}}}};` }));
  await page.route('https://challenges.cloudflare.com/**',r=>r.fulfill({contentType:'text/javascript',body:"window.turnstile={render(el,options){setTimeout(()=>options.callback('isolated-test-captcha'),0);return 1},reset(){},remove(){}};"}));
  await page.route('https://api.github.com/**',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({workflow_runs:[],artifacts:[]})}));
  await page.route('**/functions/v1/runtime-data-read',r=>r.fulfill({contentType:'application/json',status:role==='admin'?200:403,body:JSON.stringify(role==='admin'?{url:origin+'/isolated-research-report.json'}:{error:'admin required'})}));
  await page.route(origin+'/isolated-research-report.json',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({schema:1,mode:'SHADOW_ONLY',production_influence:false,auto_promote_to_prod:false,generated_at:'2026-10-16T09:17:00Z',run_number:8,completed_in_retained_history:0,historical:{status:'SHADOW_EVIDENCE_POSITIVE',windows:{holdout_matches:114},candidate:{holdout_brier:0.1946,current_holdout_brier:0.1992}},tracks:[{key:'ALL',champion:{id:'test-baseline'},challenger:{id:'test-challenger'},last_evaluation:{status:'COLLECTING_FUTURE_FIXTURES',independent_matches:112,evaluation_deadline:'2026-10-23T11:30:00Z'},history:[]}]})}));
  await page.goto(origin+'/#matches');
  await page.locator('#login-form').waitFor({state:'visible'});
  assert.equal(requests.length,0,'No runtime data before verified login');
  await page.locator('#auth-captcha-shell[data-verified="1"]').waitFor();
  await page.locator('[name=email]').fill('browser-test@example.invalid');await page.locator('[name=password]').fill('isolated-test-password');await page.locator('#login-form button').click();
  await page.locator('[data-filter="query"]').waitFor();
  assert.deepEqual(requests,['data/delivery/index.json'],'Only small match index on first render');
  await page.locator('[data-focus="all"]').click();
  await page.locator('[data-filter="query"]').fill(first.p1);
  assert(await page.locator('.match-card').count()>0);
  // Filtering preserves each tournament's expansion state. Exercise a closed
  // group explicitly, then make its card visible before testing refresh retention.
  const selectedLink=page.locator(`a[href="${hash}"]`);
  const selectedCard=page.locator('.match-card').filter({has:selectedLink}).first();
  const tournament=page.locator('.tournament-group').filter({has:selectedLink}).first();
  await tournament.evaluate(el=>el.open=false);
  await tournament.locator(':scope > summary').click();
  await selectedCard.waitFor();
  if(role==='user'){
   const previous=await page.locator('.match-card').count();
   await page.route('**/data/delivery/index.json',r=>r.abort('failed'));
   await page.locator('#refresh').click();
   await page.getByText('Nie udało się odświeżyć',{exact:true}).waitFor();
   await selectedCard.waitFor();
   assert.equal(await page.locator('.match-card').count(),previous,'A failed refresh must retain the last visible matches');
   await page.unroute('**/data/delivery/index.json');
   await page.locator('#refresh').click();
   await page.getByText('Dane wczytane',{exact:true}).waitFor();
   await selectedCard.waitFor();
  }
  const analysis=page.locator(`a[href="${hash}"]`).first();await analysis.scrollIntoViewIfNeeded();const y=await page.evaluate(()=>scrollY);
  await analysis.click();await page.locator('#detail-body').waitFor();
  assert(requests.includes(first.detail_path),'Match detail is lazy-loaded');
  for(const tab of ['stats','h2h','summary']){await page.evaluate(h=>location.hash=h,hash.replace('/summary','/'+tab));await page.locator('#detail-body').waitFor()}
  await page.locator('[data-back]').click();await page.locator('[data-filter="query"]').waitFor();
  assert.equal(await page.locator('[data-filter="query"]').inputValue(),first.p1,'Filter survives return');
  await page.waitForTimeout(100);assert(Math.abs(await page.evaluate(()=>scrollY)-y)<5,'Scroll survives return');
  await page.evaluate(()=>location.hash='#symphony');await page.locator('#symphony-market').waitFor();
  await page.evaluate(()=>location.hash='#admin/dashboard');
  if(role==='admin'){await page.getByRole('heading',{name:'Admin Control Center'}).waitFor();await page.getByRole('link',{name:'TECHNICZNE',exact:true}).click();await page.getByRole('heading',{name:'Admin Control Center'}).waitFor();assert(await page.locator('#mode-toggle').isVisible())}
  else{await page.getByText('Brak uprawnień administratora.',{exact:true}).waitFor();assert(await page.locator('#mode-toggle').isHidden())}
  if(role==='admin'){
   await page.evaluate(()=>location.hash='#admin/models');
   await page.locator('.neuron-overview').waitFor();
   await page.locator('[data-report="data/neuron_metrics.json"]').click();
   await page.locator('#report-data .report-row').first().waitFor();
   assert.equal(await page.locator('#app pre, #app code').count(),0,'Reports must render human-readable fields');
   // Real reports grow as provenance is added; exercise the public pagination
   // control instead of assuming historical metrics are in the first page.
   const more=page.locator('#report-data > .readable-report > details > .report-content > [data-report-more]');
   while(await more.count())await more.click();
   const nested=page.locator('#report-data details[data-report-node]').filter({has:page.locator('summary',{hasText:'Test historyczny'})}).last();
   await nested.locator(':scope > summary').click();
   await nested.locator('.report-row').first().waitFor();
   assert((await nested.innerText()).includes('Trafność'),'Nested model metrics expand');
   for(const route of ['dashboard','data','superbet','models']){
    await page.evaluate(route=>location.hash='#admin/'+route,route);
    await page.locator('.admin-modes').waitFor();
    for(const width of [320,412,1280]){
     await page.setViewportSize({width,height:915});
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),route+' fits '+width+'px');
    }
    if(process.env.TENIS_UI_SCREENSHOTS){
     await page.setViewportSize({width:412,height:915});
     fs.mkdirSync(process.env.TENIS_UI_SCREENSHOTS,{recursive:true});
     await page.screenshot({path:path.join(process.env.TENIS_UI_SCREENSHOTS,route+'.png')});
    }
   }
   assert(!requests.includes('data/results.json'),'Admin routes never eagerly load the full result set');
   await page.evaluate(()=>location.hash='#admin/data');await page.locator('[data-admin-match]').waitFor();
   await page.locator('[data-admin-match]').selectOption(String(first.id));await page.locator('.report-row').first().waitFor();
   await page.evaluate(()=>location.hash='#admin/evolution');await page.getByRole('heading',{name:'Rzeczywiste wyniki badań'}).waitFor();
   assert((await page.locator('.research-evidence').innerText()).includes('114'),'Research metrics come from the private report');
   for(const width of [320,412]){await page.setViewportSize({width,height:915});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Research report fits phone');}
   await page.setViewportSize({width:412,height:915});
   if(process.env.TENIS_UI_SCREENSHOTS){
    await page.screenshot({path:path.join(process.env.TENIS_UI_SCREENSHOTS,'evolution.png')});
    await page.locator('.research-evidence details summary').first().click();
    await page.locator('.research-evidence').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(process.env.TENIS_UI_SCREENSHOTS,'evolution-metrics.png')});
   }
   await page.evaluate(()=>location.hash='#start');await page.locator('.hero').waitFor();
   if(process.env.TENIS_UI_SCREENSHOTS)await page.screenshot({path:path.join(process.env.TENIS_UI_SCREENSHOTS,'start.png')});
  }
  await page.evaluate(()=>location.hash='#more');await page.getByRole('heading',{name:'Więcej',exact:true}).waitFor();
  const ineed=page.locator('a[href="#ineed"]');if(role==='user')assert.equal(await ineed.count(),0);else assert(await ineed.count()>0,'Staff entry for iNeed$');
  if(role==='user'){
   const other=index.matches.find(m=>String(m.id)!==String(first.id));
   let release;const held=new Promise(r=>release=r);
   await page.route('**/'+other.detail_path,r=>release(r));
   await page.evaluate(id=>location.hash='#match/'+encodeURIComponent(id)+'/summary',String(other.id));
   const request=await held;await page.getByText('Wczytuję szczegóły…',{exact:true}).waitFor();
   await request.fulfill({status:503,body:'isolated outage'});
   await page.locator('[data-retry-route]').waitFor();
   await page.unroute('**/'+other.detail_path);await page.locator('[data-retry-route]').click();await page.locator('#detail-body').waitFor();
   await page.evaluate(()=>location.hash='#matches');await page.locator('[data-filter="query"]').waitFor();
   await page.route('**/data/delivery/index.json',r=>r.fulfill({status:503,body:'isolated outage'}));
   await page.locator('#refresh').click();await page.getByText('Nie udało się odświeżyć',{exact:true}).waitFor();
   assert(await page.locator('.match-card').count()>0,'Last match view survives with an explicit unconfirmed-data status');
   assert(await page.locator('#data-status').evaluate(el=>el.classList.contains('is-warning')),'Retained data must never be presented as refreshed');
   assert(!requests.includes('data/results.json'),'No heavy fallback on index failure');
   await page.unroute('**/data/delivery/index.json');
   await page.route('**/data/delivery/index.json',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({...index,matches:[],symphony_count:0})}));
   await page.locator('#refresh').click();await page.getByText('Brak meczów dla tych filtrów.',{exact:false}).waitFor();
   await page.unroute('**/data/delivery/index.json');
   await page.locator('#refresh').click();await page.getByText('Dane wczytane',{exact:true}).waitFor();await selectedCard.waitFor();
   await page.route('**/data/delivery/index.json',r=>r.fulfill({status:503,body:'new account outage'}));
   await page.evaluate(()=>{window.TenisAccount.user.id='second-test-user';window.dispatchEvent(new Event('tenis-auth'))});
   assert.equal(await page.locator('.match-card').count(),0,'Switching account clears the previous account view immediately');
   await page.getByText('Nie udało się odświeżyć',{exact:true}).waitFor();
   assert.equal(await page.locator('.match-card').count(),0,'A failed new-account load never restores previous-account data');
  }
  assert.deepEqual(errors,[],role+' browser errors');
  results.push({role,passed:true,first_render_json_bytes:fs.statSync(root+'/data/delivery/index.json').size});await context.close();
 }
 console.log(JSON.stringify({engine:'Chromium',viewport:'412x915',auth:'isolated mock transport, real account.js and DOM',results},null,2));
}finally{await browser.close();await new Promise(r=>server.close(r))}
