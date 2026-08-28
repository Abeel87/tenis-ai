/* Tenis AI v9.0D — Symphony Performance in Statystyki */
(() => {
  'use strict';

  const VERSION = 'v9.0D';
  const DATA_URL = './data/symphony_stats_v90d.json';
  let cache = null;
  let loading = null;

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
  const finite = (v) => Number.isFinite(Number(v));
  const pct = (v) => finite(v) ? `${Number(v).toFixed(1)}%` : 'N/D';
  const nfmt = (v) => Number(v || 0).toLocaleString('pl-PL');

  async function load(force = false) {
    if (cache && !force) return cache;
    if (loading && !force) return loading;
    loading = fetch(`${DATA_URL}?v=${Date.now()}`, { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => (cache = data))
      .catch(() => null)
      .finally(() => { loading = null; });
    return loading;
  }

  function bar(value, kind) {
    const width = finite(value) ? Math.max(0, Math.min(100, Number(value))) : 0;
    return `<span class="symstats-bar symstats-bar--${kind}"><i style="width:${width.toFixed(1)}%"></i></span>`;
  }

  function sampleBadge(row) {
    if (!row) return '<em class="symstats-sample">brak próby</em>';
    if (row.history_weight_ready) return '<em class="symstats-sample symstats-sample--ready">UCZY AUTO</em>';
    const n = Number(row.full_settled || 0);
    return `<em class="symstats-sample">próba ${n}/20</em>`;
  }

  function legChart(data) {
    const rows = [2, 3, 4, 5, 6].map(legs => data?.leg_counts?.[String(legs)] || { legs });
    return `<div class="symstats-chart" role="img" aria-label="Skuteczność Symfonii według liczby zdarzeń">
      <div class="symstats-chart__legend"><span><i class="full"></i>pełna Symfonia</span><span><i class="legs"></i>pojedyncze nogi</span></div>
      ${rows.map(row => `
        <div class="symstats-chart__row">
          <div class="symstats-chart__label"><b>${row.legs || '—'} zd.</b>${sampleBadge(row)}</div>
          <div class="symstats-chart__metric">
            <span>całość <b>${pct(row.full_hit_rate)}</b><small>n=${nfmt(row.full_settled)}</small></span>
            ${bar(row.full_hit_rate, 'full')}
          </div>
          <div class="symstats-chart__metric">
            <span>nogi <b>${pct(row.leg_accuracy)}</b><small>n=${nfmt(row.resolved_legs)}</small></span>
            ${bar(row.leg_accuracy, 'legs')}
          </div>
          <div class="symstats-chart__quality"><span>jakość norm.</span><b>${pct(row.normalized_quality)}</b></div>
        </div>`).join('')}
    </div>`;
  }

  function readiness(data) {
    const ready = [2, 3, 4, 5, 6].filter(n => data?.leg_counts?.[String(n)]?.history_weight_ready);
    if (ready.length >= 2) return `<b>🧠 Historia aktywnie wspiera AUTO</b><span>gotowe koszyki: ${ready.join(', ')} zdarzeń</span>`;
    const best = [2, 3, 4, 5, 6]
      .map(n => data?.leg_counts?.[String(n)])
      .filter(Boolean)
      .sort((a, b) => Number(b.full_settled || 0) - Number(a.full_settled || 0))[0];
    return `<b>🌱 AUTO zbiera próbkę</b><span>${best ? `największa próba: ${best.legs} zd. · ${best.full_settled}/20 pełnych rozliczeń` : 'pierwsze zamrożone Symfonie pojawią się po kolejnych meczach'}</span>`;
  }

  function storyRows(data) {
    const rows = (data?.story_types || []).filter(x => Number(x.resolved_legs || 0) > 0).slice(0, 6);
    if (!rows.length) return '<div class="symstats-empty">Rodziny scenariuszy zaczną się porównywać po pierwszych rozliczeniach.</div>';
    return `<div class="symstats-stories">${rows.map(x => `
      <div><span>${esc(x.story_type)}</span><b>${pct(x.leg_accuracy)}</b><small>${nfmt(x.resolved_legs)} nóg · pełne ${pct(x.full_hit_rate)} (n=${nfmt(x.full_settled)})</small></div>
    `).join('')}</div>`;
  }

  function card(data) {
    const auto = data?.auto || {};
    return `<section id="symphony-performance-v90d" class="symstats-card" data-version="${VERSION}">
      <header class="symstats-head">
        <div><span>🎼 SYMFONIA TENISOWA</span><h3>Skuteczność wg liczby zdarzeń</h3><p>2 / 3 / 4 / 5 / 6 nóg są rozliczane równolegle na tych samych meczach.</p></div>
        <div class="symstats-live">${readiness(data)}</div>
      </header>

      <div class="symstats-kpis">
        <div><span>Rozliczone mecze</span><b>${nfmt(data?.settled_matches)}</b><small>${nfmt(data?.pending_matches)} oczekuje</small></div>
        <div><span>AUTO · pełna Symfonia</span><b>${pct(auto.full_hit_rate)}</b><small>n=${nfmt(auto.full_settled)}</small></div>
        <div><span>AUTO · nogi</span><b>${pct(auto.leg_accuracy)}</b><small>${nfmt(auto.leg_hits)}/${nfmt(auto.resolved_legs)}</small></div>
        <div><span>Próg nauki</span><b>20 + 50</b><small>pełne Symfonie + nogi</small></div>
      </div>

      <section class="symstats-section">
        <div class="symstats-section__head"><b>📊 Która liczba zdarzeń działa najlepiej?</b><small>pełna trafialność nie steruje AUTO sama — jakość jest normalizowana na liczbę nóg</small></div>
        ${legChart(data)}
      </section>

      <section class="symstats-section">
        <div class="symstats-section__head"><b>🧬 Rodziny scenariuszy</b><small>trafność nóg i całych Symfonii</small></div>
        ${storyRows(data)}
      </section>

      <div class="symstats-note">Pełna skuteczność jest liczona tylko wtedy, gdy da się rozliczyć wszystkie nogi. Brak danych = N/D, nigdy automatyczne pudło. Historia dostaje wagę w AUTO dopiero po odpowiedniej próbie.</div>
    </section>`;
  }

  function host() {
    return document.querySelector('#pc77');
  }

  function insert(data) {
    const root = host();
    if (!root || !data) return false;
    root.querySelector('#symphony-performance-v90d')?.remove();
    const node = document.createElement('div');
    node.innerHTML = card(data);
    const section = node.firstElementChild;
    const anchor = root.querySelector('.pc12-main-trend') || root.querySelector('.pc12-summary');
    if (anchor) anchor.insertAdjacentElement('afterend', section);
    else root.prepend(section);
    return true;
  }

  async function render(force = false) {
    const data = await load(force);
    if (data) insert(data);
  }

  function boot() {
    document.addEventListener('tenis-ai:stats-ready', () => setTimeout(() => render(), 0));
    document.addEventListener('tenis-ai:stats-dashboard-ready', () => setTimeout(() => render(), 0));
    document.addEventListener('click', event => {
      if (event.target?.closest?.('[data-view="stats"],[data-p751-nav="stats"]')) setTimeout(() => render(), 80);
    }, true);
    setTimeout(() => render(), 800);
  }

  window.TENIS_AI_SYMPHONY_STATS_V90D = Object.freeze({ version: VERSION, render, reload: () => render(true) });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
