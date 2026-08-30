/* Tenis AI v9.2.3 — defensive Superbet PLAYABLE guard + market-detail coherence.
   The backend remains the source of truth. This UI layer only prevents stale,
   unverified or internally contradictory PLAYABLE compositions from being
   presented as a bet. It also improves readability of the long Superbet market
   list without changing model scores, probabilities, training or settlement. */
(() => {
  'use strict';

  const VERSION = 'v9.2.3';
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
    reportPromise = fetch(`${DATA_URL}?playable=923`, { cache: 'no-cache' })
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

  function signatureParts(api, row) {
    try {
      const raw = String(api?.signature?.(row) || '');
      const parts = raw.split('¦');
      return {
        market: parts[0] || '',
        pick: parts[1] || '',
        line: parts[2] || '',
        checkpoint: parts[3] || '0',
        player: parts[4] || ''
      };
    } catch {
      return {market:'',pick:'',line:'',checkpoint:'0',player:''};
    }
  }

  function selectionsConflict(api, left, right) {
    const a = signatureParts(api, left);
    const b = signatureParts(api, right);
    if (!a.market || a.market !== b.market) return false;
    if (a.checkpoint !== b.checkpoint || a.player !== b.player) return false;

    const totals = new Set([
      'match_total','set1_total','set2_total','set3_total','total_sets',
      'player_total_games','match_total_aces','player_aces','player_double_faults'
    ]);
    if (totals.has(a.market) && a.line === b.line) {
      const pair = new Set([a.pick, b.pick]);
      if (pair.has('over') && pair.has('under')) return true;
    }

    const winners = new Set(['match_winner','set1_winner','set2_winner','set3_winner']);
    if (winners.has(a.market) && a.pick && b.pick && a.pick !== b.pick) return true;

    const exact = new Set(['exact_match_score','set1_exact_score','set2_exact_score','set3_exact_score','game_state']);
    if (exact.has(a.market) && a.pick && b.pick && a.pick !== b.pick) return true;

    if (a.line === b.line) {
      const pair = new Set([a.pick, b.pick]);
      if (pair.has('yes') && pair.has('no')) return true;
    }
    return false;
  }

  function compositionCoherent(api, comp) {
    const legs = Array.isArray(comp?.selection) ? comp.selection : [];
    for (let i = 0; i < legs.length; i++) {
      for (let j = i + 1; j < legs.length; j++) {
        if (selectionsConflict(api, legs[i], legs[j])) return false;
      }
    }
    return true;
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
      if (api.compositionPlayable(match,comp) && compositionCoherent(api,comp)) {
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

  function shortName(value) {
    const raw = String(value || '').trim();
    if (!raw) return 'Gracz';
    if (raw.includes(',')) return raw.split(',')[0].trim();
    const parts = raw.split(/\s+/).filter(Boolean);
    return parts[parts.length - 1] || raw;
  }

  function humanLabel(text, match) {
    const raw = String(text || '').trim();
    const p1 = shortName(match?.p1);
    const p2 = shortName(match?.p2);
    let m = raw.match(/^exact match score\s*·\s*(\d+)\s*[:\-]\s*(\d+)$/i);
    if (m) return `Dokładny wynik · ${p1} ${m[1]}:${m[2]} ${p2}`;
    m = raw.match(/^set([123]) exact score\s*·\s*(\d+)\s*[:\-]\s*(\d+)$/i);
    if (m) return `${m[1]}. set · ${p1} ${m[2]}:${m[3]} ${p2}`;
    m = raw.match(/^(set([123]) )?game state\s*·\s*(\d+)\s*[:\-]\s*(\d+)\s*·\s*po\s*(\d+)\s*gemach$/i);
    if (m) {
      const prefix = m[2] ? `${m[2]}. set · ` : '';
      return `${prefix}po ${m[5]} gemach · ${p1} ${m[3]}:${m[4]} ${p2}`;
    }
    return raw;
  }

  function ensureMarketStyle() {
    if (document.getElementById('v923-market-coherence-style')) return;
    const style = document.createElement('style');
    style.id = 'v923-market-coherence-style';
    style.textContent = `
      .dc87.v923-market-collapsed > :not(.dc87-head){display:none!important}
      .v923-market-toggle{margin-top:8px;border:1px solid rgba(123,229,255,.26);background:rgba(4,18,30,.72);color:#c9eef7;border-radius:999px;padding:8px 12px;font:inherit;font-size:.72rem;font-weight:700}
      .v923-market-toggle:active{transform:translateY(1px)}
      .v923-market-note{display:block;margin-top:6px;color:#91aab5;font-size:.62rem;line-height:1.35}
    `;
    document.head.appendChild(style);
  }

  function polishDecisionPanel(overlay, match) {
    const root = overlay?.querySelector?.('.dc87');
    if (!root) return false;
    ensureMarketStyle();

    root.querySelectorAll('b').forEach(node => {
      const before = String(node.textContent || '').trim();
      const after = humanLabel(before, match);
      if (after !== before) node.textContent = after;
    });

    const head = root.querySelector('.dc87-head');
    if (!head) return true;
    let toggle = head.querySelector('[data-v923-market-toggle]');
    if (!toggle) {
      toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'v923-market-toggle';
      toggle.dataset.v923MarketToggle = '1';
      toggle.setAttribute('aria-expanded','false');
      head.append(toggle);
      root.classList.add('v923-market-collapsed');
      const note = document.createElement('small');
      note.className = 'v923-market-note';
      note.textContent = 'Lista rynków jest zwinięta dla czytelności. MODEL / RAW i dane nie są usuwane.';
      toggle.insertAdjacentElement('afterend', note);
      toggle.addEventListener('click', () => {
        const collapsed = root.classList.toggle('v923-market-collapsed');
        toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        toggle.textContent = collapsed ? 'Pokaż realne rynki Superbet' : 'Zwiń realne rynki Superbet';
      });
    }
    const collapsed = root.classList.contains('v923-market-collapsed');
    toggle.textContent = collapsed ? 'Pokaż realne rynki Superbet' : 'Zwiń realne rynki Superbet';
    toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    return true;
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
      ${n !== 6 ? `<p class="symmatch-detail__notice">Nie ma zweryfikowanej, spójnej i zgodnej z Superbetem wersji 6‑nogowej. Pokazuję największą aktualnie grywalną kompozycję: ${n} nogi.</p>` : ''}
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
      <p class="symmatch-detail__foot">Pokazujemy wyłącznie kompozycję zweryfikowaną względem aktualnej oferty i linii Superbet oraz bez oczywistych sprzeczności typu OVER + UNDER tej samej linii. RAW pozostaje analizą modelową i nie jest tutaj prezentowany jako zakład.</p>`;
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
        ? 'Dla tego meczu nie ma obecnie poprawnej i spójnej kompozycji 2–6 nóg złożonej wyłącznie z rynków i linii dostępnych w Superbet.'
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
    if(currentPanel.__playableRenderKey!==renderKey){
      if (chosen.state === 'playable') renderPlayable(currentPanel, chosen);
      else renderBlocked(currentPanel, chosen.state);
      currentPanel.__playableRenderKey=renderKey;
    }
    polishDecisionPanel(current,match);
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
        n?.nodeType === 1 && (
          n.matches?.('[data-symphony-match-detail],.dc87') ||
          n.querySelector?.('[data-symphony-match-detail],.dc87')
        )
      ));
      if (touched) schedule(20);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  window.TENIS_AI_SYMPHONY_PLAYABLE_DETAIL_GUARD_V915 = Object.freeze({
    version: VERSION,
    guardOpenMatch,
    compositionCoherent: comp => compositionCoherent(window.TENIS_AI_PLAYABLE_UI_V917,comp),
    selectionsConflict: (a,b) => selectionsConflict(window.TENIS_AI_PLAYABLE_UI_V917,a,b),
    polishDecisionPanel,
    reload: () => {
      reportCache = null;
      return guardOpenMatch();
    }
  });

  if (document.querySelector('#p751-match-overlay:not([hidden])')) schedule(100);
})();