/* Tenis AI v9.5.0.1 — canonical Match Detail information architecture.
   Presentation only. It does not calculate model scores, Symphony decisions,
   Superbet availability, PLAYABLE status, calibration or Player Intelligence.
   Order contract: Superbet PLAYABLE -> model context -> diagnostics.
*/
(()=>{
'use strict';
if(window.TENIS_AI_MATCH_DETAIL_V950)return;
const VERSION='v9.5.0.1';
const ROOT='#p751-match-overlay:not([hidden]) .p751-detail-screen';
function label(text,kind){const el=document.createElement('div');el.className='p751-note v950-detail-label';el.dataset.v950Label=kind;const b=document.createElement('b');b.textContent=text;el.append(b);return el}
function removeOldLabels(root){root.querySelectorAll('[data-v950-label]').forEach(el=>el.remove())}
function organize(){const root=document.querySelector(ROOT);if(!root)return false;removeOldLabels(root);const matchup=root.querySelector('.p751-matchup');const decision=root.querySelector('.dc87');const verdict=root.querySelector('.p751-verdict');const list=root.querySelector('.p751-acc-list');if(decision&&matchup){matchup.after(decision);decision.before(label('1 · SUPERBET PLAYABLE — realna, zweryfikowana oferta operatora','playable'))}else if(matchup){matchup.after(label('1 · SUPERBET PLAYABLE — brak świeżo zweryfikowanej oferty; nie zastępujemy jej typem modelowym','playable'))}if(verdict){const head=verdict.querySelector('header b');if(head)head.textContent='Kontekst MODEL / RAW';verdict.querySelectorAll('article').forEach(article=>{const title=article.querySelector('span');if(title&&/^Najlepszy typ$/i.test(title.textContent.trim()))title.textContent='Najlepszy sygnał modelu';if(title&&/^Alternatywa$/i.test(title.textContent.trim()))title.textContent='Alternatywa modelu'});verdict.before(label('2 · MODEL / RAW — analiza niezależna od dostępności Superbet','model'))}if(list){list.before(label('3 · PEŁNA ANALIZA — rozwiń tylko gdy potrzebujesz szczegółów','diagnostics'));if(list.dataset.v950InitialCompact!=='1'){list.querySelectorAll(':scope > details[open]').forEach(details=>{details.open=false});list.dataset.v950InitialCompact='1'}}root.querySelectorAll('#pi85-detail,.pi851-detail,[data-pi85-detail]').forEach(pi=>{pi.dataset.v950Role='player-context';const header=pi.querySelector('header b, h3, h4');if(header&&!/SHADOW|kontekst/i.test(header.textContent))header.textContent=`${header.textContent} · SHADOW / kontekst`});root.dataset.v950Organized='1';return true}
let timer=0;function schedule(ms=0){clearTimeout(timer);timer=setTimeout(organize,ms)}
function boot(){schedule(0);document.addEventListener('click',event=>{if(event.target?.closest?.('[data-p751-open],[data-v917-top]'))schedule(40)},true);if('MutationObserver'in window){const overlay=document.querySelector('#p751-match-overlay')||document.body;new MutationObserver(()=>schedule(30)).observe(overlay,{childList:true,subtree:true})}}
window.TENIS_AI_MATCH_DETAIL_V950=Object.freeze({version:VERSION,organize,schedule});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
