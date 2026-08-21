/* Tenis AI v7.7.1 — Hold Paths + clear player/match scope */
(() => {
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>x==null||!Number.isFinite(Number(x))?null:Number(x);
  const pc=x=>num(x)==null?'—':`${Number(x).toFixed(1).replace('.0','')}%`;
  const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim();
  const safeAll=()=>{try{return Array.isArray(all)?all:[]}catch{return []}};

  function findMatch(p1,p2){
    const a=norm(p1),b=norm(p2);
    return safeAll().find(m=>
      (norm(m.p1)===a&&norm(m.p2)===b) ||
      (norm(m.p1)===b&&norm(m.p2)===a)
    )||null;
  }

  function fallbackBreakdown(m,games){
    const e=m?.early_hold_v7||{};
    const total=num(m?.game_states?.[String(games)]?.[`${games/2}:${games/2}`]);
    const a=(e.p1_service_holds||[]).map(x=>num(x)/100);
    const b=(e.p2_service_holds||[]).map(x=>num(x)/100);
    const k=games/2;
    if(total==null||a.length<k||b.length<k||[...a.slice(0,k),...b.slice(0,k)].some(x=>!Number.isFinite(x)))return null;
    const clean=[...a.slice(0,k),...b.slice(0,k)].reduce((z,x)=>z*x,1)*100;
    const withBreaks=Math.max(0,total-clean);
    return {
      games,
      state:`${k}:${k}`,
      total:Math.round(total*10)/10,
      clean_holds:Math.round(clean*10)/10,
      with_breaks:Math.round(withBreaks*10)/10,
      break_break:games===2?Math.round(withBreaks*10)/10:null
    };
  }

  function breakdown(m,games){
    const x=m?.early_hold_v7?.checkpoint_breakdown?.[String(games)];
    if(x){
      return {
        games,
        state:x.state||`${games/2}:${games/2}`,
        total:num(x.total),
        clean_holds:num(x.clean_holds),
        with_breaks:num(x.with_breaks),
        break_break:num(x.break_break)
      };
    }
    return fallbackBreakdown(m,games);
  }

  function holdChips(name,seq,base){
    const x=(seq||[]).slice(0,3);
    return `<article class="eh771-player">
      <header><span>DANE ZAWODNIKA</span><b>${esc(name||'—')}</b></header>
      <div class="eh771-holds">
        ${[0,1,2].map(i=>`<span>Hold #${i+1}<b>${pc(x[i])}</b></span>`).join('')}
      </div>
      <small>${base!=null?`Średni hold po połączeniu danych: ${pc(base)}`:'PBP + model serwis/return'}</small>
    </article>`;
  }

  function pathRow(x){
    if(!x)return '';
    const cleanLabel=x.games===2?'HOLD–HOLD':`${x.games} CZYSTYCH HOLDÓW`;
    const breakLabel=x.games===2?'BREAK–BREAK':'Z PRZEŁAMANIAMI';
    return `<article class="eh771-path">
      <header><b>${esc(x.state)} po ${x.games} gemach</b><strong>${pc(x.total)}</strong></header>
      <div>
        <span class="clean">🟢 ${cleanLabel}<b>${pc(x.clean_holds)}</b></span>
        <span class="breaks">🟠 ${breakLabel}<b>${pc(x.games===2?(x.break_break??x.with_breaks):x.with_breaks)}</b></span>
      </div>
    </article>`;
  }

  function compareHtml(m){
    const e=m?.early_hold_v7||{};
    if(!e.ready)return `<section id="eh771-match-compare" class="eh771-box nd">
      <div class="eh771-title"><div><span>PORÓWNANIE MECZU</span><b>${esc(m.p1)} vs ${esc(m.p2)}</b></div><em>N/D PBP</em></div>
      <p>Brakuje minimum 5 wiarygodnych meczów PBP dla któregoś zawodnika. Nie rozbijamy 1:1 / 2:2 / 3:3 na czyste holdy na siłę.</p>
    </section>`;

    const b2=breakdown(m,2),b4=breakdown(m,4),b6=breakdown(m,6);
    const base=m.service_model||{};
    return `<section id="eh771-match-compare" class="eh771-box">
      <div class="eh771-title">
        <div><span>PORÓWNANIE MECZU · EARLY HOLD</span><b>${esc(m.p1)} <i>vs</i> ${esc(m.p2)}</b></div>
        <em>PBP OK</em>
      </div>
      <p class="eh771-explain"><b>Jak model łączy zawodników:</b> gdy serwuje ${esc(m.p1)}, jego serwis jest zestawiany z returnem ${esc(m.p2)}; gdy serwuje ${esc(m.p2)} — odwrotnie. Następnie dokładamy PBP 1./2./3. własnego gema. Gdy kolejność pierwszego serwisu nie jest znana przed meczem, liczymy oba warianty po 50%.</p>
      <div class="eh771-players">
        ${holdChips(m.p1,e.p1_service_holds,base.p1_hold)}
        ${holdChips(m.p2,e.p2_service_holds,base.p2_hold)}
      </div>
      <div class="eh771-paths">
        ${pathRow(b2)}${pathRow(b4)}${pathRow(b6)}
      </div>
      <div class="eh771-legend"><b>Ważne:</b> główne „1:1 / 2:2 / 3:3” to prawdopodobieństwo <u>samego stanu wyniku</u>. Teraz osobno pokazujemy, jaka część pochodzi z czystych holdów, a jaka ze ścieżek z przełamaniami.</div>
    </section>`;
  }

  function currentOverlayMatch(){
    const o=$('#p751-match-overlay');
    if(!o||o.hidden)return null;
    const names=$$('.p751-matchup > b',o).map(x=>x.textContent.trim()).filter(Boolean);
    if(names.length>=2)return findMatch(names[0],names[1]);
    return null;
  }

  function decorateOverlay(){
    const o=$('#p751-match-overlay');
    if(!o||o.hidden||$('#eh771-match-compare',o))return;
    const m=currentOverlayMatch();if(!m)return;
    const matchup=$('.p751-matchup',o);
    const acc=$('.p751-acc',o);
    const host=matchup||acc;
    if(!host)return;
    host.insertAdjacentHTML(matchup?'afterend':'beforebegin',compareHtml(m));
  }

  function decoratePlayerProfile(){
    const panel=$('#player-profile-panel');
    if(!panel||panel.hidden)return;
    const name=($('#player-search-input')?.value||$('.player-profile-name h2',panel)?.textContent||'').trim();
    if(!name)return;

    const nameBox=$('.player-profile-name > div:last-child',panel);
    if(nameBox&&!$('.eh771-player-scope',nameBox)){
      nameBox.insertAdjacentHTML('afterbegin',`<span class="eh771-player-scope">👤 DANE ZAWODNIKA · ${esc(name)}</span>`);
    }

    const pro=$('#player-analytics-v76',panel);
    if(pro){
      const head=$('.pa76-head > div',pro);
      if(head){
        let scope=$('.eh771-pro-scope',head);
        if(!scope){
          head.insertAdjacentHTML('afterbegin',`<span class="eh771-pro-scope">DANE: ${esc(name)}</span>`);
        }else scope.textContent=`DANE: ${name}`;
      }
    }

    $$('.p751-pbp-player',panel).forEach(card=>{
      if($('.eh771-mini-scope',card))return;
      const n=$('header b',card)?.textContent?.trim()||name;
      card.insertAdjacentHTML('afterbegin',`<span class="eh771-mini-scope">DANE ZAWODNIKA · ${esc(n)}</span>`);
    });

    $$('.eh7-player',panel).forEach(card=>{
      if($('.eh771-mini-scope',card))return;
      const n=$('.eh7-name b',card)?.textContent?.trim()||name;
      card.insertAdjacentHTML('afterbegin',`<span class="eh771-mini-scope">DANE ZAWODNIKA · ${esc(n)}</span>`);
    });

    const pbpCards=$$('.p751-pbp-player,.eh7-player',panel);
    if(pbpCards.length){
      const parent=pbpCards[0].parentElement;
      if(parent&&!$('.eh771-history-note',parent)){
        parent.insertAdjacentHTML('afterend','<p class="eh771-history-note"><b>Historyczne 1:1 / 2:2 / 3:3 w profilu zawodnika</b> oznacza sam stan wyniku. Może powstać przez holdy albo wzajemne przełamania. W analizie konkretnego meczu rozdzielamy te ścieżki osobno.</p>');
      }
    }
  }

  function refresh(){decorateOverlay();decoratePlayerProfile();}
  const obs=new MutationObserver(()=>requestAnimationFrame(refresh));
  obs.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});
  setInterval(refresh,900);
  setTimeout(refresh,120);
})();