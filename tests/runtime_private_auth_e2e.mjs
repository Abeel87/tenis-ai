import fs from 'node:fs';
import assert from 'node:assert/strict';

/*
 * REAL Auth E2E harness for runtime-data-read.
 *
 * It never fabricates JWTs and never creates or mutates users/profiles.
 * It signs in through Supabase Auth with existing account credentials, then
 * calls the deployed Edge Function with the returned real access token.
 *
 * Required environment variables:
 *   TENIS_E2E_USER_EMAIL / TENIS_E2E_USER_PASSWORD
 *   TENIS_E2E_ADMIN_EMAIL / TENIS_E2E_ADMIN_PASSWORD
 *   TENIS_E2E_BANNED_EMAIL / TENIS_E2E_BANNED_PASSWORD
 *   TENIS_E2E_MISSING_PROFILE_EMAIL / TENIS_E2E_MISSING_PROFILE_PASSWORD
 *
 * Optional:
 *   TENIS_REQUIRE_REAL_AUTH_E2E=1  -> missing credentials are a hard failure.
 */

const configSource=fs.readFileSync('frontend/supabase-config.js','utf8');
const url=configSource.match(/url:\s*"([^"]+)"/)?.[1];
const publishableKey=configSource.match(/publishableKey:\s*"([^"]+)"/)?.[1];
assert(url&&publishableKey,'Supabase public config is missing');

const personas={
  user:{email:process.env.TENIS_E2E_USER_EMAIL,password:process.env.TENIS_E2E_USER_PASSWORD},
  admin:{email:process.env.TENIS_E2E_ADMIN_EMAIL,password:process.env.TENIS_E2E_ADMIN_PASSWORD},
  banned:{email:process.env.TENIS_E2E_BANNED_EMAIL,password:process.env.TENIS_E2E_BANNED_PASSWORD},
  missing:{email:process.env.TENIS_E2E_MISSING_PROFILE_EMAIL,password:process.env.TENIS_E2E_MISSING_PROFILE_PASSWORD},
};

const missing=Object.entries(personas).flatMap(([name,p])=>[
  ...(!p.email?[`${name}.email`]:[]),
  ...(!p.password?[`${name}.password`]:[]),
]);
if(missing.length){
  const message=`REAL_AUTH_E2E_NOT_RUN missing ${missing.join(', ')}`;
  if(process.env.TENIS_REQUIRE_REAL_AUTH_E2E==='1')throw Error(message);
  console.log(message);
  process.exit(0);
}

async function signIn(persona){
  const response=await fetch(`${url}/auth/v1/token?grant_type=password`,{
    method:'POST',
    headers:{'apikey':publishableKey,'Content-Type':'application/json'},
    body:JSON.stringify({email:persona.email,password:persona.password}),
  });
  const body=await response.json().catch(()=>({}));
  assert.equal(response.status,200,'Real Supabase sign-in failed for an E2E persona');
  assert.equal(typeof body.access_token,'string','Supabase did not return a real access token');
  return body.access_token;
}

async function runtimeRead(token,path){
  const response=await fetch(`${url}/functions/v1/runtime-data-read`,{
    method:'POST',
    headers:{
      'apikey':publishableKey,
      'Authorization':`Bearer ${token}`,
      'Content-Type':'application/json',
    },
    body:JSON.stringify({path}),
  });
  const body=await response.json().catch(()=>({}));
  return {status:response.status,body};
}

async function logout(token){
  await fetch(`${url}/auth/v1/logout`,{
    method:'POST',
    headers:{'apikey':publishableKey,'Authorization':`Bearer ${token}`},
  }).catch(()=>{});
}

const tokens={};
try{
  for(const [name,persona] of Object.entries(personas))tokens[name]=await signIn(persona);

  const userTierB=await runtimeRead(tokens.user,'data/delivery/index.json');
  assert.equal(userTierB.status,200,'Tier B must be readable by a normal authenticated user');
  assert.equal(userTierB.body.path,'data/delivery/index.json');
  assert.equal(typeof userTierB.body.url,'string');

  const userTierC=await runtimeRead(tokens.user,'data/results.json');
  assert.equal(userTierC.status,403,'Tier C must reject a non-admin user');

  const adminTierC=await runtimeRead(tokens.admin,'data/results.json');
  assert.equal(adminTierC.status,200,'Tier C must be readable by admin');
  assert.equal(adminTierC.body.path,'data/results.json');
  assert.equal(typeof adminTierC.body.url,'string');

  const bannedTierB=await runtimeRead(tokens.banned,'data/delivery/index.json');
  assert.equal(bannedTierB.status,403,'Banned user must be rejected');

  const missingProfileTierB=await runtimeRead(tokens.missing,'data/delivery/index.json');
  assert.equal(missingProfileTierB.status,403,'Authenticated user without profile must be rejected');

  console.log('PASS REAL_AUTH_E2E: Tier B user OK; Tier C admin OK; Tier C non-admin/banned/missing-profile rejected');
}finally{
  await Promise.all(Object.values(tokens).map(logout));
}
