/* Tenis AI v7.5.3 — Readability + full-match games
   Adds a dedicated whole-match game totals section to every match that has
   match_over_under data, plus a compact preview on the match card.
*/
(() => {
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>x==null||!Number.isFinite(Number(x))?null:Number(x);
  const pct=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const mkey=m=>String(m?.id ?? m?.match_id ?? [m?.p1,m?.p2,m?.scheduled_time].join('|'));

  function bestTotal(m){
    const entries=Object.entries(m?.match_over_under||{}).map(([line,x])=>{
      const o=num(x?.over),u=num(x?.under);
      if(o==null||u==null)return null;
      const side=o>=u?'OVER':'UNDER', value=Math.max(o,u);
      return {line,side,value,over:o,under:u};
    }).filter(Boolean);
    if(!entries.length)return null;
    return entries.sort((a,b)=>b.value-a.value)[0];
  }

  function decorateCards(){
    if(!Array.isArray(window.all))return;
    document.querySelectorAll('.p751-match-card[data-p751-open]').forEach(card=>{
      if(card.querySelector('.p753-match-total-preview'))return;
      let raw='';
      try{raw=decodeURIComponent(card.dataset.p751Open||'')}catch{raw=card.dataset.p751Open||''}
      const m=window.all.find(x=>mkey(x)===raw);
      if(!m)return;
      const best=bestTotal(m);
      const expected=num(m.expected_match_games);
      const box=document.createElement('div');
      box.className='p753-match-total-preview';
      box.innerHTML=best
        ? `<span>📊 Gemy · cały mecz</span><b>${best.side} ${esc(best.line)}</b><strong>${Math.round(best.value)}%</strong>${expected!=null?`<em>śr. ${expected.toFixed(1)}</em>`:''}`
        : `<span>📊 Gemy · cały mecz</span><b>N/D</b>`;
      const footer=card.querySelector('footer');
      if(footer)card.insertBefore(box,footer); else card.appendChild(box);
    });
  }

  function wholeMatchTotalsHtml(m){
    const lines=Object.entries(m?.match_over_under||{});
    const expected=num(m?.expected_match_games);
    if(!lines.length){
      return `<details class="p751-acc p753-match-games">
        <summary><div><span>📊</span><b>Liczba gemów · cały mecz</b><small>linie O/U całego spotkania</small></div><em>N/D</em><i>⌄</i></summary>
        <div class="p751-acc-body"><p class="p751-note">Brak wiarygodnej symulacji liczby gemów dla tego meczu.</p></div>
      </details>`;
    }
    return `<details class="p751-acc p753-match-games" open>
      <summary><div><span>📊</span><b>Liczba gemów · cały mecz</b><small>${expected!=null?`oczekiwane ok. ${expected.toFixed(1)} gema`:'pełny mecz · BO3'}</small></div><em>MECZ</em><i>⌄</i></summary>
      <div class="p751-acc-body">
        <div class="p753-match-games-head"><span>Linia</span><span>OVER</span><span>UNDER</span></div>
        ${lines.map(([line,x])=>{
          const o=num(x?.over),u=num(x?.under),best=Math.max(o||0,u||0);
          return `<div class="p753-match-games-row ${best>=72?'strong':''}">
            <b>${esc(line)}</b>
            <span class="${(o||0)>=(u||0)?'best':''}">O ${pct(o)}</span>
            <span class="${(u||0)>(o||0)?'best':''}">U ${pct(u)}</span>
          </div>`;
        }).join('')}
        <p class="p753-market-help">To są gemy w <b>całym meczu</b>, nie tylko w 1. secie.</p>
      </div>
    </details>`;
  }

  function findOpenMatch(){
    const overlay=document.querySelector('#p751-match-overlay');
    if(!overlay || overlay.hidden || !Array.isArray(window.all))return null;
    const names=[...overlay.querySelectorAll('.p751-matchup>b')].map(x=>x.textContent.trim());
    if(names.length<2)return null;
    return window.all.find(m=>String(m.p1)===names[0]&&String(m.p2)===names[1])||null;
  }

  function decorateDetail(){
    const overlay=document.querySelector('#p751-match-overlay');
    if(!overlay || overlay.hidden || overlay.querySelector('.p753-match-games'))return;
    const m=findOpenMatch();
    if(!m)return;
    const list=overlay.querySelector('.p751-acc-list');
    if(!list)return;
    const first=list.querySelector('.p751-acc');
    if(first)first.insertAdjacentHTML('afterend',wholeMatchTotalsHtml(m));
    else list.insertAdjacentHTML('afterbegin',wholeMatchTotalsHtml(m));
  }

  function refresh(){
    decorateCards();
    decorateDetail();
  }

  // Wrap main renderer so card game totals are restored after every filter/render.
  const hook=()=>{
    if(typeof window.renderMatches==='function'&&!window.renderMatches.__v753){
      const old=window.renderMatches;
      const wrapped=function(...args){
        const r=old.apply(this,args);
        setTimeout(decorateCards,0);
        return r;
      };
      wrapped.__v753=true;
      window.renderMatches=wrapped;
    }
  };

  // Any click opening a match is followed by detail decoration.
  document.addEventListener('click',e=>{
    if(e.target.closest?.('[data-p751-open]'))setTimeout(decorateDetail,30);
  },true);

  // Covers first load / route changes without expensive observers.
  hook();
  setTimeout(()=>{hook();refresh()},250);
  setTimeout(refresh,900);
  setInterval(refresh,1800);
})();