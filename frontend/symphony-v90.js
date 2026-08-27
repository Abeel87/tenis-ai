(() => {
  'use strict';

  const VERSION = 'v9.0';
  const DATA_URL = './data/symphony_v90.json';

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  const storyLabel = (value) => ({
    BREAK_REBREAK: 'Break → rebreak',
    SERVE_WAR: 'Wojna serwisowa',
    FAST_CONTROL: 'Szybka kontrola',
    LONG_SET: 'Długi set',
    BALANCED: 'Scenariusz zbalansowany'
  }[value] || 'Scenariusz modelowy');

  const scoreClass = (n) => n >= 85 ? 'symphony-score--elite' : n >= 75 ? 'symphony-score--good' : 'symphony-score--watch';

  async function loadData() {
    const res = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  function legHtml(leg) {
    const shadowCount = Object.keys(leg.shadow_scores || {}).length;
    return `
      <div class="symphony-leg">
        <div class="symphony-leg__main">
          <strong>${esc(leg.label || leg.key)}</strong>
          <span>${esc(leg.market)}</span>
        </div>
        <div class="symphony-leg__numbers">
          <b>${Number(leg.evidence_score || 0).toFixed(1)}</b>
          <small>PROD ${Number(leg.prod_score || 0).toFixed(1)}${shadowCount ? ` · SHADOW ×${shadowCount}` : ''}</small>
        </div>
      </div>`;
  }

  function matchCard(match) {
    const score = Number(match.symphony_score || 0);
    const frag = (match.fragility || [])[0];
    return `
      <article class="symphony-card">
        <div class="symphony-card__head">
          <div>
            <div class="symphony-meta">${esc(match.tour || '')} ${match.surface ? `· ${esc(match.surface)}` : ''}</div>
            <h3>${esc(match.p1)} <span>vs</span> ${esc(match.p2)}</h3>
            <p>${esc(storyLabel(match.story_type))}</p>
          </div>
          <div class="symphony-score ${scoreClass(score)}">
            <strong>${score.toFixed(1)}</strong><span>/100</span>
          </div>
        </div>
        <div class="symphony-story-strip">
          <span>zgodność PROD/SHADOW <b>${Math.round(Number(match.prod_shadow_agreement || 0) * 100)}%</b></span>
          <span>konflikt <b>${Math.round(Number(match.model_conflict || 0) * 100)}%</b></span>
          <span>${Number(match.legs_selected || 0)} zdarzenia</span>
        </div>
        <div class="symphony-legs">${(match.selection || []).map(legHtml).join('')}</div>
        ${frag ? `<div class="symphony-fragile"><span>⚠ Najbardziej kruche</span><strong>${esc(frag.label)}</strong><small>fragility ${Number(frag.fragility || 0).toFixed(1)}</small></div>` : ''}
        <details class="symphony-details">
          <summary>Alternatywy i dowody</summary>
          <div class="symphony-alt">${(match.alternatives || []).slice(0, 5).map(legHtml).join('')}</div>
        </details>
      </article>`;
  }

  function shell(data) {
    const matches = (data.matches || []).slice(0, 12);
    return `
      <section id="tennis-symphony-v90" class="symphony-shell" data-version="${VERSION}">
        <div class="symphony-hero">
          <div>
            <span class="symphony-kicker">🎼 TENIS AI · ${VERSION}</span>
            <h2>Symfonia Tenisowa</h2>
            <p>Modele nie wybierają pojedynczych typów. Układają spójny scenariusz meczu, a potem dobierają do niego rynki.</p>
          </div>
          <div class="symphony-contract">
            <b>PROD = rdzeń</b>
            <span>SHADOW = dowód pomocniczy</span>
            <small>bez zmiany final_score</small>
          </div>
        </div>

        <div class="symphony-controls">
          <label>Mecze <select id="symphony-match-count"><option>1</option><option>2</option><option>3</option><option selected>4</option><option>5</option><option>6</option></select></label>
          <label>Zdarzenia / mecz <select id="symphony-leg-count"><option>2</option><option>3</option><option selected>4</option><option>5</option><option>6</option></select></label>
          <button id="symphony-generate" type="button">🎼 Ułóż Symfonię</button>
        </div>

        <div class="symphony-note">To pierwszy rdzeń Symfonii: selekcja oparta na istniejących sygnałach, zgodności PROD/SHADOW, logice kombinacji i wykrywaniu kruchej nogi.</div>
        <div id="symphony-results" class="symphony-grid">${matches.slice(0, 4).map(matchCard).join('')}</div>
      </section>`;
  }

  function findScenarioHost() {
    return document.querySelector('#scenarios-view, #scenario-studio, [data-view="scenarios"], .scenario-studio, #scenarios, main');
  }

  async function mount() {
    if (document.getElementById('tennis-symphony-v90')) return;
    const host = findScenarioHost();
    if (!host) return;
    try {
      const data = await loadData();
      const wrap = document.createElement('div');
      wrap.innerHTML = shell(data);
      const node = wrap.firstElementChild;
      host.prepend(node);

      const btn = node.querySelector('#symphony-generate');
      btn?.addEventListener('click', () => {
        const m = Number(node.querySelector('#symphony-match-count')?.value || 4);
        const l = Number(node.querySelector('#symphony-leg-count')?.value || 4);
        const rows = (data.matches || [])
          .filter(x => Number(x.legs_selected || 0) >= Math.min(2, l))
          .slice(0, m)
          .map(matchCard)
          .join('');
        node.querySelector('#symphony-results').innerHTML = rows || '<div class="symphony-empty">Brak scenariuszy spełniających warunki.</div>';
      });
    } catch (err) {
      console.warn('[Symphony v9.0] data unavailable', err);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
  setTimeout(mount, 1200);
})();
