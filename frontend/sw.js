const C='tenis-ai-v701-pbp-player-id';
const ASSETS=[
  './','index.html','style.css','neon.css','player-search.css','multi-model.css','account.css','community.css','community-fix.css','community-hub.css','early-hold-v7.css',
  'app.js','player-search.js','multi-model.js','account.js','community.js','community-fix.js','avatar-fix.js','community-hub.js','early-hold-v7.js','supabase-config.js','manifest.webmanifest',
  'brand-symbol.png','brand-wordmark.png','favicon.png',
  'apple-touch-icon.png','icon-192.png','icon-512.png'
];
self.addEventListener('install',e=>{
  self.skipWaiting();
  e.waitUntil(caches.open(C).then(c=>c.addAll(ASSETS)));
});
self.addEventListener('activate',e=>e.waitUntil(Promise.all([
  self.clients.claim(),
  caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==C).map(k=>caches.delete(k))))
])));
self.addEventListener('fetch',e=>{
  e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));
});
