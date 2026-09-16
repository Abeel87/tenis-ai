/* Staged frontend transport for private runtime data.
 * Default mode is public. Dual/private modes are opt-in until real Auth E2E is complete.
 */
(()=>{
'use strict';

const MODES=new Set(['public','dual','private']);
const HISTORY_PATH='data/history.json';
const HISTORY_MANIFEST='data/private/history/manifest.json';
const PATH_RE=/^data\/[A-Za-z0-9_./-]+\.json$/;
const MAX_EVENTS=30;

const telemetry={
  mode:'public',
  public_reads:0,
  private_reads:0,
  private_success:0,
  private_errors:0,
  shadow_reads:0,
  shadow_success:0,
  shadow_errors:0,
  fallback_reads:0,
  history_reconstructions:0,
  last_events:[],
};

function now(){return Date.now()}
function currentMode(){
  const value=String(window.TENIS_RUNTIME_DATA_MODE||'public').toLowerCase();
  const mode=MODES.has(value)?value:'public';
  telemetry.mode=mode;
  return mode;
}
function record(kind,path,extra={}){
  telemetry.last_events.push({at:new Date().toISOString(),kind,path,...extra});
  if(telemetry.last_events.length>MAX_EVENTS)telemetry.last_events.splice(0,telemetry.last_events.length-MAX_EVENTS);
}
function runtimeEligible(path){return typeof path==='string'&&PATH_RE.test(path)&&!path.includes('..')}
function safeMessage(error){
  const status=Number(error?.status);
  return Number.isFinite(status)?`HTTP ${status}`:String(error?.code||error?.message||'private read failed').slice(0,120);
}
async function sessionToken(){
  const account=window.TenisAccount;
  if(!account?.authenticated||!account?.client)throw Object.assign(Error('Brak aktywnej sesji aplikacji.'),{code:'auth_unavailable'});
  const {data,error}=await account.client.auth.getSession();
  const token=data?.session?.access_token;
  if(error||!token)throw Object.assign(Error('Brak aktywnego tokenu sesji.'),{code:'session_unavailable'});
  return token;
}
async function signedObject(path,token){
  if(!runtimeEligible(path))throw Object.assign(Error('Nieprawidłowa ścieżka runtime.'),{code:'invalid_path'});
  const cfg=window.TENIS_AI_SUPABASE;
  if(!cfg?.url||!cfg?.publishableKey)throw Object.assign(Error('Brak konfiguracji Supabase.'),{code:'config_unavailable'});
  const response=await fetch(`${cfg.url}/functions/v1/runtime-data-read`,{
    method:'POST',
    cache:'no-store',
    headers:{
      'Authorization':`Bearer ${token}`,
      'apikey':cfg.publishableKey,
      'Content-Type':'application/json',
    },
    body:JSON.stringify({path}),
  });
  const metadata=await response.json().catch(()=>null);
  if(!response.ok||!metadata?.url){
    const error=Error(metadata?.error||`Private runtime HTTP ${response.status}`);
    error.status=response.status;
    throw error;
  }
  const objectResponse=await fetch(metadata.url,{cache:'no-store'});
  if(!objectResponse.ok){
    const error=Error(`Signed runtime object HTTP ${objectResponse.status}`);
    error.status=objectResponse.status;
    throw error;
  }
  return {value:await objectResponse.json(),metadata};
}
async function privateJson(path){
  const started=now();
  telemetry.private_reads+=1;
  try{
    const token=await sessionToken();
    if(path===HISTORY_PATH){
      const {value:manifest,metadata}=await signedObject(HISTORY_MANIFEST,token);
      if(manifest?.format!=='json-array-chunks-v1'||!Array.isArray(manifest.chunks))throw Object.assign(Error('Nieprawidłowy manifest historii.'),{code:'history_manifest_invalid'});
      const chunks=await Promise.all(manifest.chunks.map(async chunk=>{
        const chunkPath=String(chunk?.path||'');
        if(!chunkPath.startsWith('data/private/history/chunks/'))throw Object.assign(Error('Nieprawidłowa ścieżka chunka historii.'),{code:'history_chunk_invalid'});
        const {value}=await signedObject(chunkPath,token);
        if(!Array.isArray(value))throw Object.assign(Error('Nieprawidłowy chunk historii.'),{code:'history_chunk_invalid'});
        return value;
      }));
      const value=chunks.flat();
      if(Number.isInteger(manifest.entry_count)&&value.length!==manifest.entry_count)throw Object.assign(Error('Niekompletna rekonstrukcja historii.'),{code:'history_count_mismatch'});
      telemetry.history_reconstructions+=1;
      telemetry.private_success+=1;
      record('private_ok',path,{ms:now()-started,layer:metadata.layer,history_chunks:manifest.chunks.length});
      return value;
    }
    const {value,metadata}=await signedObject(path,token);
    telemetry.private_success+=1;
    record('private_ok',path,{ms:now()-started,layer:metadata.layer,size_bytes:metadata.size_bytes});
    return value;
  }catch(error){
    telemetry.private_errors+=1;
    record('private_error',path,{ms:now()-started,error:safeMessage(error)});
    throw error;
  }
}
function shadow(path){
  telemetry.shadow_reads+=1;
  privateJson(path).then(()=>{
    telemetry.shadow_success+=1;
    record('shadow_ok',path);
  }).catch(error=>{
    telemetry.shadow_errors+=1;
    record('shadow_error',path,{error:safeMessage(error)});
  });
}
async function read(path,publicReader){
  if(typeof publicReader!=='function')throw Error('Public reader is required.');
  const mode=currentMode();
  if(mode==='public'||!runtimeEligible(path)){
    telemetry.public_reads+=1;
    return publicReader();
  }
  if(mode==='dual'){
    telemetry.public_reads+=1;
    const result=await publicReader();
    if(window.TenisAccount?.authenticated)shadow(path);
    else record('shadow_skip',path,{reason:'not_authenticated'});
    return result;
  }
  try{
    return await privateJson(path);
  }catch(error){
    // Public fallback stays enabled during staged migration. It can be disabled
    // explicitly only after real Auth E2E and production observation succeed.
    if(window.TENIS_RUNTIME_ALLOW_PUBLIC_FALLBACK===false)throw error;
    telemetry.fallback_reads+=1;
    telemetry.public_reads+=1;
    record('public_fallback',path,{error:safeMessage(error)});
    return publicReader();
  }
}

window.TenisRuntimeTelemetry=telemetry;
window.TenisRuntimeDataTransport={read,privateJson,currentMode,runtimeEligible,telemetry};
})();
