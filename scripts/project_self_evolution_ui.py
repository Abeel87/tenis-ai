"""Read-only, bounded projection of an attested research run for the admin UI."""
import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

FLAGS = ('production_influence','playable_influence','symphony_influence','ineed_influence','real_betting_enabled','economic_roi_evaluated')
EVALUATION = ('status','registered_at','evaluation_deadline','evaluation_completed','independent_matches','independent_utc_days','champion_brier','challenger_brier','paired_brier_improvement','lower_confidence_bound_approx')
HISTORICAL = ('train_brier','validation_brier','holdout_brier','current_validation_brier','current_holdout_brier','validation_delta_vs_current','holdout_delta_vs_current')

def digest(doc):
    raw=json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
    return 'sha256:'+hashlib.sha256(raw.encode()).hexdigest()

def pick(doc, keys):
    if not isinstance(doc,dict): return None
    out={}
    for key in keys:
        value=doc.get(key)
        if value is not None and not isinstance(value,(str,int,float,bool)): raise ValueError('Non-scalar report field')
        if isinstance(value,float) and not math.isfinite(value): raise ValueError('Non-finite report field')
        if isinstance(value,str) and len(value)>256: raise ValueError('Unbounded report field')
        out[key]=value
    return out

def project(report,memory,run):
    if (run.get('head_branch')!='main' or run.get('event') not in ('schedule','workflow_dispatch')
        or run.get('conclusion')!='success' or run.get('status')!='completed'
        or run.get('path')!='.github/workflows/self-evolution-shadow.yml'
        or run.get('head_repository',{}).get('full_name')!='Abeel87/tenis-ai'):
        raise ValueError('Not a successful trusted main research execution')
    for doc,version,promotion in ((report,'self-evolution-shadow-v1','auto_promote'),(memory,'self-evolution-shadow-memory-v1','auto_promote_to_prod')):
        if doc.get('schema_version')!=version or doc.get('mode')!='SHADOW_ONLY': raise ValueError('Invalid isolated report schema')
        if any(doc.get(k) is not False for k in (*FLAGS,promotion)): raise ValueError('Report has production authority')
    if memory.get('source_research_sha256')!=digest(report) or memory.get('source_ledger_sha256')!=report.get('source_ledger_sha256'):
        raise ValueError('Research/memory provenance mismatch')
    if memory.get('generated_at')!=report.get('generated_at'): raise ValueError('Research/memory time mismatch')
    stamp=datetime.fromisoformat(report['generated_at'].replace('Z','+00:00'))
    if stamp.tzinfo is None: raise ValueError('Missing report timezone')
    tracks=memory.get('tracks')
    if not isinstance(tracks,dict) or len(tracks)>13: raise ValueError('Invalid track set')
    rows=[]
    for label,track in sorted(tracks.items()):
        if not isinstance(label,str) or len(label)>72: raise ValueError('Invalid track label')
        history=track.get('history')
        if not isinstance(history,list) or len(history)>40: raise ValueError('Invalid retained history')
        rows.append({'key':label,'champion':pick(track.get('champion'),('id','registered_at')),
          'challenger':pick(track.get('challenger'),('id','registered_at')),
          'last_evaluation':pick(track.get('last_evaluation'),EVALUATION),
          'history':[{**pick(h,('champion_id','challenger_id','decision','decision_at')),'evidence':pick(h.get('evidence'),EVALUATION)} for h in history]})
    return {'schema':1,'mode':'SHADOW_ONLY','generated_at':report['generated_at'],
      'source':{'run_id':run['id'],'head_sha':run['head_sha'],'research_sha256':digest(report),'memory_sha256':digest(memory)},
      **{k:False for k in FLAGS},'auto_promote_to_prod':False,
      'run_number':memory.get('run_number'),'historical':{**pick(report,('status','reason','samples')),
      'windows':pick(report.get('windows'),('train_matches','validation_matches','holdout_matches','train_rows','validation_rows','holdout_rows','validation_start_day','holdout_start_day')),
      'candidate':pick(report.get('candidate'),HISTORICAL)},'tracks':rows,
      'completed_in_retained_history':sum(len(r['history']) for r in rows)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('report','memory','run','output'): parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    documents=[]
    for path in (args.report,args.memory,args.run):
        if path.stat().st_size>2_000_000: raise ValueError('Oversized report input')
        documents.append(json.loads(path.read_text()))
    result=project(*documents)
    body=json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n'
    if len(body.encode())>400_000: raise ValueError('Oversized UI projection')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(body)
    print(json.dumps({'source_run':result['source']['run_id'],'tracks':len(result['tracks']),'bytes':len(body.encode())}))
