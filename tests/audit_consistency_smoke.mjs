import fs from 'node:fs';

const index = fs.readFileSync('frontend/index.html', 'utf8');
const symphony = fs.readFileSync('frontend/symphony2.js', 'utf8');

function check(ok, message) {
  if (!ok) throw new Error(message);
  console.log(`PASS  ${message}`);
}

check(index.includes('src="symphony2.js"'), 'Symphony 2 runtime is bootstrapped');
check(index.includes('href="symphony2.css"'), 'Symphony 2 styles are bootstrapped');
for (const stale of [
  'symphony2.js?v=210',
  'symphony2.js?v=220',
  'symphony2.css?v=210',
  'symphony2.css?v=220',
  'symphony2-v210',
  'symphony2-v220',
]) {
  check(!index.includes(stale), `stale Symphony pin is absent: ${stale}`);
}
check(!index.includes('scenario-studio-v82a.js'), 'retired Scenario Studio is not bootstrapped');
check(!index.includes('scenario-runtime-v202.js'), 'retired Scenario runtime is not bootstrapped');
check(!index.includes('generator-quality-v888.js'), 'retired generator quality layer is not bootstrapped');
check(!index.includes('scenario-dynamic-v84d3.js'), 'retired Scenario dynamic audit is not bootstrapped');
check(symphony.includes('symphony2_current.json'), 'Symphony 2 reads its dedicated current feed');
check(symphony.includes('SUPERBET') || symphony.includes('Superbet'), 'Symphony 2 exposes operator-first context');

console.log('Current architecture audit smoke: PASS');
