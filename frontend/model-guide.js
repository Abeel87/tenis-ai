/* Tenis AI v8.5.3M — Match Matrix. UI-only; model/tracker math untouched. */
(()=>{
'use strict';
const V='v8.5.3M',n=x=>x==null||x===''||!Number.isFinite(Number(x))?null:Number(x),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim(),key=m=>String(m?.id??m?.match_id??[m?.p1,m?.p2,m?.scheduled_time].join('|')),rows=()=>{try{return Array.isArray(all)?all:[]}catch{return[]}},alias=x=>({match_winner:'match_win',set1_winner:'set1_win',set2_winner:'set2_win',set3_winner:'set3_win'})[String(x||'').toLowerCase()]||String(x||'').toLowerCase();
const css=`#model-switcher,[data-p751-models]{display:none!important}.mm853{margin:.75rem 1rem 1rem;border:1px solid rgba(91,211,239,.2);border-radius:18px;overflow:hidden;background:#03131d}.mm853 header{display:flex;justify-content:space-between;gap:.7rem;padding:.85rem .95rem;border-bottom:1px solid rgba(88,193,220,.13)}.mm853 header div{display:flex;flex-direction:column;gap:.15rem}.mm853 header span{color:#68e7ff;font-size:.68rem;font-weight:900;letter-spacing:.08em}.mm853 header b{color:#f2fbff;font-size:1rem}.mm853 header small{color:#7897a3;font-size:.63rem}.mm853 header em{font-style:normal;color:#baff61;font-size:.6rem}.mm853-legend{display:flex;flex-wrap:wrap;gap:.4rem;padding:.48rem .7rem;background:rgba(14,48,61,.25);color:#7897a3;font-size:.58rem}.mm853-legend b{color:#d8f7ff}.mm853-wrap{overflow-x:auto;overflow-y:visible;max-height:none;scrollbar-gutter:stable}.mm853 table{border-collapse:separate;border-spacing:0;min-width:1360px;width:100%;font-size:.63rem;table-layout:fixed}.mm853 th,.mm853 td{padding:.48rem .4rem;border-right:1px solid rgba(71,161,184,.08);border-bottom:1px solid rgba(71,161,184,.08);text-align:center;white-space:nowrap}.mm853 th{position:sticky;top:0;z-index:4;background:#061923;color:#89b4c3;font-size:.57rem;text-transform:uppercase}.mm853 th:first-child,.mm853 td:first-child{position:sticky;left:0;z-index:3;background:#04151f;text-align:left;min-width:170px}.mm853 th:nth-child(2),.mm853 td:nth-child(2){position:sticky;left:170px;z-index:3;background:#04151f;text-align:left;min-width:125px}.mm853 th:first-child,.mm853 th:nth-child(2){z-index:6;background:#061923}.mm853 .grp td{position:static!important;text-align:left!important;background:rgba(79,212,242,.08)!important;color:#76eaff;font-weight:900;letter-spacing:.07em}.mm853 .sc{display:inline-flex;gap:.18rem;align-items:center;padding:.18rem .28rem;border-radius:6px;color:#9ab2bc;background:rgba(255,255,255,.02)}.mm853 .sc.g{color:#c9ff74}.mm853 .sc.e{color:#adff3d;font-weight:900;background:rgba(159,255,73,.08)}.mm853 .sc small{font-size:.48rem;color:#607f8c}.mm853 .sc em{font-size:.47rem;color:#6ee7ff;font-style:normal}.mm853 .nd{color:#405f6a}.mm853 .pick{color:#d9f1f7;font-weight:700}.mm853 .market{color:#eefbff;font-weight:800}.mm853 .market small{display:block;color:#607f8c;font-weight:500;font-size:.55rem}
.mm853 th:nth-child(n+3),.mm853 td:nth-child(n+3){min-width:72px}
.mm853 th:nth-child(12){color:#d9ff9a;background:#102319;box-shadow:inset 1px 0 rgba(179,255,89,.18),inset -1px 0 rgba(179,255,89,.18)}
.mm853 td:nth-child(12){background:rgba(154,255,67,.035);box-shadow:inset 1px 0 rgba(179,255,89,.08),inset -1px 0 rgba(179,255,89,.08)}
.mm853 th:nth-child(13),.mm853 th:nth-child(14){color:#8be9ff;background:#09202b}
.mm853 td:nth-child(13),.mm853 td:nth-child(14){background:rgba(57,198,230,.025)}
.mm853 th:nth-child(15),.mm853 th:nth-child(16){color:#d8baff;background:#171427}
.mm853 td:nth-child(15),.mm853 td:nth-child(16){background:rgba(170,111,255,.02)}
.mm853 tbody tr:not(.grp):hover td{box-shadow:inset 0 0 0 999px rgba(103,222,255,.018)}
.mm853 tbody tr:not(.grp):hover td:first-child,.mm853 tbody tr:not(.grp):hover td:nth-child(2){background:#071a24}@media(max-width:720px){.mm853{margin-left:.45rem;margin-right:.45rem}.mm853 table{font-size:.59rem;min-width:1240px}.mm853 th,.mm853 td{padding:.44rem .32rem}.mm853 th:first-child,.mm853 td:first-child{min-width:132px;width:132px}.mm853 th:nth-child(2),.mm853 td:nth-child(2){left:132px;min-width:96px;width:96px}.mm853 th:nth-child(n+3),.mm853 td:nth-child(n+3){min-width:72px;width:72px}}`;
let st=document.getElementById('mm853-style');if(!st){st=document.createElement('style');st.id='mm853-style';st.textContent=css;document.head.append(st)}
const state=s=>{const a=String(s||'').split(':').map(Number);return a.length===2&&a.every(Number.isFinite)?a[0]===a[1]?'draw':a[0]>a[1]?'p1_lead':'p2_lead':null},agg=(o,k)=>{const a=Object.entries(o||{}).map(([x,v])=>[x,n(v)]).filter(([,v])=>v!=null),t=a.reduce((z,[,v])=>z+Math.max(0,v),0);return t?a.filter(([x])=>state(x)===k).reduce((z,[,v])=>z+Math.max(0,v),0)/t*100:null},line=s=>{const d=n(s?.line??s?.selected_line??s?.suggested_line);if(d!=null)return String(d);const p=String(s?.key||s?.signal_key||'').split('|');return p.length>1&&/^\d+(\.\d+)?$/.test(p[1])?p[1]:''};
function build(m){const out=[],mp=new Map(),add=r=>{const k=[r.group,r.market,r.pick,r.line||'',r.extra||''].join('|');if(mp.has(k)){const x=mp.get(k);['base','lab','joint'].forEach(f=>{if(n(r[f])!=null)x[f]=r[f]});return x}mp.set(k,r);out.push(r);return r},obj=(g,market,label,o)=>Object.entries(o||{}).forEach(([pick,v])=>{if(n(v)!=null)add({group:g,market,label,pick,base:Number(v)})}),ou=(market,label,o,g='Gemy / O-U',f='base')=>Object.entries(o||{}).forEach(([ln,x])=>{if((market==='set1_total'||market==='set2_total')&&String(ln)==='11.5')return;['over','under'].forEach(p=>{if(n(x?.[p])!=null)add({group:g,market,label:`${label} ${ln}`,pick:p,line:String(ln),[f]:Number(x[p])})})});
obj('Wynik meczu i setów','match_win','Kto wygra mecz',m.match_win);obj('Wynik meczu i setów','set1_win','Kto wygra 1. set',m.first_set_win);obj('Wynik meczu i setów','set2_win','Kto wygra 2. set',m.second_set_win);obj('Wynik meczu i setów','set3_win','Kto wygra 3. set',m.third_set_win);obj('Wynik meczu i setów','total_sets','Liczba setów',m.total_sets);obj('Wynik meczu i setów','exact_match_score','Dokładny wynik',m.exact_match_score);ou('set1_total','1. set · gemy',m.over_under);ou('match_total','Mecz · gemy',m.match_over_under);
['2','4','6'].forEach(g=>{const o=m.game_states?.[g];if(o)[['p1_lead',`${m.p1} prowadzi`],['draw','Remis'],['p2_lead',`${m.p2} prowadzi`]].forEach(([p,d])=>add({group:'Po 2 / 4 / 6 gemach',market:`state${g}`,label:`Po ${g} gemach`,pick:p,displayPick:d,base:agg(o,p),state:true}))});
const l=m.market_lab_v741||{};ou('set1_total','1. set · gemy',l.set1_total,'Gemy / O-U','lab');ou('set2_total','2. set · gemy',l.set2_total,'Gemy / O-U','lab');Object.entries(l.player_total_games||{}).forEach(([pl,o])=>Object.entries(o||{}).forEach(([ln,x])=>['over','under'].forEach(p=>{if(n(x?.[p])!=null)add({group:'Gemy / O-U',market:'player_total_games',label:`${pl} · gemy ${ln}`,pick:p,line:String(ln),extra:pl,lab:Number(x[p])})})));
const yn=(market,label,x)=>{const y=n(x?.yes??x),no=n(x?.no);if(y!=null){add({group:'Rynki specjalne',market,label,pick:'yes',displayPick:'TAK',lab:y});add({group:'Rynki specjalne',market,label,pick:'no',displayPick:'NIE',lab:no??(y<=100?100-y:null)})}};yn('set1_exact_six_games','Dokładnie 6 gemów 1S',l.set1_exact_six_games);yn('set1_tiebreak','Tie-break 1S',l.set1_tiebreak);yn('match_tiebreak','Tie-break w meczu',l.match_tiebreak);yn('both_players_win_set','Obaj wygrają seta',l.both_players_win_set);Object.entries(l.tiebreak_count||{}).forEach(([p,v])=>n(v)!=null&&add({group:'Rynki specjalne',market:'tiebreak_count',label:'Liczba tie-breaków',pick:p,lab:Number(v)}));
const combo=(set,o)=>['p1','p2'].forEach(side=>['under','over'].forEach(p=>{const v=n(o?.[side]?.[p]);if(v!=null)add({group:'Rynki specjalne',market:`${set}_winner_player_games_6_5`,label:`${set==='set1'?'1.':'2.'} set · zwycięzca + gemy`,pick:`${side}|${p}`,displayPick:`${side==='p1'?m.p1:m.p2} + ${p==='under'?'U':'O'}6.5`,lab:v})}));combo('set1',l.set1_winner_player_games_6_5);combo('set2',l.set2_winner_player_games_6_5);
const j=m.joint_builder_v78b;if(j?.status==='READY'){const b=j.best||{},pl=String(b.player||''),side=norm(pl)===norm(m.p1)?'p1':norm(pl)===norm(m.p2)?'p2':null,r=side?j[side]||{}:{};if(side){let x=out.find(q=>q.market==='state6'&&q.pick===`${side}_lead`);if(x)x.joint=n(r.lead_after_6);x=out.find(q=>q.market==='set1_total'&&q.line==='8.5'&&q.pick==='over');if(x)x.joint=n(r.over_8_5_set1);x=out.find(q=>q.market==='set1_win'&&norm(q.pick)===norm(pl));if(x)x.joint=n(r.win_set1)}add({group:'Rynki specjalne',market:'joint_3of3',label:'Joint 3/3',pick:pl||'—',displayPick:`${pl||'—'} · lead6 + O8.5 + win1S`,joint:n(b.joint_all_3)})}return out}
function sets(m){const api=window.TENIS_AI_MODEL_API,ids=['adaptive','early','serve','form','surface'];const out=Object.fromEntries(ids.map(id=>{try{return[id,api?.signalsFor?.(id,m)||[]]}catch{return[id,[]]}}));out.consensus=(m?.specialist_signals_v79b_current||[]).filter(x=>x?.source_model==='consensus');return out}
function match(r,s){if(alias(s?.market)!==alias(r.market))return false;if(r.state)return state(s?.pick)===r.pick;if(r.market==='player_total_games')return false;if(r.line&&line(s)!==String(r.line))return false;return norm(s?.pick)===norm(r.pick)}
const find=(r,a)=>(a||[]).find(s=>match(r,s))||null,auto=(r,m)=>find(r,m?.autolearn_v84?.signals),learn=(r,m)=>find(r,m?.adaptive_learning_v79?.signals),cols=[['adaptive','Adaptive'],['early','Early'],['serve','Serve'],['form','Form'],['surface','Surface'],['consensus','Consensus'],['current','Current'],['catboost','CatBoost'],['tabpfn','TabPFN'],['ensemble','Ensemble'],['learn','Learn SH'],['player','Player SH'],['lab','Lab'],['joint','Joint']];
function val(r,id,s,m){if(id==='adaptive'){if(n(r.base)!=null)return[r.base,'%'];const x=find(r,s.adaptive);return x?[n(x.v),'%',r.state?x.pick:'']:null}if(['early','serve','form','surface','consensus'].includes(id)){const x=find(r,s[id]);const score=n(x?.score??x?.v);return score==null?null:[score,'/100',r.state?x.pick:'']}const a=auto(r,m);if(['current','catboost','tabpfn','ensemble'].includes(id))return n(a?.[id])==null?null:[n(a[id]),'%',id==='ensemble'&&a?.dynamic_weighting?.active?'DYN':''];if(id==='learn')return n(learn(r,m)?.learned_score)==null?null:[n(learn(r,m).learned_score),'/100'];if(id==='player')return n(a?.player_intelligence_v85?.shadow_score)==null?null:[n(a.player_intelligence_v85.shadow_score),'%'];if(id==='lab')return n(r.lab)==null?null:[r.lab,'%'];if(id==='joint')return n(r.joint)==null?null:[r.joint,'%'];return null}
const cell=x=>!x||n(x[0])==null?'<span class="nd">—</span>':`<span class="sc ${x[0]>=80?'e':x[0]>=72?'g':''}"><b>${Number(x[0]).toFixed(1).replace('.0','')}${x[1]}</b>${x[2]?`<small>${esc(x[2])}</small>`:''}</span>`;
function matrix(m){const rr=build(m),s=sets(m),groups=['Wynik meczu i setów','Gemy / O-U','Po 2 / 4 / 6 gemach','Rynki specjalne'];return`<section class="mm853"><header><div><span>📊 MACIERZ RYNKÓW × MODELI</span><b>Każdy rynek tylko raz</b><small>— = dany model tego rynku nie liczy. % i /100 są rozdzielone.</small></div><em>${rr.length} rynków</em></header><div class="mm853-legend"><b>%</b> prawdopodobieństwo · <b>/100</b> siła specjalisty · <b>ENS</b> finalny Ensemble · <b>SH</b> shadow · <b>LAB</b> osobny Market Lab · <b>DYN</b> dynamiczne wagi</div><div class="mm853-wrap"><table><thead><tr><th>Rynek</th><th>Typ</th>${cols.map(x=>`<th>${x[1]}</th>`).join('')}</tr></thead><tbody>${groups.map(g=>{const a=rr.filter(r=>r.group===g);return a.length?`<tr class="grp"><td colspan="${cols.length+2}">${g}</td></tr>`+a.map(r=>`<tr><td><span class="market">${esc(r.label)}${auto(r,m)?.dynamic_weighting?.active?'<small>DYN aktywne</small>':''}</span></td><td><span class="pick">${esc(String(r.displayPick||r.pick).toUpperCase())}</span></td>${cols.map(c=>`<td>${cell(val(r,c[0],s,m))}</td>`).join('')}</tr>`).join(''):''}).join('')}</tbody></table></div></section>`}
function currentMatch(raw){let w=String(raw||'');try{w=decodeURIComponent(w)}catch{}return rows().find(m=>key(m)===w)||null}

/* === V853M3_MODEL_PICKER_START === */
const MM853M3_STORE='tenis-ai-mm853m3-models';
const MM853M3_MAX=5;
const MM853M3_PRIORITY=['Ensemble','Current','Consensus','Early','Player SH','CatBoost','Adaptive','Serve','Form','Surface','Learn SH','Lab','Joint','TabPFN'];

function mm853m3HasData(cell){
  if(!cell)return false;
  const t=String(cell.textContent||'').replace(/\s+/g,' ').trim();
  return !!t && t!=='—' && t!=='-' && t!=='N/D';
}
function mm853m3Saved(){
  try{
    const v=JSON.parse(localStorage.getItem(MM853M3_STORE)||'[]');
    return Array.isArray(v)?v.map(String):[];
  }catch{return[]}
}
function mm853m3Save(v){
  try{localStorage.setItem(MM853M3_STORE,JSON.stringify(v))}catch{}
}
function mm853m3Priority(name){
  const i=MM853M3_PRIORITY.indexOf(name);
  return i<0?999:i;
}
function installPicker(root,m){
  if(!root||root.dataset.mm853m3==='1')return;
  const table=root.querySelector('table');
  const head=[...root.querySelectorAll('thead th')];
  const bodyRows=[...root.querySelectorAll('tbody tr:not(.grp)')];
  if(!table||head.length<3||!bodyRows.length)return;

  root.dataset.mm853m3='1';
  root.classList.add('mm853-m3');

  const models=head.slice(2).map((th,i)=>{
    const name=String(th.textContent||'').trim();
    const col=i+2;
    const coverage=bodyRows.reduce((z,tr)=>z+(mm853m3HasData(tr.children[col])?1:0),0);
    return {name,col,coverage};
  });

  let selected=mm853m3Saved()
    .filter(name=>models.some(x=>x.name===name&&x.coverage>0))
    .slice(0,MM853M3_MAX);

  function autoPick(){
    const sorted=[...models].filter(x=>x.coverage>0).sort((a,b)=>{
      const pa=mm853m3Priority(a.name),pb=mm853m3Priority(b.name);
      return b.coverage-a.coverage || pa-pb || a.name.localeCompare(b.name);
    });
    selected=sorted.slice(0,MM853M3_MAX).map(x=>x.name);
    mm853m3Save(selected);
  }
  if(!selected.length)autoPick();

  const controls=document.createElement('section');
  controls.className='mm853m3-controls';
  controls.innerHTML=`
    <div class="mm853m3-copy">
      <b>Modele w tabeli <span data-mm853m3-count></span></b>
      <small>Wybierz maks. ${MM853M3_MAX}. Liczba przy modelu = ile rynków ma dane.</small>
    </div>
    <div class="mm853m3-actions">
      <button type="button" data-mm853m3-auto>AUTO 5 · NAJWIĘCEJ DANYCH</button>
      <label><input type="checkbox" data-mm853m3-empty> Pokaż rynki bez danych / niepełne</label>
    </div>
    <div class="mm853m3-chips"></div>
    <div class="mm853m3-note" data-mm853m3-note></div>`;
  const legend=root.querySelector('.mm853-legend');
  (legend||root.querySelector('header'))?.insertAdjacentElement('afterend',controls);

  const chipbox=controls.querySelector('.mm853m3-chips');
  const note=controls.querySelector('[data-mm853m3-note]');
  const emptyToggle=controls.querySelector('[data-mm853m3-empty]');
  let showEmpty=false;

  function drawChips(){
    chipbox.innerHTML=models.map(x=>{
      const on=selected.includes(x.name);
      const zero=x.coverage===0;
      return `<button type="button"
        class="${on?'on':''} ${zero?'zero':''}"
        data-mm853m3-model="${esc(x.name)}"
        ${zero?'disabled':''}
        title="${zero?'Brak danych dla tego meczu':`${x.coverage}/${bodyRows.length} rynków ma dane`}">
        <span>${esc(x.name)}</span><b>${x.coverage}/${bodyRows.length}</b>
      </button>`;
    }).join('');
    const c=controls.querySelector('[data-mm853m3-count]');
    if(c)c.textContent=`${selected.length}/${MM853M3_MAX}`;
  }

  function apply(){
    const selectedCols=new Set(models.filter(x=>selected.includes(x.name)).map(x=>x.col));

    models.forEach(x=>{
      const hide=!selectedCols.has(x.col);
      head[x.col].style.display=hide?'none':'';
      bodyRows.forEach(tr=>{
        if(tr.children[x.col])tr.children[x.col].style.display=hide?'none':'';
      });
    });

    root.querySelectorAll('tbody tr.grp td').forEach(td=>{
      td.colSpan=2+selectedCols.size;
    });

    let visible=0;
    const selectedList=[...selectedCols];
    bodyRows.forEach(tr=>{
      const filled=selectedList.reduce((z,col)=>z+(mm853m3HasData(tr.children[col])?1:0),0);
      const complete=selectedList.length>0 && filled===selectedList.length;
      const hide=showEmpty ? false : !complete;
      tr.style.display=hide?'none':'';
      tr.dataset.mm853m3Coverage=`${filled}/${selectedList.length}`;
      if(!hide)visible++;
    });

    const all=[...root.querySelectorAll('tbody tr')];
    all.forEach((tr,i)=>{
      if(!tr.classList.contains('grp'))return;
      let has=false;
      for(let j=i+1;j<all.length&&!all[j].classList.contains('grp');j++){
        if(all[j].style.display!=='none'){has=true;break}
      }
      tr.style.display=has||showEmpty?'':'none';
    });

    table.style.minWidth='100%';
    table.style.width='max-content';
    table.style.tableLayout='auto';

    const total=root.querySelector('header em');
    if(total)total.textContent=`${visible}/${bodyRows.length} widocznych`;

    note.textContent=selected.length
      ? `Pokazujesz: ${selected.join(' · ')} · bez checkboxa tylko pełne ${selected.length}/${selected.length}`
      : 'Wybierz przynajmniej 1 model z danymi.';
    drawChips();
  }

  chipbox.addEventListener('click',e=>{
    const b=e.target.closest('[data-mm853m3-model]');
    if(!b||b.disabled)return;
    const name=b.dataset.mm853m3Model;
    if(selected.includes(name)){
      selected=selected.filter(x=>x!==name);
    }else{
      if(selected.length>=MM853M3_MAX){
        note.textContent=`Maksymalnie ${MM853M3_MAX} modeli. Odznacz jeden i wybierz inny.`;
        note.classList.add('warn');
        setTimeout(()=>note.classList.remove('warn'),900);
        return;
      }
      selected=[...selected,name];
    }
    mm853m3Save(selected);
    apply();
  });

  controls.querySelector('[data-mm853m3-auto]').addEventListener('click',()=>{
    autoPick();
    apply();
  });

  emptyToggle.addEventListener('change',()=>{
    showEmpty=!!emptyToggle.checked;
    apply();
  });

  drawChips();
  apply();
}

const MM853M3_STYLE=`
.mm853-m3 .mm853-wrap{overflow-x:auto!important;overflow-y:visible!important;max-height:none!important}
.mm853-m3 table{min-width:100%!important;width:max-content!important;table-layout:auto!important}
.mm853-m3 th:first-child,.mm853-m3 td:first-child,
.mm853-m3 th:nth-child(2),.mm853-m3 td:nth-child(2){
  position:static!important;left:auto!important;z-index:auto!important
}
.mm853-m3 th:first-child,.mm853-m3 td:first-child{min-width:118px!important;width:118px!important;max-width:118px!important}
.mm853-m3 th:nth-child(2),.mm853-m3 td:nth-child(2){min-width:92px!important;width:92px!important;max-width:92px!important}
.mm853-m3 th:nth-child(n+3),.mm853-m3 td:nth-child(n+3){min-width:88px!important;width:88px!important}
.mm853-m3 td:first-child .market,.mm853-m3 td:nth-child(2) .pick{display:block!important;white-space:normal!important;line-height:1.16!important}
.mm853-m3 td:first-child,.mm853-m3 td:nth-child(2){white-space:normal!important}
.mm853m3-controls{padding:.62rem .72rem;border-bottom:1px solid rgba(74,186,214,.13);background:rgba(5,24,34,.82)}
.mm853m3-copy{display:flex;align-items:baseline;gap:.55rem;flex-wrap:wrap}
.mm853m3-copy b{color:#eafbff;font-size:.72rem}.mm853m3-copy b span{color:#baff61}
.mm853m3-copy small{color:#6f8d99;font-size:.58rem}
.mm853m3-actions{display:flex;align-items:center;gap:.75rem;margin-top:.45rem}
.mm853m3-actions button{border:1px solid rgba(173,255,77,.28);background:rgba(133,255,52,.08);color:#c8ff81;border-radius:8px;padding:.35rem .55rem;font-size:.6rem;font-weight:900;cursor:pointer}
.mm853m3-actions label{color:#7898a5;font-size:.6rem}
.mm853m3-chips{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.5rem}
.mm853m3-chips button{display:flex;align-items:center;gap:.35rem;border:1px solid rgba(74,183,211,.15);background:#071b25;color:#89aab7;border-radius:999px;padding:.3rem .48rem;font-size:.59rem;cursor:pointer}
.mm853m3-chips button b{font-size:.52rem;color:#607f8b}
.mm853m3-chips button.on{border-color:rgba(176,255,78,.45);background:rgba(133,255,52,.09);color:#e4ffc2}
.mm853m3-chips button.on b{color:#baff61}
.mm853m3-chips button.zero{opacity:.32;cursor:not-allowed}
.mm853m3-note{margin-top:.4rem;min-height:.75rem;color:#6f8f9b;font-size:.56rem}
.mm853m3-note.warn{color:#ffcf78}
@media(max-width:720px){
  .mm853m3-actions{align-items:flex-start;flex-direction:column;gap:.4rem}
  .mm853-m3 th:first-child,.mm853-m3 td:first-child{min-width:108px!important;width:108px!important;max-width:108px!important}
  .mm853-m3 th:nth-child(2),.mm853-m3 td:nth-child(2){min-width:82px!important;width:82px!important;max-width:82px!important}
  .mm853-m3 th:nth-child(n+3),.mm853-m3 td:nth-child(n+3){min-width:82px!important;width:82px!important}
}`;
if(!document.getElementById('mm853m3-style')){
  const s=document.createElement('style');
  s.id='mm853m3-style';
  s.textContent=MM853M3_STYLE;
  document.head.append(s);
}
/* === V853M3_MODEL_PICKER_END === */

function tidy(m){const screen=document.querySelector('.p751-detail-screen');if(!screen)return;screen.querySelector('#eh771-match-compare')?.remove();screen.querySelectorAll('[data-p751-models]').forEach(x=>x.remove());screen.querySelector('.p751-verdict')?.remove();screen.querySelector('.v79-live-panel')?.remove();const list=screen.querySelector('.p751-acc-list');if(list){const keep=[...list.querySelectorAll('[data-p751-lazy78e23="stats"],[data-p751-lazy78e23="analytics"],[data-p751-lazy78e23="serve"]')];list.innerHTML='';list.append(...keep);const mat=document.createElement('div');mat.innerHTML=matrix(m);const matrixEl=mat.firstElementChild;list.before(matrixEl);installPicker(matrixEl,m)}[0,80,300].forEach(ms=>setTimeout(()=>{screen.querySelector('.v79-live-panel')?.remove();const pi=screen.querySelector('[data-pi851-detail]'),mat=screen.querySelector('.mm853');if(pi&&mat&&pi.previousElementSibling!==mat)mat.after(pi)},ms))}
function afterOpen(e){const t=e.target?.closest?.('[data-p751-open]');if(!t||e.target?.closest?.('.v762-player-link'))return;if(e.type==='keydown'&&e.key!=='Enter'&&e.key!==' ')return;const m=currentMatch(t.getAttribute('data-p751-open'));if(m)setTimeout(()=>tidy(m),0)}
document.addEventListener('click',afterOpen);document.addEventListener('keydown',afterOpen);function clean(){document.querySelector('#model-switcher')?.remove();document.querySelectorAll('[data-p751-models]').forEach(x=>x.remove())}clean();setTimeout(clean,300);setTimeout(clean,1200);window.TENIS_AI_MATCH_MATRIX_V853M={version:V,matrix,tidy};
})();
