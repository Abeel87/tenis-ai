(() => {
  'use strict';

  const VERSION = 'v9.0B';
  const DATA_URL = './data/symphony_v90.json';
  let cache = null;

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  const storyLabel = (value) => ({
    BREAK_REBREAK: 'Break → szybki rebreak',
    SERVE_WAR: 'Wojna serwisowa',
    TIEBREAK_MAGNET: 'Scenariusz tie-breakowy',
    FAST_CONTROL: 'Szybka kontrola seta',
    LONG_SET: 'Długi set',
    ONE_SIDED: 'Jednostronny mecz',
    BALANCED: 'Scenariusz zbalansowany'
  }[value] || 'Scenariusz modelowy');

  const scoreClass = (n) => n >= 85 ? 'symphony-score--elite' : n >= 75 ? 'symphony-score--good' : 'symphony-score--watch';
  const pct = (v) => Number.isFinite(Number(v)) ? `${Number(v).toFixed(1)}%` : 'N/D';

  async function loadData(force = false) {
    if (cache && !force) return cache;
    const res = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    cache = await res.json();
    return cache;
  }

  function localDate(value) {
    const d = new Date(value || '');
    if (!Number.isFinite(d.getTime())) return '';
    return d.toLocaleDateString('en-CA');
  }

  function todayKey() {
    return new Date().toLocaleDateString('en-CA');
  }

  function timeLabel(value) {
    const d = new Date(value || '');
    return Number.isFinite(d.getTime()) ? d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' }) : '—';
  }

  function legHtml(leg) {
    const shadowCount = Object.keys(leg.shadow_scores || {}).length;
    const path = leg.path_probability == null ? '' : ` · PATH ${pct(leg.path_probability)}`;
    return `
      <div class="symphony-leg">
        <div class="symphony-leg__main">
          <strong>${esc(leg.label || leg.key)}</strong>
          <span>${esc(leg.market)}</span>
        </div>
        <div class="symphony-leg__numbers">
          <b>${Number(leg.evidence_score || 0).toFixed(1)}</b>
          <small>PROD ${Number(leg.prod_score || 0).toFixed(1)}${shadowCount ? ` · SHADOW ×${shadowCount}` : ''}${path}</small>
        </div>
      </div>`;
  }

  function pathsHtml(paths) {
    if (!paths?.length) return '<div class="symphony-path-empty">Brak pełnej ścieżki dla tej kombinacji.</div>';
    return `<div class="symphony-paths">${paths.slice(0, 5).map((p, i) => `
      <div class="symphony-path">
        <span>#${i + 1}</span>
        <strong>${esc(p.path)}</strong>
        <small>${Number(p.probability_mass || 0).toFixed(3)}% masy dokładnej ścieżki · ${Number(p.total_games || 0)} gemów</small>
      </div>`).join('')}</div>`;
  }

  function compositionFor(match, legs, variant = 0) {
    const root = match?.compositions?.[String(legs)];
    if (!root) return null;
    if (!variant) return root;
    return root.alternatives?.[variant - 1] || root;
  }

  function matchCard(match, comp, legs) {
    if (!comp) return '';
    const score = Number(comp.symphony_score || 0);
    const frag = (comp.fragility || [])[0];
    const exactJoint = comp.joint_probability;
    const coverage = Math.round(Number(comp.path_coverage || 0) * 100);
    return `
      <article class="symphony-card">
        <div class="symphony-card__head">
          <div>
            <div class="symphony-meta">${esc(match.tour || '')}${match.surface ? ` · ${esc(match.surface)}` : ''} · ${esc(timeLabel(match.scheduled_time))}</div>
            <h3>${esc(match.p1)} <span>vs</span> ${esc(match.p2)}</h3>
            <p>${esc(storyLabel(comp.story_type))}</p>
          </div>
          <div class="symphony-score ${scoreClass(score)}">
            <strong>${score.toFixed(1)}</strong><span>/100</span>
          </div>
        </div>

        <div class="symphony-story-strip">
          <span>silnik <b>${esc(match.path_engine || 'EVIDENCE')}</b></span>
          <span>joint coverage <b>${coverage}%</b></span>
          <span>PROD/SHADOW <b>${Math.round(Number(comp.prod_shadow_agreement || 0) * 100)}%</b></span>
          <span>konflikt <b>${Math.round(Number(comp.model_conflict || 0) * 100)}%</b></span>
        </div>

        ${exactJoint != null
          ? `<div class="symphony-joint"><span>Wspólna masa scenariusza</span><strong>${Number(exactJoint).toFixed(2)}%</strong><small>policzona na tych samych dokładnych stanach meczu</small></div>`
          : `<div class="symphony-joint symphony-joint--partial"><span>Ocena scenariusza</span><strong>${score.toFixed(1)}/100</strong><small>nie pokazuję fałszywego joint probability — nie wszystkie ${legs} rynki są jeszcze w exact engine</small></div>`}

        <div class="symphony-legs">${(comp.selection || []).map(legHtml).join('')}</div>

        ${frag ? `<div class="symphony-fragile"><span>⚠ Najbardziej kruche</span><strong>${esc(frag.label)}</strong><small>fragility ${Number(frag.fragility || 0).toFixed(1)}${frag.remove_joint_probability != null ? ` · bez niego joint ${Number(frag.remove_joint_probability).toFixed(2)}%` : ''}</small></div>` : ''}

        <details class="symphony-details">
          <summary>🎼 Najbardziej prawdopodobne ścieżki</summary>
          ${pathsHtml(comp.top_paths)}
        </details>
      </article>`;
  }

  function rankedMatches(data, legs, variant) {
    const rows = (data.matches || [])
      .map(match => ({ match, comp: compositionFor(match, legs, variant) }))
      .filter(x => x.comp);
    const today = rows.filter(x => localDate(x.match.scheduled_time) === todayKey());
    const source = today.length ? today : rows;
    return source.sort((a, b) => Number(b.comp.symphony_score || 0) - Number(a.comp.symphony_score || 0));
  }

  function resultsHtml(data, matchCount, legs, variant) {
    const rows = rankedMatches(data, legs, variant).slice(0, matchCount);
    if (!rows.length) return '<div class="symphony-empty">Brak scenariuszy spełniających warunki.</div>';
    return rows.map(x => matchCard(x.match, x.comp, legs)).join('');
  }

  function shell(data) {
    return `
      <section id="tennis-symphony-v90" class="symphony-shell" data-version="${VERSION}">
        <button class="symphony-back" type="button" data-symphony-back>← Scenariusze</button>
        <div class="symphony-hero">
          <div>
            <span class="symphony-kicker">🎼 TENIS AI · ${esc(data.version || VERSION)}</span>
            <h2>Symfonia Tenisowa</h2>
            <p>Najpierw możliwy przebieg meczu. Dopiero potem rynki, które opisują tę samą historię.</p>
          </div>
          <div class="symphony-contract">
            <b>PROD = rdzeń</b>
            <span>SHADOW = dowód pomocniczy</span>
            <small>bez zmiany Ensemble / final_score</small>
          </div>
        </div>

        <div class="symphony-controls">
          <label>Mecze
            <select id="symphony-match-count">
              <option>1</option><option>2</option><option>3</option><option selected>4</option><option>5</option><option>6</option>
            </select>
          </label>
          <label>Zdarzenia / mecz
            <select id="symphony-leg-count">
              <option>2</option><option>3</option><option selected>4</option><option>5</option><option>6</option>
            </select>
          </label>
          <label>Wariant
            <select id="symphony-variant">
              <option value="0" selected>Główna Symfonia</option>
              <option value="1">Kontrscenariusz A</option>
              <option value="2">Kontrscenariusz B</option>
              <option value="3">Kontrscenariusz C</option>
            </select>
          </label>
          <button id="symphony-generate" type="button">🎼 Ułóż Symfonię</button>
        </div>

        <div class="symphony-note">
          Exact State Engine liczy po 2 / 4 / 6 gemach, wynik 1. seta, wynik meczu, liczbę setów i gemy z jednego wspólnego drzewa. Jeśli któregoś rynku jeszcze nie umie policzyć dokładnie, nie udaje joint probability.
        </div>
        <div id="symphony-results" class="symphony-grid">${resultsHtml(data, 4, 4, 0)}</div>
      </section>`;
  }

  function scenarioPanel() {
    return document.querySelector('#scenario-v82a-panel');
  }

  function scenarioBody() {
    return scenarioPanel()?.querySelector('.sc82-body') || null;
  }

  function decorateHome() {
    const panel = scenarioPanel();
    if (!panel || panel.hidden) return;
    const button = panel.querySelector('[data-sc-go="generator"]');
    if (!button) return;
    button.innerHTML = '<b>🎼 Symfonia Tenisowa</b><span>1–6 meczów · 2–6 zdarzeń · pełny scenariusz meczu</span>';
  }

  async function openSymphony() {
    const body = scenarioBody();
    if (!body) return;
    body.innerHTML = '<div class="sc82-loading">Stroję modele i ścieżki meczu…</div>';
    try {
      const data = await loadData();
      body.innerHTML = shell(data);
      bindBody(body, data);
    } catch (err) {
      console.warn('[Symphony] load failed', err);
      body.innerHTML = `
        <section class="symphony-shell">
          <button class="symphony-back" type="button" data-symphony-back>← Scenariusze</button>
          <div class="symphony-empty"><b>Symfonia nie ma jeszcze aktualnego raportu.</b><br>Po następnym przebiegu danych spróbuj ponownie.</div>
        </section>`;
      bindBody(body, null);
    }
  }

  function bindBody(body, data) {
    body.querySelector('[data-symphony-back]')?.addEventListener('click', () => {
      window.TENIS_AI_SCENARIOS?.open?.('home');
      setTimeout(decorateHome, 0);
    });
    if (!data) return;
    body.querySelector('#symphony-generate')?.addEventListener('click', () => {
      const matchCount = Number(body.querySelector('#symphony-match-count')?.value || 4);
      const legs = Number(body.querySelector('#symphony-leg-count')?.value || 4);
      const variant = Number(body.querySelector('#symphony-variant')?.value || 0);
      const target = body.querySelector('#symphony-results');
      if (target) target.innerHTML = resultsHtml(data, matchCount, legs, variant);
    });
  }

  function interceptGeneratorClicks() {
    document.addEventListener('click', (event) => {
      const generator = event.target.closest?.('#scenario-v82a-panel [data-sc-go="generator"]');
      if (generator) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        openSymphony();
        return;
      }
      if (event.target.closest?.('#p751-bottom-nav [data-p751-nav="scenarios"]')) {
        setTimeout(decorateHome, 0);
      }
    }, true);
  }

  function patchScenarioApi() {
    const api = window.TENIS_AI_SCENARIOS;
    if (!api || api.__symphony_v90) return false;
    api.legacyGenerate = api.generate;
    api.generate = openSymphony;
    api.symphony = openSymphony;
    api.__symphony_v90 = true;
    return true;
  }

  function bootstrap() {
    interceptGeneratorClicks();
    if (!patchScenarioApi()) {
      [100, 300, 700, 1400, 2600].forEach(ms => setTimeout(() => {
        patchScenarioApi();
        decorateHome();
      }, ms));
    }
    decorateHome();
  }

  window.TENIS_AI_SYMPHONY_V90 = {
    version: VERSION,
    open: openSymphony,
    reload: () => loadData(true),
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bootstrap, { once: true });
  else bootstrap();
})();
