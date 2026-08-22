/* Tenis AI v7.8E8 — Shadow Lab inline Match Center */
(() => {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;',
    '<':'&lt;',
    '>':'&gt;',
    '"':'&quot;',
    "'":'&#39;'
  }[c]));

  const sc = x => x == null || !Number.isFinite(Number(x))
    ? 'N/D'
    : `${Math.round(Number(x))}/100`;

  const pc = x => x == null || !Number.isFinite(Number(x))
    ? '—'
    : `${Number(x).toFixed(1).replace('.0','')}%`;

  let current = [];
  let stats = {};
  let active = false;

  async function safeJson(url, fallback) {
    try {
      const r = await fetch(url + '?v=' + Date.now());
      return r.ok ? await r.json() : fallback;
    } catch {
      return fallback;
    }
  }

  async function reload() {
    [current, stats] = await Promise.all([
      safeJson('data/shadow_current.json', []),
      safeJson('data/shadow_stats.json', {})
    ]);

    if (!Array.isArray(current)) current = [];
    if (!stats || typeof stats !== 'object') stats = {};
  }

  function tour(x) {
    const t = String(x?.tour || '').toLowerCase();
    if (t.includes('chall')) return 'CH';
    if (t.includes('itf')) return 'ITF';
    return t.toUpperCase() || 'TENIS';
  }

  function surface(x) {
    const s = String(x?.surface || '').trim();
    if (!s) return '—';

    const k = s.toLowerCase();
    if (k === 'hard') return 'Hard';
    if (k === 'clay') return 'Clay';
    if (k === 'grass') return 'Grass';
    return s;
  }

  function time(x) {
    const d = new Date(x?.scheduled_time || '');
    return Number.isFinite(d.getTime())
      ? d.toLocaleTimeString('pl-PL', {
          hour: '2-digit',
          minute: '2-digit'
        })
      : '—';
  }

  function currentTourFilter() {
    try {
      return typeof filter !== 'undefined' ? String(filter || 'all') : 'all';
    } catch {
      return 'all';
    }
  }

  function shadowTourKey(x) {
    const t = String(x?.tour || '').toLowerCase();
    if (t.includes('chall')) return 'challenger';
    if (t.includes('itf')) return 'itf';
    if (t.includes('wta')) return 'wta';
    if (t.includes('atp')) return 'atp';
    return t || 'other';
  }

  function filteredRows() {
    const f = currentTourFilter();

    return current
      .filter(Boolean)
      .filter(x => f === 'all' || shadowTourKey(x) === f)
      .sort((a,b) =>
        new Date(a.scheduled_time || 0) -
        new Date(b.scheduled_time || 0)
      );
  }

  function bestSignal(x) {
    const rows = Array.isArray(x?.signals) ? x.signals : [];

    return rows
      .filter(s => Number.isFinite(Number(s?.score)))
      .sort((a,b) => Number(b.score) - Number(a.score))[0] || null;
  }

  function matchExists(x) {
    try {
      return !!window.TENIS_AI_PROJECT_UI?.findMatch?.(
        String(x?.match_id ?? '')
      );
    } catch {
      return false;
    }
  }

  function card(x) {
    const sig = bestSignal(x);
    const score = sig ? Number(sig.score) : null;
    const ready = !!x.model_ready;
    const canOpen = matchExists(x);

    const state = ready
      ? 'SHADOW'
      : 'BRAK DANYCH';

    const topLabel = sig
      ? `${sig.label || 'Sygnał'} · ${String(sig.pick || '').toUpperCase()}`
      : 'Brak rozliczalnego sygnału';

    const reason = x.rejection_reason || 'Odrzucone przez filtr głównego modelu.';

    return `
      <button
        class="p751-match-card sl78-main-card ${ready ? '' : 'sl78-main-nodata'}"
        ${canOpen ? `data-shadow-match="${esc(String(x.match_id))}"` : ''}
        type="button"
      >
        <div class="p751-match-meta">
          <span class="p751-status sl78-shadow-status">${state}</span>
          <b>${esc(tour(x))}</b>
          <span>${esc(x.tournament || 'Turniej')}</span>
          <span>• ${esc(surface(x))}</span>
          <time>${esc(time(x))}</time>
        </div>

        <div class="p751-card-center">
          <div class="p751-names">
            <b>${esc(x.p1)}</b>
            <span>VS</span>
            <b>${esc(x.p2)}</b>
          </div>

          <div class="p751-top-pick">
            <span>🧪 Top Shadow</span>
            <b>${esc(topLabel)}</b>
            <em>${sc(score)}</em>
          </div>
        </div>

        <aside class="p751-strength">
          <span>Shadow score</span>
          <b>${score == null ? 'N/D' : Math.round(score) + '/100'}</b>
          <span class="p751-bars">
            ${[1,2,3,4,5].map(i =>
              `<i class="${score != null && score >= i * 18 ? 'on' : ''}"></i>`
            ).join('')}
          </span>
          <small>${(x.signals || []).length} sygnałów</small>
        </aside>

        <div class="p753-match-total-preview sl78-reason">
          <span>🧪 Powód odrzucenia</span>
          <b>${esc(reason)}</b>
          <em>
            ${esc(x.p1)} n=${x.p1_matches ?? '—'}
            ·
            ${esc(x.p2)} n=${x.p2_matches ?? '—'}
          </em>
        </div>

        <footer>
          <span>🧪 Shadow Lab</span>
          <span>DANE ${esc(x.quality || '—')}</span>
          <span>${ready ? '55–71/100' : 'N/D'}</span>
          <b>${canOpen ? 'Analiza ›' : 'Brak pełnej analizy'}</b>
        </footer>
      </button>
    `;
  }

  function groupRows(rows) {
    const groups = new Map();

    rows.forEach(x => {
      const k = `${tour(x)}|${x.tournament || 'Turniej'}`;

      if (!groups.has(k)) {
        groups.set(k, {
          tour: tour(x),
          name: x.tournament || 'Turniej',
          rows: []
        });
      }

      groups.get(k).rows.push(x);
    });

    return [...groups.values()];
  }

  function summary() {
    const o = stats.overall || {};

    return `
      <section class="sl78-inline-summary">
        <div>
          <b>🧪 Shadow Lab</b>
          <span>
            Odrzucone przez główny model · obserwacja 55–71/100
          </span>
        </div>

        <div class="sl78-inline-numbers">
          <span>
            Śledzone
            <b>${stats.matches_tracked || 0}</b>
          </span>

          <span>
            Oczekuje
            <b>${stats.matches_pending || 0}</b>
          </span>

          <span>
            Rozliczone
            <b>${o.settled || 0}</b>
          </span>

          <span>
            Skuteczność
            <b>${o.accuracy == null ? '—' : pc(o.accuracy)}</b>
          </span>
        </div>

        <small>
          Shadow nie zmienia oficjalnej skuteczności głównego modelu.
          Nauka progów dopiero po minimum
          ${stats.learning_target_sample || 300}
          rozliczalnych sygnałach.
        </small>
      </section>
    `;
  }

  function ensureButton() {
    const bar = document.querySelector('#app .p751-focus');
    if (!bar) return;

    let b = bar.querySelector('[data-shadow-open]');

    if (!b) {
      b = document.createElement('button');
      b.type = 'button';
      b.dataset.shadowOpen = '1';
      b.innerHTML = '🧪 Odrzucone';

      const model = bar.querySelector('[data-p751-models]');

      // EXACT PLACE:
      // PBP OK -> Odrzucone -> Model
      bar.insertBefore(b, model || null);

      b.onclick = e => {
        e.preventDefault();
        e.stopPropagation();
        openShadow();
      };
    }

    bar.querySelectorAll('button').forEach(x => {
      if (x !== b && active) x.classList.remove('active');
    });

    b.classList.toggle('active', active);
  }

  function updateTourCounts(rows) {
    const counts = {
      all: rows.length,
      atp: 0,
      wta: 0,
      challenger: 0,
      itf: 0
    };

    current.forEach(x => {
      const k = shadowTourKey(x);
      if (Object.prototype.hasOwnProperty.call(counts, k)) {
        counts[k]++;
      }
    });

    counts.all = current.length;

    document.querySelectorAll('#tour-nav [data-filter]').forEach(b => {
      const k = b.dataset.filter;
      const c = b.querySelector('.count');

      if (c && Object.prototype.hasOwnProperty.call(counts, k)) {
        c.textContent = String(counts[k]);
      }
    });
  }

  function bindCards() {
    document.querySelectorAll('[data-shadow-match]').forEach(b => {
      b.onclick = () => {
        const id = String(b.dataset.shadowMatch || '');

        window.TENIS_AI_PROJECT_UI?.openMatch?.(id);
      };
    });
  }

  function bindCollapse() {
    const c = document.querySelector('#collapse-all');
    const e = document.querySelector('#expand-all');

    if (c && !c.dataset.shadowBound) {
      c.dataset.shadowBound = '1';

      c.addEventListener('click', () => {
        if (!active) return;

        document
          .querySelectorAll('#app .p751-group')
          .forEach(d => d.open = false);
      });
    }

    if (e && !e.dataset.shadowBound) {
      e.dataset.shadowBound = '1';

      e.addEventListener('click', () => {
        if (!active) return;

        document
          .querySelectorAll('#app .p751-group')
          .forEach(d => d.open = true);
      });
    }
  }

  function renderShadow() {
    active = true;

    // Build the normal Match Center shell first.
    // We keep its filters/navigation and replace only the match list.
    window.TENIS_AI_PROJECT_UI?.renderMatches?.();

    const app = document.querySelector('#app');
    if (!app) return;

    const focus = app.querySelector('.p751-focus');
    if (!focus) return;

    [...app.children].forEach(el => {
      if (el !== focus) el.remove();
    });

    ensureButton();

    const rows = filteredRows();

    const holder = document.createElement('div');
    holder.className = 'sl78-inline-view';

    holder.innerHTML = `
      ${summary()}

      ${
        rows.length
          ? `<div class="p751-groups">
              ${groupRows(rows).map((g,i) => `
                <details
                  class="p751-group"
                  ${i < 4 ? 'open' : ''}
                >
                  <summary>
                    <div>
                      <span>${esc(g.tour)}</span>
                      <b>${esc(g.name)}</b>
                      <small>
                        ${g.rows.length}
                        ${g.rows.length === 1 ? 'mecz' : 'meczów'}
                        ·
                        ${esc([...new Set(g.rows.map(surface))].join('/'))}
                      </small>
                    </div>
                    <i>⌄</i>
                  </summary>

                  <div class="p751-group-body">
                    ${g.rows.map(card).join('')}
                  </div>
                </details>
              `).join('')}
            </div>`
          : `<div class="p751-empty">
              <b>Brak odrzuconych meczów dla tego filtra.</b>
              <span>Wybierz „Wszystkie” albo inny tour.</span>
            </div>`
      }
    `;

    app.appendChild(holder);

    ensureButton();
    updateTourCounts(rows);
    bindCards();
    bindCollapse();
  }

  async function openShadow() {
    active = true;
    await reload();
    renderShadow();
  }

  // Leaving Shadow through normal Match Center filters.
  document.addEventListener('click', e => {
    const normalFocus = e.target.closest(
      '.p751-focus button:not([data-shadow-open])'
    );

    if (normalFocus) {
      active = false;
    }

    const bottom = e.target.closest(
      '#p751-bottom-nav [data-p751-nav]'
    );

    if (bottom) {
      active = false;
    }

    const tourButton = e.target.closest(
      '#tour-nav [data-filter]'
    );

    if (tourButton && active) {
      setTimeout(() => renderShadow(), 0);
    }
  }, true);

  // The Match Center re-renders often, so keep Shadow button
  // in its exact place whenever the normal filter bar exists.
  const observer = new MutationObserver(() => {
    if (document.querySelector('#app .p751-focus')) {
      ensureButton();
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });

  reload();
  setTimeout(ensureButton, 100);
  setTimeout(ensureButton, 500);
  setTimeout(ensureButton, 1500);

  window.TENIS_AI_SHADOW_LAB = {
    reload,
    open: openShadow,
    render: renderShadow
  };
})();
