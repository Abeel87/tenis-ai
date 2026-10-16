"""Report delivery must preserve source evidence and never grant authority."""
import copy
from pathlib import Path
import pytest
from scripts.project_self_evolution_ui import FLAGS,digest,project
from scripts import publish_runtime_private as delivery


def documents():
    report={'schema_version':'self-evolution-shadow-v1','mode':'SHADOW_ONLY',
      'generated_at':'2026-10-16T04:40:00+00:00','source_ledger_sha256':'sha256:'+'a'*64,
      **{k:False for k in FLAGS},'auto_promote':False,'status':'COLLECTING_VERIFIED_HISTORY',
      'samples':0,'candidate':None,'windows':None,'private_predictions':[{'never':'publish'}]}
    memory={'schema_version':'self-evolution-shadow-memory-v1','mode':'SHADOW_ONLY',
      'generated_at':report['generated_at'],'source_ledger_sha256':report['source_ledger_sha256'],
      'source_research_sha256':digest(report),**{k:False for k in FLAGS},'auto_promote_to_prod':False,
      'run_number':4,'tracks':{'ALL':{'champion':{'id':'known-version','weights':{'current':1}},
      'challenger':None,'last_evaluation':None,'history':[]}}}
    run={'id':123,'head_sha':'b'*40,'head_branch':'main','head_repository':{'full_name':'Abeel87/tenis-ai'},
      'event':'schedule','status':'completed','conclusion':'success','path':'.github/workflows/self-evolution-shadow.yml'}
    return report,memory,run


def test_exact_projection_preserves_zero_missing_and_inputs():
    docs=documents();before=copy.deepcopy(docs);out=project(*docs)
    assert docs==before
    assert out['historical']['samples']==0 and out['historical']['candidate'] is None
    assert out['completed_in_retained_history']==0 and out['run_number']==4
    assert out['tracks'][0]['champion']['id']=='known-version'
    assert 'weights' not in str(out) and 'private_predictions' not in str(out)
    assert all(out[k] is False for k in FLAGS)


@pytest.mark.parametrize('field',FLAGS+('auto_promote',))
def test_rejects_research_authority(field):
    docs=documents();docs[0][field]=True;docs[1]['source_research_sha256']=digest(docs[0])
    with pytest.raises(ValueError,match='authority'): project(*docs)


@pytest.mark.parametrize('change',[{'head_branch':'feature'},{'event':'pull_request'},{'conclusion':'failure'},
    {'status':'in_progress'},{'path':'.github/workflows/other.yml'},{'head_repository':{'full_name':'other/fork'}}])
def test_rejects_untrusted_run(change):
    docs=documents();docs[2].update(change)
    with pytest.raises(ValueError,match='trusted'): project(*docs)


def test_mismatched_report_memory_fails_closed():
    docs=documents();docs[0]['samples']=1
    with pytest.raises(ValueError,match='provenance'): project(*docs)
    docs=documents();docs[1]['generated_at']='2026-10-15T04:40:00+00:00'
    with pytest.raises(ValueError,match='time'): project(*docs)


def test_bounded_tracks_and_private_owner():
    docs=documents();docs[1]['tracks']={str(i):{} for i in range(14)}
    with pytest.raises(ValueError,match='track'): project(*docs)
    assert delivery.owner_layer('data/self_evolution_ui.json')=='research'
    assert delivery.tier_for('data/self_evolution_ui.json')=='c'
    transport=Path('frontend/runtime-data-transport.js').read_text()
    assert transport.index("if(path==='data/self_evolution_ui.json')")<transport.index("if(mode==='public'")


def test_push_bootstrap_cannot_publish_a_production_layer():
    edge=Path('supabase/functions/runtime-data-publish/index.ts').read_text()
    # Both prepare and activate retain this restriction.
    assert edge.count('auth.payload.event_name === "push" && layer !== "research"')==2
    assert 'files[0].tier !== "c"' in edge
    assert 'files[0].path !== "data/self_evolution_ui.json"' in edge
    workflow=Path('.github/workflows/runtime-private-delivery.yml').read_text()
    assert 'scripts/project_self_evolution_ui.py' in workflow
    assert 'Self Evolution SHADOW research' in workflow
    assert 'contents: write' not in workflow
