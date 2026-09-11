/* UI assets only. Data and authenticated requests always go to the network. */
const CACHE='tenis-ai-mobile-history-20260912';
const CORE=[
  './','index.html','style.css','manifest.webmanifest','favicon.png','apple-touch-icon.png','icon-192.png','icon-512.png','brand-symbol.png','brand-wordmark.png',
  'supabase-config.js','multi-model.js','signal-mapping-v84d4.js','autolearn-v84.js','adaptive-prod-bridge.js','market-quality.js','model-guide.js','clean-core-v80.js','serve-props-v72.js','player-analytics.js','match-time.js','playable-ui.js','player-avatars.js','early-hold-paths.js','match-tendencies.js','performance-center.js','presentation-data.js','account.js','auth-enhancements.js','match-detail-data.js','app.js','history-ui.js','admin-users.js','ineed-loader.js','ineed.js'
];
self.addEventListener('install',event=>{self.skipWaiting();event.waitUntil(caches.open(CACHE).then(cache=>Promise.allSettled(CORE.map(x=>cache.add(x)))))});
self.addEventListener('activate',event=>{event.waitUntil((async()=>{await Promise.all((await caches.keys()).filter(k=>k.startsWith('tenis-ai-')&&k!==CACHE).map(k=>caches.delete(k)));await self.clients.claim()})())});
self.addEventListener('fetch',event=>{const r=event.request,u=new URL(r.url);if(r.method!=='GET'||u.origin!==self.location.origin||u.pathname.includes('/data/')||r.headers.has('Authorization'))return;event.respondWith((async()=>{const cache=await caches.open(CACHE);try{const response=await fetch(r);if(response.ok)await cache.put(r,response.clone());return response}catch{return await cache.match(r)||(r.mode==='navigate'?await cache.match('index.html'):null)||Response.error()}})())});
