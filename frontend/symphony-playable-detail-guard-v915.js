/* Tenis AI v9.1.5 — defensive Superbet PLAYABLE guard for full Symphony detail.
   The backend remains the source of truth. This UI layer only prevents a stale
   or unverified RAW full_composition from being presented as a playable bet. */
(() => {
  'use strict';

  const VERSION = 'v9.1.5';
  const DATA_URL = './data/symphony_v90.json';
  let reportCache = null;
  let cachedAt = 0;
  let reportPromise = null;
  let timer = null;

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
  const finite = (v) => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const score = (v) => finite(v) ? `${Number(v).toFixed(1).replace('.0', '')}/100` : 'N/D';
  const pct = (v) => finite(v) ? `${Number(v).toFixed(1).replace('.0', '')}%` : 'N/D';
  const lineText = (v) => finite(v) ? Number(v).toFixed(1).replace('.0', '') : '';

  function loadReport() {
    if (reportCache && Date.now()-cachedAt < 60000) return Promise.resolve(reportCache);
    if (reportPromise) return reportPromise;
    reportPromise = fetch(`${DATA_URL}?playable=915`, { cache: 'no-cache' })
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {cachedAt=Date.now();return reportCache=data;})
      .catch(() => null)
      .finally(() => { reportPromise = null; });
    return reportPromise;
  }

  function lookupMap(report) {
    const map = new Map();
    for (const row of report?.matches || []) {
      if (!row || typeof row !== 'object') continue;
      if (row.id !== null && row.id !== undefined) map.set(String(row.id), row);
      const key = String(row.match_key || '');
      if (key) {
        map.set(key, row);
        if (key.startsWith('id:')) map.set(key.slice(3), row);
      }
      const fallback = [row.p1, row.p2, row.scheduled_time].map(x => String(x || '')).join('|');
      if (fallback !== '||') map.set(fallback, row);
    }
    return map;
  }

  function findRow(report, raw) {
    if (!report) return null;
    const map = lookupMap(report);
    return map.get(raw) || map.get(`id:${raw}`) || null;
  }

  function playableComposition(row,match) {
    if (!row || typeof row !== 'object') return { state: 'missing' };
    const gate = row.operator_reprojection || {};
    const api=window.TENIS_AI_PLAYABLE_UI_V917;
    if(api?.active?.(match)!==true)return {state:'unverified',gate};
    if (gate.active !== true || gate.verified_operator_match !== true) {
      return { state: 'unverified', gate };
    }
    if (gate.status !== 'PLAYABLE_SUPERBET_ONLY') {
      return { state: 'none', gate };
    }
    const comps = row.compositions || {};
    for (const n of [6, 5, 4, 3, 2]) {
      const comp = comps[String(n)];
      if (api.compositionPlayable(match,comp)) {
        return { state: 'playable', n, comp, gate };
      }
    }
    return { state: 'none', gate };
  }

  function legScore(leg) {
    if (finite(leg?.evidence_score)) return score(leg.evidence_score);
    if (finite(leg?.prod_score)) return score(leg.prod_score);
    if (finite(leg?.operator_model_score)) return score(leg.operator_model_score);
    if (finite(leg?.score)) return score(leg.score);
    return 'N/D';
  }

  function legMeta(leg) {
    const bits = ['Superbet ✓'];
    if (leg?.market) bits.push(String(leg.market).replaceAll('_', ' '));
    if (finite(leg?.line)) bits.push(`linia ${lineText(leg.line)}`);
    if (finite(leg?.path_probability)) bits.push(`ścieżka ${pct(leg.path_probability)}`);
    return bits.join(' · ');
  }

  function renderPlayable(panel, chosen) {
    const { n, comp } = chosen;
    const legs = comp.selection || [];
    const coverage = finite(comp.path_coverage) ? `${Math.round(Number(comp.path_coverage) * 100)}%` : 'N/D';
    const joint = finite(comp.joint_probability) ? pct(comp.joint_probability) : 'N/D';
    const supported = finite(comp.supported_legs) ? `${Number(comp.supported_legs)}/${n}` : 'N/D';
    const dna = String(comp.story_type || '').replaceAll('_', ' ');
    const fragile = Array.isArray(comp.fragility) && comp.fragility.length ? comp.fragility[0] : null;

    panel.dataset.symphonyPlayableGuard = VERSION;
    panel.innerHTML = `
      <header class="symmatch-detail__head">
        <div><span>🎼 PEŁNA SYMFONIA · SUPERBET PLAYABLE</span><b>${n === 6 ? '6 NÓG' : `MAX ${n} NÓG`}</b></div>
        <strong>${score(comp.symphony_score)}</strong>
      </header>
      ${n !== 6 ? `<p class="symmatch-detail__notice">Nie ma zweryfikowanej, zgodnej z Superbetem wersji 6‑nogowej. Pokazuję największą aktualnie grywalną kompozycję: ${n} nogi.</p>` : ''}
      <div class="symmatch-detail__metrics">
        <span><small>coverage</small><b>${coverage}</b></span>
        <span><small>joint</small><b>${joint}</b></span>
        <span><small>exact</small><b>${supported}</b></span>
        <span><small>DNA</small><b>${esc(dna || 'BALANCED')}</b></span>
      </div>
      <div class="symmatch-detail__legs">
        ${legs.map((leg, i) => `<article>
          <i>${i + 1}</i>
          <div><b>${esc(leg?.label || leg?.key || 'Zdarzenie')}</b><small>${esc(legMeta(leg))}</small></div>
          <strong>${legScore(leg)}</strong>
        </article>`).join('')}
      </div>
      ${fragile ? `<footer><span>⚠ Najbardziej krucha noga</span><b>${esc(fragile.label || fragile.key || 'N/D')}</b><em>fragility ${finite(fragile.fragility) ? Number(fragile.fragility).toFixed(1) : 'N/D'}</em></footer>` : ''}
      <p class="symmatch-detail__foot">Pokazujemy wyłącznie kompozycję zweryfikowaną względem aktualnej oferty i linii Superbet. RAW pozostaje analizą modelową i nie jest tutaj prezentowany jako zakład.</p>`;
  }

  function renderBlocked(panel, state) {
    const unavailable = state === 'none';
    panel.dataset.symphonyPlayableGuard = VERSION;
    panel.innerHTML = `
      <header class="symmatch-detail__head">
        <div><span>🎼 PEŁNA SYMFONIA · SUPERBET PLAYABLE</span><b>N/D</b></div>
        <strong>N/D</strong>
      </header>
      <p class="symmatch-detail__notice">${unavailable
        ? 'Dla tego meczu nie ma obecnie poprawnej kompozycji 2–6 nóg złożonej wyłącznie z rynków i linii dostępnych w Superbet.'
        : 'Brak świeżo zweryfikowanej oferty Superbet dla tego meczu. Nie pokazuję surowej Symfonii jako typu do zagrania.'}</p>
      <p class="symmatch-detail__foot">RAW/modelowa analiza może istnieć w tle, ale bez potwierdzenia operatora pozostaje analizą — nie PLAYABLE.</p>`;
  }

  async function guardOpenMatch() {
    const overlay = document.querySelector('#p751-match-overlay:not([hidden])');
    const panel = overlay?.querySelector('[data-symphony-match-detail]');
    const raw = String(overlay?.dataset?.matchKey || '');
    if (!overlay || !panel || !raw) return false;

    const report = await loadReport();
    const current = document.querySelector('#p751-match-overlay:not([hidden])');
    if (!current || String(current.dataset.matchKey || '') !== raw) return false;
    const currentPanel = current.querySelector('[data-symphony-match-detail]');
    if (!currentPanel) return false;

    const row = findRow(report, raw);
    const match=window.TENIS_AI_PLAYABLE_UI_V917?.findMatch?.(raw);
    const chosen = playableComposition(row,match);
    const renderKey=JSON.stringify([raw,chosen.state,chosen.n,chosen.comp]);
    if(currentPanel.__playableRenderKey===renderKey)return chosen.state==='playable';
    if (chosen.state === 'playable') renderPlayable(currentPanel, chosen);
    else renderBlocked(currentPanel, chosen.state);
    currentPanel.__playableRenderKey=renderKey;
    return chosen.state === 'playable';
  }

  function schedule(delay = 30) {
    clearTimeout(timer);
    timer = setTimeout(() => guardOpenMatch(), delay);
  }

  document.addEventListener('click', event => {
    if (event.target?.closest?.('[data-p751-open]')) {
      schedule(80);
      setTimeout(() => guardOpenMatch(), 350);
      setTimeout(() => guardOpenMatch(), 900);
    }
  }, true);

  if ('MutationObserver' in window) {
    const observer = new MutationObserver(records => {
      const touched = records.some(r => [...r.addedNodes].some(n =>
        n?.nodeType === 1 && (n.matches?.('[data-symphony-match-detail]') || n.querySelector?.('[data-symphony-match-detail]'))
      ));
      if (touched) schedule(20);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  window.TENIS_AI_SYMPHONY_PLAYABLE_DETAIL_GUARD_V915 = Object.freeze({
    version: VERSION,
    guardOpenMatch,
    reload: () => {
      reportCache = null;
      return guardOpenMatch();
    }
  });

  if (document.querySelector('#p751-match-overlay:not([hidden])')) schedule(100);
})();

/* v9.3J is a separate MODEL/RAW presentation addon. Loading it here keeps the
   existing index contract untouched; the addon itself never reads PLAYABLE data. */
(() => {
  const d = typeof document === 'object' ? document : null;
  if (!d || typeof d.createElement !== 'function' || !d.body || typeof d.body.appendChild !== 'function') return;
  if (typeof d.getElementById === 'function' && d.getElementById('symphony-raw-story-v93j-addon')) return;
  const s = d.createElement('script');
  s.id = 'symphony-raw-story-v93j-addon';
  s.src = 'symphony-raw-story-v93j.js?v=93j';
  s.async = false;
  d.body.appendChild(s);
})();
