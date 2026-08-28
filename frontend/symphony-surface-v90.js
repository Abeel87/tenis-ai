/* Tenis AI v9.0D.2 — keep Symphony visible in Stats + compact match-card view */
(() => {
  'use strict';

  const VERSION = 'v9.0D.2';
  const DATA_URL = './data/symphony_v90.json';
  let reportPromise = null;
  let reportCache = null;
  let decorateTimer = null;

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
  const finite = (v) => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const score = (v) => finite(v) ? `${Number(v).toFixed(1).replace('.0', '')}/100` : 'N/D';
  const pct = (v) => finite(v) ? `${Number(v).toFixed(1).replace('.0', '')}%` : 'N/D';

  function ensureCss() {
    if (document.querySelector('link[data-symphony-surface-v90]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'symphony-surface-v90.css?v=90d2';
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

    // v883-final groups unknown direct children into its PRO/legacy disclosure.
    // Symphony Performance is a first-class current dashboard, so pull it back
    // out after cleanup instead of letting it disappear in diagnostics.
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
    reportPromise = fetch(`${DATA_URL}?surface=90d2`, { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => (reportCache = data))
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

  function composition(row) {
    const recommended = Number(row?.recommended_leg_count);
    const candidates = [recommended, 2, 3, 4, 5, 6].filter((x, i, a) => Number.isInteger(x) && a.indexOf(x) === i);
    for (const n of candidates) {
      const comp = row?.compositions?.[String(n)];
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
      <small>${coverage}${joint}${dna ? ` · ${esc(dna)}` : ''} · pełny widok w Scenariuszach</small>
    </div>`;
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

  function scheduleDecorate(delay = 120) {
    clearTimeout(decorateTimer);
    decorateTimer = setTimeout(() => decorateMatchCards(), delay);
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
    }, true);

    setTimeout(() => ensureStatsVisible(), 500);
    if (document.querySelector('.p751-match-card[data-p751-open]')) scheduleDecorate(900);

    const app = document.querySelector('#app');
    if (app && 'MutationObserver' in window) {
      const observer = new MutationObserver(records => {
        if (records.some(r => [...r.addedNodes].some(n => n.nodeType === 1 && (n.matches?.('.p751-match-card') || n.querySelector?.('.p751-match-card'))))) {
          scheduleDecorate(100);
        }
      });
      observer.observe(app, { childList: true, subtree: true });
    }
  }

  window.TENIS_AI_SYMPHONY_SURFACE_V90 = Object.freeze({
    version: VERSION,
    ensureStatsVisible,
    decorateMatchCards,
    reload: async () => {
      reportCache = null;
      const report = await loadReport();
      await decorateMatchCards();
      await ensureStatsVisible();
      return report;
    }
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
