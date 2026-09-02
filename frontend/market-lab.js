/* Tenis AI v7.4.1 — Market Lab */
(() => {
  const e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const p=x=>x==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const pill=(l,v)=>`<div class="ml741-pill"><span>${e(l)}</span><b>${p(v)}</b></div>`;
  const lines=o=>Object.entries(o||{}).map(([ln,x])=>`<div class="ml741-line"><span>${ln}</span>${pill('OVER',x.over)}${pill('UNDER',x.under)}</div>`).join('');
  const best=o=>Object.entries(o||{}).sort((a,b)=>Math.max(b[1].over,b[1].under)-Math.max(a[1].over,a[1].under)).slice(0,6);
  const extra=m=>{
    const l=m.market_lab_v741;if(!l)return '';
    const pg=l.player_total_games||{};
    return `<section class="ml741"><div class="ml741-title"><div><b>🧪 Market Lab v7.4.1</b><small>Rynki z filmu · najpierw walidacja, potem awans do głównego modelu</small></div><span>LAB</span></div>
      <details class="ml741-box"><summary>🎾 1. set · liczba gemów 6.5–12.5 <i>⌄</i></summary><div class="ml741-body">${lines(l.set1_total)}<div class="ml741-grid">${pill('Dokładnie 6 gemów',l.set1_exact_six_games)}${pill('Tie-break w 1. secie',l.set1_tiebreak?.yes)}</div></div></details>
      <details class="ml741-box"><summary>👤 Gemy zawodnika · cały mecz <i>⌄</i></summary><div class="ml741-body"><h4>${e(m.p1)}</h4>${best(pg[m.p1]).map(([ln,x])=>`<div class="ml741-line"><span>${ln}</span>${pill('OVER',x.over)}${pill('UNDER',x.under)}</div>`).join('')}<h4>${e(m.p2)}</h4>${best(pg[m.p2]).map(([ln,x])=>`<div class="ml741-line"><span>${ln}</span>${pill('OVER',x.over)}${pill('UNDER',x.under)}</div>`).join('')}<small>Pełny zakres modelu: 6.5–15.5.</small></div></details>
      <details class="ml741-box"><summary>🔀 Tie-breaki / 3 sety <i>⌄</i></summary><div class="ml741-body ml741-grid">${pill('Tie-break w meczu · TAK',l.match_tiebreak?.yes)}${pill('Obaj wygrają seta · TAK',l.both_players_win_set?.yes)}${Object.entries(l.tiebreak_count||{}).map(([k,v])=>pill(`${k} tie-break`,v)).join('')}</div></details>
      <details class="ml741-box"><summary>🧩 Zwycięzca seta + własne gemy 6.5 <i>⌄</i></summary><div class="ml741-body"><small>Liczone jako jedno wspólne zdarzenie, a nie mnożenie dwóch procentów.</small><h4>1. set</h4><div class="ml741-grid">${pill(`${m.p1} wygra + U6.5`,l.set1_winner_player_games_6_5?.p1?.under)}${pill(`${m.p1} wygra + O6.5`,l.set1_winner_player_games_6_5?.p1?.over)}${pill(`${m.p2} wygra + U6.5`,l.set1_winner_player_games_6_5?.p2?.under)}${pill(`${m.p2} wygra + O6.5`,l.set1_winner_player_games_6_5?.p2?.over)}</div><h4>2. set</h4><div class="ml741-grid">${pill(`${m.p1} wygra + U6.5`,l.set2_winner_player_games_6_5?.p1?.under)}${pill(`${m.p1} wygra + O6.5`,l.set2_winner_player_games_6_5?.p1?.over)}${pill(`${m.p2} wygra + U6.5`,l.set2_winner_player_games_6_5?.p2?.under)}${pill(`${m.p2} wygra + O6.5`,l.set2_winner_player_games_6_5?.p2?.over)}</div></div></details>
      <p class="ml741-foot">Nowe rynki są zamrażane przed meczem w osobnym trackerze. Na razie nie podbijają wyniku 72/80+.</p></section>`;
  };
  function patch(){
    if(typeof window.renderMatchDetail==='function'&&!window.renderMatchDetail.__ml741){
      const old=window.renderMatchDetail;const w=m=>old(m)+extra(m);w.__ml741=true;window.renderMatchDetail=w;
    }
  }
  patch();setTimeout(patch,100);setTimeout(patch,900);
})();