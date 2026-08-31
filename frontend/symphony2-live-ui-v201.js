/* Tenis AI — Symphony 2.0 live UI recovery v2.0.2
   UI-only layer: exposes current Symphony 2.0 on match cards/details.
   Scenario runtime is intentionally NOT intercepted here. */
(() => {
  'use strict';
  if (window.TENIS_AI_SYMPHONY2_LIVE_V201) return;

  const VERSION='2.0.2-live-ui';
  const DATA_URL='data/symphony2_current.json';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const num=v=>v==null||!Number.isFinite(Number(v))?null:Number(v);
  const pct=v=>num(v)==null?'N/D':`${Number(v).toFixed(1)}%`;
  const norm=v=>String(v??'').trim().toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ');
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
  function rowForDetail(data){const overlay=document.querySelector('#p751-match-overlay:not([hidden])');const key=overlay?.dataset?.matchKey||'';let row=rowForKey(data,key);if(row)return row;const names=[...overlay?.querySelectorAll?.('.p751-matchup b')||[]].map(x=>norm(x.textContent));if(names.length>=2)row=(data.matches||[]).find(r=>{const a=norm(r.p1),b=norm(r.p2);return(a===names[0]&&b===names[1])||(a===names[1]&&b===names[0])});return row||null}
  function composition(row){if(!row)return null;const n=row.recommended_leg_count;if(n&&row.compositions?.[String(n)])return row.compositions[String(n)];for(const k of ['2','3','4','5','6'])if(row.compositions?.[k])return row.compositions[k];return null}
  function bestProbability(row){return Math.max(-Infinity,...(row?.scored_selections||[]).map(x=>num(x.operator_model_probability)).filter(x=>x!=null))}
  function badgeHtml(row){const comp=composition(row),best=bestProbability(row),ready=!!comp;return `<div class="s2-live-card-badge ${ready?'ready':'scored'}" data-s2-live-card="1"><span>🎼 <b>SYMFONIA 2.0</b></span><strong>${ready?`PLAYABLE · joint ${pct(comp.joint_probability)}`:(Number.isFinite(best)?`ocenione · max P(hit) ${pct(best)}`:'oferta oceniana')}</strong></div>`}
  async function decorateCards(force=false){
    const cards=[...document.querySelectorAll('.p751-match-card[data-p751-open]')];
    if(!cards.length)return;
    const data=await fetchFeed(force);if(!data)return;
    for(const card of cards){
      const row=rowForKey(data,decodeKey(card));if(!row)continue;
      const current=card.querySelector('[data-s2-live-card]');
      const html=badgeHtml(row);
      if(current&&current.outerHTML===html)continue;
      current?.remove();
      const footer=card.querySelector('footer');const wrap=document.createElement('div');wrap.innerHTML=html;const badge=wrap.firstElementChild;
      footer?footer.insertAdjacentElement('beforebegin',badge):card.append(badge);
    }
  }
  function detailFallbackHtml(row,data){const comp=composition(row),best=bestProbability(row);if(comp)return `<section id="symphony2-match-detail" class="s2-match-detail s2-match-ready" data-symphony2-match="1"><header><div><small>🎼 SYMFONIA 2.0 · PLAYABLE</small><h3>Najlepsza spójna kompozycja</h3><p>Dokładne selekcje z aktualnej oferty Superbet.</p></div><strong>${pct(comp.joint_probability)}</strong></header><footer>Exact shared-state joint · ${Number(comp.legs||0)} zdarzenia · model ${esc(data?.model_status||'N/D')}</footer></section>`;return `<section id="symphony2-match-detail" class="s2-match-detail s2-match-wait" data-symphony2-match="1"><header><div><small>🎼 SYMFONIA 2.0 · PLAYABLE</small><h3>Brak kompozycji powyżej progu</h3><p>Realna oferta Superbet została oceniona. Nie dokładam słabszego układu na siłę.</p></div><strong>${Number.isFinite(best)?pct(best):'—'}</strong></header><footer>${Number(row?.offer_selections||0)} realnych selekcji · model ${esc(data?.model_status||'N/D')}</footer></section>`}
  async function ensureDetail(force=false){const overlay=document.querySelector('#p751-match-overlay:not([hidden])');if(!overlay)return;if(window.TENIS_AI_SYMPHONY2?.renderMatchDetail){try{await window.TENIS_AI_SYMPHONY2.renderMatchDetail(force)}catch{}if(overlay.querySelector('#symphony2-match-detail'))return}const data=await fetchFeed(force);if(!data)return;const row=rowForDetail(data);if(!row)return;const screen=overlay.querySelector('.p751-detail-screen')||overlay;screen.querySelector('#symphony2-match-detail')?.remove();const wrap=document.createElement('div');wrap.innerHTML=detailFallbackHtml(row,data);const block=wrap.firstElementChild;const decision=screen.querySelector('.dc87');decision?decision.insertAdjacentElement('beforebegin',block):screen.append(block)}

  document.addEventListener('click',e=>{
    if(e.target?.closest?.('[data-p751-open]'))setTimeout(()=>ensureDetail(true),60);
    if(e.target?.closest?.('[data-p751-nav="matches"],[data-view="matches"]'))setTimeout(()=>decorateCards(false),120);
  },true);

  const style=document.createElement('style');style.textContent=`.s2-live-card-badge{display:flex;justify-content:space-between;align-items:center;gap:.55rem;margin:.55rem .75rem;padding:.52rem .65rem;border:1px solid rgba(89,226,255,.2);border-radius:10px;background:rgba(40,190,220,.06);font-size:.7rem}.s2-live-card-badge span{color:#9eddea}.s2-live-card-badge strong{color:#c8f3fa;text-align:right}.s2-live-card-badge.ready{border-color:rgba(161,255,91,.25);background:rgba(161,255,91,.055)}.s2-live-card-badge.ready strong{color:#bdff85}`;document.head.appendChild(style);
  [80,500,1400].forEach((ms,i)=>setTimeout(()=>decorateCards(i===0),ms));
  setTimeout(()=>ensureDetail(false),300);

  if(!document.getElementById('scenario-runtime-v202')){
    const s=document.createElement('script');
    s.id='scenario-runtime-v202';
    s.src='scenario-runtime-v202.js?v=202';
    s.async=false;
    document.body.appendChild(s);
  }

  window.TENIS_AI_SYMPHONY2_LIVE_V201=Object.freeze({version:VERSION,fetchFeed,decorateCards,ensureDetail});
})();