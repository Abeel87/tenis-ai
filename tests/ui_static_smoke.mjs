import fs from 'node:fs';

const read = p => fs.readFileSync(p, 'utf8');

const ui = read('frontend/ui-v751.js');
const shadow = read('frontend/shadow-lab-v78e6.js');
const restore = read('frontend/restore-v762.js');
const css = read('frontend/ui-v751.css');
const index = read('frontend/index.html');
const sw = read('frontend/sw.js');

const checks = [
  [
    'Shadow button is between PBP and Model',
    /PBP OK[\s\S]{0,400}data-shadow-open[\s\S]{0,400}data-p751-models/.test(ui)
  ],
  [
    'Main match cards are semantic containers, not nested buttons',
    !/<button[^>]*class=["'][^"']*p751-match-card/.test(ui)
  ],
  [
    'Shadow cards are semantic containers, not nested buttons',
    !/<button[^>]*class=["'][^"']*p751-match-card/.test(shadow)
  ],
  [
    'No old 1.2 second UI refresh loop',
    !restore.includes('setInterval(refresh,1200)')
  ],
  [
    'No body-wide MutationObserver in restore layer',
    !/observe\(document\.body/.test(restore)
  ],
  [
    'Shadow does not observe whole document body',
    !/observe\(document\.body/.test(shadow)
  ],
  [
    'Desktop responsive rules exist',
    css.includes('v7.8E9 DESKTOP RESPONSIVE') || css.includes('v7.8E10')
  ],
  [
    'Supabase version is pinned',
    /@supabase\/supabase-js@2\.112\.3/.test(index)
  ],
  [
    'Central app metadata is loaded',
    /app-meta\.js\?v=/.test(index)
  ],
  [
    'PWA cache is E10',
    /tenis-ai-v78e\d+/i.test(sw)
  ],
  [
    'Old fragile cache.addAll(ASSETS) is gone',
    !sw.includes('cache.addAll(ASSETS)')
  ],
  [
    'Obsolete readability-v753 JS layer is not loaded',
    !index.includes('readability-v753.js')
  ],
  [
    'Main card shows signal strength plus green count',
    ui.includes('Siła sygnału') && ui.includes('zielonych')
  ],
  [
    'Bottom nav contains Shadow/Odrzucone',
    /data-p751-nav="shadow"[\s\S]{0,120}Odrzucone/.test(ui)
  ],
  [
    'Market Lab highlights OVER and UNDER independently',
    ui.includes("o>=72,u>=72") && ui.includes("rightHot?'hot':''")
  ],
  [
    'Shadow strength box reports rejected-signal count',
    shadow.includes('Odrzucone sygnały')
  ]
];

let failed = 0;

for(const [name, ok] of checks){
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}`);
  if(!ok) failed++;
}

if(failed){
  console.error(`\n${failed} smoke check(s) failed.`);
  process.exit(1);
}

console.log('\nUI smoke: PASS');
