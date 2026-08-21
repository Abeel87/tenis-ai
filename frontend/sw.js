const C='tenis-ai-v771-hold-paths';
const ASSETS=[
  './','index.html','style.css','neon.css','player-search.css','player-trends-v71.css','player-analytics-v76.css','restore-v762.css','match-tendencies-v712.css','serve-props-v72.css','pbp-validation-v73.css','performance-center-v77.css','history-days-v732.css','multi-model.css','model-guide.css','account.css','registration-ux-v752.css','community.css','community-fix.css','community-hub.css','community-admin-v74.css','admin-delete-v754.css','early-hold-v7.css','early-hold-paths-v771.css','ui-v75.css','ui-v751.css','readability-v753.css',
  'app.js','player-search.js','player-trends-v71.js','player-analytics-v76.js','multi-model.js','model-guide.js','clarity-labels-v711.js','match-tendencies-v712.js','serve-props-v72.js','pbp-validation-v73.js','history-days-v732.js','account.js','community.js','community-fix.js','avatar-fix.js','community-hub.js','community-count-fix.js','community-admin-v74.js','admin-delete-v754.js','early-hold-v7.js','ui-v75.js','ui-v751.js','readability-v753.js','restore-v762.js','early-hold-paths-v771.js','performance-center-v77.js','supabase-config.js','registration-fix-v741.js','registration-ux-v752.js','market-lab-v741.js','market-lab-v741.css','manifest.webmanifest',
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
