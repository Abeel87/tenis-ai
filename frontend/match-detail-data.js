/* Read-only match detail contract. No probability synthesis or model decisions. */
(()=>{
'use strict';
const D=window.TenisPresentation;
const nameKey=v=>String(v??'').toLowerCase().replaceAll('ł','l').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').match(/[\p{L}\p{N}]+/gu)?.sort().join(' ')||'';
function samePlayer(a,as,b,bs){
 const ai=a[as+'_id'],bi=b[bs+'_id'];
 // When both feeds publish IDs, conflicting identities must not fall back to names.
 if(ai!=null&&bi!=null)return String(ai)===String(bi);
 const an=nameKey(a[as]),bn=nameKey(b[bs]);
 return !!an&&an===bn;
}
function historyRows(rows,m,side,h2h=false){
 const cutoff=Math.min(Date.now(),Date.parse(m.scheduled_time)||Date.now()),seen=new Set();
 return rows.filter(r=>r.result&&!['void','cancelled','canceled','walkover','walk over'].includes(String(r.result.status||'').toLowerCase())&&String(r.match_id??r.id??'')!==String(m.match_id??m.id??'__fixture__')&&Date.parse(r.scheduled_time)<cutoff&&
 (h2h?((samePlayer(m,'p1',r,'p1')&&samePlayer(m,'p2',r,'p2'))||(samePlayer(m,'p1',r,'p2')&&samePlayer(m,'p2',r,'p1'))):['p1','p2'].some(s=>samePlayer(m,side,r,s))))
 .sort((a,b)=>Date.parse(b.scheduled_time)-Date.parse(a.scheduled_time))
 .filter(r=>{const id=r.match_id??r.id??[r.scheduled_time,r.p1,r.p2,r.result.score_text].join('|');if(seen.has(String(id)))return false;seen.add(String(id));return true});
}
function winnerSide(r){
 const winner=r.result?.winner;
 // This contract publishes the winner's full name, never infer from predictions.
 const sides=['p1','p2'].filter(s=>nameKey(winner)&&nameKey(winner)===nameKey(r[s]));
 return sides.length===1?sides[0]:null;
}
function comparison(m){
 const profiles=m.player_intelligence_v85?.profiles||{};
 const row=(label,get,format=D.ratio,lower=false,highlight=true)=>{
  const a=D.num(get('p1')),b=D.num(get('p2'));
  const winner=highlight&&a!=null&&b!=null&&a!==b?((lower?a<b:a>b)?'p1':'p2'):null;
  return {label,a,b,winner,displayA:a==null?'N/D':format(a),displayB:b==null?'N/D':format(b)};
 };
 return [row('Ranking',s=>m[s+'_rank']??m[s+'_stats']?.rank,v=>String(v),true),
 ...[20,10,5].map(n=>row('Forma '+n,s=>profiles[s]?.windows?.[n]?.metrics?.won?.adjusted)),
 row('Forma · indeks',s=>profiles[s]?.indexes?.form,D.score),
 row('Wygrane mecze',s=>m[s+'_stats']?.won),
 row('Serwis · utrzymany',s=>m[s+'_stats']?.hold_rate),
 row('Return · przełamania',s=>m[s+'_stats']?.break_rate),
 row('Return · wygrane punkty',s=>m[s+'_stats']?.return_points_won),
 row('Zmienność serwisu',s=>profiles[s]?.windows?.['10']?.metrics?.hold_rate?.volatility,D.ratio,true),
 ...[1,2,3].map(n=>row('Utrzymany '+n+'. gem serwisowy',s=>m.early_hold_v7?.[s]?.['hold'+n],D.pct)),
 row('Mecze w próbce',s=>m[s+'_stats']?.matches,String,false,false)
 ].filter(r=>r.a!=null||r.b!=null);
}
function assessment(m){
 const p=['p1','p2'].map(s=>D.num(m.match_win?.[m[s]]));
 if(p.every(v=>v!=null&&v>=0&&v<=100))return {p,winner:p[0]===p[1]?null:p[0]>p[1]?'p1':'p2'};
 return {p:null,winner:null};
}
function form(m,side){
 const rows=[20,10,5].map(n=>({n,v:D.num(m.player_intelligence_v85?.profiles?.[side]?.windows?.[n]?.metrics?.won?.adjusted)}));
 const v=rows.map(x=>x.v);
 let trend='N/D';
 if(v.every(x=>x!=null))trend=v.every(x=>x===v[0])?'stabilny':v[0]<=v[1]&&v[1]<=v[2]?'rosnący':v[0]>=v[1]&&v[1]>=v[2]?'spadkowy':'zmienny';
 return {rows,trend};
}
window.TenisMatchDetail={nameKey,samePlayer,historyRows,winnerSide,comparison,assessment,form};
})();