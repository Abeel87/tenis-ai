/* UI assets only. Data and authenticated requests always go to the network. */
const CACHE='tenis-ai-mobile-presentation-20260910';
const CORE=['./','index.html','style.css','app.js','account.js','presentation-data.js','player-avatars.js','manifest.webmanifest','favicon.png','brand-symbol.png'];
self.addEventListener('install',event=>{self.skipWaiting();event.waitUntil(caches.open(CACHE).then(cache=>Promise.allSettled(CORE.map(x=>cache.add(x)))))});
self.addEventListener('activate',event=>{event.waitUntil((async()=>{await Promise.all((await caches.keys()).filter(k=>k.startsWith('tenis-ai-')&&k!==CACHE).map(k=>caches.delete(k)));await self.clients.claim()})())});
self.addEventListener('fetch',event=>{const r=event.request,u=new URL(r.url);if(r.method!=='GET'||u.origin!==self.location.origin||u.pathname.includes('/data/')||r.headers.has('Authorization'))return;event.respondWith((async()=>{const cache=await caches.open(CACHE);try{const response=await fetch(r);if(response.ok)await cache.put(r,response.clone());return response}catch{return await cache.match(r)||(r.mode==='navigate'?await cache.match('index.html'):null)||Response.error()}})())});
