const C='tenis-ai-v61-neon';
const ASSETS=[
  './','index.html','style.css','neon.css','app.js','manifest.webmanifest',
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
