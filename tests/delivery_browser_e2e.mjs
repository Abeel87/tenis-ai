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
window.supabase={createClient(){let logged=false;const q={select(){return this},eq(){return this},is(){return this},in(){return this},order(){return this},limit(){return this},maybeSingle(){return Promise.resolve({data:null})},single(){return Promise.resolve({data:{id:'test-user',username:'Browser test',role:'${role}',banned_at:null}})},then(resolve){return Promise.resolve({data:[]}).then(resolve)}};return {auth:{async getUser(){return {data:{user:logged?{id:'test-user'}:null}}},async signInWithPassword(){logged=true;return {data:{}}},async signUp(){return {data:{}}},async resetPasswordForEmail(){return {}},onAuthStateChange(){},async signOut(){logged=false;return {}}},from(){return Object.create(q)},async rpc(){return {data:[]}}}}};` }));
  await page.route('https://challenges.cloudflare.com/**',r=>r.fulfill({contentType:'text/javascript',body:"window.turnstile={render(el,options){setTimeout(()=>options.callback('isolated-test-captcha'),0);return 1},reset(){},remove(){}};"}));
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
  await page.locator('.tournament-group').first().evaluate(el=>el.open=true);
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
   await page.locator('#refresh').click();await page.getByText('Nie wszystkie dane udało się pobrać.',{exact:false}).waitFor();
   assert.equal(await page.locator('.match-card').count(),0,'Failed refresh cannot retain stale offer cards');
   assert(!requests.includes('data/results.json'),'No heavy fallback on index failure');
   await page.unroute('**/data/delivery/index.json');
   await page.route('**/data/delivery/index.json',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({...index,matches:[],symphony_count:0})}));
   await page.locator('#refresh').click();await page.getByText('Brak meczów dla tych filtrów.',{exact:false}).waitFor();
  }
  assert.deepEqual(errors,[],role+' browser errors');
  results.push({role,passed:true,first_render_json_bytes:fs.statSync(root+'/data/delivery/index.json').size});await context.close();
 }
 console.log(JSON.stringify({engine:'Chromium',viewport:'412x915',auth:'isolated mock transport, real account.js and DOM',results},null,2));
}finally{await browser.close();await new Promise(r=>server.close(r))}
