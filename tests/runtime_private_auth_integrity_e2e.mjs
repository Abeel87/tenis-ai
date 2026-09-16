import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';

const cfg=fs.readFileSync('frontend/supabase-config.js','utf8');
const url=cfg.match(/url:\s*"([^"]+)"/)?.[1];
const key=cfg.match(/publishableKey:\s*"([^"]+)"/)?.[1];
assert(url&&key,'Supabase public config is missing');

const people={
  user:[process.env.TENIS_E2E_USER_EMAIL,process.env.TENIS_E2E_USER_PASSWORD],
  admin:[process.env.TENIS_E2E_ADMIN_EMAIL,process.env.TENIS_E2E_ADMIN_PASSWORD],
  banned:[process.env.TENIS_E2E_BANNED_EMAIL,process.env.TENIS_E2E_BANNED_PASSWORD],
  missing:[process.env.TENIS_E2E_MISSING_PROFILE_EMAIL,process.env.TENIS_E2E_MISSING_PROFILE_PASSWORD],
};
const missing=Object.entries(people).flatMap(([name,v])=>v[0]&&v[1]?[]:[name]);
if(missing.length){
  const msg=`REAL_AUTH_E2E_NOT_RUN missing credentials for ${missing.join(', ')}`;
  if(process.env.TENIS_REQUIRE_REAL_AUTH_E2E==='1')throw Error(msg);
  console.log(msg);process.exit(0);
}

async function signIn([email,password]){
  const r=await fetch(`${url}/auth/v1/token?grant_type=password`,{
    method:'POST',headers:{apikey:key,'Content-Type':'application/json'},body:JSON.stringify({email,password})});
  const b=await r.json().catch(()=>({}));
  assert.equal(r.status,200,'Real Supabase sign-in failed');
  assert.equal(typeof b.access_token,'string','Missing real access token');
  return b.access_token;
}

async function read(token,path){
  const r=await fetch(`${url}/functions/v1/runtime-data-read`,{
    method:'POST',headers:{apikey:key,Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify({path})});
  return {status:r.status,body:await r.json().catch(()=>({}))};
}

async function verified(meta,label){
  assert.equal(typeof meta.url,'string',`${label}: signed URL missing`);
  assert.match(meta.sha256,/^[a-f0-9]{64}$/i,`${label}: invalid sha256 metadata`);
  assert.equal(Number.isInteger(meta.size_bytes),true,`${label}: invalid size metadata`);
  const r=await fetch(meta.url,{cache:'no-store'});
  assert.equal(r.status,200,`${label}: signed download failed`);
  const bytes=Buffer.from(await r.arrayBuffer());
  assert.equal(bytes.length,meta.size_bytes,`${label}: size mismatch`);
  assert.equal(createHash('sha256').update(bytes).digest('hex'),meta.sha256,`${label}: SHA-256 mismatch`);
  return bytes;
}

function json(bytes,label){
  try{return JSON.parse(bytes.toString('utf8'));}
  catch(e){throw Error(`${label}: invalid JSON: ${e.message}`);}
}

async function logout(token){
  await fetch(`${url}/auth/v1/logout`,{method:'POST',headers:{apikey:key,Authorization:`Bearer ${token}`}}).catch(()=>{});
}

const t={};
try{
  for(const [name,p] of Object.entries(people))t[name]=await signIn(p);

  const b=await read(t.user,'data/delivery/index.json');
  assert.equal(b.status,200,'Tier B must allow authenticated user');
  json(await verified(b.body,'Tier B delivery index'),'Tier B delivery index');

  assert.equal((await read(t.user,'data/results.json')).status,403,'Tier C must reject non-admin');
  const c=await read(t.admin,'data/results.json');
  assert.equal(c.status,200,'Tier C must allow admin');
  json(await verified(c.body,'Tier C results'),'Tier C results');

  assert.equal((await read(t.banned,'data/delivery/index.json')).status,403,'Banned user must be rejected');
  assert.equal((await read(t.missing,'data/delivery/index.json')).status,403,'User without profile must be rejected');

  const mr=await read(t.user,'data/private/history/manifest.json');
  assert.equal(mr.status,200,'History manifest must allow authenticated user');
  const m=json(await verified(mr.body,'History manifest'),'History manifest');
  assert.equal(m.schema,1);
  assert.equal(m.format,'json-array-chunks-v1');
  assert.equal(m.source_path,'data/history.json');
  assert.match(m.source_sha256,/^[a-f0-9]{64}$/i,'Canonical history source SHA-256 missing');
  assert.equal(Number.isInteger(m.source_size_bytes)&&m.source_size_bytes>0,true,'Canonical history source size invalid');
  assert.equal(Number.isInteger(m.entry_count)&&m.entry_count>=0,true,'History entry_count invalid');
  assert.equal(Array.isArray(m.chunks)&&m.chunks.length>0,true,'History chunks missing');

  const seen=new Set();let entries=0;
  for(const ch of m.chunks){
    assert.match(ch.path,/^data\/private\/history\/chunks\/\d{4}\.json$/,'Invalid history chunk path');
    assert.equal(seen.has(ch.path),false,`Duplicate history chunk ${ch.path}`);seen.add(ch.path);
    assert.match(ch.sha256,/^[a-f0-9]{64}$/i,`${ch.path}: invalid manifest sha256`);
    assert.equal(Number.isInteger(ch.size_bytes),true,`${ch.path}: invalid manifest size`);
    assert.equal(Number.isInteger(ch.entries)&&ch.entries>=0,true,`${ch.path}: invalid manifest entry count`);
    const cr=await read(t.user,ch.path);
    assert.equal(cr.status,200,`${ch.path}: authenticated read failed`);
    assert.equal(cr.body.sha256,ch.sha256,`${ch.path}: reader hash differs from manifest`);
    assert.equal(cr.body.size_bytes,ch.size_bytes,`${ch.path}: reader size differs from manifest`);
    const rows=json(await verified(cr.body,ch.path),ch.path);
    assert.equal(Array.isArray(rows),true,`${ch.path}: chunk is not an array`);
    assert.equal(rows.length,ch.entries,`${ch.path}: entry count differs from manifest`);
    entries+=rows.length;
  }
  assert.equal(entries,m.entry_count,'History chunk entry total differs from manifest');
  console.log(`PASS REAL_AUTH_INTEGRITY_E2E: role matrix + signed SHA/size + ${m.chunks.length} history chunks (${entries} entries)`);
}finally{
  await Promise.all(Object.values(t).map(logout));
}
