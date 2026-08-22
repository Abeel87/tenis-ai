/* Tenis AI v7.8E10 — resilient PWA cache */
const CACHE = 'tenis-ai-v78e114-ou-highlight-nav-restore';

const CORE = [
  './',
  'index.html',
  'manifest.webmanifest',
  'favicon.png',
  'icon-192.png',
  'icon-512.png'
];

self.addEventListener('install', event => {
  self.skipWaiting();

  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);

    // One missing optional asset must never kill the whole SW install.
    await Promise.allSettled(
      CORE.map(asset => cache.add(asset))
    );
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();

    await Promise.all(
      keys
        .filter(key => key.startsWith('tenis-ai-') && key !== CACHE)
        .map(key => caches.delete(key))
    );

    await self.clients.claim();
  })());
});

async function networkFirst(request){
  const cache = await caches.open(CACHE);

  try{
    const response = await fetch(request);

    if(response && response.ok){
      cache.put(request, response.clone()).catch(() => {});
    }

    return response;
  }catch(error){
    const cached = await cache.match(request);
    if(cached) return cached;
    throw error;
  }
}

self.addEventListener('fetch', event => {
  const request = event.request;

  if(request.method !== 'GET') return;

  const url = new URL(request.url);

  // Do not interfere with Supabase/CDN/other external services.
  if(url.origin !== self.location.origin) return;

  if(request.mode === 'navigate'){
    event.respondWith((async () => {
      try{
        const response = await fetch(request);
        const cache = await caches.open(CACHE);

        if(response && response.ok){
          cache.put('index.html', response.clone()).catch(() => {});
        }

        return response;
      }catch{
        const cache = await caches.open(CACHE);
        return (await cache.match('index.html')) ||
               (await cache.match('./')) ||
               Response.error();
      }
    })());
    return;
  }

  // Data, JS, CSS, images: prefer fresh network, keep last good copy offline.
  event.respondWith(networkFirst(request));
});
