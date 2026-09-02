/* Tenis AI v8.5.3 — Signals / Stats organizer
   UI-only. No model math, no API calls, no MutationObserver, no interval.
   v8.8.19 runtime cleanup: one debounced pass driven by explicit stats events.
*/
(() => {
  'use strict';
  const VERSION = 'v8.5.3';
  const RUNTIME_FIX = 'v8.8.19';
  const KEY = 'tenis-ai-v853-stats-mode';
  let timer = null;

  function savedMode() {
    try {
      const value = localStorage.getItem(KEY);
      return value === 'pro' ? 'pro' : 'simple';
    } catch {
      return 'simple';
    }
  }

  function setMode(mode) {
    const next = mode === 'pro' ? 'pro' : 'simple';
    document.documentElement.dataset.tenisStatsMode = next;
    try { localStorage.setItem(KEY, next); } catch {}
    document.querySelectorAll('[data-v853-mode]').forEach(button => {
      const active = button.dataset.v853Mode === next;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function proxyLabels(root = document) {
    root.querySelectorAll('#al84-performance .al84-card header b').forEach(el => {
      if (el.textContent.trim() === 'Ensemble Generator') el.textContent = 'Selektor Ensemble (proxy)';
    });
    root.querySelectorAll('#pi85-stats .pi851-metrics-table b').forEach(el => {
      if (el.textContent.trim() === 'Generator + Player') el.textContent = 'Generator proxy + Player';
    });
  }

  function trendSummary() {
    const cards = [...document.querySelectorAll('#mt84e2 .mt84e2-grid:not(.secondary) .mt84e2-card')];
    if (!cards.length) return '<span>Trend modeli: zbieramy dane</span>';
    const bits = cards.slice(0, 5).map(card => {
      const name = card.querySelector('header b')?.textContent?.trim() || 'Model';
      const status = card.querySelector('header em')?.textContent?.trim() || '…';
      return `<span><b>${escapeHtml(name)}</b> ${escapeHtml(status)}</span>`;
    });
    return bits.join('');
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
  }

  function ensureToolbar(app) {
    let bar = document.querySelector('#v853-stats-toolbar');
    if (!bar) {
      bar = document.createElement('section');
      bar.id = 'v853-stats-toolbar';
      bar.className = 'v853-stats-toolbar';
      bar.innerHTML = `
        <div class="v853-toolbar-copy">
          <b>🧭 Widok statystyk</b>
          <small>Najważniejsze na wierzchu, diagnostyka dopiero w PRO.</small>
        </div>
        <div class="v853-mode-switch" role="group" aria-label="Poziom szczegółowości">
          <button type="button" data-v853-mode="simple">Przejrzysty</button>
          <button type="button" data-v853-mode="pro">PRO</button>
        </div>
        <div id="v853-trend-summary" class="v853-trend-summary"></div>`;
      bar.querySelectorAll('[data-v853-mode]').forEach(button => {
        button.addEventListener('click', () => setMode(button.dataset.v853Mode));
      });
    }
    if (app.firstElementChild !== bar) app.prepend(bar);
    return bar;
  }

  function ensureSectionLabel(target, title, subtitle){
    if(!target || target.previousElementSibling?.classList?.contains('v853b-section-label')) return;
    const row=document.createElement('div');
    row.className='v853b-section-label';
    row.innerHTML=`<b>${escapeHtml(title)}</b><small>${escapeHtml(subtitle)}</small>`;
    target.before(row);
  }

  function ensureHealthToggle(){
    const health=document.querySelector('#v79-health, .v79-health');
    if(!health) return;

    health.classList.remove('v853b-collapsed');

    let button=health.querySelector('.v853b-health-toggle');
    if(!button){
      const host=health.querySelector('.v79-health-main') || health.firstElementChild || health;
      button=document.createElement('button');
      button.type='button';
      button.className='v853b-health-toggle';
      host.append(button);
    }

    const sync=()=>{
      const expanded=health.classList.contains('expanded');
      button.textContent=expanded?'Zwiń':'Szczegóły';
      button.setAttribute('aria-expanded',expanded?'true':'false');
    };

    if(button.dataset.v853dBound!=='1'){
      button.dataset.v853dBound='1';
      button.addEventListener('click',event=>{
        event.preventDefault();
        event.stopPropagation();
        health.classList.toggle('expanded');
        sync();
      });
    }

    sync();
  }

  function visualPolish(){
    document.body.classList.add('v853b-visual');
    ensureHealthToggle();
    const pi=document.querySelector('#pi85-stats');
    const al=document.querySelector('#al84-performance');
    if(pi) ensureSectionLabel(pi,'Player Intelligence','Profil zawodników · SHADOW bez wpływu na wynik');
    if(al) ensureSectionLabel(al,'Modele produkcyjne','Current · CatBoost · TabPFN · Ensemble');
  }

  function ensureReadabilityControls(){
    // App/version branding belongs to app-meta. This legacy organizer must not
    // overwrite a newer release label after the page has already rendered.
    const pi=document.querySelector('#pi85-stats');
    if(pi && pi.dataset.v853cReady!=='1'){
      pi.dataset.v853cReady='1';
      pi.classList.add('v853c-collapsed');
      const btn=document.createElement('button');
      btn.type='button';
      btn.className='v853c-toggle';
      btn.textContent='Pokaż szczegóły Player Intelligence';
      btn.addEventListener('click',()=>{
        const collapsed=pi.classList.toggle('v853c-collapsed');
        btn.textContent=collapsed?'Pokaż szczegóły Player Intelligence':'Ukryj szczegóły Player Intelligence';
      });
      const title=pi.querySelector('header') || pi.firstElementChild;
      if(title) title.after(btn); else pi.prepend(btn);
    }

    const trend=document.querySelector('#mt84e2, .model-trend-monitor');
    if(trend && trend.dataset.v853cReady!=='1'){
      trend.dataset.v853cReady='1';
      trend.classList.add('v853c-collapsed');
      const btn=document.createElement('button');
      btn.type='button';
      btn.className='v853c-toggle';
      btn.textContent='Pokaż wykresy modeli';
      btn.addEventListener('click',()=>{
        const collapsed=trend.classList.toggle('v853c-collapsed');
        btn.textContent=collapsed?'Pokaż wykresy modeli':'Ukryj wykresy modeli';
      });
      trend.append(btn);
    }
  }

  function organize() {
    const app = document.querySelector('#app');
    const pc = document.querySelector('#pc77');
    if (!app || !pc) return;

    const bar = ensureToolbar(app);
    setMode(document.documentElement.dataset.tenisStatsMode || savedMode());
    proxyLabels(app);

    document.querySelector('#pi85-stats')?.classList.add('v853-primary-block');
    document.querySelector('#al84-performance')?.classList.add('v853-primary-block');
    document.querySelector('#dynamic-weights-audit-v84d1')?.classList.add('v853-technical-block');
    document.querySelector('#mt84e2')?.classList.add('v853-technical-block');
    document.querySelector('.al84-telemetry')?.classList.add('v853-technical-block');
    document.querySelectorAll('.al84-policy,.al84-foot').forEach(el => el.classList.add('v853-technical-inline'));

    const trend = bar.querySelector('#v853-trend-summary');
    if (trend) trend.innerHTML = trendSummary();
    visualPolish();
    ensureReadabilityControls();
  }

  function schedule(delay = 60) {
    clearTimeout(timer);
    timer = setTimeout(organize, delay);
  }

  document.documentElement.dataset.tenisStatsMode = savedMode();

  try {
    if (typeof renderStats === 'function' && !renderStats.__v853Organized) {
      const base = renderStats;
      const wrapped = function () {
        const value = base.apply(this, arguments);
        schedule(50);
        return value;
      };
      wrapped.__v853Organized = true;
      renderStats = wrapped;
    }
  } catch {}

  document.addEventListener('tenis-ai:stats-ready', () => schedule(0));
  document.addEventListener('tenis-ai:stats-dashboard-ready', () => schedule(0));
  document.addEventListener('click', event => {
    if (event.target?.closest?.('[data-view="stats"],[data-pc77-period],[data-pc77],[data-pc882-period],[data-pc882-tab]')) schedule(40);
  });

  if (document.querySelector('#pc77')) schedule(0);
  else {
    visualPolish();
    ensureReadabilityControls();
  }

  window.TENIS_AI_UI_ORGANIZER_V853 = Object.freeze({
    version: VERSION,
    runtimeFix: RUNTIME_FIX,
    organize,
    setMode,
    schedule
  });
})();
