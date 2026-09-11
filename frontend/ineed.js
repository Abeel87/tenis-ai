(()=>{
'use strict';
const A=()=>window.TenisAccount;
const staff=()=>A()?.authenticated&&['admin','moderator'].includes(A()?.role);
const admin=()=>A()?.authenticated&&A()?.role==='admin';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const money=v=>`${n(v).toFixed(2)} PLN`;
const pct=(v,d=1)=>v==null?'—':`${(n(v)*100).toFixed(d)}%`;
const pp=v=>v==null?'—':`${n(v).toFixed(1)} pp`;
const dt=v=>v?new Date(v).toLocaleString('pl-PL'):'—';
let rendering=false;
function nav(){
  const bar=document.querySelector('#bottom-nav');if(!bar)return;
  const old=bar.querySelector('[data-ineed-nav]');
  if(!staff()){old?.remove();bar.classList.remove('ineed-staff-nav');return}
  if(!old){const a=document.createElement('a');a.href='#ineed';a.dataset.ineedNav='1';a.innerHTML='<span aria-hidden="true">💰</span>iNeed$';bar.insertBefore(a,bar.lastElementChild)}
  bar.classList.add('ineed-staff-nav');
}
async function load(){
  const c=A().client;
  const {data:exp,error}=await c.from('ineed_experiments').select('*').eq('status','ACTIVE').maybeSingle();if(error)throw error;
  if(!exp)return{exp:null,signals:[],bets:[],ledger:[],health:null};
  const [s,b,l,h]=await Promise.all([
    c.from('ineed_signals').select('*').eq('experiment_id',exp.id).order('updated_at',{ascending:false}).limit(80),
    c.from('ineed_shadow_bets').select('*').eq('experiment_id',exp.id).order('placed_at',{ascending:false}).limit(80),
    c.from('ineed_bankroll_ledger').select('*').eq('experiment_id',exp.id).order('created_at',{ascending:true}).limit(500),
    c.from('ineed_runtime_health').select('*').eq('experiment_id',exp.id).maybeSingle()
  ]);
  for(const r of [s,b,l,h])if(r.error)throw r.error;
  return{exp,signals:s.data||[],bets:b.data||[],ledger:l.data||[],health:h.data||null};
}
function chart(ledger,start){
  const pts=[{v:n(start)},...ledger.map(x=>({v:n(x.bankroll_after)}))];
  if(pts.length<2)return'<div class="ineed-empty">Wykres pojawi się po pierwszej zmianie bankrollu.</div>';
  const vals=pts.map(x=>x.v),min=Math.min(...vals),max=Math.max(...vals),span=Math.max(1,max-min),w=760,h=180,p=14;
  const xy=pts.map((x,i)=>`${p+i*(w-2*p)/Math.max(1,pts.length-1)},${h-p-(x.v-min)*(h-2*p)/span}`).join(' ');
  return`<svg class="ineed-chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="Bankroll"><polyline fill="none" stroke="currentColor" stroke-width="3" points="${xy}"/></svg>`;
}
function signalCard(s){
  const snap=s.current_snapshot||{},status=String(s.status||''),cls=status==='QUALIFIED'||status==='PENDING'?'qualified':status==='WIN'?'win':status==='LOSS'?'loss':'rejected';
  return`<article class="ineed-card ineed-signal"><div class="main"><span class="ineed-pill ${cls}">${esc(status)}</span><strong>${esc(snap.p1||s.match_id)} — ${esc(snap.p2||'')}</strong><div class="ineed-muted">${esc(s.market)} · ${esc(s.selection||'—')}${s.reason_code?` · ${esc(s.reason_code)}`:''}</div></div><div><span class="ineed-label">Kurs</span><strong>${s.odds??'—'}</strong></div><div><span class="ineed-label">Model</span><strong>${pct(s.model_probability)}</strong></div><div><span class="ineed-label">NET EV</span><strong class="${n(s.expected_value_net)>0?'ineed-good':''}">${pct(s.expected_value_net)}</strong></div><div><span class="ineed-label">Edge</span><strong>${pp(s.edge_probability_points)}</strong></div><div><span class="ineed-label">Stawka</span><strong>${s.final_stake==null?'—':money(s.final_stake)}</strong></div>${admin()?`<div class="ineed-tech" style="grid-column:1/-1">fair ${s.fair_odds??'—'} · break-even ${pct(s.break_even_probability)} · no-vig ${pct(s.no_vig_probability)} · confidence ${s.confidence??'—'} · quote ${dt(s.odds_timestamp)}</div>`:''}</article>`;
}
function betCard(b){const s=b.placement_snapshot||{};return`<article class="ineed-card ineed-signal"><div class="main"><span class="ineed-pill ${String(b.status).toLowerCase()}">${esc(b.status)}</span><strong>${esc(s.p1||b.match_id)} — ${esc(s.p2||'')}</strong><div class="ineed-muted">${esc(b.market)} · ${esc(b.selection||'—')} · ${dt(b.placed_at)}</div></div><div><span class="ineed-label">Kurs</span><strong>${b.odds}</strong></div><div><span class="ineed-label">Stawka</span><strong>${money(b.stake)}</strong></div><div><span class="ineed-label">Wypłata</span><strong>${b.payout==null?'—':money(b.payout)}</strong></div><div><span class="ineed-label">P/L</span><strong>${b.net_profit==null?'—':money(b.net_profit)}</strong></div><div><span class="ineed-label">Bankroll po</span><strong>${b.bankroll_after==null?'—':money(b.bankroll_after)}</strong></div></article>`}
function milestones(equity){const marks=[250,300,500,1000,2500,5000,10000,25000,100000,500000,1000000],next=marks.find(x=>x>equity)||1000000,p=Math.min(100,equity/next*100);return`<div class="ineed-card"><span class="ineed-label">ROAD TO 1,000,000</span><strong>${money(equity)}</strong><div class="ineed-muted">Następny kamień: ${money(next)}</div><div class="ineed-bar"><i style="width:${p}%"></i></div></div>`}
async function newExperiment(){if(!admin())return;if(!confirm('Zamknąć obecny eksperyment i rozpocząć nowy? Otwarte zakłady blokują reset.'))return;const{error}=await A().client.rpc('ineed_admin_start_experiment',{next_name:null,config_override:null});if(error){alert(error.message);return}alert('Nowy eksperyment uruchomiony.');render()}
async function render(){
  nav();if(location.hash!=='#ineed')return;if(!staff()){location.hash='#start';return}if(rendering)return;rendering=true;
  const app=document.querySelector('#app');if(!app){rendering=false;return}app.innerHTML='<div class="ineed-page"><div class="ineed-empty">Ładowanie iNeed$…</div></div>';
  try{
    const d=await load();if(!d.exp){app.innerHTML='<div class="ineed-page"><div class="ineed-empty">Brak aktywnego eksperymentu iNeed$.</div></div>';return}
    const cfg=d.exp.config||{},open=d.bets.filter(x=>['PENDING','SHADOW_PLACED'].includes(x.status)),settled=d.bets.filter(x=>['WIN','LOSS','VOID','CANCELLED','SETTLED'].includes(x.status));
    const available=d.ledger.length?n(d.ledger[d.ledger.length-1].bankroll_after):n(d.exp.starting_bankroll),exposure=open.reduce((a,b)=>a+n(b.stake),0),equity=available+exposure;
    const peak=Math.max(n(d.exp.starting_bankroll),equity,...settled.map(x=>n(x.bankroll_after))),dd=peak?Math.max(0,(peak-equity)/peak):0,pl=equity-n(d.exp.starting_bankroll),roi=n(d.exp.starting_bankroll)?pl/n(d.exp.starting_bankroll):0;
    const today=new Date().toISOString().slice(0,10),todaySignals=d.signals.filter(x=>String(x.first_seen_at||'').startsWith(today)).length;
    app.innerHTML=`<div class="ineed-page"><div class="ineed-head"><div><div class="ineed-kicker">SHADOW · SUPERBET.PL</div><h1>💰 iNeed$</h1><div class="ineed-muted">${esc(d.exp.name)} · ${esc(d.exp.config_version)}</div></div><div class="ineed-actions">${admin()?'<button id="ineed-new" class="ineed-btn">Nowy eksperyment</button>':''}<a class="ineed-btn primary" href="#symphony">Symfonia 2.0</a></div></div><div class="ineed-grid"><div class="ineed-card"><span class="ineed-label">Bankroll</span><strong>${money(equity)}</strong><span class="${pl>=0?'ineed-good':'ineed-bad'}">${pl>=0?'+':''}${money(pl)}</span></div><div class="ineed-card"><span class="ineed-label">ROI</span><strong>${pct(roi)}</strong><span class="ineed-muted">Start ${money(d.exp.starting_bankroll)}</span></div><div class="ineed-card"><span class="ineed-label">Ekspozycja</span><strong>${money(exposure)}</strong><span class="ineed-muted">Dostępne ${money(available)}</span></div><div class="ineed-card"><span class="ineed-label">Drawdown</span><strong>${pct(dd)}</strong><span class="ineed-muted">Peak ${money(peak)}</span></div><div class="ineed-card"><span class="ineed-label">Sygnały dziś</span><strong>${todaySignals}</strong></div><div class="ineed-card"><span class="ineed-label">Otwarte</span><strong>${open.length}</strong></div><div class="ineed-card"><span class="ineed-label">Rozliczone</span><strong>${settled.length}</strong></div><div class="ineed-card"><span class="ineed-label">Runtime</span><strong>${esc(d.health?.status||'—')}</strong><span class="ineed-muted">${dt(d.health?.last_sync_at)}</span></div></div><div class="ineed-section"><h2>Bankroll</h2><div class="ineed-card">${chart(d.ledger,d.exp.starting_bankroll)}</div></div><div class="ineed-section"><h2>Cel</h2>${milestones(equity)}</div><div class="ineed-section"><h2>Aktywne sygnały</h2><div class="ineed-signals">${d.signals.filter(x=>['QUALIFIED','PENDING'].includes(x.status)).map(signalCard).join('')||'<div class="ineed-empty ineed-card">Brak aktywnych sygnałów. NO BET jest poprawnym wynikiem.</div>'}</div></div><div class="ineed-section"><h2>Historia zakładów SHADOW</h2><div class="ineed-signals">${d.bets.map(betCard).join('')||'<div class="ineed-empty ineed-card">Jeszcze brak zakładów SHADOW.</div>'}</div></div><div class="ineed-section"><h2>Odrzucone / wygasłe</h2><div class="ineed-signals">${d.signals.filter(x=>['REJECTED','EXPIRED'].includes(x.status)).slice(0,30).map(signalCard).join('')||'<div class="ineed-empty ineed-card">Brak odrzuconych sygnałów.</div>'}</div></div>${admin()?`<div class="ineed-section"><h2>Diagnostyka admina</h2><div class="ineed-card ineed-health"><span class="ineed-pill">${esc(d.health?.status||'—')}</span><span>ostatni sync: ${dt(d.health?.last_sync_at)}</span><span>Kelly ${cfg.fractional_kelly??'—'}</span><span>EV min ${pct(cfg.minimum_net_ev)}</span><span>edge min ${cfg.minimum_edge_pp??'—'} pp</span><span>single cap ${pct(cfg.max_single_bet_pct)}</span><span>total cap ${pct(cfg.max_total_exposure_pct)}</span></div></div>`:''}</div>`;
    document.querySelector('#ineed-new')?.addEventListener('click',newExperiment);
  }catch(e){app.innerHTML=`<div class="ineed-page"><div class="ineed-card ineed-bad">Nie udało się wczytać iNeed$: ${esc(e.message||e)}</div></div>`}finally{rendering=false}
}
window.addEventListener('tenis-auth',()=>{nav();setTimeout(render,0)});window.addEventListener('hashchange',()=>setTimeout(render,0));document.addEventListener('DOMContentLoaded',()=>{nav();setTimeout(render,0)});setTimeout(()=>{nav();render()},300);
})();
