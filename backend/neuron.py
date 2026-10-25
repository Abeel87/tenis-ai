from __future__ import annotations
"""Tenis AI Neuron: leakage-safe residual Siamese MLP, SHADOW_RESEARCH only."""
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import argparse, hashlib, json, math, os, re, sys, unicodedata
from pathlib import Path
import numpy as np
import pandas as pd

try:
    from .history_hygiene_v78a import clean_history
except ImportError:
    from history_hygiene_v78a import clean_history

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'frontend'/'data'
MODEL=DATA/'neuron_model.json'; METRICS=DATA/'neuron_metrics.json'; CURRENT=DATA/'neuron_current.json'
MODE='SHADOW_RESEARCH'; POLICY='RAW_TENIS_AI_HISTORY_ONLY; NO_LEGACY_NEURON_OUTPUTS; NO_MODEL_PROBABILITY_STACKING'
PF=['log_rank','rank_missing','elo','surface_elo','wr10','wr25','wr50','surface_wr20','hold20','break20','spw20','rpw20','matches7','sets7','days_last','log_matches','age','age_missing','height','height_missing','left','hand_missing']
CF=['h2h_a','log_h2h','bo5','hard','clay','grass','other_surface','atp','wta','challenger','other_tour','grand_slam']
SET_RE=re.compile(r'(\d+)\s*[-:]\s*(\d+)')
ELO_I=PF.index('elo'); ELO_LOGIT=math.log(10.0)/400.0

def key(v):
    if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)):
        return ''
    s=unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())
def num(v):
    try: x=float(v)
    except (TypeError,ValueError): return math.nan
    return x if math.isfinite(x) else math.nan
def ratio(a,b):
    a,b=num(a),num(b); return a/b if math.isfinite(a) and math.isfinite(b) and b>0 else math.nan
def mean(xs,default=math.nan):
    z=[float(x) for x in xs if x is not None and math.isfinite(num(x))]; return sum(z)/len(z) if z else default
def date(v):
    s=str(v or '').strip(); d=pd.to_datetime(s,format='%Y%m%d',errors='coerce')
    if pd.isna(d):
        d=pd.to_datetime(s,errors='coerce',utc=True)
        if not pd.isna(d): d=pd.Timestamp(d.date())
    return d
def surface(v):
    s=str(v or '').strip().lower(); return s if s in {'hard','clay','grass'} else 'other'
def best_of(r):
    for k in ('best_of','best_of_sets'):
        try:
            x=int(r.get(k))
            if x in (3,5): return x
        except (TypeError,ValueError): pass
    return 5 if str(r.get('source_tour') or '').lower()=='atp' and str(r.get('tourney_level') or '').upper()=='G' else 3
def hand(v):
    s=str(v or '').upper(); return 1. if s.startswith('L') else 0. if s.startswith('R') else math.nan

def perf(r,side,d,s):
    o='l' if side=='w' else 'w'; sv=num(r.get(f'{side}_svpt')); fi=num(r.get(f'{side}_1stIn'))
    fw=num(r.get(f'{side}_1stWon')); sw=num(r.get(f'{side}_2ndWon')); sg=num(r.get(f'{side}_SvGms'))
    bf=num(r.get(f'{side}_bpFaced')); bs=num(r.get(f'{side}_bpSaved')); osg=num(r.get(f'{o}_SvGms'))
    obf=num(r.get(f'{o}_bpFaced')); obs=num(r.get(f'{o}_bpSaved')); osv=num(r.get(f'{o}_svpt'))
    ofw=num(r.get(f'{o}_1stWon')); osw=num(r.get(f'{o}_2ndWon'))
    conceded=bf-bs if math.isfinite(bf) and math.isfinite(bs) else math.nan
    made=obf-obs if math.isfinite(obf) and math.isfinite(obs) else math.nan
    ospw=ratio(ofw+osw,osv) if math.isfinite(ofw) and math.isfinite(osw) else math.nan
    return {'d':d,'s':s,'w':1. if side=='w' else 0.,'hold':1-ratio(conceded,sg) if math.isfinite(conceded) else math.nan,
            'break':ratio(made,osg) if math.isfinite(made) else math.nan,'spw':ratio(fw+sw,sv) if math.isfinite(fw) and math.isfinite(sw) else math.nan,
            'rpw':1-ospw if math.isfinite(ospw) else math.nan,'sets':float(len(SET_RE.findall(str(r.get('score') or ''))))}

class State:
    def __init__(self): self.p=defaultdict(lambda:{'h':deque(maxlen=64),'elo':1500.,'se':{},'rank':math.nan,'age':math.nan,'ht':math.nan,'hand':math.nan}); self.h2h={}; self.latest_date=None
    def snap(self,n,d,s,rank=None):
        if self.latest_date is not None and self.latest_date >= d:
            raise ValueError('HISTORY_NOT_STRICTLY_PREMATCH')
        p=self.p[n]; h=list(p['h']); rr=num(rank); rr=rr if math.isfinite(rr) and rr>0 else p['rank']; r20=h[-20:]
        wr=lambda z: mean([x['w'] for x in z],.5); st=lambda k: mean([x[k] for x in r20])
        ss=[x for x in reversed(h) if x['s']==s][:20]; m7=sets7=0.; days=60.
        if h:
            ds=[int((d-x['d']).days) for x in h if d>=x['d']]
            if ds: days=float(min(60,max(0,min(ds))))
            for x in h:
                dd=int((d-x['d']).days)
                if 0<dd<=7: m7+=1; sets7+=x['sets'] if math.isfinite(num(x['sets'])) else 0
        rm=0. if math.isfinite(rr) and rr>0 else 1.; am=0. if math.isfinite(p['age']) else 1.; hm=0. if math.isfinite(p['ht']) else 1.; hdm=0. if math.isfinite(p['hand']) else 1.
        v=[math.log1p(rr) if not rm else math.nan,rm,p['elo'],p['se'].get(s,p['elo']),wr(h[-10:]),wr(h[-25:]),wr(h[-50:]),wr(ss),st('hold'),st('break'),st('spw'),st('rpw'),m7,sets7,days,math.log1p(len(h)),p['age'],am,p['ht'],hm,p['hand'],hdm]
        return np.asarray(v,float)
    def context(self,a,b,r,s):
        pair=tuple(sorted((a,b))); rec=self.h2h.get(pair,{}); n=float(rec.get('n',0)); ar=float(rec.get(a,0))/n if n else .5
        tour=str(r.get('source_tour') or r.get('tour') or '').lower(); lvl=str(r.get('tourney_level') or r.get('level') or '').upper()
        return np.asarray([ar,math.log1p(n),1. if best_of(r)==5 else 0.,*(1. if s==x else 0. for x in ('hard','clay','grass','other')),
            1. if tour=='atp' else 0.,1. if tour=='wta' else 0.,1. if tour in ('ch','challenger') else 0.,1. if tour not in ('atp','wta','ch','challenger') else 0.,1. if lvl=='G' else 0.],float)
    def update(self,r,d):
        w,l=key(r.get('winner_name')),key(r.get('loser_name'))
        if not w or not l or w==l: return
        self.latest_date = d if self.latest_date is None else max(self.latest_date, d)
        s=surface(r.get('surface')); pw,pl=self.p[w],self.p[l]; ew=1/(1+10**((pl['elo']-pw['elo'])/400)); delta=24*(1-ew); wo,lo=pw['elo'],pl['elo']; pw['elo']+=delta; pl['elo']-=delta
        ws=pw['se'].get(s,wo); ls=pl['se'].get(s,lo); es=1/(1+10**((ls-ws)/400)); ds=28*(1-es); pw['se'][s]=ws+ds; pl['se'][s]=ls-ds
        pair=tuple(sorted((w,l))); rec=self.h2h.setdefault(pair,{'n':0.}); rec['n']+=1; rec[w]=rec.get(w,0.)+1
        pw['h'].append(perf(r,'w',d,s)); pl['h'].append(perf(r,'l',d,s))
        for p,pre in ((pw,'winner'),(pl,'loser')):
            for dest,src,lo2,hi in (('rank','rank',1,5000),('age','age',10,70),('ht','ht',130,230)):
                x=num(r.get(f'{pre}_{src}'))
                if math.isfinite(x) and lo2<=x<=hi: p[dest]=x
            hh=hand(r.get(f'{pre}_hand'))
            if math.isfinite(hh): p['hand']=hh

def build(raw,swap=True,cutoff=None):
    req={'winner_name','loser_name','tourney_date','score'}
    if raw is None or raw.empty or not req.issubset(raw.columns): raise ValueError('Tenis AI history missing required match columns')
    df,hygiene=clean_history(raw)
    df=df.copy(); df['_d']=df.tourney_date.map(date); df=df[df['_d'].notna()].copy(); df['_w']=df.winner_name.map(key); df['_l']=df.loser_name.map(key); df=df[(df._w!='')&(df._l!='')&(df._w!=df._l)]
    excluded_date=0
    if cutoff is not None:
        bound=date(cutoff)
        if pd.isna(bound): raise ValueError('invalid history cutoff')
        allowed=df['_d'] < bound
        excluded_date=int((~allowed).sum()); df=df[allowed].copy()
    cols=[c for c in ('tourney_date','tourney_name','winner_name','loser_name','score') if c in df]; df=df.drop_duplicates(cols).sort_values(['_d','_w','_l'],kind='stable')
    st=State(); A=[]; B=[]; C=[]; Y=[]; D=[]
    for d,g in df.groupby('_d',sort=True):
        rows=list(g.iterrows())
        for _,r in rows:
            s=surface(r.get('surface')); w,l=r['_w'],r['_l']; a=st.snap(w,d,s,r.get('winner_rank')); b=st.snap(l,d,s,r.get('loser_rank'))
            A.append(a); B.append(b); C.append(st.context(w,l,r,s)); Y.append(1.); D.append(d.date().isoformat())
            if swap: A.append(b); B.append(a); C.append(st.context(l,w,r,s)); Y.append(0.); D.append(d.date().isoformat())
        for _,r in rows: st.update(r,d)
    if not A: raise ValueError('no leakage-safe rows')
    return (np.asarray(A),np.asarray(B),np.asarray(C),np.asarray(Y),np.asarray(D)),st,{'raw_rows':len(raw),'usable_matches':len(df),'rows':len(Y),'date_min':min(D),'date_max':max(D),'leakage':'STRICT_PRE_DATE; SAME_DAY_RESULTS_APPLIED_AFTER_FEATURISATION','date_basis':'source_tourney_date; no intraday ordering inferred','history_cutoff_exclusive':str(cutoff) if cutoff is not None else None,'excluded_same_day_or_future':excluded_date,'hygiene':hygiene}
def split(D):
    u=np.unique(D)
    if len(u)<10: raise ValueError('need >=10 distinct dates')
    a=max(1,int(.70*len(u))); b=min(len(u)-1,max(a+1,int(.85*len(u))))
    return {n:np.isin(D,x) for n,x in {'train':u[:a],'validation':u[a:b],'test':u[b:]}.items()}

def _sigmoid(x): return 1/(1+np.exp(-np.clip(x,-35,35)))

class Model:
    PARAMS=('W1','b1','W2','b2','W3','b3','W4','b4','Ws')
    def __init__(self,p=len(PF),c=len(CF),seed=87):
        rng=np.random.default_rng(seed); self.p=p; self.c=c; self.mu_p=self.sd_p=self.mu_c=self.sd_c=None
        self.W1=rng.normal(0,math.sqrt(2/max(1,p)),(p,64)); self.b1=np.zeros(64)
        self.W2=rng.normal(0,math.sqrt(2/64),(64,32)); self.b2=np.zeros(32)
        self.W3=rng.normal(0,math.sqrt(2/(32*3+c)),(32*3+c,32)); self.b3=np.zeros(32)
        self.W4=np.zeros((32,1)); self.b4=np.zeros(1); self.Ws=np.zeros((p,1)); self.temperature=1.0; self.training_info={}
    def _std(self,X,mu,sd): return np.nan_to_num((X-mu)/sd,nan=0.,posinf=0.,neginf=0.)
    def _prep(self,A,B,C): return self._std(np.atleast_2d(A),self.mu_p,self.sd_p),self._std(np.atleast_2d(B),self.mu_p,self.sd_p),self._std(np.atleast_2d(C),self.mu_c,self.sd_c)
    def _base(self,A,B):
        A=np.atleast_2d(A); B=np.atleast_2d(B); ea=np.nan_to_num(A[:,ELO_I],nan=1500.,posinf=1500.,neginf=1500.); eb=np.nan_to_num(B[:,ELO_I],nan=1500.,posinf=1500.,neginf=1500.)
        return ELO_LOGIT*(ea-eb)
    def _f(self,A,B,C,base,train=False,rng=None,dropout=.15):
        h1a=np.maximum(0,A@self.W1+self.b1); h1b=np.maximum(0,B@self.W1+self.b1)
        ea=np.maximum(0,h1a@self.W2+self.b2); eb=np.maximum(0,h1b@self.W2+self.b2)
        z=np.c_[ea,eb,ea-eb,C]; h=np.maximum(0,z@self.W3+self.b3); mask=None; hd=h
        if train and rng is not None and dropout>0:
            mask=(rng.random(h.shape)>=dropout)/(1-dropout); hd=h*mask
        q=np.asarray(base,float)[:,None]+(A-B)@self.Ws+hd@self.W4+self.b4
        return _sigmoid(q)[:,0],(h1a,h1b,ea,eb,z,h,hd,mask)
    def _one(self,A0,B0,C0):
        A0,B0,C0=np.atleast_2d(A0),np.atleast_2d(B0),np.atleast_2d(C0); A,B,C=self._prep(A0,B0,C0)
        return self._f(A,B,C,self._base(A0,B0))[0]
    def _sym(self,A0,B0,C0):
        A0,B0,C0=np.atleast_2d(A0),np.atleast_2d(B0),np.atleast_2d(C0); p=self._one(A0,B0,C0); CS=C0.copy(); CS[:,0]=1-CS[:,0]; q=1-self._one(B0,A0,CS)
        return np.clip((p+q)/2,1e-6,1-1e-6)
    @staticmethod
    def _calibrate(p,t):
        p=np.clip(np.asarray(p,float),1e-6,1-1e-6); t=max(.25,float(t)); return _sigmoid(np.log(p/(1-p))/t)
    def predict(self,A,B,C): return np.clip(self._calibrate(self._sym(A,B,C),self.temperature),1e-6,1-1e-6)
    def fit(self,A,B,C,Y,VA,VB,VC,VY,epochs=80,lr=.0025,seed=87,batch_size=1024,patience=12,dropout=.15):
        RA,RB,RC=np.atleast_2d(np.asarray(A,float)),np.atleast_2d(np.asarray(B,float)),np.atleast_2d(np.asarray(C,float)); Y=np.asarray(Y,float)
        RVA,RVB,RVC=np.atleast_2d(np.asarray(VA,float)),np.atleast_2d(np.asarray(VB,float)),np.atleast_2d(np.asarray(VC,float)); VY=np.asarray(VY,float)
        self.mu_p=np.nanmean(np.r_[RA,RB],axis=0); self.sd_p=np.nanstd(np.r_[RA,RB],axis=0); self.sd_p=np.where((self.sd_p<1e-6)|~np.isfinite(self.sd_p),1,self.sd_p); self.mu_p=np.nan_to_num(self.mu_p)
        self.mu_c=np.nanmean(RC,axis=0); self.sd_c=np.nanstd(RC,axis=0); self.sd_c=np.where((self.sd_c<1e-6)|~np.isfinite(self.sd_c),1,self.sd_c); self.mu_c=np.nan_to_num(self.mu_c)
        SA,SB,SC=self._prep(RA,RB,RC); rng=np.random.default_rng(seed); self.temperature=1.0
        init=self._sym(RVA,RVB,RVC); init_loss=ll(VY,init); init_acc=float(np.mean((init>=.5)==VY))
        best=init_loss; best_acc=init_acc; snap={x:getattr(self,x).copy() for x in self.PARAMS}; stale=0; best_epoch=0
        m1={x:np.zeros_like(getattr(self,x)) for x in self.PARAMS}; m2={x:np.zeros_like(getattr(self,x)) for x in self.PARAMS}; step=0
        n=len(Y); batch_size=max(64,min(int(batch_size),n)); reg=1e-5; beta1=.9; beta2=.999; eps=1e-8; epoch=0
        for epoch in range(1,int(epochs)+1):
            order=rng.permutation(n)
            for start in range(0,n,batch_size):
                ix=order[start:start+batch_size]; a,b,c,y=SA[ix],SB[ix],SC[ix],Y[ix]; base=self._base(RA[ix],RB[ix])
                p,(h1a,h1b,ea,eb,z,h,hd,mask)=self._f(a,b,c,base,True,rng,dropout); k=max(1,len(ix)); dq=(p-y)[:,None]/k
                dWs=(a-b).T@dq+reg*self.Ws; dW4=hd.T@dq+reg*self.W4; db4=dq.sum(0); dh=dq@self.W4.T
                if mask is not None: dh*=mask
                d3=dh*(h>0); dW3=z.T@d3+reg*self.W3; db3=d3.sum(0); dz=d3@self.W3.T
                dea=dz[:,:32]+dz[:,64:96]; deb=dz[:,32:64]-dz[:,64:96]; d2a=dea*(ea>0); d2b=deb*(eb>0)
                dW2=h1a.T@d2a+h1b.T@d2b+reg*self.W2; db2=(d2a+d2b).sum(0)
                dh1a=(d2a@self.W2.T)*(h1a>0); dh1b=(d2b@self.W2.T)*(h1b>0)
                dW1=a.T@dh1a+b.T@dh1b+reg*self.W1; db1=(dh1a+dh1b).sum(0)
                grads={'Ws':dWs,'W4':dW4,'b4':db4,'W3':dW3,'b3':db3,'W2':dW2,'b2':db2,'W1':dW1,'b1':db1}; step+=1
                for name in self.PARAMS:
                    g=np.clip(grads[name],-5,5); m1[name]=beta1*m1[name]+(1-beta1)*g; m2[name]=beta2*m2[name]+(1-beta2)*(g*g)
                    mh=m1[name]/(1-beta1**step); vh=m2[name]/(1-beta2**step); setattr(self,name,getattr(self,name)-lr*mh/(np.sqrt(vh)+eps))
            vp=self._sym(RVA,RVB,RVC); loss=ll(VY,vp); acc=float(np.mean((vp>=.5)==VY)); eligible=acc>=init_acc-1e-12
            if eligible and (loss<best-1e-5 or (abs(loss-best)<=1e-5 and acc>best_acc)):
                best=loss; best_acc=acc; best_epoch=epoch; snap={x:getattr(self,x).copy() for x in self.PARAMS}; stale=0
            else: stale+=1
            if stale>=patience: break
        for k,v in snap.items(): setattr(self,k,v)
        raw=self._sym(RVA,RVB,RVC); candidates=np.linspace(.60,1.60,51); losses=[ll(VY,self._calibrate(raw,t)) for t in candidates]; self.temperature=float(candidates[int(np.argmin(losses))])
        final=self.predict(RVA,RVB,RVC)
        self.training_info={'optimizer':'adam','residual_prior':'pre_match_elo_logit','dropout':float(dropout),'best_epoch':int(best_epoch),'epochs_ran':int(epoch),'validation_start_log_loss':float(init_loss),'validation_best_log_loss':float(ll(VY,final)),'validation_start_accuracy':float(init_acc),'validation_best_accuracy':float(np.mean((final>=.5)==VY)),'temperature':self.temperature}
        return self.training_info
    def dump(self):
        arr=lambda x:getattr(self,x).tolist(); return {'format':'tenis-ai-neuron-siamese','architecture':'Elo-logit residual + shared 22->64->32; [A,B,A-B,context]->32->correction; Adam; dropout=0.15','temperature':float(self.temperature),'training_info':self.training_info,'mu_p':arr('mu_p'),'sd_p':arr('sd_p'),'mu_c':arr('mu_c'),'sd_c':arr('sd_c'),**{x:arr(x) for x in self.PARAMS}}
    @classmethod
    def load(cls,d):
        m=cls(len(d['mu_p']),len(d['mu_c']))
        for x in ('mu_p','sd_p','mu_c','sd_c','W1','b1','W2','b2','W3','b3','W4','b4'): setattr(m,x,np.asarray(d[x],float))
        m.Ws=np.asarray(d.get('Ws',np.zeros((len(d['mu_p']),1))),float); m.temperature=float(d.get('temperature',1.0)); m.training_info=d.get('training_info') or {}
        return m

def ll(y,p): p=np.clip(p,1e-9,1-1e-9); return float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p)))
def metrics(y,p):
    acc=float(np.mean((p>=.5)==y)); b=float(np.mean((p-y)**2)); e=0.
    for lo in np.linspace(0,1,11)[:-1]:
        m=(p>=lo)&(p<(lo+.1) if lo<.9 else p<=1)
        if m.any(): e+=m.mean()*abs(y[m].mean()-p[m].mean())
    return {'accuracy':acc,'log_loss':ll(y,p),'brier':b,'ece_10':float(e)}
def flags(): return {'mode':MODE,'production_influence':False,'playable_influence':False,'symphony_influence':False,'ineed_influence':False,'auto_promote':False}
def write(path,payload): path.parent.mkdir(parents=True,exist_ok=True); t=path.with_suffix('.tmp'); t.write_text(json.dumps(payload,ensure_ascii=False,indent=2)); t.replace(path)
def load_history():
    b=str(ROOT/'backend'); sys.path.insert(0,b) if b not in sys.path else None; import update
    raw,warn,info=update.load_history()
    if raw is None or raw.empty: raise RuntimeError(f'Tenis AI history unavailable: {warn}')
    return raw,warn,info

def utc(value):
    try:
        parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def read_json(path, default=None):
    # A malformed existing ledger must never silently become an empty ledger.
    return json.loads(path.read_text()) if path.exists() else default


def digest(value):
    content=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    return hashlib.sha256(content.encode()).hexdigest()


def model_identity(payload):
    fields=('format','architecture','temperature','mu_p','sd_p','mu_c','sd_c',*Model.PARAMS,
            'player_features','context_features','inputs_policy')
    return 'neuron-'+digest({name:payload.get(name) for name in fields})


def dataset_identity(arrays):
    h=hashlib.sha256()
    h.update(json.dumps({'player_features':PF,'context_features':CF}).encode())
    for name, values in zip(('A','B','C','Y','D'), arrays):
        h.update(name.encode()); h.update(str(values.shape).encode())
        if name=='D': h.update(json.dumps(values.tolist()).encode())
        else: h.update(np.asarray(values,dtype='<f8').tobytes())
    return h.hexdigest()


def training_artifacts():
    return ROOT/'artifacts'/'neuron'


def _training_summary(report):
    return {k:report.get(k) for k in ('model_id','generated_at','dataset','splits','split_dates',
            'split_feature_sha256','learning_progress','training','test','elo_baseline_test','quality_gate','training_status')}


def learning_progress(previous_report, previous_model_id, model_id, split_hashes):
    old=previous_report.get('split_feature_sha256') or {}
    changed={name:(value!=old[name] if old.get(name) else None) for name,value in split_hashes.items()}
    known=all(changed.get(name) is not None for name in ('train','validation'))
    return {'input_changes':changed,
            'training_inputs_status':('CHANGED' if changed['train'] or changed['validation'] else 'UNCHANGED') if known else 'UNKNOWN_PREVIOUS_INPUTS',
            'model_parameters_changed':model_id!=previous_model_id if previous_model_id else None,
            'quality_improvement_proven':False}


def _incumbent_comparison(previous, A, B, C, Y, D, test_mask, candidate):
    if not previous or previous.get('format')!='tenis-ai-neuron-siamese':
        return {'status':'NO_PREVIOUS_MODEL','matches':0}
    # Legacy models have no saved split boundaries: use the later artifact date,
    # rather than inventing their training/temperature-calibration boundary.
    boundary=previous.get('validation_end_date')
    basis='saved_validation_end_date'
    if not boundary:
        stamp=utc(previous.get('generated_at'))
        if stamp is None: return {'status':'UNKNOWN_PREVIOUS_DATA_BOUNDARY','matches':0}
        boundary=stamp.date().isoformat(); basis='conservative_legacy_artifact_date'
    mask=test_mask & (D>boundary)
    if not mask.any():
        return {'status':'NO_COMMON_UNSEEN_MATCHES','matches':0,'after':boundary,'boundary_basis':basis}
    old=Model.load(previous).predict(A[mask],B[mask],C[mask])
    new=candidate.predict(A[mask],B[mask],C[mask])
    return {'status':'DESCRIPTIVE_COMMON_HOLDOUT','matches':int(mask.sum())//2,
            'previous_model_id':model_identity(previous),'after':boundary,'boundary_basis':basis,
            'candidate':metrics(Y[mask],new),'previous':metrics(Y[mask],old),
            'automatic_promotion':False,'statistical_superiority_claimed':False}


def train():
    started=datetime.now(timezone.utc)
    previous=read_json(MODEL,{})
    previous_report=read_json(METRICS,{})
    raw,warn,info=load_history()
    arrays,_,meta=build(raw,True,cutoff=started.date().isoformat())
    A,B,C,Y,D=arrays; S=split(D); tr,va,te=S['train'],S['validation'],S['test']
    m=Model()
    training=m.fit(A[tr],B[tr],C[tr],Y[tr],A[va],B[va],C[va],Y[va])
    vp=m.predict(A[va],B[va],C[va]); tp=m.predict(A[te],B[te],C[te])
    elo=lambda mask:1/(1+10**(-((A[mask,ELO_I]-B[mask,ELO_I])/400)))
    vm,tm,ve,te_m=metrics(Y[va],vp),metrics(Y[te],tp),metrics(Y[va],elo(va)),metrics(Y[te],elo(te))
    gate={'beats_elo_log_loss':tm['log_loss']<te_m['log_loss'],
          'beats_elo_accuracy':tm['accuracy']>te_m['accuracy'],'ece_le_0_05':tm['ece_10']<=.05,
          'test_rows_ge_1000':int(te.sum())>=1000,
          'all_history_sources_available':info.get('missing_sources')==0,
          'finite_metrics':all(math.isfinite(v) for group in (vm,tm,ve,te_m) for v in group.values())}
    gate['passed']=all(gate.values()); now=datetime.now(timezone.utc).isoformat()
    boundaries={name:{'first_date':str(min(D[mask])),'last_date':str(max(D[mask])),
                      'unique_matches':int(mask.sum())//2} for name,mask in S.items()}
    data_sha=dataset_identity(arrays)
    split_hashes={name:dataset_identity(tuple(values[mask] for values in arrays)) for name,mask in S.items()}
    mp={**m.dump(),**flags(),'generated_at':now,'inputs_policy':POLICY,'player_features':PF,
        'context_features':CF,'training_dataset_sha256':data_sha,
        'validation_end_date':boundaries['validation']['last_date'],
        'source_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    mp['model_id']=model_identity(mp)
    previous_id=model_identity(previous) if previous.get('format') else None
    report={**flags(),'generated_at':now,'training_started_at':started.isoformat(),
            'model_id':mp['model_id'],'previous_model_id':previous_id,
            'dataset':{**meta,'feature_dataset_sha256':data_sha},'source':info,'source_warnings':warn,
            'splits':{k:int(v.sum()) for k,v in S.items()},'split_dates':boundaries,'training':training,
            'split_feature_sha256':split_hashes,
            'learning_progress':learning_progress(previous_report,previous_id,mp['model_id'],split_hashes),
            'training_status':'ACCEPTED' if gate['passed'] else 'REJECTED_KEEP_PREVIOUS',
            'validation':vm,'test':tm,'elo_baseline_validation':ve,'elo_baseline_test':te_m,
            'quality_gate':gate,'promotion_eligible':False,
            'promotion_reason':'manual architecture and quality review required',
            'run_id':os.environ.get('GITHUB_RUN_ID'),
            'common_holdout':_incumbent_comparison(previous,A,B,C,Y,D,te,m)}
    history=list(previous_report.get('training_history') or [])
    if not history and previous_report.get('generated_at'):
        history.append(_training_summary(previous_report))
    report['training_history']=history+[_training_summary(report)]
    archive=training_artifacts(); archive.mkdir(parents=True,exist_ok=True)
    write(archive/'candidate_model.json',mp); write(archive/'candidate_metrics.json',report)
    np.savez_compressed(archive/'training_dataset.npz',A=A,B=B,C=C,Y=Y,D=D,**S)
    # A rejected candidate remains downloadable but never replaces the active pair.
    if gate['passed']:
        write(MODEL,mp); write(METRICS,report)
    return report


def quality_gate():
    candidate=read_json(training_artifacts()/'candidate_metrics.json',{})
    if candidate.get('quality_gate',{}).get('passed') is not True:
        raise RuntimeError('NEURON_CANDIDATE_REJECTED; previous model retained')
    active=read_json(MODEL,{})
    if candidate.get('model_id')!=model_identity(active):
        raise RuntimeError('NEURON_MODEL_METRICS_MISMATCH')
    return {'passed':True,'model_id':candidate['model_id']}


def current_features(st,m,now=None):
    now=now or datetime.now(timezone.utc)
    start=utc(m.get('scheduled_time') or m.get('start_time'))
    if start is None: raise ValueError('MISSING_OR_INVALID_START')
    if start<=now: raise ValueError('MATCH_NOT_PREMATCH')
    a=key(m.get('p1') or m.get('player1')); b=key(m.get('p2') or m.get('player2'))
    if not a or not b or a==b: raise ValueError('MISSING_OR_AMBIGUOUS_PLAYERS')
    if any(name not in st.p or not st.p[name]['h'] for name in (a,b)):
        raise ValueError('NO_PLAYER_HISTORY')
    # Even for tomorrow's fixture, today's un-timed results are not used.
    d=pd.Timestamp(min(start.date(),now.date())); s=surface(m.get('surface'))
    r=dict(m); r['source_tour']=m.get('tour'); r['tourney_level']=m.get('level')
    r['best_of']=m.get('best_of') or m.get('bestOf')
    return st.snap(a,d,s,m.get('p1_rank')),st.snap(b,d,s,m.get('p2_rank')),st.context(a,b,r,s)


def predictions_dir():
    return ROOT/'data'/'neuron_predictions'


def load_predictions():
    rows={}
    for path in sorted(predictions_dir().glob('*.json')):
        document=read_json(path)
        if document.get('schema')!='neuron-predictions-1' or document.get('mode')!=MODE:
            raise ValueError('INVALID_NEURON_LEDGER')
        for row in document['predictions']:
            validate_prediction(row)
            if row['prediction_id'] in rows: raise ValueError('DUPLICATE_NEURON_PREDICTION')
            rows[row['prediction_id']]=row
    return rows


def frozen_prediction(row):
    return {k:v for k,v in row.items() if k not in ('settlement','snapshot_sha256')}


def validate_prediction(row):
    captured=utc(row.get('captured_at')); start=utc(row.get('scheduled_time'))
    if not captured or not start or captured>=start:
        raise ValueError('LEDGER_NOT_PREMATCH')
    trained=utc(row.get('model_trained_at'))
    if trained is None or trained>captured:
        raise ValueError('INVALID_FROZEN_MODEL_TIME')
    identity={name:row.get(name) for name in ('model_id','match_id','scheduled_time','p1','p2')}
    if (not str(row.get('match_id')).isdigit() or row.get('match_key')!='id:'+str(row['match_id'])
            or not row.get('model_id') or not key(row.get('p1')) or not key(row.get('p2'))
            or key(row['p1'])==key(row['p2']) or row.get('pick')!=row['p1']
            or row.get('market')!='match_win'
            or row.get('prediction_id')!='neuron-prediction-'+digest(identity)):
        raise ValueError('INVALID_FROZEN_IDENTITY')
    if row.get('snapshot_sha256')!=digest(frozen_prediction(row)):
        raise ValueError('IMMUTABLE_NEURON_PREDICTION_CHANGED')
    for name in ('p1_win_probability','elo_p1_win_probability'):
        value=row.get(name)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<value<1:
            raise ValueError('INVALID_FROZEN_PROBABILITY')


def save_predictions(rows):
    groups=defaultdict(list)
    for row in rows.values():
        validate_prediction(row)
        groups[utc(row['captured_at']).strftime('%Y-%m')].append(row)
    for month,items in groups.items():
        payload={**flags(),'schema':'neuron-predictions-1',
                 'predictions':sorted(items,key=lambda x:x['prediction_id'])}
        path=predictions_dir()/f'{month}.json'
        if read_json(path)!=payload: write(path,payload)


def freeze_predictions(existing, rows, model_id, trained_at, captured_at, history_sha):
    result=dict(existing)
    for row in rows:
        if row.get('status')!='SHADOW_SCORE': continue
        identity={'model_id':model_id,'match_id':str(row['match_id']),
                  'scheduled_time':row['scheduled_time'],'p1':row['p1'],'p2':row['p2']}
        pid='neuron-prediction-'+digest(identity)
        if pid in result: continue
        record={**identity,'prediction_id':pid,'match_key':'id:'+str(row['match_id']),
                'captured_at':captured_at,'model_trained_at':trained_at,
                'p1_win_probability':row['p1_win_probability'],
                'elo_p1_win_probability':row['elo_p1_win_probability'],
                'feature_snapshot':row['feature_snapshot'],'history_sha256':history_sha,
                'market':'match_win','pick':row['p1']}
        record['snapshot_sha256']=digest(record)
        record['settlement']={'status':'N/D','result':None,'reason':'AWAITING_EXACT_TERMINAL_EVIDENCE'}
        validate_prediction(record); result[pid]=record
    return result


def summarize_predictions(rows):
    values=list(rows.values()) if isinstance(rows,dict) else list(rows)
    def summary(items):
        first={}
        for row in sorted(items,key=lambda x:(utc(x['captured_at']),x['prediction_id'])):
            first.setdefault(row['match_key'],row)
        unique=list(first.values())
        scored=[r for r in unique if r.get('settlement',{}).get('result') in ('hit','miss')]
        y=np.asarray([1. if r['settlement']['result']=='hit' else 0. for r in scored])
        return {'unique_fixtures':len(unique),'settled_matches':len(scored),
                'pending_matches':sum(r.get('settlement',{}).get('status')!='SETTLED' for r in unique),
                'void_matches':sum(r.get('settlement',{}).get('result')=='void' for r in unique),
                'neuron':metrics(y,np.asarray([r['p1_win_probability'] for r in scored])) if scored else None,
                'elo':metrics(y,np.asarray([r['elo_p1_win_probability'] for r in scored])) if scored else None}
    by_model=defaultdict(list)
    for row in values: by_model[row['model_id']].append(row)
    aggregate=summary(values)
    return {**aggregate,'forecast_snapshots':len(values),'population':'FIRST_PREMATCH_FORECAST_PER_EXACT_FIXTURE',
            'status':'HAS_SETTLED_EVIDENCE' if aggregate['settled_matches'] else 'COLLECTING_PROSPECTIVE_EVIDENCE',
            'by_model':{name:summary(items) for name,items in sorted(by_model.items())},
            'automatic_promotion':False,'profitability_claimed':False}


def current():
    now=datetime.now(timezone.utc); mp=read_json(MODEL); model_id=model_identity(mp); m=Model.load(mp)
    raw,warn,info=load_history(); arrays,st,meta=build(raw,False,cutoff=now.date().isoformat())
    history_sha=dataset_identity(arrays); src=read_json(DATA/'results.json'); rows=[]
    if not isinstance(src,list): raise RuntimeError('results.json is not a list')
    now=datetime.now(timezone.utc)
    for x in src:
        if not isinstance(x,dict): continue
        row={'match_id':x.get('match_id') or x.get('id'),'p1':x.get('p1') or x.get('player1'),'p2':x.get('p2') or x.get('player2'),
             'scheduled_time':x.get('scheduled_time') or x.get('start_time'),'model_id':model_id}
        try:
            if not str(row['match_id']).isdigit(): raise ValueError('MISSING_EXACT_FIXTURE_ID')
            a,b,c=current_features(st,x,now=now); p=float(m.predict(a,b,c)[0])
            if not math.isfinite(p): raise ValueError('NONFINITE_MODEL_SCORE')
            feature=lambda values:[float(v) if math.isfinite(float(v)) else None for v in values]
            row.update({'p1_win_probability':round(p,6),'p2_win_probability':round(1-p,6),
                        'elo_p1_win_probability':float(_sigmoid(ELO_LOGIT*(a[ELO_I]-b[ELO_I]))),
                        'status':'SHADOW_SCORE','scheduled_time':utc(row['scheduled_time']).isoformat(),
                        'feature_snapshot':{'A':feature(a),'B':feature(b),'C':feature(c)}})
        except ValueError as error:
            row.update({'status':'NO_SCORE','reason':str(error)})
        rows.append(row)
    existing=load_predictions()
    # Timestamp the completed forecast, not the earlier download start. A fixture
    # that starts during computation cannot enter the prospective sample.
    now=datetime.now(timezone.utc)
    for row in rows:
        if row['status']=='SHADOW_SCORE' and utc(row['scheduled_time'])<=now:
            row.update({'status':'NO_SCORE','reason':'MATCH_NOT_PREMATCH'})
            for field in ('p1_win_probability','p2_win_probability','elo_p1_win_probability','feature_snapshot'):
                row.pop(field,None)
    frozen=freeze_predictions(existing,rows,model_id,mp.get('generated_at'),now.isoformat(),history_sha)
    save_predictions(frozen)
    out={**flags(),'operator_playable':False,'generated_at':now.isoformat(),'model_id':model_id,
         'model_trained_at':mp.get('generated_at'),'source':info,'source_warnings':warn,
         'history_date_max':meta['date_max'],'history_cutoff_exclusive':meta['history_cutoff_exclusive'],
         'history_sha256':history_sha,'history_hygiene':meta['hygiene'],
         'excluded_same_day_or_future':meta['excluded_same_day_or_future'],
         'no_score_reasons':dict(Counter(r['reason'] for r in rows if r['status']=='NO_SCORE')),
         'prospective':summarize_predictions(frozen),
         'matches':[{k:v for k,v in row.items() if k!='feature_snapshot'} for row in rows]}
    write(CURRENT,out); return out


def settle_predictions(rows, history, now=None):
    # Reuse the canonical exact-identity/provenance checks and result scorer.
    try:
        from .prediction_ledger_settlement_shadow import _history_index, _settlement_fact
    except ImportError:
        from prediction_ledger_settlement_shadow import _history_index, _settlement_fact
    now=now or datetime.now(timezone.utc); index=_history_index(history); result={}
    for pid,row in rows.items():
        validate_prediction(row); updated=dict(row)
        if row.get('settlement',{}).get('status')=='SETTLED':
            result[pid]=updated; continue
        evidence=index.get(row['match_key']) or []
        if len(evidence)==1:
            if (utc(evidence[0].get('scheduled_time')) is None
                    or utc(evidence[0].get('settled_at')) is None):
                updated['settlement']={'status':'N/D','result':None,'reason':'INVALID_SETTLEMENT_TIME'}
                result[pid]=updated; continue
            final=evidence[0].get('result') or {}
            participants=(key(final.get('p1')),key(final.get('p2')))
            if participants!=(key(row['p1']),key(row['p2'])):
                updated['settlement']={'status':'N/D','result':None,'reason':'EXACT_PARTICIPANT_CONFLICT'}
                result[pid]=updated; continue
        fact=_settlement_fact(row,index)
        if fact.get('status')=='SETTLED':
            settled=utc(fact.get('settled_at'))
            if settled is None or settled>now:
                fact={'status':'N/D','result':None,'reason':'INVALID_SETTLEMENT_TIME'}
        updated['settlement']=fact; result[pid]=updated
    return result


def evaluate():
    history=read_json(DATA/'history.json',[])
    if not isinstance(history,list): raise ValueError('INVALID_CANONICAL_HISTORY')
    rows=settle_predictions(load_predictions(),history)
    save_predictions(rows)
    current_report=read_json(CURRENT,{})
    current_report['prospective']=summarize_predictions(rows)
    current_report['prospective']['evaluated_at']=datetime.now(timezone.utc).isoformat()
    write(CURRENT,current_report)
    return current_report['prospective']
def audit():
    out={**flags(),'legacy_neuron_inputs_allowed':False,'model_exists':MODEL.exists(),'metrics_exists':METRICS.exists(),'current_exists':CURRENT.exists()}
    if MODEL.exists():
        m=json.loads(MODEL.read_text()); assert m.get('format')=='tenis-ai-neuron-siamese' and m.get('inputs_policy')==POLICY and m.get('production_influence') is False
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['train','gate','current','evaluate','audit'])
    actions={'train':train,'gate':quality_gate,'current':current,'evaluate':evaluate,'audit':audit}
    print(json.dumps(actions[p.parse_args().action](),ensure_ascii=False,indent=2))
