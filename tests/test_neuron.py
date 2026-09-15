import numpy as np, pandas as pd
from backend.neuron import PF, CF, build, split, Model, flags, POLICY

def hist(days=40):
    rows=[]
    for i in range(days):
        d=(pd.Timestamp('2026-07-01')+pd.Timedelta(days=i)).strftime('%Y%m%d'); w,l=('Alice','Betty') if i%2==0 else ('Betty','Alice')
        rows.append({'tourney_date':d,'tourney_name':'T','surface':'Hard','source_tour':'WTA','tourney_level':'A','winner_name':w,'loser_name':l,'winner_rank':10 if w=='Alice' else 20,'loser_rank':20 if l=='Betty' else 10,'winner_age':25,'loser_age':26,'winner_ht':180,'loser_ht':175,'winner_hand':'R','loser_hand':'L','score':'6-4 6-4','w_svpt':60,'w_1stIn':36,'w_1stWon':28,'w_2ndWon':14,'w_SvGms':10,'w_bpSaved':3,'w_bpFaced':4,'l_svpt':62,'l_1stIn':37,'l_1stWon':24,'l_2ndWon':11,'l_SvGms':10,'l_bpSaved':4,'l_bpFaced':7})
    return pd.DataFrame(rows)
def test_dataset_is_balanced_and_leakage_safe():
    (A,B,C,Y,D),_,meta=build(hist(),True); assert len(Y)==80 and Y.mean()==.5; assert meta['leakage'].startswith('STRICT_PRE_DATE'); i=PF.index('log_matches'); assert A[0,i]==B[0,i]==A[1,i]==B[1,i]==0 and A[2,i]>0
def test_chrono_split_does_not_mix_dates():
    (_,_,_,_,D),_,_=build(hist(),True); s=split(D); sets={k:set(D[v]) for k,v in s.items()}; assert sets['train'].isdisjoint(sets['validation']|sets['test']); assert sets['validation'].isdisjoint(sets['test']); assert max(sets['train'])<min(sets['validation'])<min(sets['test'])
def test_siamese_model_returns_probabilities_and_serializes():
    (A,B,C,Y,D),_,_=build(hist(),True); s=split(D); m=Model(); m.fit(A[s['train']],B[s['train']],C[s['train']],Y[s['train']],A[s['validation']],B[s['validation']],C[s['validation']],Y[s['validation']],epochs=8); p=m.predict(A[s['test']],B[s['test']],C[s['test']]); assert np.all((p>0)&(p<1)); q=Model.load(m.dump()).predict(A[s['test']],B[s['test']],C[s['test']]); assert np.allclose(p,q); assert m.training_info['residual_prior']=='pre_match_elo_logit'
def test_residual_optimizer_learns_non_elo_signal_and_is_symmetric():
    rng=np.random.default_rng(11); n=320; A=np.zeros((n,len(PF))); B=np.zeros_like(A); C=np.zeros((n,len(CF))); C[:,0]=.5
    x=rng.normal(size=n); z=rng.normal(size=n); A[:,PF.index('elo')]=1500; B[:,PF.index('elo')]=1500; A[:,PF.index('log_rank')]=5-x; B[:,PF.index('log_rank')]=5-z; Y=(x>z).astype(float)
    m=Model(seed=5); m.fit(A[:220],B[:220],C[:220],Y[:220],A[220:270],B[220:270],C[220:270],Y[220:270],epochs=25,batch_size=64,patience=8)
    p=m.predict(A[270:],B[270:],C[270:]); assert np.mean((p>=.5)==Y[270:])>.85
    cs=C[270:].copy(); cs[:,0]=1-cs[:,0]; q=m.predict(B[270:],A[270:],cs); assert np.allclose(p,1-q,atol=1e-10)
def test_hard_isolation_contract():
    f=flags(); assert f=={'mode':'SHADOW_RESEARCH','production_influence':False,'playable_influence':False,'symphony_influence':False,'ineed_influence':False,'auto_promote':False}; assert 'NO_LEGACY_NEURON_OUTPUTS' in POLICY

# PR gate anchor refreshed after Runtime Health baseline fix (#326): rerun real OOS Neuron quality gate on latest main.
