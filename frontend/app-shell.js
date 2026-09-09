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

  function syncAuthenticatedShell() {
    const state = authState();
    document.body.classList.toggle('tenis-shell-ready', state === 'authenticated');
    if (state !== 'authenticated') return;

    syncRole();
    syncTabs();
    syncViewContext();
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
  });
  window.addEventListener('pageshow', () => setTimeout(syncAll, 0));

  document.addEventListener('click', event => {
    if (event.target?.closest?.('.main-tabs button[data-view]')) {
      setTimeout(syncViewContext, 0);
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
    activeView
  });
})();
