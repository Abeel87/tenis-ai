/* Tenis AI v8.8.8 — Generator Pair Quality Lock
   UI/runtime guard around the existing generator. Does not alter model scores.
   It removes weak auto-generated pairs instead of filling the requested count at any cost.
*/
(() => {
  'use strict';
  if (window.TENIS_AI_GENERATOR_QUALITY_V888) return;

  const num = x => x == null || x === '' || !Number.isFinite(Number(x)) ? null : Number(x);
  let accuracyLab = null;

  fetch('data/accuracy_lab_v86.json').then(r => r.ok ? r.json() : null).then(x => { accuracyLab = x; }).catch(()=>{});

  function api(){ return window.TENIS_AI_SCENARIOS || null; }
  function draft(){ try { return api()?.draft?.() || null; } catch { return null; } }
  function itemScore(x){ return num(x?.composer_score) ?? num(x?.adaptive_prod_score) ?? num(x?.value) ?? 0; }
  function profilePolicy(profile){
    return ({
      balanced:{minItem:78,minAvg:80,matchTotalMin:84},
      stable:{minItem:76,minAvg:79,matchTotalMin:84},
      strong:{minItem:82,minAvg:84,matchTotalMin:86}
    })[profile] || {minItem:78,minAvg:80,matchTotalMin:84};
  }
  function matchTotalValidationWeak(){
    const x = num(accuracyLab?.market_thresholds_shadow?.match_total?.baseline_65_val?.accuracy);
    return x != null && x < 68;
  }
  function groupDraft(d){
    const out = new Map();
    for (const item of d?.items || []) {
      const k = String(item.match_key || item.match_id || `${item.p1}|${item.p2}`);
      if (!out.has(k)) out.set(k, []);
      out.get(k).push(item);
    }
    return out;
  }
  function checkGroup(items, profile){
    const p = profilePolicy(profile);
    const scores = items.map(itemScore);
    const min = scores.length ? Math.min(...scores) : 0;
    const avg = scores.length ? scores.reduce((a,b)=>a+b,0)/scores.length : 0;
    const matchTotal = items.filter(x => String(x.market || '').toLowerCase() === 'match_total');
    const weakTotal = matchTotalValidationWeak() && matchTotal.some(x => itemScore(x) < p.matchTotalMin);
    const valid = items.length >= 2 && min >= p.minItem && avg >= p.minAvg && !weakTotal;
    let reason = '';
    if (items.length < 2) reason = 'para ma mniej niż 2 zdarzenia';
    else if (min < p.minItem) reason = `najsłabsze zdarzenie ma ${Math.round(min)}/100 (min. ${p.minItem})`;
    else if (avg < p.minAvg) reason = `średnia pary to ${Math.round(avg)}/100 (min. ${p.minAvg})`;
    else if (weakTotal) reason = 'rynek całego meczu ma zbyt słabą walidację dla tego wyniku';
    return {valid,min,avg,reason};
  }

  function removeItem(item){
    const buttons = [...document.querySelectorAll('[data-sc-remove]')];
    const btn = buttons.find(b => {
      let mk = b.dataset.scRemove || '', sk = b.dataset.scSig || '';
      try { mk = decodeURIComponent(mk); } catch {}
      try { sk = decodeURIComponent(sk); } catch {}
      return String(mk) === String(item.match_key) && String(sk) === String(item.signal_key);
    });
    if (btn) { btn.click(); return true; }
    return false;
  }
  function notice(text, tone='warn'){
    const host = document.querySelector('.sc82-panel') || document.querySelector('.sc82-body') || document.querySelector('[data-sc-panel]');
    if (!host) return;
    host.querySelector('.sc888-quality-note')?.remove();
    const el = document.createElement('div');
    el.className = `sc888-quality-note ${tone}`;
    el.innerHTML = `<b>🛡️ Quality Lock</b><span>${String(text)}</span>`;
    host.prepend(el);
  }

  function reviewGenerated(){
    const d = draft();
    if (!d || d.mode !== 'generator' || d.profile === 'experimental') return {removed:0,kept:0};
    const groups = groupDraft(d);
    const reject = [];
    const reasons = [];
    for (const [,items] of groups) {
      const c = checkGroup(items, d.profile || 'balanced');
      if (!c.valid) { reject.push(...items); reasons.push(c.reason); }
    }
    let removed = 0;
    for (const item of reject) if (removeItem(item)) removed++;
    const removedMatches = reject.length ? new Set(reject.map(x=>String(x.match_key))).size : 0;
    const keptMatches = Math.max(0, groups.size - removedMatches);
    if (removedMatches) {
      const pairWord = removedMatches === 1 ? 'słabą parę' : (removedMatches < 5 ? 'słabe pary' : 'słabych par');
      notice(`Odrzuciłem ${removedMatches} ${pairWord}. Zostało ${keptMatches} mocniejszych spotkań. Nie dokładam słabszych tylko po to, żeby dobić do żądanej liczby.`);
    } else if (groups.size) {
      notice(`Wszystkie ${groups.size} wygenerowane pary przeszły dodatkowy filtr jakości.`, 'ok');
    }
    return {removed,kept:keptMatches,reasons};
  }

  function currentProblems(){
    const d = draft();
    if (!d || d.mode !== 'generator' || d.profile === 'experimental') return [];
    const bad = [];
    for (const [,items] of groupDraft(d)) {
      const c = checkGroup(items, d.profile || 'balanced');
      if (!c.valid) bad.push(c.reason);
    }
    return bad;
  }

  const style = document.createElement('style');
  style.textContent = `
    .sc888-quality-note{display:flex;gap:.5rem;align-items:flex-start;margin:.55rem .7rem;padding:.62rem .72rem;border-radius:11px;border:1px solid rgba(255,190,87,.22);background:rgba(255,173,67,.07);color:#dceff5;font-size:.68rem;line-height:1.45}.sc888-quality-note b{white-space:nowrap;color:#ffd18a}.sc888-quality-note span{color:#a9bec7}.sc888-quality-note.ok{border-color:rgba(169,255,94,.18);background:rgba(169,255,94,.055)}.sc888-quality-note.ok b{color:#baff67}
  `;
  document.head.appendChild(style);

  // Internal generator handler is registered earlier on document. This listener runs after it,
  // then removes whole weak match-pairs from the newly rendered draft.
  document.addEventListener('click', e => {
    if (!e.target.closest?.('[data-sc-generate]')) return;
    setTimeout(reviewGenerated, 0);
  });

  // Saving is guarded in capture phase so a weak generated pair cannot slip through after line edits.
  // Manual scenarios remain completely under the user's control.
  document.addEventListener('click', e => {
    if (!e.target.closest?.('[data-sc-save]')) return;
    const bad = currentProblems();
    if (!bad.length) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation?.();
    notice(`Nie zapisuję scenariusza: ${bad[0]}. Usuń słabą parę albo wybierz mocniejsze zdarzenia.`);
  }, true);

  window.TENIS_AI_GENERATOR_QUALITY_V888 = Object.freeze({version:'v8.8.8', reviewGenerated, currentProblems});
})();
