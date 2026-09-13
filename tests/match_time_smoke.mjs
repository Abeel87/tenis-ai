import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';

const require=createRequire(import.meta.url);
const time=require('../frontend/match-time.js');

const sandboxWindow={
  TENIS_AI_MATCH_TIME:time,
  TENIS_AI_MODEL_API:{signals:()=>[]}
};
vm.runInNewContext(
  fs.readFileSync('frontend/presentation-data.js','utf8'),
  {window:sandboxWindow,URL,Date,Map,Set,Object,Array,String,Number,Math,JSON,Error,fetch:()=>{throw new Error('unexpected fetch')}}
);

const now=Date.parse('2026-09-13T11:57:00Z'); // 13:57 Europe/Warsaw
const rows=[
  {id:'stale',scheduled_time:'2026-09-13T06:30:00Z',feed_status:'upcoming'}, // 08:30 Warsaw
  {id:'recent',scheduled_time:'2026-09-13T11:40:00Z',feed_status:'upcoming'},
  {id:'future',scheduled_time:'2026-09-13T12:30:00Z',feed_status:'upcoming'},
  {id:'live-old-clock',scheduled_time:'2026-09-13T06:30:00Z',event_status:'Live'},
  {id:'tomorrow',scheduled_time:'2026-09-14T08:00:00Z',feed_status:'upcoming'}
];

const visible=sandboxWindow.TenisPresentation
  .filterRows(rows,{focus:'today',sort:'time'},{now})
  .map(x=>x.id)
  .sort()
  .join(',');

assert.equal(visible,'future,live-old-clock,recent');
assert.equal(time.isCurrent(rows[0],now),false,'stale scheduled fixture must expire');
assert.equal(time.isCurrent(rows[3],now),true,'explicit LIVE must stay current even after scheduled start');
assert.equal(time.cardStatus(rows[0],now).txt,'OCZEKUJE NA STATUS');

console.log('PASS: today feed expires stale scheduled fixtures and keeps explicit LIVE');
