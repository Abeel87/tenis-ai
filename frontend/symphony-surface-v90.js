/* Tenis AI v9.0E.1 — Symphony stats rescue + match cards + full match detail */
(() => {
  'use strict';

  const VERSION = 'v9.0E.1';
  const DATA_URL = './data/symphony_match_cards_v90.json';
  const FULL_DATA_URL = './data/symphony_v90.json';
  let reportPromise = null;
  let reportCache = null;
  let fullReportPromise = null;
  let fullReportCache = null;
  let decorateTimer = null;
  let detailTimer = null;

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
  const finite = (v) => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const score = (v) => finite(v) ? `${Number(v).toFixed(1).replace('.0', '')}/100` : 'N/D';
  const pct = (v) => finite(v) ? `${Number(v).toFixed(1).replace('.0', '')}%` : 'N/D';
  const lineText = (v) => finite(v) ? Number(v).toFixed(1).replace('.0', '') : '';

  function ensureCss() {
    if (document.querySelector('link[data-symphony-surface-v90]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'symphony-surface-v90.css?v=90e1';
    link.dataset.symphonySurfaceV90 = '1';
    document.head.append(link);
  }

  async function ensureStatsVisible() {
    const api = window.TENIS_AI_SYMPHONY_STATS_V90D;
    try { await api?.render?.(); } catch {}
    await new Promise(resolve => setTimeout(resolve, 0));
    const root = document.querySelector('#pc77');
    const card = root?.querySelector('#symphony-performance-v90d');
    if (!root || !card) return false;

    if (card.parentElement !== root) {
      const anchor = root.querySelector('.pc882-dash')
        || root.querySelector('.pc12-main-trend')
        || root.querySelector('.pc12-summary')
        || root.firstElementChild;
      if (anchor && anchor !== card) anchor.insertAdjacentElement('afterend', card);
      else root.prepend(card);
    }
    card.dataset.symphonyPinned = '1';
    return true;
  }

  function loadReport() {
    if (reportCache) return Promise.resolve(reportCache);
    if (reportPromise) return reportPromise;
    reportPromise = fetch(`${DATA_URL}?surface=90e1`, { cache: 'no-cache' })
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => (reportCache = data))
      .catch(() => null)
      .finally(() => { reportPromise = null; });
    return reportPromise;
  }

  function loadFullReport() {
    if (fullReportCache) return Promise.resolve(fullReportCache);
    if (fullReportPromise) return fullReportPromise;
    fullReportPromise = fetch(`${FULL_DATA_URL}?detail=90e1`, { cache: 'no-cache' })
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => (fullReportCache = data))
      .catch(() => null)
      .finally(() => { fullReportPromise = null; });
    return fullReportPromise;
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

  function composition(row) {
    const comp = row?.composition;
    if (!comp || !Array.isArray(comp.selection) || !comp.selection.length) return null;
    const recommended = Number(row?.recommended_leg_count);
    const n = Number.isInteger(recommended) && recommended >= 2 && recommended <= 6
      ? recommended
      : comp.selection.length;
    return { n, comp };
  }

  function fullComposition(row) {
    if (!row || typeof row !== 'object') return null;
    if (row.full_composition && Array.isArray(row.full_composition.selection) && row.full_composition.selection.length) {
      return { n: Number(row.full_composition.legs || row.full_composition.selection.length), comp: row.full_composition };
    }
    const comps = row.compositions || {};
    for (const n of [6, 5, 4, 3, 2]) {
      const comp = comps[String(n)];
      if (comp && Array.isArray(comp.selection) && comp.selection.length) return { n, comp };
    }
    return null;
  }

  function miniHtml(row) {
    const chosen = composition(row);
    if (!chosen) return '';
    const { n, comp } = chosen;
    const legs = comp.selection || [];
    const preview = legs.slice(0, 3);
    const coverage = finite(comp.path_coverage) ? `${Math.round(Number(comp.path_coverage) * 100)}% path` : 'path N/D';
    const joint = finite(comp.joint_probability) ? ` · joint ${pct(comp.joint_probability)}` : '';
    const dna = String(comp.story_type || '').replaceAll('_', ' ');
    return `<div class="symmatch-mini" data-symphony-match-mini="1">
      <div class="symmatch-mini__head">
        <span>🎼 SYMFONIA</span>
        <b>AUTO · ${n} zd. · ${score(comp.symphony_score)}</b>
      </div>
      <div class="symmatch-mini__legs">
        ${preview.map((leg, i) => `<span><i>${i + 1}</i>${esc(leg?.label || leg?.key || 'Zdarzenie')}</span>`).join('')}
        ${legs.length > preview.length ? `<span class="symmatch-mini__more">+${legs.length - preview.length} zd.</span>` : ''}
      </div>
      <small>${coverage}${joint}${dna ? ` · ${esc(dna)}` : ''} · pełna Symfonia po otwarciu meczu</small>
    </div>`;
  }

  function legScore(leg) {
    if (finite(leg?.evidence_score)) return score(leg.evidence_score);
    if (finite(leg?.prod_score)) return score(leg.prod_score);
    if (finite(leg?.score)) return score(leg.score);
    return 'N/D';
  }

  function legMeta(leg) {
    const bits = [];
    if (leg?.market) bits.push(String(leg.market).replaceAll('_', ' '));
    if (finite(leg?.line)) bits.push(`linia ${lineText(leg.line)}`);
    if (finite(leg?.path_probability)) bits.push(`ścieżka ${pct(leg.path_probability)}`);
    else if (finite(leg?.prod_score)) bits.push(`PROD ${score(leg.prod_score)}`);
    return bits.join(' · ');
  }

  function detailHtml(row, chosen) {
    const { n, comp } = chosen;
    const legs = comp.selection || [];
    const coverage = finite(comp.path_coverage) ? `${Math.round(Number(comp.path_coverage) * 100)}%` : 'N/D';
    const joint = finite(comp.joint_probability) ? pct(comp.joint_probability) : 'N/D';
    const supported = finite(comp.supported_legs) ? `${Number(comp.supported_legs)}/${n}` : 'N/D';
    const dna = String(comp.story_type || '').replaceAll('_', ' ');
    const fragile = Array.isArray(comp.fragility) && comp.fragility.length ? comp.fragility[0] : null;
    const exactSix = n === 6;
    return `<section class="symmatch-detail" data-symphony-match-detail="1">
      <header class="symmatch-detail__head">
        <div><span>🎼 PEŁNA SYMFONIA</span><b>${exactSix ? '6 NÓG' : `MAX ${n} NÓG`}</b></div>
        <strong>${score(comp.symphony_score)}</strong>
      </header>
      ${!exactSix ? `<p class="symmatch-detail__notice">W tym meczu silnik nie zbudował bezpiecznej wersji 6‑nogowej. Pokazuję największą poprawną kompozycję: ${n} nogi.</p>` : ''}
      <div class="symmatch-detail__metrics">
        <span><small>coverage</small><b>${coverage}</b></span>
        <span><small>joint</small><b>${joint}</b></span>
        <span><small>exact</small><b>${supported}</b></span>
        <span><small>DNA</small><b>${esc(dna || 'BALANCED')}</b></span>
      </div>
      <div class="symmatch-detail__legs">
        ${legs.map((leg, i) => `<article>
          <i>${i + 1}</i>
          <div><b>${esc(leg?.label || leg?.key || 'Zdarzenie')}</b><small>${esc(legMeta(leg) || 'modelowa noga Symfonii')}</small></div>
          <strong>${legScore(leg)}</strong>
        </article>`).join('')}
      </div>
      ${fragile ? `<footer><span>⚠ Najbardziej krucha noga</span><b>${esc(fragile.label || fragile.key || 'N/D')}</b><em>fragility ${finite(fragile.fragility) ? Number(fragile.fragility).toFixed(1) : 'N/D'}</em></footer>` : ''}
      <p class="symmatch-detail__foot">AUTO na liście wybiera optymalną liczbę zdarzeń. Tutaj pokazujemy pełny wariant do 6 nóg z tej samej policzonej Symfonii.</p>
    </section>`;
  }

  async function decorateMatchCards() {
    const cards = [...document.querySelectorAll('.p751-match-card[data-p751-open]')];
    if (!cards.length) return 0;
    const report = await loadReport();
    if (!report) return 0;
    const map = lookupMap(report);
    let rendered = 0;

    for (const card of cards) {
      let raw = String(card.dataset.p751Open || '');
      try { raw = decodeURIComponent(raw); } catch {}
      const row = map.get(raw) || map.get(`id:${raw}`);
      if (!row) continue;
      const html = miniHtml(row);
      if (!html) continue;
      card.querySelector('[data-symphony-match-mini]')?.remove();
      const holder = document.createElement('div');
      holder.innerHTML = html;
      const mini = holder.firstElementChild;
      if (!mini) continue;
      const footer = card.querySelector('footer');
      if (footer) footer.insertAdjacentElement('beforebegin', mini);
      else card.append(mini);
      rendered += 1;
    }
    return rendered;
  }

  async function decorateOpenMatch() {
    const overlay = document.querySelector('#p751-match-overlay:not([hidden])');
    if (!overlay) return false;
    const raw = String(overlay.dataset.matchKey || '');
    if (!raw) return false;

    const old = overlay.querySelector('[data-symphony-match-detail]');
    if (old?.dataset?.matchKey === raw) return true;
    old?.remove();

    const anchor = overlay.querySelector('.p751-verdict') || overlay.querySelector('.p751-matchup');
    if (!anchor) return false;
    const loading = document.createElement('section');
    loading.className = 'symmatch-detail symmatch-detail--loading';
    loading.dataset.symphonyMatchDetail = '1';
    loading.dataset.matchKey = raw;
    loading.innerHTML = '<b>🎼 Pełna Symfonia</b><span>Ładowanie wariantu 6‑nogowego…</span>';
    anchor.insertAdjacentElement('afterend', loading);

    let chosen = null;
    let row = null;
    const compact = await loadReport();
    if (compact) {
      row = findRow(compact, raw);
      chosen = fullComposition(row);
    }
    if (!chosen) {
      const full = await loadFullReport();
      row = findRow(full, raw);
      chosen = fullComposition(row);
    }

    const current = document.querySelector('#p751-match-overlay:not([hidden])');
    if (!current || String(current.dataset.matchKey || '') !== raw) return false;
    const slot = current.querySelector('[data-symphony-match-detail]');
    if (!slot) return false;
    if (!row || !chosen) {
      slot.classList.remove('symmatch-detail--loading');
      slot.innerHTML = '<b>🎼 Pełna Symfonia</b><span>Brak gotowej kompozycji dla tego meczu.</span>';
      return false;
    }
    const holder = document.createElement('div');
    holder.innerHTML = detailHtml(row, chosen);
    const detail = holder.firstElementChild;
    if (!detail) return false;
    detail.dataset.matchKey = raw;
    slot.replaceWith(detail);
    return true;
  }

  function scheduleDecorate(delay = 120) {
    clearTimeout(decorateTimer);
    decorateTimer = setTimeout(() => decorateMatchCards(), delay);
  }

  function scheduleDetail(delay = 0) {
    clearTimeout(detailTimer);
    detailTimer = setTimeout(() => decorateOpenMatch(), delay);
  }

  function attachOverlayObserver() {
    const overlay = document.querySelector('#p751-match-overlay');
    if (!overlay || overlay.dataset.symphonyObserver === '1' || !('MutationObserver' in window)) return;
    overlay.dataset.symphonyObserver = '1';
    const observer = new MutationObserver(() => scheduleDetail(20));
    observer.observe(overlay, { childList: true, attributes: true, attributeFilter: ['hidden', 'data-match-key'] });
  }

  function boot() {
    ensureCss();

    const rescue = () => setTimeout(() => ensureStatsVisible(), 0);
    document.addEventListener('tenis-ai:stats-ready', rescue);
    document.addEventListener('tenis-ai:stats-dashboard-ready', rescue);
    document.addEventListener('tenis-ai:matches-rendered', () => scheduleDecorate(80));
    document.addEventListener('click', event => {
      if (event.target?.closest?.('[data-view="stats"],[data-p751-nav="stats"],#pc882-legacy,summary')) rescue();
      if (event.target?.closest?.('[data-view="matches"],[data-p751-nav="matches"]')) scheduleDecorate(120);
      if (event.target?.closest?.('[data-p751-open]')) {
        setTimeout(attachOverlayObserver, 0);
        scheduleDetail(30);
      }
    }, true);

    setTimeout(() => ensureStatsVisible(), 500);
    if (document.querySelector('.p751-match-card[data-p751-open]')) scheduleDecorate(900);
    attachOverlayObserver();

    const app = document.querySelector('#app');
    if (app && 'MutationObserver' in window) {
      const observer = new MutationObserver(records => {
        if (records.some(r => [...r.addedNodes].some(n => n.nodeType === 1 && (n.matches?.('.p751-match-card') || n.querySelector?.('.p751-match-card'))))) {
          scheduleDecorate(100);
        }
      });
      observer.observe(app, { childList: true, subtree: true });
    }

    if ('MutationObserver' in window) {
      const bodyObserver = new MutationObserver(records => {
        if (records.some(r => [...r.addedNodes].some(n => n.nodeType === 1 && (n.id === 'p751-match-overlay' || n.querySelector?.('#p751-match-overlay'))))) {
          attachOverlayObserver();
          scheduleDetail(20);
        }
      });
      bodyObserver.observe(document.body, { childList: true });
    }
  }

  window.TENIS_AI_SYMPHONY_SURFACE_V90 = Object.freeze({
    version: VERSION,
    ensureStatsVisible,
    decorateMatchCards,
    decorateOpenMatch,
    reload: async () => {
      reportCache = null;
      fullReportCache = null;
      const report = await loadReport();
      await decorateMatchCards();
      await decorateOpenMatch();
      await ensureStatsVisible();
      return report;
    }
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
