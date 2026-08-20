const C='tenis-ai-v65-community';
const ASSETS=[
  './','index.html','style.css','neon.css','player-search.css','multi-model.css','account.css','community.css',
  'app.js','player-search.js','multi-model.js','account.js','community.js','supabase-config.js','manifest.webmanifest',
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
