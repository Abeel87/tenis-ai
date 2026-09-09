import fs from 'node:fs';
const read=p=>fs.readFileSync(p,'utf8');
const ui=read('frontend/project-ui.js');
const shadow=read('frontend/shadow-lab-v78e6.js');
const style=read('frontend/style.css');
const index=read('frontend/index.html');
const sw=read('frontend/sw.js');
const meta=read('frontend/app-meta.js');
const clean=read('frontend/clean-core-v80.js');
const app=read('frontend/app.js');

const stylesheetCount=(index.match(/rel="stylesheet"/g)||[]).length;
const legacyUi=[
  'clean-core-v80.css',
  'symphony2.css',
  'project-ui.css',
  'neon.css',
  'navigation-tools.js',
  'clarity-labels.js',
  'ui-cleanup.js',
  'project-ui-quality.js',
  'app-shell.js',
  'app-shell.css'
];

const checks=[
 ['Clean Core logic remains loaded after Adaptive Learning',/adaptive-learning-v79\.js[\s\S]{0,700}clean-core-v80\.js/.test(index)],
 ['Legacy Clean Core CSS is removed',!index.includes('clean-core-v80.css')&&!sw.includes('clean-core-v80.css')],
 ['Single canonical stylesheet is loaded',stylesheetCount===1&&index.includes('href="style.css"')],
 ['Legacy layered UI is not loaded',legacyUi.every(name=>!index.includes(name))],
 ['Old History v7.3.2 is not loaded',!index.includes('history-days-v732.js')&&!index.includes('history-days-v732.css')],
 ['Post-Match Center logic still exists',clean.includes('RAPORT PO MECZU')&&clean.includes('Co nie weszło')&&clean.includes('Modele — wynik tego meczu')],
 ['Adaptive review is still available',clean.includes('adaptive_review_v79')&&clean.includes('Dlaczego model się pomylił')],
 ['Specialist learning remains available',clean.includes('learning_signals_v79b')&&clean.includes('learning-only')],
 ['History report logic remains available',clean.includes('data-v80-history-open')&&clean.includes('openPostMatch')],
 ['Header has no old hardcoded v7.8D override',!ui.includes("Tenis AI v7.8D · Calibration Guard")],
 ['Central app metadata is v8.0.1',meta.includes("appVersion: 'v8.0.1'")&&meta.includes("cacheVersion: 'v801'")],
 ['PWA registration is v801',app.includes("serviceWorker.register('sw.js?v=801')")],
 ['PWA registration actively checks update',app.includes(".then(r=>r.update())")],
 ['PWA cache is v84b',/const CACHE\s*=\s*['"]tenis-ai-v84b-[0-9a-z._-]+['"]/i.test(sw)],
 ['PWA cache owns canonical style only',sw.includes("'style.css'")&&!sw.includes('symphony2.css')],
 ['Dynamic JSON cache is canonical',sw.includes('canonicalDataRequest')&&sw.includes("url.pathname.includes('/data/')")],
 ['No old fragile cache.addAll(ASSETS)',!sw.includes('cache.addAll(ASSETS)')],
 ['Supabase version is pinned',/@supabase\/supabase-js@2\.112\.3/.test(index)],
 ['Shadow Lab remains available without legacy bottom nav',index.includes('shadow-lab-v78e6.js')&&shadow.includes('window.TENIS_AI_SHADOW_LAB')&&shadow.includes('open:openShadow')&&!ui.includes('p751-bottom-nav')],
 ['Main cards remain semantic containers',!/<button[^>]*class=["'][^"']*p751-match-card/.test(ui)],
 ['Canonical responsive rules exist',style.includes('@media(max-width:760px)')&&style.includes('.match-grid')],
 ['Match detail is in-app, not legacy overlay',ui.includes("app.innerHTML=detailHtml(m)")&&!ui.includes('p751-match-overlay')],
 ['Shadow cards remain semantic containers',!/<button[^>]*class=["'][^"']*p751-match-card/.test(shadow)]
];

let failed=0;
for(const [name,ok] of checks){console.log(`${ok?'PASS':'FAIL'}  ${name}`);if(!ok)failed++}
if(failed){console.error(`\n${failed} smoke check(s) failed.`);process.exit(1)}
console.log('\nUI smoke clean rebuild: PASS');
