/* Tenis AI — canonical application shell
   Presentation/auth-shell only. No model math, no market mapping, no data mutation.
*/
(() => {
  'use strict';

  const AUTH_EVENT = 'tenis-ai-auth-change';
  const VIEW_LABELS = {
    matches: ['Mecze', 'Dzisiejsze spotkania, sygnały i rynki w jednym miejscu.'],
    stats: ['Statystyki', 'Skuteczność modeli i forma sygnałów bez technicznego szumu.'],
    history: ['Historia', 'Rozliczone typy, wyniki i wcześniejsze sygnały.'],
    feedback: ['Pomysły', 'Sugestie i poprawki dotyczące aplikacji.'],
    coupons: ['Kupony', 'Twoje kupony i społeczność Tenis AI.']
  };
  const ROLE_LABELS = {
    admin: 'ADMIN',
    moderator: 'MODERATOR',
    user: 'UŻYTKOWNIK'
  };

  let gate;
  let context;
  let roleChip;

  const account = () => window.tenisAIAccount || null;
  const profile = () => account()?.profile || null;
  const user = () => account()?.user || null;
  const isReady = () => Boolean(account()?.authReady);
  const isConfigured = () => account()?.configured !== false;

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
  }

  function role() {
    const value = String(profile()?.role || 'user').toLowerCase();
    return ['admin', 'moderator', 'user'].includes(value) ? value : 'user';
  }

  function authState() {
    if (!isReady()) return 'pending';
    return user() && profile() ? 'authenticated' : 'guest';
  }

  function ensureGate() {
    gate = document.querySelector('#tenis-login-gate');
    if (gate) return gate;

    gate = document.createElement('section');
    gate.id = 'tenis-login-gate';
    gate.className = 'tenis-login-gate';
    gate.setAttribute('aria-live', 'polite');
    gate.innerHTML = `
      <div class="tenis-login-card">
        <div class="tenis-login-brand">
          <img src="brand-symbol.png" alt="" class="tenis-login-symbol">
          <div>
            <span>Tenis AI</span>
            <b>Twoje centrum analizy meczu</b>
          </div>
        </div>
        <div class="tenis-login-copy">
          <span class="tenis-login-kicker">PRYWATNA APLIKACJA</span>
          <h1>Wszystko o meczu. Bez przekopywania się przez techniczne dane.</h1>
          <p id="tenis-login-message">Sprawdzam Twoją sesję…</p>
        </div>
        <div class="tenis-login-actions">
          <button id="tenis-gate-login" class="tenis-gate-primary" type="button">Zaloguj się</button>
          <button id="tenis-gate-register" class="tenis-gate-secondary" type="button">Załóż konto</button>
        </div>
        <small class="tenis-login-foot">Modele, Symfonia, Player DNA i dane Superbet pozostają pod spodem bez zmian.</small>
      </div>`;

    document.body.append(gate);

    gate.querySelector('#tenis-gate-login')?.addEventListener('click', () => {
      document.querySelector('#account-button')?.click();
    });
    gate.querySelector('#tenis-gate-register')?.addEventListener('click', () => {
      document.querySelector('#account-button')?.click();
      setTimeout(() => document.querySelector('[data-auth-mode="register"]')?.click(), 0);
    });

    return gate;
  }

  function ensureContext() {
    const status = document.querySelector('.status');
    if (!status) return null;
    context = document.querySelector('#tenis-shell-context');
    if (!context) {
      context = document.createElement('section');
      context.id = 'tenis-shell-context';
      context.className = 'tenis-shell-context';
      context.innerHTML = `
        <div>
          <span class="tenis-shell-eyebrow">TENIS AI</span>
          <h1 id="tenis-shell-title">Mecze</h1>
          <p id="tenis-shell-subtitle">Dzisiejsze spotkania, sygnały i rynki w jednym miejscu.</p>
        </div>
        <div class="tenis-shell-context-actions">
          <span id="tenis-shell-view-badge">LIVE</span>
        </div>`;
      status.insertAdjacentElement('afterend', context);
    }
    return context;
  }

  function ensureRoleChip() {
    const host = document.querySelector('.header-actions');
    if (!host) return null;
    roleChip = document.querySelector('#tenis-role-chip');
    if (!roleChip) {
      roleChip = document.createElement('span');
      roleChip.id = 'tenis-role-chip';
      roleChip.className = 'tenis-role-chip';
      const accountButton = host.querySelector('#account-button');
      if (accountButton) host.insertBefore(roleChip, accountButton);
      else host.prepend(roleChip);
    }
    return roleChip;
  }

  function activeView() {
    return document.querySelector('.main-tabs button.active')?.dataset.view || 'matches';
  }

  function syncViewContext() {
    const view = activeView();
    const [title, subtitle] = VIEW_LABELS[view] || VIEW_LABELS.matches;
    ensureContext();
    const titleEl = document.querySelector('#tenis-shell-title');
    const subtitleEl = document.querySelector('#tenis-shell-subtitle');
    const badge = document.querySelector('#tenis-shell-view-badge');
    if (titleEl) titleEl.textContent = title;
    if (subtitleEl) subtitleEl.textContent = subtitle;
    if (badge) badge.textContent = view === 'matches' ? 'LIVE' : 'TENIS AI';
    document.documentElement.dataset.tenisView = view;
  }

  function syncTabs() {
    const labels = {
      matches: ['🎾', 'Mecze'],
      stats: ['📊', 'Statystyki'],
      history: ['🕘', 'Historia'],
      feedback: ['💡', 'Pomysły'],
      coupons: ['🧾', 'Kupony']
    };

    document.querySelectorAll('.main-tabs button[data-view]').forEach(button => {
      const data = labels[button.dataset.view];
      if (!data || button.dataset.shellNormalized === '1') return;
      button.dataset.shellNormalized = '1';
      button.innerHTML = `<span class="tenis-nav-icon">${data[0]}</span><span class="tenis-nav-label">${data[1]}</span>`;
      button.setAttribute('aria-label', data[1]);
      button.addEventListener('click', () => setTimeout(syncViewContext, 0));
    });
  }

  function syncRole() {
    const currentRole = role();
    document.documentElement.dataset.tenisRole = currentRole;
    const chip = ensureRoleChip();
    if (chip) {
      chip.textContent = ROLE_LABELS[currentRole] || ROLE_LABELS.user;
      chip.dataset.role = currentRole;
      chip.title = currentRole === 'admin'
        ? 'Pełny dostęp administracyjny'
        : currentRole === 'moderator'
          ? 'Dostęp moderatora'
          : 'Standardowy widok użytkownika';
    }
  }

  function syncGate() {
    ensureGate();
    const state = authState();
    const configured = isConfigured();
    document.documentElement.dataset.tenisAuthState = state;

    const message = gate.querySelector('#tenis-login-message');
    const login = gate.querySelector('#tenis-gate-login');
    const register = gate.querySelector('#tenis-gate-register');

    if (state === 'pending') {
      if (message) message.textContent = 'Sprawdzam Twoją sesję…';
      if (login) login.hidden = true;
      if (register) register.hidden = true;
      return;
    }

    if (!configured) {
      if (message) message.textContent = 'Logowanie jest chwilowo niedostępne — brak konfiguracji połączenia.';
      if (login) login.hidden = false;
      if (register) register.hidden = true;
      return;
    }

    if (state === 'guest') {
      if (message) message.textContent = 'Zaloguj się, aby wejść do aplikacji i zobaczyć mecze, modele oraz swoje dane.';
      if (login) login.hidden = false;
      if (register) register.hidden = false;
      return;
    }

    if (message) message.textContent = `Witaj, ${profile()?.username || 'użytkowniku'}.`;
  }


  function technicalMode() {
    return document.documentElement.dataset.tenisUiMode === 'technical';
  }

  function decorateMatchBrowser() {
    const technical = technicalMode();

    document.querySelectorAll('.match-card').forEach(card => {
      card.classList.add('tenis-shell-match-card');

      const score = card.querySelector('.match-score span');
      if (score) {
        if (!score.dataset.shellOriginal) score.dataset.shellOriginal = score.textContent.trim();
        const original = score.dataset.shellOriginal;
        if (technical) {
          score.textContent = original;
        } else if (/^MODEL\\s+/i.test(original)) {
          score.textContent = original.replace(/^MODEL\\s+/i, 'Siła ');
        }
      }

      const quality = card.querySelector('.match-score small');
      if (quality) quality.classList.add('tenis-technical-detail');

      const signalsTitle = card.querySelector('.signals-title');
      if (signalsTitle) {
        if (!signalsTitle.dataset.shellOriginal) signalsTitle.dataset.shellOriginal = signalsTitle.textContent.trim();
        signalsTitle.textContent = technical
          ? signalsTitle.dataset.shellOriginal
          : '🔥 Najmocniejsze sygnały';
      }

      const pick = card.querySelector('.pick b');
      if (pick) {
        if (!pick.dataset.shellOriginal) pick.dataset.shellOriginal = pick.textContent;
        pick.textContent = technical
          ? pick.dataset.shellOriginal
          : pick.dataset.shellOriginal.replace('🎯 Model 1. seta:', '🎯 Typ na 1. set:');
      }

      card.querySelectorAll('.marketbox .tag, .modelnote').forEach(el => {
        el.classList.add('tenis-technical-detail');
      });
    });
  }

  function wrapMatchRenderer() {
    try {
      if (typeof renderMatches === 'function' && !renderMatches.__tenisShellWrapped) {
        const base = renderMatches;
        const wrapped = function () {
          const value = base.apply(this, arguments);
          decorateMatchBrowser();
          return value;
        };
        wrapped.__tenisShellWrapped = true;
        renderMatches = wrapped;
      }
    } catch {}
    decorateMatchBrowser();
  }


  const SHELL_STATE_KEY = 'tenis-ai-product-shell-state';
  let decorateTimer = null;

  function readShellState() {
    try { return JSON.parse(localStorage.getItem(SHELL_STATE_KEY) || '{}') || {}; }
    catch { return {}; }
  }

  function writeShellState(next) {
    try {
      const current = readShellState();
      localStorage.setItem(SHELL_STATE_KEY, JSON.stringify({...current, ...next}));
    } catch {}
  }

  function ensureSurfaceHeader(target, key, kicker, title, subtitle) {
    if (!target) return;
    let header = document.querySelector(`.tenis-surface-header[data-tenis-surface="${CSS.escape(key)}"]`);
    if (!header) {
      header = document.createElement('div');
      header.className = 'tenis-surface-header';
      header.dataset.tenisSurface = key;
      header.innerHTML = `
        <div>
          <span>${escapeHtml(kicker)}</span>
          <b>${escapeHtml(title)}</b>
          <small>${escapeHtml(subtitle)}</small>
        </div>`;
    }
    target.dataset.tenisSurfaceReady = '1';
    if (target.previousElementSibling !== header) target.before(header);
  }

  function normalizeSimpleCopy(root = document) {
    const technical = technicalMode();

    root.querySelectorAll('.stats-hero span').forEach(el => {
      if (!el.dataset.shellOriginal) el.dataset.shellOriginal = el.textContent;
      el.textContent = technical
        ? el.dataset.shellOriginal
        : el.dataset.shellOriginal.replace('📊 Skuteczność modelu · zielone sygnały', '📊 Skuteczność typów');
    });

    root.querySelectorAll('.stats-note').forEach(el => {
      if (!el.dataset.shellOriginal) el.dataset.shellOriginal = el.textContent;
      el.textContent = technical
        ? el.dataset.shellOriginal
        : 'Skuteczność pokazuje tylko typy, które da się jednoznacznie rozliczyć po meczu.';
    });

    root.querySelectorAll('.s2-kicker').forEach(el => {
      if (!el.dataset.shellOriginal) el.dataset.shellOriginal = el.textContent;
      el.textContent = technical
        ? el.dataset.shellOriginal
        : (/SYMPHONY/i.test(el.dataset.shellOriginal) ? 'SYMFONIA 2.0' : el.dataset.shellOriginal);
    });

    root.querySelectorAll('.pds-subhead, .pi851-tech-note, .pc882-note').forEach(el => {
      el.classList.add('tenis-secondary-copy');
    });
  }

  function decorateStats() {
    const app = document.querySelector('#app');
    if (!app || activeView() !== 'stats') return;
    app.classList.add('tenis-stats-view');

    const hero = app.querySelector('.stats-hero');
    if (hero) hero.classList.add('tenis-product-hero');

    const pc = document.querySelector('#pc882-dashboard');
    const pi = document.querySelector('#pi85-stats');
    const models = document.querySelector('#al84-performance');
    const trends = document.querySelector('#mt84e2');

    if (pc) {
      pc.classList.add('tenis-product-surface', 'tenis-performance-surface');
      ensureSurfaceHeader(pc, 'performance', 'WYNIKI', 'Skuteczność i jakość', 'Najważniejsze wyniki modeli oraz jakość sygnałów.');
    }
    if (pi) {
      pi.classList.add('tenis-product-surface', 'tenis-player-intelligence-surface');
      ensureSurfaceHeader(pi, 'player-intelligence', 'ZAWODNICY', 'Player Intelligence', 'Forma, matchup i dane zawodników w czytelnej warstwie.');
    }
    if (models) {
      models.classList.add('tenis-product-surface', 'tenis-models-surface');
      ensureSurfaceHeader(models, 'models', 'SILNIK', 'Modele i uczenie', 'Status modeli produkcyjnych oraz warstwy uczącej.');
    }
    if (trends) trends.classList.add('tenis-product-surface', 'tenis-trends-surface');

    app.querySelectorAll('.stats-section,.stat-grid,.pc882-card,.pi851-card-compare,.pi851-metrics,.al84-card')
      .forEach(el => el.classList.add('tenis-product-card'));
  }

  function decorateHistory() {
    const app = document.querySelector('#app');
    if (!app || activeView() !== 'history') return;
    app.classList.add('tenis-history-view');
    app.querySelectorAll('.v75-history-stats,.history-head').forEach(el => el.classList.add('tenis-product-hero'));
    app.querySelectorAll('.v75-history-day,.v75-history-card,.history-card').forEach(el => el.classList.add('tenis-product-card'));
    app.querySelectorAll('.v75-history-signal,.history-signal').forEach(el => el.classList.add('tenis-result-row'));
  }

  function decorateCommunity() {
    document.querySelectorAll(
      '.shared-hero,.community-hero,.community-live-stats,.hub-profile-card,.hub-gate,.hub-panel-title'
    ).forEach(el => el.classList.add('tenis-product-hero'));

    document.querySelectorAll(
      '.shared-card,.coupon-card,.hub-person,.hub-message,.hub-coupon-mini,.community-card,.hub-activity'
    ).forEach(el => el.classList.add('tenis-product-card'));

    document.querySelectorAll(
      '.shared-toolbar,.hub-nav,.admin74-filters,.admin74-toolbar'
    ).forEach(el => el.classList.add('tenis-product-toolbar'));

    const hub = document.querySelector('#community-hub-body');
    if (hub) hub.classList.add('tenis-community-surface');
  }

  function decoratePlayerProfiles() {
    const panel = document.querySelector('#player-profile-panel');
    if (panel && !panel.hidden) panel.classList.add('tenis-product-surface', 'tenis-player-profile-surface');

    document.querySelectorAll(
      '.player-current-card,.player-section,.player-history-row,.player-stat,.player-kpi,.player-surface-row,.player-market-row'
    ).forEach(el => el.classList.add('tenis-product-card'));

    document.querySelectorAll('.player-section-title').forEach(el => el.classList.add('tenis-product-section-title'));
  }

  function decorateSymphony() {
    document.querySelectorAll('.s2-shell').forEach(el => el.classList.add('tenis-symphony-surface', 'tenis-product-surface'));
    document.querySelectorAll('.s2-hero,.s2-head,.s2stats-head').forEach(el => el.classList.add('tenis-product-hero'));
    document.querySelectorAll('.s2-card,.s2-match-ready,.s2-match-wait,.s2stats-card,.s2-leg,.s2-joint')
      .forEach(el => el.classList.add('tenis-product-card'));
    document.querySelectorAll('.s2-controls').forEach(el => el.classList.add('tenis-product-toolbar'));

    const surface = document.querySelector('.s2-shell');
    if (surface) ensureSurfaceHeader(surface, 'symphony', 'DECYZJA', 'Symfonia 2.0', 'Połączony obraz modeli, rynku i finalnego PLAYABLE.');
  }

  function decoratePlayerDna() {
    const dna = document.querySelector('#player-dna-match-trajectory');
    if (dna) {
      dna.classList.add('tenis-product-surface', 'tenis-dna-surface');
      ensureSurfaceHeader(dna, 'player-dna', 'PRZEBIEG MECZU', 'Player DNA', 'Scenariusze gem po gemie i możliwe gałęzie meczu.');
    }
    document.querySelectorAll(
      '.pds-scenario,.pds-metric,.pds-market-row,.pds-trajectory-branch,.pds-direct-cell,.pds-health-item'
    ).forEach(el => el.classList.add('tenis-product-card'));
    document.querySelectorAll('.pds-health,.pds-foot,.phase11-technical').forEach(el => el.classList.add('tenis-technical-surface'));
  }

  function decorateAdmin() {
    document.querySelectorAll('.admin74').forEach(el => el.classList.add('tenis-admin-surface', 'tenis-product-surface'));
    document.querySelectorAll('.admin74-user,.admin74-request,.admin74-summary').forEach(el => el.classList.add('tenis-product-card'));
    document.querySelectorAll('.admin74-actions').forEach(el => el.classList.add('tenis-product-actions'));
  }

  function decorateAccount() {
    const modal = document.querySelector('.account-modal');
    if (modal) modal.classList.add('tenis-account-surface');
    document.querySelectorAll('.account-profile-card,.profile-editor,.account-setup')
      .forEach(el => el.classList.add('tenis-product-card'));
  }

  function gotoView(view) {
    const button = document.querySelector(`.main-tabs button[data-view="${CSS.escape(view)}"]`);
    if (!button) return false;
    button.click();
    setTimeout(() => window.scrollTo({top:0, behavior:'smooth'}), 30);
    closeAdminCenter();
    return true;
  }

  function ensureAdminCenter() {
    const admin = role() === 'admin';
    const host = document.querySelector('.header-actions');
    let button = document.querySelector('#tenis-admin-center-open');
    let overlay = document.querySelector('#tenis-admin-center');

    if (!admin) {
      button?.remove();
      if (overlay) overlay.hidden = true;
      return;
    }

    if (host && !button) {
      button = document.createElement('button');
      button.id = 'tenis-admin-center-open';
      button.className = 'tenis-admin-center-open';
      button.type = 'button';
      button.innerHTML = '<span>⚙️</span><span><b>Control</b><small>Admin</small></span>';
      button.setAttribute('aria-label', 'Otwórz centrum administratora');
      const accountButton = host.querySelector('#account-button');
      if (accountButton) host.insertBefore(button, accountButton);
      else host.append(button);
      button.addEventListener('click', openAdminCenter);
    }

    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'tenis-admin-center';
      overlay.className = 'tenis-admin-center';
      overlay.hidden = true;
      overlay.innerHTML = `
        <section class="tenis-admin-center-panel" role="dialog" aria-modal="true" aria-labelledby="tenis-admin-center-title">
          <header>
            <div>
              <span>ADMIN</span>
              <h2 id="tenis-admin-center-title">Control Center</h2>
              <p>Najważniejsze narzędzia i diagnostyka w jednym miejscu.</p>
            </div>
            <button type="button" data-admin-center-close aria-label="Zamknij">✕</button>
          </header>
          <div class="tenis-admin-center-grid">
            <button type="button" data-admin-action="view:matches"><span>🎾</span><b>Mecze</b><small>Match Browser</small></button>
            <button type="button" data-admin-action="symphony"><span>🎼</span><b>Symfonia 2.0</b><small>Finalny PLAYABLE</small></button>
            <button type="button" data-admin-action="view:stats"><span>📊</span><b>Statystyki</b><small>Modele i wyniki</small></button>
            <button type="button" data-admin-action="technical"><span>🛠️</span><b>Tryb techniczny</b><small>Pełna diagnostyka</small></button>
            <button type="button" data-admin-action="community"><span>👥</span><b>Użytkownicy</b><small>Moderacja i role</small></button>
            <button type="button" data-admin-action="view:history"><span>🕘</span><b>Historia</b><small>Settlement i wyniki</small></button>
            <button type="button" data-admin-action="view:coupons"><span>🧾</span><b>Kupony</b><small>Społeczność</small></button>
            <button type="button" data-admin-action="refresh"><span>↻</span><b>Odśwież</b><small>Dane aplikacji</small></button>
          </div>
          <footer>
            <span id="tenis-admin-center-role">Rola: ADMIN</span>
            <span id="tenis-admin-center-mode">Widok: prosty</span>
          </footer>
        </section>`;
      document.body.append(overlay);
      overlay.addEventListener('click', event => {
        if (event.target === overlay || event.target.closest('[data-admin-center-close]')) closeAdminCenter();
        const action = event.target.closest('[data-admin-action]')?.dataset.adminAction;
        if (!action) return;
        if (action.startsWith('view:')) return void gotoView(action.split(':')[1]);
        if (action === 'refresh') {
          document.querySelector('#refresh')?.click();
          closeAdminCenter();
        }
        if (action === 'technical') {
          const next = technicalMode() ? 'simple' : 'technical';
          window.TENIS_AI_UI_ORGANIZER_V853?.setMode?.(next);
          syncAdminCenterMeta();
          scheduleDecorate(20);
        }
        if (action === 'symphony') {
          const target = document.querySelector('#p751-bottom-nav [data-p751-nav="symphony2"]');
          target?.click();
          closeAdminCenter();
          scheduleDecorate(60);
        }
        if (action === 'community') {
          const adminOpen = document.querySelector('#community-admin-open');
          if (adminOpen) adminOpen.click();
          else document.querySelector('#community-hub-open')?.click();
          closeAdminCenter();
          scheduleDecorate(120);
        }
      });
    }
    syncAdminCenterMeta();
  }

  function syncAdminCenterMeta() {
    const technical = technicalMode();
    const mode = document.querySelector('#tenis-admin-center-mode');
    if (mode) mode.textContent = `Widok: ${technical ? 'techniczny' : 'prosty'}`;
    const button = document.querySelector('[data-admin-action="technical"]');
    if (button) {
      const title = button.querySelector('b');
      const copy = button.querySelector('small');
      if (title) title.textContent = technical ? 'Widok prosty' : 'Tryb techniczny';
      if (copy) copy.textContent = technical ? 'Wróć do codziennego widoku' : 'Pełna diagnostyka';
    }
  }

  function openAdminCenter() {
    const overlay = document.querySelector('#tenis-admin-center');
    if (!overlay || role() !== 'admin') return;
    syncAdminCenterMeta();
    overlay.hidden = false;
    document.body.classList.add('tenis-modal-open');
  }

  function closeAdminCenter() {
    const overlay = document.querySelector('#tenis-admin-center');
    if (overlay) overlay.hidden = true;
    document.body.classList.remove('tenis-modal-open');
  }

  function decorateProductSurfaces() {
    if (authState() !== 'authenticated') return;
    const app = document.querySelector('#app');
    if (app) {
      app.classList.toggle('tenis-stats-view', activeView() === 'stats');
      app.classList.toggle('tenis-history-view', activeView() === 'history');
      app.classList.toggle('tenis-coupons-view', activeView() === 'coupons');
      app.classList.toggle('tenis-feedback-view', activeView() === 'feedback');
    }
    decorateMatchBrowser();
    decorateStats();
    decorateHistory();
    decorateCommunity();
    decoratePlayerProfiles();
    decorateSymphony();
    decoratePlayerDna();
    decorateAdmin();
    decorateAccount();
    normalizeSimpleCopy(document);
    ensureAdminCenter();
  }

  function scheduleDecorate(delay = 30) {
    clearTimeout(decorateTimer);
    decorateTimer = setTimeout(decorateProductSurfaces, delay);
  }

  function saveUiState() {
    writeShellState({
      view: activeView(),
      scrollY: Math.max(0, Math.round(window.scrollY || 0))
    });
  }

  function restoreUiState() {
    if (authState() !== 'authenticated') return;
    const state = readShellState();
    if (state.view && state.view !== activeView()) {
      document.querySelector(`.main-tabs button[data-view="${CSS.escape(state.view)}"]`)?.click();
    }
    if (Number.isFinite(Number(state.scrollY)) && Number(state.scrollY) > 0) {
      setTimeout(() => window.scrollTo({top:Number(state.scrollY), behavior:'auto'}), 120);
    }
  }

  function syncAuthenticatedShell() {
    const state = authState();
    document.body.classList.toggle('tenis-shell-ready', state === 'authenticated');
    if (state !== 'authenticated') return;

    syncRole();
    syncTabs();
    syncViewContext();
    wrapMatchRenderer();
    decorateMatchBrowser();
    ensureAdminCenter();
    scheduleDecorate(20);
  }

  function syncAll() {
    syncGate();
    syncAuthenticatedShell();
  }

  window.addEventListener(AUTH_EVENT, () => setTimeout(syncAll, 0));
  window.addEventListener('tenis-ai-ui-mode-change', () => {
    document.body.classList.toggle(
      'tenis-technical-view',
      document.documentElement.dataset.tenisUiMode === 'technical'
    );
    decorateMatchBrowser();
    syncAdminCenterMeta();
    scheduleDecorate(20);
  });
  window.addEventListener('pageshow', () => setTimeout(() => { syncAll(); restoreUiState(); scheduleDecorate(80); }, 0));
  window.addEventListener('pagehide', saveUiState);

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !document.querySelector('#tenis-admin-center')?.hidden) closeAdminCenter();
  });

  document.addEventListener('click', event => {
    if (event.target?.closest?.('.main-tabs button[data-view]')) {
      writeShellState({view:event.target.closest('.main-tabs button[data-view]')?.dataset.view || activeView(), scrollY:0});
      setTimeout(() => { syncViewContext(); decorateMatchBrowser(); scheduleDecorate(50); }, 0);
    }
    if (event.target?.closest?.('#tour-nav button,#collapse-all,#expand-all,.tournament-summary,.match-summary,.player-suggestion,#community-hub-open,[data-p751-nav],.s2-generate,.hub-nav button,.shared-toolbar button')) {
      setTimeout(() => { decorateMatchBrowser(); scheduleDecorate(80); }, 0);
      setTimeout(() => scheduleDecorate(0), 220);
    }
  });

  ensureGate();
  ensureContext();
  syncTabs();
  syncViewContext();
  syncAll();

  window.TENIS_AI_APP_SHELL = Object.freeze({
    sync: syncAll,
    authState,
    role,
    activeView,
    decorateMatchBrowser,
    decorateProductSurfaces,
    scheduleDecorate,
    openAdminCenter,
    closeAdminCenter
  });
})();
