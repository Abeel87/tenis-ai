/* Tenis AI v8.5.3 — runtime data dedupe
   Short-lived in-memory cache for same-origin /data/*.json GETs.
   Prevents repeated downloads/parses triggered by layered UI modules.
*/
(() => {
  'use strict';
  if (window.TENIS_AI_RUNTIME_V853) return;

  const nativeFetch = window.fetch.bind(window);
  const inflight = new Map();
  const cache = new Map();
  const stats = { network: 0, cacheHits: 0, joined: 0 };

  function urlOf(input) {
    try {
      const raw = input instanceof Request ? input.url : String(input);
      return new URL(raw, location.href);
    } catch {
      return null;
    }
  }

  function methodOf(input, init) {
    return String(init?.method || (input instanceof Request ? input.method : 'GET') || 'GET').toUpperCase();
  }

  function dataKey(input, init) {
    if (methodOf(input, init) !== 'GET') return null;
    const url = urlOf(input);
    if (!url || url.origin !== location.origin) return null;
    if (!url.pathname.includes('/data/') || !url.pathname.endsWith('.json')) return null;
    return url.pathname;
  }

  function ttlFor(key) {
    if (key.endsWith('/data/results.json')) return 60000;
    if (key.endsWith('/data/history.json')) return 60000;
    if (key.endsWith('/data/history_stats.json')) return 30000;
    return 15000;
  }

  async function cachedFetch(input, init) {
    const key = dataKey(input, init);
    if (!key) return nativeFetch(input, init);

    const now = Date.now();
    const hit = cache.get(key);
    if (hit && now - hit.at < ttlFor(key)) {
      stats.cacheHits += 1;
      return hit.response.clone();
    }

    const active = inflight.get(key);
    if (active) {
      stats.joined += 1;
      const response = await active;
      return response.clone();
    }

    stats.network += 1;
    const task = nativeFetch(input, init)
      .then(response => {
        if (response?.ok) {
          cache.set(key, { at: Date.now(), response: response.clone() });
        }
        return response;
      })
      .finally(() => inflight.delete(key));

    inflight.set(key, task);
    const response = await task;
    return response.clone();
  }

  function invalidate(path = '') {
    const needle = String(path || '');
    for (const key of [...cache.keys()]) {
      if (!needle || key.includes(needle)) cache.delete(key);
    }
  }

  window.fetch = cachedFetch;
  window.TENIS_AI_RUNTIME_V853 = Object.freeze({
    version: 'v8.5.3',
    invalidate,
    snapshot: () => ({ ...stats, cached: cache.size, inflight: inflight.size })
  });

  document.addEventListener('click', event => {
    if (event.target?.closest?.('#refresh')) invalidate();
  }, true);
})();
