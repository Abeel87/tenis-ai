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
// Split inside a multi-byte character: decoding must happen after reconstruction.
const split=original.indexOf(Buffer.from('🎾'))+2;
const blocks=[original.subarray(0,split),original.subarray(split)];
let checked=0;
for(const encoding of ['base64','gzip-base64']){
 const cases=['valid','chunk-hash','source-hash','source-size','wrong-path','wrong-encoding'];
 if(encoding==='gzip-base64')cases.push('inflation-overrun','invalid-bound','truncated-gzip');
 for(const scenario of cases){
  const chunks=await Promise.all(blocks.map(async(block,index)=>({path:prefix+'chunks/'+String(index).padStart(4,'0')+'.json',bytes:block.length,sha256:await sha(block)})));
  const payloads=new Map(chunks.map((chunk,index)=>[chunk.path,{encoding,data:(encoding==='base64'?blocks[index]:gzipSync(blocks[index])).toString('base64')} ]));
  const manifest={format:encoding==='base64'?'exact-json-base64-chunks-v1':'exact-json-gzip-base64-chunks-v1',source_path:path,source_sha256:await sha(original),source_size_bytes:original.length,chunks};
  const expected={
   'chunk-hash':'large_chunk_mismatch','source-hash':'large_digest_mismatch',
   'source-size':'large_count_mismatch','wrong-path':'large_chunk_invalid',
   'wrong-encoding':'large_chunk_invalid','inflation-overrun':'large_chunk_mismatch',
   'invalid-bound':'large_chunk_invalid'
  };
  if(scenario==='chunk-hash')chunks[0].sha256='0'.repeat(64);
  if(scenario==='source-hash')manifest.source_sha256='0'.repeat(64);
  if(scenario==='source-size')manifest.source_size_bytes++;
  if(scenario==='wrong-path')chunks[0].path=prefix+'chunks/9999.json';
  if(scenario==='wrong-encoding')payloads.get(chunks[0].path).encoding='unknown';
  if(scenario==='inflation-overrun')chunks[0].bytes=1;
  if(scenario==='invalid-bound')chunks[0].bytes=20*1024*1024+1;
  if(scenario==='truncated-gzip')payloads.get(chunks[0].path).data=gzipSync(blocks[0]).subarray(0,8).toString('base64');
  const window={TENIS_AI_SUPABASE:{url:'https://test.invalid',publishableKey:'test'},TenisAccount:{authenticated:true,client:{auth:{getSession:async()=>({data:{session:{access_token:'test'}}})}}}};
  const fetch=async(url,options)=>({ok:true,json:async()=>options?.method==='POST'?{url:JSON.parse(options.body).path}:url.endsWith('manifest.json')?manifest:payloads.get(url)});
  vm.runInNewContext(source,{window,fetch,crypto:webcrypto,TextDecoder,Uint8Array,Blob,DecompressionStream,atob,console,Date,Map,Set});
  const read=window.TenisRuntimeDataTransport.privateJson(path);
  if(scenario==='valid')assert.equal(JSON.stringify(await read),JSON.stringify(JSON.parse(original)));
  else if(scenario==='truncated-gzip')await assert.rejects(read);
  else await assert.rejects(read,e=>e.code===expected[scenario],`${encoding}: ${scenario}`);
  checked++;
 }
}
console.log(`${checked} compressed/legacy reconstruction and corruption checks passed`);
