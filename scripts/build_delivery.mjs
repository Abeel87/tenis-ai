/* Publication projection only. Reuses the existing UI readers and PLAYABLE guard. */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
export function buildDelivery(root='frontend') {
 const data=path.join(root,'data');
 const read=n=>JSON.parse(fs.readFileSync(path.join(data,n),'utf8'));
 const results=read('results.json'), symphony=read('symphony2_current.json');
 const dna=read('player_dna_current_shadow.json'),direct=read('superbet_direct_current.json'),meta=read('meta.json');
 const stamp=Math.max(...[meta.updated_at,symphony.generated_at,direct.generated_at].map(x=>Date.parse(x)||0));
 const SourceDate=class extends Date{static now(){return stamp}};
 const ctx={console:{log(){},info(){}},Date:SourceDate,Map,Set,URL,JSON,Math,Number,String,Object,Array,localStorage:{getItem(){return null}},document:{querySelector(){return null},getElementById(){return {}},addEventListener(){}},setInterval(){},setTimeout(){},addEventListener(){}};
 ctx.window=ctx;vm.createContext(ctx);
 const scripts=['multi-model.js','signal-mapping-v84d4.js','autolearn-v84.js','adaptive-prod-bridge.js','market-quality.js','model-guide.js','clean-core-v80.js','serve-props-v72.js','player-analytics.js','match-time.js','playable-ui.js','early-hold-paths.js','presentation-data.js'];
 for(const name of scripts)vm.runInContext(fs.readFileSync(path.join(root,name),'utf8'),ctx,{filename:name});
 const D=ctx.TenisPresentation,api=ctx.TENIS_AI_PLAYABLE_UI_V917;
 const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
 const pick=(o,keys)=>Object.fromEntries(keys.filter(k=>o?.[k]!==undefined).map(k=>[k,o[k]]));
 const eventKeys=['key','signal_key','selection_id','market','pick','displayPick','line','selected_line','suggested_line','checkpoint','player','extra','set_no','label','operator','operator_available','operator_line_verified','fixture_line_verified','odds','price','decimal_odds','operator_model_probability','v','source','value','unit','eventKey'];
 const contextKeys=['operator','operator_verified','status','suspended','source_generated_at','source_max_age_hours','operator_start_time'];
 const compactContext=(m,signatures)=>({...pick(m.superbet_market_v91,contextKeys),canonical_selections:(m.superbet_market_v91?.canonical_selections||[]).filter(x=>!signatures||signatures.has(api.signature(x))).map(x=>pick(x,eventKeys))});
 const out=path.join(data,'delivery');fs.rmSync(out,{recursive:true,force:true});fs.mkdirSync(path.join(out,'matches'),{recursive:true});
 const write=(name,value)=>{const bytes=JSON.stringify(value);fs.writeFileSync(path.join(out,name),bytes);return Buffer.byteLength(bytes)};
 const summaries=[],symRows=[];
 for(const m of results){
  const s=D.find(symphony.matches||[],m),events=D.allEvents(m,s),top=ctx.TENIS_AI_MODEL_API.signals(m,1)[0]||null;
  const selected=s?.compositions?.[String(s.recommended_leg_count)];
  const layer=m.symphony2_playable;
  // Keep the exact source evidence, never make PLAYABLE true from a cached boolean.
  const evidence=layer?.playable===true?{superbet_market_v91:compactContext(m,new Set((layer.signals||[]).map(api.signature))),symphony2_playable:layer}:{};
  const symEvidence=s?{id:s.id,match_key:s.match_key,recommended_leg_count:s.recommended_leg_count,compositions:selected?{[String(s.recommended_leg_count)]:{selection:(selected.selection||[]).map(x=>pick(x,eventKeys))}}:{}}:null;
  const item={...pick(m,['id','tour','tournament','surface','p1','p2','p1_id','p2_id','p1_rank','p2_rank','scheduled_time','best_of','feed_status','event_status','status','model_ready','quality','risk','exact_match_score']),p1_stats:pick(m.p1_stats,['matches','won','hold_rate']),p2_stats:pick(m.p2_stats,['matches','won','hold_rate']),...evidence,delivery_summary:true,ui_summary:{top:top?pick(top,eventKeys):null,probability:top?events.find(e=>e.source==='Model bazowy'&&api.signature(e)===api.signature(top))?.value??null:null,has_data:events.some(e=>e.value!=null),has_dna:!!m.player_intelligence_v85},playable:events.some(e=>D.availability(m,e,s,symphony.generated_at).playable),symphony_evidence:symEvidence};
  const detail={match:m,symphony:s,symphony_generated_at:symphony.generated_at,dna:D.find(dna.matches||[],m),direct:{...pick(direct,['generated_at','operator','status']),matches:(direct.matches||[]).filter(r=>D.find([r],m))}};
  const bytes=JSON.stringify(detail),file=hash(bytes)+'.json';fs.writeFileSync(path.join(out,'matches',file),bytes);item.detail_path='data/delivery/matches/'+file;
  summaries.push(item);
  if(s)symRows.push({...item,ui_events:events.map(x=>pick(x,eventKeys)),superbet_market_v91:compactContext(m),...symEvidence});
 }
 const index={schema:1,generated_at:meta.updated_at,symphony_generated_at:symphony.generated_at,symphony_count:(symphony.matches||[]).length,matches:summaries};
 const sizes={index:write('index.json',index),symphony:write('symphony.json',{generated_at:symphony.generated_at,matches:symRows}),before:fs.statSync(path.join(data,'results.json')).size+fs.statSync(path.join(data,'symphony2_current.json')).size+fs.statSync(path.join(data,'superbet_direct_current.json')).size+fs.statSync(path.join(data,'player_dna_current_shadow.json')).size+fs.statSync(path.join(data,'meta.json')).size};
 const coverage=read('history_coverage_audit_v949.json'),stats=read('symphony2_stats.json'),training=stats.training||{},calibration=training.market_calibration||{};
 write('diagnostics.json',{diagnostic_only:true,production_influence:false,coverage_generated_at:coverage.generated_at,coverage:coverage.summary,markets_generated_at:stats.generated_at,support_label_policy:'UI_ONLY: LOW <100; MEDIUM 100-999; HIGH >=1000 training rows; no effect on model thresholds',markets:Object.entries(training.market_support||{}).sort(([a],[b])=>a.localeCompare(b)).map(([market,count])=>{const cal=calibration[market]||{};return {market,training_rows:count,validation_rows:cal.rows??null,calibration_fit_rows:cal.fit_rows??null,calibration_evaluation_rows:cal.evaluation_rows??null,test_rows:null,log_loss:null,raw_brier:cal.raw_brier??null,calibrated_brier:cal.calibrated_brier??null,calibration_accepted:cal.accepted??null,support_label:count<100?'LOW':count<1000?'MEDIUM':'HIGH'}})});
 write('manifest.json',{schema:1,source_sha:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),source_files:Object.fromEntries(['results.json','symphony2_current.json','superbet_direct_current.json','player_dna_current_shadow.json','meta.json'].map(n=>[n,hash(fs.readFileSync(path.join(data,n)))])),sizes});
 return sizes;
}
if(process.argv[1]===new URL(import.meta.url).pathname)console.log(JSON.stringify(buildDelivery(process.argv[2]||'frontend')));
