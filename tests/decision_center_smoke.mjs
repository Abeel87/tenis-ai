import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

globalThis.window = {
  TENIS_AI_MODEL_API: {
    signalsFor() {
      return [];
    }
  }
};
globalThis.document = {
  addEventListener() {},
  querySelector() {
    return null;
  },
  querySelectorAll() {
    return [];
  }
};
globalThis.setTimeout = () => 0;

vm.runInThisContext(fs.readFileSync('frontend/model-guide.js', 'utf8'));

const center = window.TENIS_AI_DECISION_CENTER_V87;
assert.ok(center, 'Decision Center API should be exported');

const match = {
  p1: 'Alpha',
  p2: 'Beta',
  match_win: {Alpha: 60, Beta: 40},
  adaptive_learning_v79: {mode: 'PROD', status: 'ACTIVE', signals: []},
  autolearn_v84: {
    signals: [
      {
        market: 'match_win',
        pick: 'Alpha',
        current: 61,
        catboost: 63,
        tabpfn: 62,
        ensemble: 64,
        ensemble_raw: 64,
        raw_score: 64,
        final_score: 66.5,
        adaptive_delta_pp: 2.5,
        adaptive_prod_v79: {
          mode: 'PROD',
          status: 'EARLY',
          applied: true,
          cap_pp: 2.5,
          raw_score: 64,
          final_score: 66.5,
          delta_pp: 2.5,
          similar_n: 12
        }
      },
      {
        market: 'match_win',
        pick: 'Beta',
        current: 39,
        catboost: 37,
        tabpfn: 38,
        ensemble: 36,
        ensemble_raw: 36,
        raw_score: 36,
        final_score: 33.5,
        adaptive_delta_pp: -2.5,
        adaptive_prod_v79: {
          mode: 'PROD',
          status: 'EARLY',
          applied: true,
          cap_pp: 2.5,
          raw_score: 36,
          final_score: 33.5,
          delta_pp: -2.5,
          similar_n: 12
        }
      }
    ]
  }
};

const rows = center.buildRows(match);
const alpha = rows.find(row => row.market === 'match_win' && row.pick === 'Alpha');
assert.ok(alpha, 'match winner market should be adapted into a card row');

const info = center.adaptiveInfo(alpha, match);
assert.equal(info.raw, 64, 'RAW must come from ensemble_raw');
assert.equal(info.final, 66.5, 'FINAL must come from backend final_score');
assert.equal(info.delta, 2.5, 'delta must be read from backend');
assert.equal(center.finalScore(alpha, match, {adaptive: [], consensus: []}), 66.5);

const top = center.topRows(rows, match, {adaptive: [], early: [], serve: [], form: [], surface: [], consensus: []});
assert.equal(top[0].pick, 'Alpha', 'Top mode should rank by backend FINAL');

const view = center.decisionCenter(match).html;
for (const marker of [
  'Centrum Decyzji Meczu',
  'data-dc-mode="top"',
  'data-dc-mode="all"',
  'data-dc-mode="pro"',
  'type="search"',
  'Accuracy Lab v8.6 · SHADOW'
]) {
  assert.ok(view.includes(marker), 'missing UI marker: ' + marker);
}
assert.ok(!view.includes('<table'), 'wide table must not return');

const legacyMatch = structuredClone(match);
legacyMatch.adaptive_learning_v79.mode = 'shadow';
const legacyView = center.decisionCenter(legacyMatch).html;
assert.ok(legacyView.includes('Adaptive PROD · ACTIVE · SYNC'), 'old records should fail safe to controlled PROD sync state');
assert.ok(!legacyView.includes('Adaptive SHADOW'), 'Adaptive must not return to a SHADOW badge');

console.log('Decision Center runtime smoke: PASS');

const checkpoints = structuredClone(match);
checkpoints.game_states = {'6': {'4:2':30, '3:3':50, '2:4':20}};
checkpoints.autolearn_v84.signals.push(
  {market:'game_state', checkpoint:6, key:'state|6|3:3',pick:'3:3',ensemble:20,final_score:16.4},
  {market:'game_state', checkpoint:6, key:'state|6|4:2',pick:'4:2',ensemble:28,final_score:25},
  {market:'game_state', checkpoint:4, key:'state|4|3:1',pick:'3:1',ensemble:90,final_score:90}
);
const stateRows = center.buildRows(checkpoints).filter(r=>r.market==='state6');
assert.equal(center.finalScore(stateRows.find(r=>r.pick==='3:3'), checkpoints, {}),16.4);
assert.equal(center.finalScore(stateRows.find(r=>r.pick==='4:2'), checkpoints, {}),25);
assert.equal(center.finalScore(stateRows.find(r=>r.pick==='2:4'), checkpoints, {}),null);
assert.ok(!stateRows.some(r=>r.pick==='p1_lead'), 'exact score must not masquerade as all leads');

const mixed = structuredClone(match);
mixed.match_win.Alpha = 99;
mixed.autolearn_v84.signals = mixed.autolearn_v84.signals.filter(s=>s.pick==='Beta');
mixed.match_over_under = {'18.5':{over:85,under:15}};
mixed.autolearn_v84.signals.push({market:'match_total',line:18.5,pick:'over',ensemble:80,final_score:76.4});
const ranked = center.topRows(center.buildRows(mixed),mixed,{});
assert.equal(ranked[0].market,'match_total','winner must not be pinned ahead of stronger FINAL');
assert.ok(!ranked.some(r=>r.pick==='Alpha'),'base fallback must not compete with FINAL');
assert.ok(center.decisionCenter(mixed).html.includes('nie prawdopodobieństwo'));
console.log('Checkpoint mapping and FINAL-only ranking regressions: PASS');
