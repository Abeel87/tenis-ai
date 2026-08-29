/* Tenis AI v9.3J — human-readable deep MODEL/RAW Symphony story.
   UI-only. Reads the compact MODEL_RAW_DEEP feed produced by v9.3I and never
   touches Superbet PLAYABLE projection, model math, training or settlement. */
(() => {
  'use strict';
  if (window.TENIS_AI_SYMPHONY_RAW_STORY_V93J) return;

  const VERSION = 'v9.3J';
  const DATA_URL = './data/symphony_match_cards_v90.json';
  let reportPromise = null;
  let reportCache = null;
  let timer = null;

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
  const finite = (v) => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const pct = (v) => finite(v) ? `${Number(v).toFixed(1).replace('.0', '')}%` : 'N/D';

  function style() {
    if (document.getElementById('symraw93j-style')) return;
    const s = document.createElement('style');
    s.id = 'symraw93j-style';
    s.textContent = `
      .symraw93j{margin-top:.55rem;padding:.6rem;border:1px solid rgba(183,145,255,.18);border-radius:11px;background:rgba(137,92,224,.035)}
      .symraw93j__head{display:flex;justify-content:space-between;gap:.5rem;align-items:center;margin-bottom:.38rem}
      .symraw93j__head b{font-size:.68rem;color:#e4d8ff}.symraw93j__head span{font-size:.54rem;color:#9a88bd;padding:.22rem .38rem;border:1px solid rgba(183,145,255,.16);border-radius:999px}
      .symraw93j__story{margin:.1rem 0 .48rem;font-size:.63rem;line-height:1.45;color:#c7bedd}
      .symraw93j__paths{display:grid;gap:.32rem}.symraw93j__path{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:.42rem;align-items:start;padding:.4rem .46rem;border-radius:8px;background:rgba(255,255,255,.025)}
      .symraw93j__path i{font-style:normal;font-size:.58rem;color:#987bd7}.symraw93j__path b{display:block;font-size:.6rem;color:#d8d0e8;line-height:1.35;overflow-wrap:anywhere}.symraw93j__path small{display:block;margin-top:.12rem;font-size:.52rem;color:#7f7692}.symraw93j__path strong{font-size:.58rem;color:#cbb8ff;white-space:nowrap}
      .symraw93j__foot{margin:.45rem 0 0;font-size:.52rem;color:#796f8c;line-height:1.35}
    `;
    document.head.appendChild(s);
  }

  function loadReport() {
    if (reportCache) return Promise.resolve(reportCache);
    if (reportPromise) return reportPromise;
    reportPromise = fetch(`${DATA_URL}?rawstory=93j`, { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        // Hard layer contract: never render operator-aware / PLAYABLE data here.
        if (!data || data.layer !== 'MODEL_RAW_DEEP' || data.analysis_only !== true || data.operator_playable !== false) return null;
        reportCache = data;
        return data;
      })
      .catch(() => null)
      .finally(() => { reportPromise = null; });
    return reportPromise;
  }

  function findRow(report, raw) {
    const key = String(raw || '').replace(/^id:/, '');
    return (report?.matches || []).find(row => {
      if (!row || row.layer !== 'MODEL_RAW_DEEP' || row.analysis_only !== true || row.operator_playable !== false) return false;
      const id = String(row.id ?? '');
      const matchKey = String(row.match_key || '').replace(/^id:/, '');
      return id === key || matchKey === key;
    }) || null;
  }

  function pathMeta(path) {
    const bits = [];
    if (path?.set1) bits.push(`1S ${path.set1}`);
    if (path?.set2) bits.push(`2S ${path.set2}`);
    if (path?.set3) bits.push(`3S ${path.set3}`);
    if (path?.match_score) bits.push(`mecz ${path.match_score}`);
    if (finite(path?.total_games)) bits.push(`${Number(path.total_games)} gemów`);
    return bits.join(' · ');
  }

  function render(host, row) {
    const comp = row?.composition;
    if (!host || !comp || comp.analysis_only !== true || comp.operator_playable !== false) return false;
    const paths = Array.isArray(comp.top_paths) ? comp.top_paths.slice(0, 3) : [];
    const narrative = String(comp.scenario_narrative || '').trim();
    const scope = String(comp.exact_path_scope || row?.path_engine || 'MODEL/RAW DEEP');
    if (!narrative && !paths.length) return false;

    style();
    let box = host.querySelector('[data-symraw93j]');
    if (!box) {
      box = document.createElement('div');
      box.className = 'symraw93j';
      box.dataset.symraw93j = '1';
      host.appendChild(box);
    }

    const html = `
      <div class="symraw93j__head"><b>🧭 Jak model widzi ten mecz</b><span>${esc(scope)}</span></div>
      ${narrative ? `<p class="symraw93j__story">${esc(narrative)}</p>` : ''}
      ${paths.length ? `<div class="symraw93j__paths">${paths.map((path, i) => `
        <div class="symraw93j__path">
          <i>#${i + 1}</i>
          <div><b>${esc(path?.path || pathMeta(path) || 'Ścieżka modelowa')}</b><small>${esc(pathMeta(path))}</small></div>
          <strong>${pct(path?.probability_mass)}</strong>
        </div>`).join('')}</div>` : ''}
      <p class="symraw93j__foot">To są ścieżki MODEL/RAW z deep lattice. Nie oznaczają dostępności rynku ani możliwości zagrania w Superbet.</p>`;
    if (box.innerHTML !== html) box.innerHTML = html;
    box.dataset.renderKey = String(row?.match_key || row?.id || '');
    return true;
  }

  async function refreshOpenMatch() {
    const overlay = document.querySelector('#p751-match-overlay:not([hidden])');
    const rawHost = overlay?.querySelector('[data-rp921-sym-detail]');
    const raw = String(overlay?.dataset?.matchKey || '');
    if (!overlay || !rawHost || !raw) return false;

    const report = await loadReport();
    const current = document.querySelector('#p751-match-overlay:not([hidden])');
    if (!report || !current || String(current.dataset.matchKey || '') !== raw) return false;
    const host = current.querySelector('[data-rp921-sym-detail]');
    if (!host) return false;
    return render(host, findRow(report, raw));
  }

  function schedule(delay = 30) {
    clearTimeout(timer);
    timer = setTimeout(refreshOpenMatch, delay);
  }

  document.addEventListener('click', event => {
    if (event.target?.closest?.('[data-p751-open]')) {
      schedule(120);
      setTimeout(refreshOpenMatch, 450);
      setTimeout(refreshOpenMatch, 1000);
    }
  }, true);

  if ('MutationObserver' in window) {
    const observer = new MutationObserver(records => {
      const touched = records.some(record => [...record.addedNodes].some(node =>
        node?.nodeType === 1 && (node.matches?.('[data-rp921-sym-detail]') || node.querySelector?.('[data-rp921-sym-detail]'))
      ));
      if (touched) schedule(20);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  window.TENIS_AI_SYMPHONY_RAW_STORY_V93J = Object.freeze({
    version: VERSION,
    refresh: refreshOpenMatch,
    reload: () => { reportCache = null; return refreshOpenMatch(); }
  });

  if (document.querySelector('#p751-match-overlay:not([hidden])')) schedule(100);
})();
