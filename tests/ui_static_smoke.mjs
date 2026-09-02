import fs from 'node:fs';
const read=p=>fs.readFileSync(p,'utf8');
const ui=read('frontend/project-ui.js');
const shadow=read('frontend/shadow-lab-v78e6.js');
const restore=read('frontend/navigation-tools.js');
const css=read('frontend/project-ui.css');
const index=read('frontend/index.html');
const sw=read('frontend/sw.js');
const meta=read('frontend/app-meta.js');
const clean=read('frontend/clean-core-v80.js');
const app=read('frontend/app.js');

const checks=[
 ['Clean Core v8 is loaded after Adaptive Learning',/adaptive-learning-v79\.js[\s\S]{0,700}clean-core-v80\.js/.test(index)],
 ['Clean Core CSS v8 is loaded',index.includes('clean-core-v80.css')],
 ['Old History v7.3.2 is not loaded',!index.includes('history-days-v732.js')&&!index.includes('history-days-v732.css')],
 ['Post-Match Center exists',clean.includes('RAPORT PO MECZU')&&clean.includes('Co nie weszło')&&clean.includes('Modele — wynik tego meczu')],
 ['Adaptive review is rendered directly',clean.includes('adaptive_review_v79')&&clean.includes('Dlaczego model się pomylił')],
 ['Specialist learning is visible',clean.includes('learning_signals_v79b')&&clean.includes('learning-only')],
 ['History cards open a dedicated report',clean.includes('data-v80-history-open')&&clean.includes('openPostMatch')],
 ['Header has no old hardcoded v7.8D override',!ui.includes("Tenis AI v7.8D · Calibration Guard")],
 ['Central app metadata is v8.0.1',meta.includes("appVersion: 'v8.0.1'")&&meta.includes("cacheVersion: 'v801'")],
 ['PWA registration is v801',app.includes("serviceWorker.register('sw.js?v=801')")],
 ['PWA registration actively checks update',app.includes(".then(r=>r.update())")],
 ['PWA cache is v84b',/const CACHE\s*=\s*['"]tenis-ai-v84b-[0-9a-z._-]+['"]/i.test(sw)],
 ['Dynamic JSON cache is canonical',sw.includes('canonicalDataRequest')&&sw.includes("url.pathname.includes('/data/')")],
 ['No old fragile cache.addAll(ASSETS)',!sw.includes('cache.addAll(ASSETS)')],
 ['Supabase version is pinned',/@supabase\/supabase-js@2\.112\.3/.test(index)],
 ['Shadow button remains available',/data-p751-nav="shadow"[\s\S]{0,120}Odrzucone/.test(ui)],
 ['Main cards remain semantic containers',!/<button[^>]*class=["'][^"']*p751-match-card/.test(ui)],
 ['No old 1.2 second UI refresh loop',!restore.includes('setInterval(refresh,1200)')],
 ['Desktop responsive rules still exist',css.includes('v7.8E9 DESKTOP RESPONSIVE')||css.includes('v7.8E10')],
 ['Shadow cards remain semantic containers',!/<button[^>]*class=["'][^"']*p751-match-card/.test(shadow)]
];
let failed=0;
for(const [name,ok] of checks){console.log(`${ok?'PASS':'FAIL'}  ${name}`);if(!ok)failed++}
if(failed){console.error(`\n${failed} smoke check(s) failed.`);process.exit(1)}
console.log('\nUI smoke v8: PASS');
