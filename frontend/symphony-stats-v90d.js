/* Tenis AI v9.3B — separate Symphony MODEL/RAW and operator-aware stats */
(() => {
  'use strict';

  const VERSION = 'v9.3B';
  const OPERATOR_URL = './data/symphony_stats_v90d.json';
  const MODEL_URL = './data/symphony_model_stats_v93.json';
  let cache = null;
  let loading = null;

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
  const finite = (v) => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const pct = (v) => finite(v) ? `${Number(v).toFixed(1)}%` : 'N/D';
  const nfmt = (v) => Number(v || 0).toLocaleString('pl-PL');

  async function fetchJson(url) {
    try {
      const r = await fetch(`${url}?v=${Date.now()}`, { cache: 'no-store' });
      return r.ok ? await r.json() : null;
    } catch (_) {
      return null;
    }
  }

  async function load(force = false) {
    if (cache && !force) return cache;
    if (loading && !force) return loading;
    loading = Promise.all([fetchJson(OPERATOR_URL), fetchJson(MODEL_URL)])
      .then(([operatorAware, modelRaw]) => (cache = { operatorAware, modelRaw }))
      .finally(() => { loading = null; });
    return loading;
  }

  function bar(value, kind) {
    const width = finite(value) ? Math.max(0, Math.min(100, Number(value))) : 0;
    return `<span class="symstats-bar symstats-bar--${kind}"><i style="width:${width.toFixed(1)}%"></i></span>`;
  }

  function sampleBadge(row, learning) {
    if (!row) return '<em class="symstats-sample">brak próby</em>';
    if (learning && row.history_weight_ready) return '<em class="symstats-sample symstats-sample--ready">UCZY AUTO</em>';
    const n = Number(row.full_settled || 0);
    return `<em class="symstats-sample">${learning ? `próba ${n}/20` : `obserwacja n=${n}`}</em>`;
  }

  function legChart(data, learning = false) {
    const rows = [2, 3, 4, 5, 6].map(legs => data?.leg_counts?.[String(legs)] || { legs });
    return `<div class="symstats-chart" role="img" aria-label="Skuteczność Symfonii według liczby zdarzeń">
      <div class="symstats-chart__legend"><span><i class="full"></i>pełna Symfonia</span><span><i class="legs"></i>pojedyncze nogi</span></div>
      ${rows.map(row => `
        <div class="symstats-chart__row">
          <div class="symstats-chart__label"><b>${row.legs || '—'} zd.</b>${sampleBadge(row, learning)}</div>
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

  function readiness(data, learning) {
    if (!learning) {
      const settled = Number(data?.settled_matches || 0);
      const pending = Number(data?.pending_matches || 0);
      return `<b>🔬 MODEL/RAW · obserwacja</b><span>${settled} rozliczonych · ${pending} oczekuje · bez wpływu na AUTO/PLAYABLE</span>`;
    }
    const ready = [2, 3, 4, 5, 6].filter(n => data?.leg_counts?.[String(n)]?.history_weight_ready);
    if (ready.length >= 2) return `<b>🧠 Historia aktywnie wspiera AUTO</b><span>gotowe koszyki: ${ready.join(', ')} zdarzeń</span>`;
    const best = [2, 3, 4, 5, 6]
      .map(n => data?.leg_counts?.[String(n)])
      .filter(Boolean)
      .sort((a, b) => Number(b.full_settled || 0) - Number(a.full_settled || 0))[0];
    return `<b>🌱 AUTO zbiera próbkę</b><span>${best ? `największa próba: ${best.legs} zd. · ${best.full_settled}/20 pełnych rozliczeń` : 'pierwsze zamrożone Symfonie pojawią się po kolejnych meczach'}</span>`;
  }

  function storyRows(data, model = false) {
    const source = model && Array.isArray(data?.auto_story_types) ? data.auto_story_types : (data?.story_types || []);
    const rows = source.filter(x => Number(x.resolved_legs || 0) > 0).slice(0, 8);
    if (!rows.length) return '<div class="symstats-empty">Rodziny scenariuszy zaczną się porównywać po pierwszych rozliczeniach.</div>';
    return `<div class="symstats-stories">${rows.map(x => `
      <div><span>${esc(x.story_type)}</span><b>${pct(x.leg_accuracy)}</b><small>${nfmt(x.resolved_legs)} nóg · pełne ${pct(x.full_hit_rate)} (n=${nfmt(x.full_settled)})</small></div>
    `).join('')}</div>`;
  }

  function marketRows(data) {
    const rows = (data?.auto_market_accuracy || []).filter(x => Number(x.resolved || 0) > 0).slice(0, 12);
    if (!rows.length) return '<div class="symstats-empty">Dokładność rodzin rynków pojawi się po rozliczeniu pierwszych deep Symfonii.</div>';
    return `<div class="symstats-stories">${rows.map(x => `
      <div><span>${esc(String(x.market || '').replaceAll('_', ' '))}</span><b>${pct(x.accuracy)}</b><small>${nfmt(x.hits)}/${nfmt(x.resolved)} nóg · N/D ${nfmt(x.unknown)}${finite(x.avg_evidence_score) ? ` · evidence ${Number(x.avg_evidence_score).toFixed(1)}` : ''}</small></div>
    `).join('')}</div>`;
  }

  function calibrationRows(data) {
    const rows = (data?.joint_calibration || []).filter(x => Number(x.n || 0) > 0);
    if (!rows.length) return '<div class="symstats-empty">Kalibracja joint probability potrzebuje pełnych, rozliczonych kompozycji exact.</div>';
    return `<div class="symstats-stories">${rows.map(x => `
      <div><span>joint ${esc(x.bucket)}</span><b>${pct(x.observed_full_hit_rate)}</b><small>model średnio ${pct(x.avg_predicted_joint)} · n=${nfmt(x.n)} · gap ${finite(x.calibration_gap) ? `${Number(x.calibration_gap) >= 0 ? '+' : ''}${Number(x.calibration_gap).toFixed(1)} pp` : 'N/D'}</small></div>
    `).join('')}</div>`;
  }

  function card(data, { model = false } = {}) {
    const auto = data?.auto || {};
    const id = model ? 'symphony-model-performance-v93' : 'symphony-performance-v90d';
    const kicker = model ? '🎼 SYMFONIA · MODEL/RAW DEEP' : '🎼 SYMFONIA · OPERATOR-AWARE';
    const title = model ? 'Skuteczność głębokich scenariuszy' : 'Skuteczność wg liczby zdarzeń';
    const subtitle = model
      ? 'Osobna historia modelowa. Nie jest mieszana ze skutecznością Superbet PLAYABLE i nie steruje jeszcze AUTO.'
      : 'Warstwa bieżącej Symfonii z gate Superbet tam, gdzie oferta operatora jest świeżo zweryfikowana.';
    return `<section id="${id}" class="symstats-card" data-version="${VERSION}">
      <header class="symstats-head">
        <div><span>${kicker}</span><h3>${title}</h3><p>${subtitle}</p></div>
        <div class="symstats-live">${readiness(data, !model)}</div>
      </header>

      <div class="symstats-kpis">
        <div><span>Rozliczone mecze</span><b>${nfmt(data?.settled_matches)}</b><small>${nfmt(data?.pending_matches)} oczekuje</small></div>
        <div><span>AUTO · pełna Symfonia</span><b>${pct(auto.full_hit_rate)}</b><small>n=${nfmt(auto.full_settled)}</small></div>
        <div><span>AUTO · nogi</span><b>${pct(auto.leg_accuracy)}</b><small>${nfmt(auto.leg_hits)}/${nfmt(auto.resolved_legs)}</small></div>
        <div><span>${model ? 'Wpływ na PLAYABLE' : 'Próg nauki'}</span><b>${model ? '0' : '20 + 50'}</b><small>${model ? 'obserwacja בלבד' : 'pełne Symfonie + nogi'}</small></div>
      </div>

      <section class="symstats-section">
        <div class="symstats-section__head"><b>📊 Która liczba zdarzeń działa najlepiej?</b><small>${model ? 'MODEL/RAW liczone osobno' : 'jakość normalizowana na liczbę nóg'}</small></div>
        ${legChart(data, !model)}
      </section>

      <section class="symstats-section">
        <div class="symstats-section__head"><b>🧬 Rodziny scenariuszy</b><small>${model ? 'DNA głębokiej Symfonii · AUTO' : 'trafność nóg i całych Symfonii'}</small></div>
        ${storyRows(data, model)}
      </section>

      ${model ? `<section class="symstats-section">
        <div class="symstats-section__head"><b>🎯 Rynki użyte przez AUTO</b><small>bez dublowania tych samych nóg z wariantów 2–6</small></div>
        ${marketRows(data)}
      </section>
      <section class="symstats-section">
        <div class="symstats-section__head"><b>🧪 Kalibracja joint probability</b><small>czy wspólna masa scenariusza zgadza się z realną trafialnością całych kompozycji</small></div>
        ${calibrationRows(data)}
      </section>` : ''}

      <div class="symstats-note">${model
        ? 'MODEL/RAW ma własną historię i settlement. Brak danych = N/D. Stan 2. seta po 2/4/6 gemach pozostaje N/D, dopóki nie mamy prawdziwego PBP dla tego checkpointu. Te statystyki nie zwiększają ani nie obniżają skuteczności PLAYABLE.'
        : 'Pełna skuteczność jest liczona tylko wtedy, gdy da się rozliczyć wszystkie nogi. Brak danych = N/D, nigdy automatyczne pudło. Historia dostaje wagę w AUTO dopiero po odpowiedniej próbie.'}</div>
    </section>`;
  }

  function host() {
    return document.querySelector('#pc77');
  }

  function insert(bundle) {
    const root = host();
    if (!root || (!bundle?.operatorAware && !bundle?.modelRaw)) return false;
    root.querySelector('#symphony-performance-suite-v93')?.remove();
    root.querySelector('#symphony-performance-v90d')?.remove();
    root.querySelector('#symphony-model-performance-v93')?.remove();

    const wrapper = document.createElement('div');
    wrapper.id = 'symphony-performance-suite-v93';
    wrapper.dataset.version = VERSION;
    wrapper.innerHTML = [
      bundle.modelRaw ? card(bundle.modelRaw, { model: true }) : '',
      bundle.operatorAware ? card(bundle.operatorAware, { model: false }) : '',
    ].join('');

    const anchor = root.querySelector('.pc12-main-trend') || root.querySelector('.pc12-summary');
    if (anchor) anchor.insertAdjacentElement('afterend', wrapper);
    else root.prepend(wrapper);
    return true;
  }

  async function render(force = false) {
    const data = await load(force);
    return insert(data);
  }

  function scheduleRender(force = false) {
    [0, 120, 500, 1200].forEach(delay => setTimeout(() => render(force && delay === 0), delay));
  }

  function boot() {
    document.addEventListener('tenis-ai:stats-ready', () => scheduleRender());
    document.addEventListener('tenis-ai:stats-dashboard-ready', () => scheduleRender());
    document.addEventListener('click', event => {
      if (event.target?.closest?.('[data-view="stats"],[data-p751-nav="stats"]')) scheduleRender();
    }, true);
    scheduleRender();
  }

  window.TENIS_AI_SYMPHONY_STATS_V90D = Object.freeze({ version: VERSION, render, reload: () => render(true) });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
