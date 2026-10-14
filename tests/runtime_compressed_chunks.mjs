import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {gzipSync} from 'node:zlib';
import {webcrypto} from 'node:crypto';
const source=fs.readFileSync('frontend/runtime-data-transport.js','utf8');
const path='data/player_dna_prospective_validation.json';
const prefix='data/private/large/player_dna_prospective_validation/';
const original=Buffer.from('{"text":"Zażółć 🎾", "rows":[1,2,3]}');
const sha=async bytes=>Buffer.from(await webcrypto.subtle.digest('SHA-256',bytes)).toString('hex');
for(const encoding of ['base64','gzip-base64']){
 for(const corrupt of [false,true]){
  const bytes=encoding==='base64'?original:gzipSync(original);
  const manifest={format:encoding==='base64'?'exact-json-base64-chunks-v1':'exact-json-gzip-base64-chunks-v1',source_path:path,source_sha256:await sha(original),source_size_bytes:original.length,chunks:[{path:prefix+'chunks/0000.json',bytes:original.length,sha256:corrupt?'0'.repeat(64):await sha(original)}]};
  const window={TENIS_AI_SUPABASE:{url:'https://test.invalid',publishableKey:'test'},TenisAccount:{authenticated:true,client:{auth:{getSession:async()=>({data:{session:{access_token:'test'}}})}}}};
  const fetch=async(url,options)=>({ok:true,json:async()=>options?.method==='POST'?{url:JSON.parse(options.body).path}:url.endsWith('manifest.json')?manifest:{encoding,data:bytes.toString('base64')}});
  vm.runInNewContext(source,{window,fetch,crypto:webcrypto,TextDecoder,Uint8Array,Blob,DecompressionStream,atob,console,Date,Map,Set});
  const read=window.TenisRuntimeDataTransport.privateJson(path);
  if(corrupt)await assert.rejects(read,e=>e.code==='large_chunk_mismatch');
  else assert.equal(JSON.stringify(await read),JSON.stringify(JSON.parse(original)));
 }
}
console.log('compressed/legacy roundtrip and corrupt digest rejection passed');
