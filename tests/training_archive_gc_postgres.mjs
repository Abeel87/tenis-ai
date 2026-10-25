// Real PostgreSQL SQL/PLpgSQL through an isolated, in-memory PGlite database.
// Storage here is a metadata fixture. No network, production DB or files are deleted.
import assert from 'node:assert/strict';
import { before, after, beforeEach, afterEach, test } from 'node:test';
import { readFileSync } from 'node:fs';
import { PGlite } from '@electric-sql/pglite';

const root = new URL('../', import.meta.url);
const read = path => readFileSync(new URL(path, root), 'utf8');
const migration = 'supabase/migrations/20261025224109_training_archive_gc_query_plan.sql';
const oldObserve = read('supabase/migrations/20260916140500_training_archive_retention_observe_returning_fix.sql');
const oldPrepare = read('supabase/migrations/20260922203000_training_archive_gc_apply.sql');
const newSQL = read(migration);
const bucket = 'tenis-ai-training-archive-private';
const sha = n => n.toString(16).padStart(64, '0');
const uuid = n => `00000000-0000-0000-0000-${n.toString(16).padStart(12, '0')}`;
const path = n => `objects/${sha(n).slice(0, 2)}/${sha(n)}`;
let db;
let beforeACL;

async function rows(sql, args = []) { return (await db.query(sql, args)).rows; }
async function scalar(sql, args = []) { return Object.values((await rows(sql, args))[0])[0]; }
async function object(n, physical = 100) {
  await db.query('insert into public.training_archive_objects(sha256,storage_path,size_bytes) values ($1,$2,100)', [sha(n),path(n)]);
  if (physical !== null) await db.query('insert into storage.objects(bucket_id,name,metadata) values ($1,$2,$3)', [bucket,path(n),{size:physical}]);
}
async function manifest(n, age, status = 'complete') {
  await db.query(`insert into public.training_archive_manifests
    (manifest_id,archive_run_id,archive_run_attempt,source_sha,source_workflow,inventory_schema_version,
     expected_files,expected_bytes,expected_unique_objects,expected_unique_bytes,status,created_at)
    values ($1,$2,1,repeat('a',40),'test',1,1,100,1,100,$3,now()-make_interval(hours=>$4))`, [uuid(n),n,status,age]);
}
async function entry(m, o, name = `item${o}.json`) {
  await db.query(`insert into public.training_archive_entries
    (manifest_id,logical_path,object_sha256,object_class,provider,size_bytes)
    values ($1,$2,$3,'pbp_state','fixture',100)`, [uuid(m),name,sha(o)]);
}
async function pin(m, released = false) {
  await db.query(`insert into public.training_archive_manifest_pins(pin_key,manifest_id,released_at)
    values ($1,$2,case when $3 then now() else null end)`, [`pin${m}`,uuid(m),released]);
}
async function observe(hours = 168) { return rows('select * from public.training_archive_retention_observe(2,$1)', [hours]); }
async function ageCandidates(ns, grace = "now()-interval '1 hour'") {
  await db.query(`update public.training_archive_gc_candidates set first_eligible_at=now()-interval '10 days',
    last_eligible_at=now(), grace_until=${grace} where sha256=any($1::text[])`, [ns.map(sha)]);
}
async function prepare(run = 9001, limit = 100) {
  return (await rows('select * from public.training_archive_gc_prepare($1,1,repeat(\'a\',40),2,168,$2)', [run,limit]))[0];
}
async function claim(apply, n) { return (await rows('select * from public.training_archive_gc_claim_object($1,$2)', [apply,sha(n)]))[0].state; }
async function finalize(apply, n) { return scalar('select public.training_archive_gc_finalize_object($1,$2)', [apply,sha(n)]); }
async function baseline() {
  for (let n=1;n<=4;n++) { await object(n); await manifest(n, (5-n)*24); await entry(n,n); }
}
async function acl() {
  return rows(`select proname,proconfig,proacl::text,prosecdef,
    has_function_privilege('anon',oid,'execute') as anon,
    has_function_privilege('authenticated',oid,'execute') as authenticated,
    has_function_privilege('service_role',oid,'execute') as service
    from pg_proc where pronamespace='public'::regnamespace and proname in
    ('training_archive_retention_observe','training_archive_gc_prepare') order by proname`);
}

before(async () => {
  db = await PGlite.create();
  await db.exec(`create role anon; create role authenticated; create role service_role bypassrls;
    create schema storage;
    create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
    create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text,name text,metadata jsonb,unique(bucket_id,name));`);
  for (const name of [
    '20260916095147_durable_training_archive',
    '20260916133500_training_archive_retention_preview',
    '20260916135000_training_archive_retention_grace_audit',
    '20260916140500_training_archive_retention_observe_returning_fix',
    '20260916141500_training_archive_retention_acl_hardening',
    '20260922203000_training_archive_gc_apply',
    '20260923083000_training_archive_observer_timeout',
    '20260924055625_training_archive_gc_prepare_timeout',
    '20260924085122_training_archive_abandoned_manifests',
  ]) await db.exec(read(`supabase/migrations/${name}.sql`));
  beforeACL = await acl();
  await db.exec(newSQL);
});
beforeEach(async () => { await db.exec('begin'); });
afterEach(async () => { await db.exec('rollback'); });
after(async () => { await db?.close(); });

test('migration preserves service-only execution, fixed search paths and bounded timeouts', async () => {
  const actual = await acl();
  assert.deepEqual(actual,beforeACL);
  for (const f of actual) {
    assert.equal(f.anon,false); assert.equal(f.authenticated,false); assert.equal(f.service,true);
    assert.equal(f.prosecdef,true); assert.ok(f.proconfig.includes('statement_timeout=30s'));
  }
});

test('latest two, active pins, in-flight refs, grace and physical-size gates survive apply', async () => {
  await baseline();
  await pin(2);
  await object(5); await manifest(5,1,'staged'); await entry(5,5);
  for (const [n,physical] of [[6,100],[7,100],[8,null],[9,99],[10,100]]) await object(n,physical);
  for (let n=6;n<=12;n++) await manifest(n,500+n);
  await entry(6,6); await entry(6,3); // shared newest object is retained
  await entry(7,7); await entry(8,8); await entry(9,9);
  await entry(10,5); await entry(11,2); await entry(12,10);
  await observe(); await ageCandidates([1,6,8,9]);
  const beforeProtected = await rows('select * from public.training_archive_entries where manifest_id=any($1::uuid[]) order by manifest_id,logical_path', [[2,3,4,5].map(uuid)]);
  const result = await prepare();
  assert.equal(result.expired_manifests,4); // 1,6 and two manifests sharing protected objects
  assert.equal(result.planned_objects,2); assert.equal(Number(result.planned_bytes),200);
  assert.deepEqual(await rows('select * from public.training_archive_entries where manifest_id=any($1::uuid[]) order by manifest_id,logical_path', [[2,3,4,5].map(uuid)]),beforeProtected);
  assert.deepEqual((await rows("select manifest_id from public.training_archive_manifests where status='expired' order by manifest_id")).map(x=>x.manifest_id),[1,6,10,11].map(uuid));
  assert.deepEqual((await rows('select sha256 from public.training_archive_gc_apply_objects order by sha256')).map(x=>x.sha256),[1,6].map(sha));
  assert.equal(Number(await scalar('select count(*) from storage.objects')),9); // prepare does not remove physical objects
});

test('a shared object is never planned while any unexpired manifest still references it', async () => {
  await baseline(); await object(5); await manifest(5,200); await entry(5,1); await entry(5,5);
  await observe(); await ageCandidates([1,2]);
  const result=await prepare();
  assert.equal(result.expired_manifests,2); assert.equal(result.planned_objects,1);
  assert.equal(await scalar('select sha256 from public.training_archive_gc_apply_objects'),sha(2));
  assert.equal(await scalar('select status from public.training_archive_manifests where manifest_id=$1',[uuid(5)]),'complete');
});

test('exact 168h boundary passes, future grace blocks, reacquired eligibility restarts the clock', async () => {
  await baseline(); await observe();
  await ageCandidates([1], 'now()'); await ageCandidates([2], "now()+interval '1 microsecond'");
  assert.equal((await prepare()).planned_objects,1);
  assert.equal(await scalar('select sha256 from public.training_archive_gc_apply_objects'),sha(1));
  await pin(2); await observe();
  assert.equal(await scalar('select current_eligible from public.training_archive_gc_candidates where sha256=$1',[sha(2)]),false);
  await db.query('update public.training_archive_manifest_pins set released_at=clock_timestamp() where manifest_id=$1',[uuid(2)]);
  await observe();
  assert.equal(await scalar("select grace_until >= first_eligible_at+interval '168 hours' and first_eligible_at >= now() from public.training_archive_gc_candidates where sha256=$1",[sha(2)]),true);
  await observe(240); const extended=await scalar('select grace_until::text from public.training_archive_gc_candidates where sha256=$1',[sha(2)]);
  await observe(168); assert.equal(await scalar('select grace_until::text from public.training_archive_gc_candidates where sha256=$1',[sha(2)]),extended);
});

test('resume uses the existing batch and rechecks references acquired after prepare', async () => {
  await baseline(); await observe(); await ageCandidates([1,2]);
  const p=await prepare(); const again=await prepare(9002); assert.equal(p.apply_id,again.apply_id);
  await manifest(5,1,'staged'); await entry(5,1);
  assert.equal(await claim(p.apply_id,1),'referenced');
  assert.equal(await scalar("select public.training_archive_gc_skip_object($1,$2,'referenced')",[p.apply_id,sha(1)]),true);
  assert.equal(await finalize(p.apply_id,1),false);
  assert.equal(Number(await scalar('select count(*) from storage.objects')),4);
});

test('unexpected absence and size drift fail closed; recorded removal resumes idempotently', async () => {
  await baseline(); await observe(); await ageCandidates([1,2]); const p=await prepare();
  await db.query('delete from storage.objects where name=$1',[path(1)]);
  assert.equal(await claim(p.apply_id,1),'missing_unexpected'); assert.equal(await finalize(p.apply_id,1),false);
  await db.query('update storage.objects set metadata=$1 where name=$2',[{size:99},path(2)]);
  assert.equal(await claim(p.apply_id,2),'size_mismatch');
  await db.query('update storage.objects set metadata=$1 where name=$2',[{size:100},path(2)]);
  assert.equal(await claim(p.apply_id,2),'delete');
  await db.query('delete from storage.objects where name=$1',[path(2)]); // simulated interruption after Storage.remove
  assert.equal(await claim(p.apply_id,2),'resume_finalize');
  assert.equal(await finalize(p.apply_id,2),true); assert.equal(await finalize(p.apply_id,2),true);
  assert.equal(Number(await scalar('select deleted_bytes from public.training_archive_gc_apply_audit where apply_id=$1',[p.apply_id])),100);
  assert.equal(await scalar('select public.training_archive_gc_finish_apply($1)',[p.apply_id]),'partial');
});

test('bounded batches make progress without duplicating removals', async () => {
  await baseline(); for(let n=5;n<=7;n++) await object(n);
  await observe(); await ageCandidates([1,2,5,6,7]);
  let total=0;
  for(let run=9001;run<=9003;run++) {
    const p=await prepare(run,2); assert.ok(p.planned_objects<=2);
    const plan=await rows('select sha256,storage_path from public.training_archive_gc_apply_objects where apply_id=$1',[p.apply_id]);
    for(const o of plan) {
      const n=parseInt(o.sha256,16); assert.equal(await claim(p.apply_id,n),'delete');
      await db.query('delete from storage.objects where name=$1',[o.storage_path]);
      assert.equal(await finalize(p.apply_id,n),true); total++;
    }
    assert.equal(await scalar('select public.training_archive_gc_finish_apply($1)',[p.apply_id]),'complete');
  }
  assert.equal(total,5); assert.equal((await prepare(9004,2)).planned_objects,0);
  assert.equal(Number(await scalar('select count(*) from storage.objects')),2);
});

test('an error after expiry rolls back all manifest and entry mutations', async () => {
  await baseline(); await observe(); await ageCandidates([1,2]);
  await db.exec(`create function public.test_gc_abort() returns trigger language plpgsql as $$ begin raise exception 'forced audit failure'; end $$;
    create trigger test_gc_abort before insert on public.training_archive_gc_apply_audit for each row execute function public.test_gc_abort();
    savepoint attempt`);
  await assert.rejects(prepare(),/forced audit failure/); await db.exec('rollback to savepoint attempt');
  assert.equal(Number(await scalar("select count(*) from public.training_archive_manifests where status='complete'")),4);
  assert.equal(Number(await scalar('select count(*) from public.training_archive_entries')),4);
  assert.equal(Number(await scalar('select count(*) from public.training_archive_gc_apply_objects')),0);
});

function candidateQuery(source) {
  const q=source.slice(source.indexOf('  with ranked_complete'),source.indexOf('  update public.training_archive_gc_candidates'));
  return q.replace(/  into\n[\s\S]*?  from eventual_candidates/,'  from eventual_candidates').replaceAll('p_keep_latest','2');
}
function readyQuery(source) {
  const start=source.indexOf('  with ranked_complete',source.toLowerCase().indexOf('function public.training_archive_gc_prepare'));
  return source.slice(start,source.indexOf('  v_expired :=',start)).replace(/    into v_expire_ids\s*\n/,'').replaceAll('p_keep_latest','2').replaceAll('v_now','now()');
}

test('old and optimized SQL agree across deterministic mixed retention fixtures', async () => {
  for(let seed=1;seed<=24;seed++) {
    await db.exec('savepoint fixture');
    for(let n=1;n<=20;n++) await object(n,(n+seed)%7===0?null:((n+seed)%9===0?99:100));
    for(let m=1;m<=10;m++) {
      await manifest(m,(12-m)*24,m===6?'staged':'complete');
      if((m+seed)%5===0) await pin(m,(m+seed)%2===0);
      for(let n=1;n<=20;n++) if((m*31+n*13+seed)%11<2) await entry(m,n);
    }
    await observe();
    const mature=Array.from({length:20},(_,i)=>i+1).filter(n=>(n+seed)%3!==0);
    await ageCandidates(mature);
    const col='(shas,objects,bytes,complete,pins,pinned,retained,expirable)';
    const original=candidateQuery(oldObserve).trim().replace(/;$/,'');
    const optimized=candidateQuery(newSQL).trim().replace(/;$/,'');
    assert.equal(await scalar(`with a${col} as (${original}),b${col} as (${optimized}) select to_jsonb(a)=to_jsonb(b) from a,b`),true,`candidate seed ${seed}`);
    assert.deepEqual(await rows(readyQuery(newSQL)),await rows(readyQuery(oldPrepare)),`expiry seed ${seed}`);
    await db.exec('rollback to savepoint fixture');
  }
});

test('skewed terminal manifests use indexed entry lookups instead of full entry scans', async () => {
  await baseline();
  await db.exec(`insert into public.training_archive_manifests
    (manifest_id,archive_run_id,archive_run_attempt,source_sha,source_workflow,inventory_schema_version,
     expected_files,expected_bytes,expected_unique_objects,expected_unique_bytes,status,expired_at)
    select ('00000000-0000-0000-0000-'||lpad(to_hex(i),12,'0'))::uuid,i,1,repeat('a',40),'test',1,1,100,1,100,'expired',now()
    from generate_series(100,211) i;
    insert into public.training_archive_manifests
    (manifest_id,archive_run_id,archive_run_attempt,source_sha,source_workflow,inventory_schema_version,
     expected_files,expected_bytes,expected_unique_objects,expected_unique_bytes,status,created_at)
    select ('00000000-0000-0000-0000-'||lpad(to_hex(i),12,'0'))::uuid,i,1,repeat('a',40),'test',1,1,100,1,100,'complete',now()-interval '10 days'
    from generate_series(10,79) i;
    insert into public.training_archive_objects(sha256,storage_path,size_bytes)
    select lpad(to_hex(i),64,'0'),'objects/00/'||lpad(to_hex(i),64,'0'),100 from generate_series(10,2009) i;
    insert into public.training_archive_entries(manifest_id,logical_path,object_sha256,object_class,provider,size_bytes)
    select ('00000000-0000-0000-0000-'||lpad(to_hex(10+i%70),12,'0'))::uuid,
      'bulk/'||i||'.json',lpad(to_hex(10+i%2000),64,'0'),'pbp_state','fixture',100 from generate_series(1,100000) i;
    analyze public.training_archive_manifests; analyze public.training_archive_entries; analyze public.training_archive_objects;`);
  await observe(); await ageCandidates([1,2]);
  const entryScans=[];
  function visit(p) { if(p['Relation Name']==='training_archive_entries') entryScans.push(p); for(const child of p.Plans||[]) visit(child); }
  for(const query of [candidateQuery(newSQL),readyQuery(newSQL)]) {
    const plan=await scalar('explain (format json) '+query); visit(plan[0].Plan);
  }
  assert.ok(entryScans.length>0);
  assert.equal(entryScans.filter(p=>p['Node Type']==='Seq Scan').length,0,JSON.stringify(entryScans));
});
