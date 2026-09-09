/* Tenis AI — Symphony 2.0 live UI recovery v2.0.3
   UI-only layer: exposes current Symphony 2.0 on match cards/details.
   Scenario runtime is intentionally NOT intercepted or bootstrapped here. */
(() => {
  'use strict';
  if (window.TENIS_AI_SYMPHONY2_LIVE_V201) return;

  const VERSION='2.0.3-live-ui';
  const DATA_URL='data/symphony2_current.json';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const num=v=>v==null||!Number.isFinite(Number(v))?null:Number(v);
  const pct=v=>num(v)==null?'N/D':`${Number(v).toFixed(1)}%`;
  const norm=v=>String(v??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ');
  function projectMatchFor(row,key=''){
    const keys=[key,row?.match_key,row?.match_id,row?.id].filter(v=>v!=null&&String(v)!=='').map(String);
    for(const k of keys){try{const match=window.TENIS_AI_PROJECT_UI?.findMatch?.(k);if(match)return match}catch{}}
    return null;
  }
  function rowPreMatch(row,match=null,now=Date.now()){
    const scheduled=Date.parse(row?.scheduled_time||'');
    if(!Number.isFinite(scheduled)||scheduled<=Number(now)||!match)return false;
    const api=window.TENIS_AI_PLAYABLE_UI_V917;
    if(typeof api?.preMatch!=='function'||api.preMatch(row,now)!==true||api.preMatch(match,now)!==true)return false;
    if(typeof api?.active!=='function'||api.active(match,now)!==true)return false;
    return true;
  }
  let feed=null,feedPromise=null;

  async function fetchFeed(force=false){
    if(feed&&!force)return feed;
    if(feedPromise&&!force)return feedPromise;
    const ctrl=typeof AbortController==='function'?new AbortController():null;
    const timer=ctrl?setTimeout(()=>ctrl.abort(),7000):null;
    feedPromise=fetch(`${DATA_URL}?v=${Date.now()}`,{cache:'no-store',signal:ctrl?.signal})
      .then(async r=>{if(!r.ok)throw new Error(`Symphony2 HTTP ${r.status}`);const text=await r.text();if(!text.trim())throw new Error('Symphony2 empty feed');const data=JSON.parse(text);if(!data||!Array.isArray(data.matches))throw new Error('Symphony2 invalid feed');feed=data;return data})
      .catch(e=>{console.warn('[Symphony2 live feed]',e);return null})
      .finally(()=>{if(timer)clearTimeout(timer);feedPromise=null});
    return feedPromise;
  }
  function decodeKey(card){let k=card?.dataset?.p751Open||'';try{k=decodeURIComponent(k)}catch{}return String(k)}
  function rowForKey(data,key){if(!data||!key)return null;return (data.matches||[]).find(r=>[r.id,r.match_id,r.match_key].some(v=>v!=null&&String(v)===String(key)))||null}
  function rowForDetail(data){const app=document.querySelector('#app[data-match-key]'),screen=app?.querySelector('.p751-detail-screen');const key=app?.dataset?.matchKey||screen?.dataset?.matchKey||'';let row=rowForKey(data,key);if(row)return row;const names=[...screen?.querySelectorAll?.('.match-hero-players b')||[]].map(x=>norm(x.textContent));if(names.length>=2)row=(data.matches||[]).find(r=>{const a=norm(r.p1),b=norm(r.p2);return(a===names[0]&&b===names[1])||(a===names[1]&&b===names[0])});return row||null}
  function composition(row,match=null,data=null){
    if(!rowPreMatch(row,match))return null;
    const api=window.TENIS_AI_PLAYABLE_UI_V917,layer=match?.symphony2_playable;
    if(!layer||layer.final_playable_authority!==true||layer.playable!==true||!Array.isArray(layer.signals))return null;
    if(data?.generated_at&&String(layer.source_generated_at||'')!==String(data.generated_at))return null;
    const recommended=Number(row?.recommended_leg_count),published=Number(layer.recommended_leg_count);
    if(!Number.isInteger(recommended)||recommended<2||published!==recommended)return null;
    const comp=row?.compositions?.[String(recommended)],legs=comp?.selection;
    if(!comp||!Array.isArray(legs)||legs.length!==recommended)return null;
    if(typeof api?.compositionPlayable!=='function'||api.compositionPlayable(match,comp)!==true)return null;
    const projected=api.playableSignals?.(match,100)||[],signature=api.signature;
    if(typeof signature!=='function'||projected.length!==legs.length)return null;
    const a=projected.map(signature).sort().join('||'),b=legs.map(signature).sort().join('||');
    return a===b?comp:null;
  }
  function bestProbability(row){return Math.max(-Infinity,...(row?.scored_selections||[]).map(x=>num(x.operator_model_probability)).filter(x=>x!=null))}
  function badgeHtml(row,match=null,data=null){if(!rowPreMatch(row,match))return '';const comp=composition(row,match,data),best=bestProbability(row),ready=!!comp;return `<div class="s2-live-card-badge ${ready?'ready':'scored'}" data-s2-live-card="1"><span>🎼 <b>SYMFONIA 2.0</b></span><strong>${ready?`PLAYABLE · joint ${pct(comp.joint_probability)}`:(Number.isFinite(best)?`ocenione · max P(hit) ${pct(best)}`:'oferta oceniana')}</strong></div>`}
  async function decorateCards(force=false){
    const cards=[...document.querySelectorAll('.p751-match-card[data-p751-open]')];
    if(!cards.length)return;
    const data=await fetchFeed(force);if(!data)return;
    for(const card of cards){
      const key=decodeKey(card),row=rowForKey(data,key);if(!row)continue;
      const current=card.querySelector('[data-s2-live-card]'),match=projectMatchFor(row,key);
      const html=badgeHtml(row,match,data);
      if(!html){current?.remove();continue}
      if(current&&current.outerHTML===html)continue;
      current?.remove();
      const footer=card.querySelector('footer');const wrap=document.createElement('div');wrap.innerHTML=html;const badge=wrap.firstElementChild;
      footer?footer.insertAdjacentElement('beforebegin',badge):card.append(badge);
    }
  }
  function detailFallbackHtml(row,data,match=null){if(!rowPreMatch(row,match))return `<section id="symphony2-match-detail" class="s2-match-detail s2-match-wait" data-symphony2-match="1"><header><div><small>🎼 SYMFONIA 2.0 · NIEAKTYWNA</small><h3>Snapshot pre-match lub oferta operatora wygasła</h3><p>Finalny PLAYABLE wymaga przyszłego meczu i świeżej, zweryfikowanej oferty Superbet. Dane MODEL/RAW pozostają bez zmian.</p></div><strong>—</strong></header></section>`;const comp=composition(row,match,data),best=bestProbability(row);if(comp)return `<section id="symphony2-match-detail" class="s2-match-detail s2-match-ready" data-symphony2-match="1"><header><div><small>🎼 SYMFONIA 2.0 · PLAYABLE</small><h3>Najlepsza spójna kompozycja</h3><p>Dokładne selekcje z aktualnej oferty Superbet.</p></div><strong>${pct(comp.joint_probability)}</strong></header><footer>Exact shared-state joint · ${Number(comp.legs||0)} zdarzenia · model ${esc(data?.model_status||'N/D')}</footer></section>`;return `<section id="symphony2-match-detail" class="s2-match-detail s2-match-wait" data-symphony2-match="1"><header><div><small>🎼 SYMFONIA 2.0 · BRAK PLAYABLE</small><h3>Brak kompozycji powyżej progu</h3><p>Realna oferta Superbet została oceniona. Nie dokładam słabszego układu na siłę.</p></div><strong>${Number.isFinite(best)?pct(best):'—'}</strong></header><footer>${Number(row?.offer_selections||0)} realnych selekcji · model ${esc(data?.model_status||'N/D')}</footer></section>`}
  async function ensureDetail(force=false){const app=document.querySelector('#app[data-match-key]'),screen=app?.querySelector('.p751-detail-screen');if(!app||!screen)return;if(window.TENIS_AI_SYMPHONY2?.renderMatchDetail){try{await window.TENIS_AI_SYMPHONY2.renderMatchDetail(force)}catch{}if(screen.querySelector('#symphony2-match-detail'))return}const data=await fetchFeed(force);if(!data)return;const row=rowForDetail(data);if(!row)return;const match=projectMatchFor(row,app.dataset.matchKey||'');screen.querySelector('#symphony2-match-detail')?.remove();const wrap=document.createElement('div');wrap.innerHTML=detailFallbackHtml(row,data,match);const block=wrap.firstElementChild;const decision=screen.querySelector('.dc87');decision?decision.insertAdjacentElement('beforebegin',block):screen.append(block)}

  document.addEventListener('click',e=>{
    if(e.target?.closest?.('[data-p751-open]'))setTimeout(()=>ensureDetail(true),60);
    if(e.target?.closest?.('[data-view="matches"]'))setTimeout(()=>decorateCards(false),120);
  },true);
  document.addEventListener('tenis-ai:matches-rendered',()=>decorateCards(false));
  document.addEventListener('tenis-ai:match-open',()=>ensureDetail(true));
  document.addEventListener('tenis-ai:match-refresh',()=>ensureDetail(true));
  document.addEventListener('tenis-ai:superbet-coverage-ready',()=>ensureDetail(false));
  [80,500,1400].forEach((ms,i)=>setTimeout(()=>decorateCards(i===0),ms));
  setTimeout(()=>ensureDetail(false),300);

  window.TENIS_AI_SYMPHONY2_LIVE_V201=Object.freeze({version:VERSION,fetchFeed,decorateCards,ensureDetail});
})();