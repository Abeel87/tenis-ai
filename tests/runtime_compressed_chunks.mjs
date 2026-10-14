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
const history=[{id:1,name:'Żółć 🎾',score:0,missing:null,flag:false},{id:2,values:[null,0],nested:{}}];
for(const compressed of [false,true]){
 const cases=['valid','empty','total-count','wrong-path'];
 if(compressed)cases.push('chunk-hash','inflation-overrun','invalid-bound','entry-count','wrong-encoding','truncated-gzip');
 for(const scenario of cases){
  const expectedRows=scenario==='empty'?[]:history;
  const prefix='data/private/history/';
  const chunks=await Promise.all(expectedRows.map(async(row,index)=>{const bytes=Buffer.from(JSON.stringify([row]));return {path:prefix+'chunks/'+String(index).padStart(4,'0')+'.json',sha256:await sha(bytes),size_bytes:bytes.length,entries:1}}));
  const payloads=new Map(chunks.map((chunk,index)=>{const bytes=Buffer.from(JSON.stringify([expectedRows[index]]));return [chunk.path,compressed?{encoding:'gzip-base64',data:gzipSync(bytes).toString('base64')}:[expectedRows[index]]]}));
  const manifest={format:compressed?'json-array-gzip-base64-chunks-v1':'json-array-chunks-v1',source_path:'data/history.json',entry_count:expectedRows.length,chunks};
  const expected={'total-count':'history_count_mismatch','wrong-path':'history_chunk_invalid','chunk-hash':'history_chunk_mismatch','inflation-overrun':'history_chunk_mismatch','invalid-bound':'history_chunk_invalid','entry-count':'history_count_mismatch','wrong-encoding':'history_chunk_invalid'};
  if(scenario==='total-count')manifest.entry_count++;
  if(scenario==='wrong-path')chunks[0].path=prefix+'chunks/9999.json';
  if(scenario==='chunk-hash')chunks[0].sha256='0'.repeat(64);
  if(scenario==='inflation-overrun')chunks[0].size_bytes=1;
  if(scenario==='invalid-bound')chunks[0].size_bytes=20*1024*1024+1;
  if(scenario==='entry-count')chunks[0].entries++;
  if(scenario==='wrong-encoding')payloads.get(chunks[0].path).encoding='unknown';
  if(scenario==='truncated-gzip')payloads.get(chunks[0].path).data=Buffer.from([31,139]).toString('base64');
  const window={TENIS_AI_SUPABASE:{url:'https://test.invalid',publishableKey:'test'},TenisAccount:{authenticated:true,client:{auth:{getSession:async()=>({data:{session:{access_token:'test'}}})}}}};
  const fetch=async(url,options)=>({ok:true,json:async()=>options?.method==='POST'?{url:JSON.parse(options.body).path,layer:'core'}:url.endsWith('manifest.json')?manifest:payloads.get(url)});
  vm.runInNewContext(source,{window,fetch,crypto:webcrypto,TextDecoder,Uint8Array,Blob,DecompressionStream,atob,console,Date,Map,Set});
  const read=window.TenisRuntimeDataTransport.privateJson('data/history.json');
  if(scenario==='valid'||scenario==='empty')assert.equal(JSON.stringify(await read),JSON.stringify(expectedRows));
  else if(scenario==='truncated-gzip')await assert.rejects(read);
  else await assert.rejects(read,e=>e.code===expected[scenario],`history ${compressed}: ${scenario}`);
  checked++;
 }
}
console.log(`${checked} compressed/legacy reconstruction and corruption checks passed`);
