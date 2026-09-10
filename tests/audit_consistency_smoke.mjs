import fs from 'node:fs';

const index = fs.readFileSync('frontend/index.html', 'utf8');
const style = fs.readFileSync('frontend/style.css', 'utf8');
const polish = fs.readFileSync('frontend/product-polish.js', 'utf8');
const symphony = fs.readFileSync('frontend/symphony2.js', 'utf8');

function check(ok, message) {
  if (!ok) throw new Error(message);
  console.log(`PASS  ${message}`);
}

check(/src="symphony2\.js(?:\?[^\"]*)?"/.test(index), 'Symphony 2 runtime is bootstrapped');
check(/href="style\.css(?:\?[^\"]*)?"/.test(index), 'Canonical product styles are bootstrapped');
check((index.match(/rel="stylesheet"/g)||[]).length === 1, 'Exactly one linked stylesheet owns the product');
check(/src="product-polish\.js(?:\?[^\"]*)?"/.test(index), 'Role-aware product polish is bootstrapped');
check(
  polish.includes('.s2-hub') && polish.includes('.s2-shell') && polish.includes('.s2-card'),
  'Current product polish styles the Symphony hub and cards'
);
check(
  polish.includes('data-admin-route="admin"') &&
  polish.includes('data-admin-route="stats"') &&
  polish.includes('data-switch-user') &&
  polish.includes("role()==='admin'"),
  'Admin and user product surfaces are explicitly separated'
);
check(
  polish.includes('renderAdminStats') && polish.includes('statsData') && polish.includes('by_market'),
  'Admin model statistics use the existing analytics dataset'
);
check(
  polish.includes('renderCleanHistory') && polish.includes('historyRows'),
  'History is rendered through the polished product surface'
);
check(!index.includes('symphony2.css') && !fs.existsSync('frontend/symphony2.css'), 'Retired Symphony stylesheet stays absent');
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
