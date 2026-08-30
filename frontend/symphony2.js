(() => {
  'use strict';
  const VERSION='2.0-foundation';
  const DATA_URL='./data/symphony2_current.json';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>Number.isFinite(Number(v))?Number(v):null;
  const pct=v=>num(v)==null?'N/D':`${Number(v).toFixed(1)}%`;
  let cache=null;

  async function load(force=false){
    if(cache&&!force)return cache;
    const r=await fetch(`${DATA_URL}?v=${Date.now()}`,{cache:'no-store'});
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    cache=await r.json();
    return cache;
  }

  function panel(){return document.querySelector('#scenario-v82a-panel')}
  function body(){return panel()?.querySelector('.sc82-body')||null}
  function homeButton(){return panel()?.querySelector('[data-sc-go="generator"]')||null}

  function decorate(){
    const b=homeButton();
    if(!b)return;
    b.innerHTML='<b>🎼 Symfonia 2.0</b><span>Realne linie Superbet → model P(hit) → najlepsza spójna kompozycja</span>';
    b.dataset.symphony2='1';
  }

  function status(data){
    const train=data?.training||{};
    return `<div class="s2-status">
      <div class="s2-stat"><small>Model linii</small><strong>${esc(data?.model_status||'N/D')}</strong></div>
      <div class="s2-stat"><small>Mecze z ofertą</small><strong>${Number(data?.matches_count||0)}</strong></div>
      <div class="s2-stat"><small>Wygenerowano</small><strong>${esc((data?.generated_at||'').replace('T',' ').slice(0,16)||'N/D')}</strong></div>
    </div>`;
  }

  function leg(x){
    return `<div class="s2-leg"><div><strong>${esc(x.label||x.selection_id)}</strong><small>${esc(x.market||'')} · dokładna linia Superbet${x.operator_line_source?` · ${esc(x.operator_line_source)}`:''}</small></div><div class="s2-prob">${pct(x.operator_model_probability)}</div></div>`;
  }

  function card(m,c){
    const joint=c.joint_probability;
    return `<article class="s2-card">
      <div class="s2-head"><div><small>${esc(m.tour||'')} ${m.surface?`· ${esc(m.surface)}`:''}</small><h3>${esc(m.p1)} <span>vs</span> ${esc(m.p2)}</h3><div class="s2-muted">${c.legs} zdarzenia · wszystkie z bieżącej oferty operatora</div></div><div class="s2-score"><small>utility</small><strong>${Number(c.score||0).toFixed(1)}</strong></div></div>
      <div>${(c.selection||[]).map(leg).join('')}</div>
      <div class="s2-joint">${joint==null?`Joint probability: czeka na wspólny exact-state engine 2.0. Nie pokazuję fałszywego procentu.`:`Joint probability: ${pct(joint)}`}</div>
    </article>`;
  }

  function render(data,count,legs){
    const rows=(data.matches||[]).map(m=>{
      const n=legs==='auto'?m.recommended_leg_count:Number(legs);
      return {m,c:n?m.compositions?.[String(n)]:null};
    }).filter(x=>x.c).sort((a,b)=>Number(b.c.score||0)-Number(a.c.score||0)).slice(0,count);
    if(!rows.length)return '<div class="s2-empty">Brak kompozycji Symfonii 2.0. To nie znaczy „brak sygnałów RAW” — oznacza, że nowy model nie ma jeszcze wystarczająco jakościowych, dokładnych selekcji z bieżącej oferty Superbet.</div>';
    return rows.map(x=>card(x.m,x.c)).join('');
  }

  function shell(data){
    return `<section class="s2-shell" data-symphony2-version="${VERSION}">
      <button type="button" class="s2-back" data-s2-back>← Scenariusze</button>
      <div class="s2-hero"><div class="s2-kicker">TENIS AI · SYMFONIA 2.0</div><h2>Symfonia 2.0</h2><p>Nie wymyślam linii do kuponu. Najpierw biorę dokładną aktualną ofertę Superbet, potem oceniam każdą realną selekcję modelem uczonym na historycznych liniach operatora.</p></div>
      ${status(data)}
      <div class="s2-controls"><label>Mecze<select id="s2-count"><option>1</option><option>2</option><option>3</option><option selected>4</option><option>5</option><option>6</option></select></label><label>Zdarzenia / mecz<select id="s2-legs"><option value="auto" selected>AUTO 2–6</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option><option value="6">6</option></select></label><button class="s2-generate" id="s2-generate" type="button">🎼 Ułóż Symfonię 2.0</button></div>
      <div id="s2-results" class="s2-grid">${render(data,4,'auto')}</div>
    </section>`;
  }

  async function open(){
    const b=body();if(!b)return;
    b.innerHTML='<div class="s2-empty">Ładuję aktualny snapshot Superbet i model Symfonii 2.0…</div>';
    try{
      const data=await load(true);b.innerHTML=shell(data);
      b.querySelector('[data-s2-back]')?.addEventListener('click',()=>window.TENIS_AI_SCENARIOS_V82A?.open?.('home'));
      b.querySelector('#s2-generate')?.addEventListener('click',()=>{const c=Number(b.querySelector('#s2-count')?.value||4);const l=b.querySelector('#s2-legs')?.value||'auto';b.querySelector('#s2-results').innerHTML=render(data,c,l)});
    }catch(e){
      console.warn('[Symphony2]',e);b.innerHTML='<div class="s2-empty">Symfonia 2.0 nie ma jeszcze opublikowanego feedu. Stara Symfonia nie jest używana jako fallback.</div>';
    }
  }

  document.addEventListener('click',e=>{
    const t=e.target?.closest?.('[data-sc-go="generator"]');
    if(!t)return;
    e.preventDefault();e.stopImmediatePropagation();open();
  },true);

  const observer=new MutationObserver(()=>decorate());
  observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden']});
  decorate();
  window.TENIS_AI_SYMPHONY2={version:VERSION,open,load};
})();