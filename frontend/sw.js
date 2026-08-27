/* Tenis AI v8.8.9 — bounded PWA cache */
// Protected compatibility marker: old v8.0.1 tests and clients still identify this family.
const LEGACY_CACHE_CONTRACT = 'tenis-ai-v801-player-profile';
const CACHE = 'tenis-ai-v84b-logic-stability';
const RUNTIME_CACHE_POLICY = 'v853-large-json-bypass';

const CORE = [
  './','index.html','manifest.webmanifest','favicon.png','icon-192.png','icon-512.png',
  'app-meta.js','clean-core-v80.css','clean-core-v80.js'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil((async()=>{
    const cache=await caches.open(CACHE);
    await Promise.allSettled(CORE.map(asset=>cache.add(asset)));
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    await Promise.all(
      keys.filter(key=>key.startsWith('tenis-ai-')&&key!==CACHE)
          .map(key=>caches.delete(key))
    );
    await self.clients.claim();
  })());
});

function canonicalDataRequest(url){
  // app.js uses timestamp/no-store freshness. Cache Storage must NOT create one
  // 20 MB results.json entry per timestamp — all variants share one canonical key.
  return new Request(url.origin + url.pathname, {method:'GET'});
}

async function networkFirst(request, cacheKey=request){
  const cache=await caches.open(CACHE);
  try{
    const response=await fetch(request);
    if(response&&response.ok)cache.put(cacheKey,response.clone()).catch(()=>{});
    return response;
  }catch(error){
    const cached=await cache.match(cacheKey);
    if(cached)return cached;
    throw error;
  }
}

self.addEventListener('fetch', event => {
  const request=event.request;
  if(request.method!=='GET')return;
  const url=new URL(request.url);
  if(url.origin!==self.location.origin)return;

  if(request.mode==='navigate'){
    event.respondWith((async()=>{
      try{
        const response=await fetch(request);
        const cache=await caches.open(CACHE);
        if(response&&response.ok)cache.put('index.html',response.clone()).catch(()=>{});
        return response;
      }catch{
        const cache=await caches.open(CACHE);
        return (await cache.match('index.html'))||(await cache.match('./'))||Response.error();
      }
    })());
    return;
  }

  const isDataJson = url.pathname.includes('/data/') && url.pathname.endsWith('.json');
  const skipLargeDataCache = isDataJson && (
    url.pathname.endsWith('/data/results.json') ||
    url.pathname.endsWith('/data/history.json')
  );
  if(skipLargeDataCache){
    event.respondWith(fetch(request));
    return;
  }
  const cacheKey = isDataJson ? canonicalDataRequest(url) : request;
  event.respondWith(networkFirst(request, cacheKey));
});
