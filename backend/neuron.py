from __future__ import annotations
"""Tenis AI Neuron: leakage-safe residual Siamese MLP, SHADOW_RESEARCH only."""
from collections import defaultdict, deque
from datetime import datetime, timezone
import argparse, json, math, re, sys, unicodedata
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'frontend'/'data'
MODEL=DATA/'neuron_model.json'; METRICS=DATA/'neuron_metrics.json'; CURRENT=DATA/'neuron_current.json'
MODE='SHADOW_RESEARCH'; POLICY='RAW_TENIS_AI_HISTORY_ONLY; NO_LEGACY_NEURON_OUTPUTS; NO_MODEL_PROBABILITY_STACKING'
PF=['log_rank','rank_missing','elo','surface_elo','wr10','wr25','wr50','surface_wr20','hold20','break20','spw20','rpw20','matches7','sets7','days_last','log_matches','age','age_missing','height','height_missing','left','hand_missing']
CF=['h2h_a','log_h2h','bo5','hard','clay','grass','other_surface','atp','wta','challenger','other_tour','grand_slam']
SET_RE=re.compile(r'(\d+)\s*[-:]\s*(\d+)')
ELO_I=PF.index('elo'); ELO_LOGIT=math.log(10.0)/400.0

def key(v):
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
    def __init__(self): self.p=defaultdict(lambda:{'h':deque(maxlen=64),'elo':1500.,'se':{},'rank':math.nan,'age':math.nan,'ht':math.nan,'hand':math.nan}); self.h2h={}
    def snap(self,n,d,s,rank=None):
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

def build(raw,swap=True):
    req={'winner_name','loser_name','tourney_date'}
    if raw is None or raw.empty or not req.issubset(raw.columns): raise ValueError('Tenis AI history missing required match columns')
    df=raw.copy(); df['_d']=df.tourney_date.map(date); df=df[df['_d'].notna()].copy(); df['_w']=df.winner_name.map(key); df['_l']=df.loser_name.map(key); df=df[(df._w!='')&(df._l!='')&(df._w!=df._l)]
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
    return (np.asarray(A),np.asarray(B),np.asarray(C),np.asarray(Y),np.asarray(D)),st,{'raw_rows':len(raw),'usable_matches':len(df),'rows':len(Y),'date_min':min(D),'date_max':max(D),'leakage':'STRICT_PRE_DATE; SAME_DAY_RESULTS_APPLIED_AFTER_FEATURISATION'}
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

def train():
    raw,warn,info=load_history(); (A,B,C,Y,D),_,meta=build(raw,True); S=split(D); tr,va,te=S['train'],S['validation'],S['test']; m=Model(); training=m.fit(A[tr],B[tr],C[tr],Y[tr],A[va],B[va],C[va],Y[va]); vp=m.predict(A[va],B[va],C[va]); tp=m.predict(A[te],B[te],C[te])
    elo=lambda mask:1/(1+10**(-((A[mask,ELO_I]-B[mask,ELO_I])/400)))
    vm,tm,ve,te_m=metrics(Y[va],vp),metrics(Y[te],tp),metrics(Y[va],elo(va)),metrics(Y[te],elo(te)); gate={'beats_elo_log_loss':tm['log_loss']<te_m['log_loss'],'beats_elo_accuracy':tm['accuracy']>te_m['accuracy'],'ece_le_0_05':tm['ece_10']<=.05,'test_rows_ge_1000':int(te.sum())>=1000}; gate['passed']=all(gate.values()); now=datetime.now(timezone.utc).isoformat()
    mp={**m.dump(),**flags(),'generated_at':now,'inputs_policy':POLICY,'player_features':PF,'context_features':CF}; write(MODEL,mp)
    report={**flags(),'generated_at':now,'dataset':meta,'source':info,'source_warnings':warn,'splits':{k:int(v.sum()) for k,v in S.items()},'training':training,'validation':vm,'test':tm,'elo_baseline_validation':ve,'elo_baseline_test':te_m,'quality_gate':gate,'promotion_eligible':False,'promotion_reason':'manual architecture and quality review required'}; write(METRICS,report); return report

def current_features(st,m):
    a=key(m.get('p1') or m.get('player1')); b=key(m.get('p2') or m.get('player2'))
    if not a or not b or a==b: raise ValueError('missing players')
    d=date(m.get('scheduled_time') or m.get('start_time') or datetime.now(timezone.utc).date()); d=pd.Timestamp(datetime.now(timezone.utc).date()) if pd.isna(d) else d; s=surface(m.get('surface')); r=dict(m); r['source_tour']=m.get('tour'); r['tourney_level']=m.get('level'); r['best_of']=m.get('best_of') or m.get('bestOf')
    return st.snap(a,d,s,m.get('p1_rank')),st.snap(b,d,s,m.get('p2_rank')),st.context(a,b,r,s)
def current():
    mp=json.loads(MODEL.read_text()); m=Model.load(mp); raw,warn,info=load_history(); _,st,meta=build(raw,False); src=json.loads((DATA/'results.json').read_text()); rows=[]
    if not isinstance(src,list): raise RuntimeError('results.json is not a list')
    for x in src:
        if not isinstance(x,dict): continue
        try: a,b,c=current_features(st,x); p=float(m.predict(a,b,c)[0]); rows.append({'match_id':x.get('match_id') or x.get('id'),'p1':x.get('p1'),'p2':x.get('p2'),'p1_win_probability':round(p,6),'p2_win_probability':round(1-p,6),'status':'SHADOW_SCORE'})
        except Exception as e: rows.append({'match_id':x.get('match_id') or x.get('id'),'status':'NO_SCORE','reason':type(e).__name__})
    out={**flags(),'operator_playable':False,'generated_at':datetime.now(timezone.utc).isoformat(),'source':info,'source_warnings':warn,'history_date_max':meta['date_max'],'matches':rows}; write(CURRENT,out); return out
def audit():
    out={**flags(),'legacy_neuron_inputs_allowed':False,'model_exists':MODEL.exists(),'metrics_exists':METRICS.exists(),'current_exists':CURRENT.exists()}
    if MODEL.exists():
        m=json.loads(MODEL.read_text()); assert m.get('format')=='tenis-ai-neuron-siamese' and m.get('inputs_policy')==POLICY and m.get('production_influence') is False
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['train','current','audit']); a=p.parse_args().action; print(json.dumps(train() if a=='train' else current() if a=='current' else audit(),ensure_ascii=False,indent=2))
