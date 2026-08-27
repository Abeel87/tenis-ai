/* Tenis AI v8.8.9 — Match Loading Race Guard
   Prevents a false "no matches" state while results.json is still loading.
   It primes match data independently from the much heavier history/statistics load.
*/
(() => {
  'use strict';
  if (window.TENIS_AI_MATCH_LOADING_V889) return;
  if (typeof renderMatches !== 'function') return;

  let state = 'loading'; // loading | ready | error
  const originalRenderMatches = renderMatches;

  function appHost(){ return document.querySelector('#app'); }
  function showLoading(){
    const app = appHost();
    if (!app) return;
    app.innerHTML = '<div class="empty" data-v889-loading><b>Ładowanie meczów…</b><br><br>Pobieram dzisiejsze spotkania. Historia i statystyki doładują się osobno.</div>';
  }
  function showError(){
    const app = appHost();
    if (!app) return;
    app.innerHTML = '<div class="empty"><b>Nie udało się wczytać meczów.</b><br><br>Spróbuj odświeżyć dane przyciskiem ↻.</div>';
  }

  renderMatches = function(){
    const hasRows = Array.isArray(all) && all.length > 0;
    if (state === 'loading' && !hasRows) { showLoading(); return; }
    if (state === 'error' && !hasRows) { showError(); return; }
    return originalRenderMatches();
  };

  async function primeMatches(){
    try {
      const r = await fetch(`data/results.json?ts=${Date.now()}`, {cache:'no-store'});
      if (!r.ok) throw new Error(`results ${r.status}`);
      const rows = await r.json();
      if (!Array.isArray(rows)) throw new Error('results payload is not an array');
      all = rows;
      state = 'ready';
      if (typeof updateCounts === 'function') updateCounts();
      if (typeof view === 'undefined' || view === 'matches') originalRenderMatches();
    } catch {
      state = 'error';
      if (typeof view === 'undefined' || view === 'matches') renderMatches();
    }
  }

  const fast = window.TENIS_AI_FAST_BOOT_V888;
  try {
    if (fast?.snapshot?.().resultsReady && Array.isArray(all)) state = 'ready';
  } catch {}
  if (state !== 'ready') primeMatches();

  document.addEventListener('click', e => {
    if (!e.target?.closest?.('#refresh')) return;
    state = 'loading';
    if (typeof view === 'undefined' || view === 'matches') showLoading();
    setTimeout(primeMatches, 0);
  }, true);

  window.TENIS_AI_MATCH_LOADING_V889 = Object.freeze({
    version:'v8.8.9',
    snapshot:()=>({state,rows:Array.isArray(all)?all.length:0})
  });
})();
