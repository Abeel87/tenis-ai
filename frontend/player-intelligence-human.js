/* Tenis AI v8.8.8 — Player Intelligence: human-readable layer
   UI-only. Keeps v8.5 SHADOW semantics and existing calculations intact.
*/
(() => {
  'use strict';
  if (window.TENIS_AI_PLAYER_HUMAN_V888) return;

  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num = x => x == null || x === '' || !Number.isFinite(Number(x)) ? null : Number(x);
  const matchKey = m => String(m?.id ?? m?.match_id ?? [m?.p1,m?.p2,m?.scheduled_time].join('|'));
  const rows = () => { try { return typeof all !== 'undefined' && Array.isArray(all) ? all : []; } catch { return []; } };

  function decode(raw){
    try { return decodeURIComponent(String(raw || '')); } catch { return String(raw || ''); }
  }
  function findMatch(raw){
    const wanted = decode(raw);
    return rows().find(m => matchKey(m) === wanted) || null;
  }
  function pi(m){ return m?.player_intelligence_v85 || {}; }
  function profile(m, side){ return pi(m)?.profiles?.[side] || {}; }
  function ix(p, key){ return num(p?.indexes?.[key]); }

  function qualityName(q){
    const x = String(q || '').toLowerCase();
    if (x.includes('high') || x.includes('moc')) return 'Mocne dane';
    if (x.includes('medium') || x.includes('med') || x.includes('śred')) return 'Średnie dane';
    if (x.includes('low') || x.includes('słab')) return 'Słabe dane';
    return 'Za mało danych';
  }
  function surfaceName(s){
    const x = String(s || '').toLowerCase();
    if (x.includes('clay')) return 'mączka';
    if (x.includes('hard')) return 'twarda';
    if (x.includes('grass')) return 'trawa';
    if (x.includes('carpet')) return 'dywan';
    return s ? String(s) : 'nieznana';
  }
  function formatName(mu){
    const bo = Number(mu?.best_of || 0);
    if (bo === 3) return 'do 2 wygranych setów';
    if (bo === 5) return 'do 3 wygranych setów';
    return 'format N/D';
  }
  function verdict(m){
    const mu = pi(m)?.matchup || {};
    const edge = num(mu.edge_p1);
    const q = qualityName(mu.quality);
    if (edge == null) return { title:'Brak pewnego wniosku', text:'Za mało porównywalnych danych. Tego modułu nie używaj jako argumentu za żadnym zawodnikiem.', q, side:null, edge:null };
    const a = Math.abs(edge);
    if (a < 2) return { title:'Mecz praktycznie równy', text:'Player Intelligence nie widzi sensownej przewagi żadnego zawodnika.', q, side:null, edge };
    const side = edge > 0 ? m.p1 : m.p2;
    if (a < 5) return { title:`Lekka przewaga: ${side}`, text:'Różnica profili jest mała. To tylko wsparcie dla innych modeli, nie samodzielny typ.', q, side, edge };
    if (a < 9) return { title:`Przewaga profilu: ${side}`, text:'Kilka elementów profilu przemawia za tym zawodnikiem, ale moduł nadal działa tylko pomocniczo.', q, side, edge };
    return { title:`Wyraźna przewaga profilu: ${side}`, text:'Profile zawodników różnią się mocniej. Nadal nie jest to procent szans na wygraną.', q, side, edge };
  }

  const FACTORS = [
    ['Serwis','serve'],
    ['Return','return'],
    ['Forma','form'],
    ['Mental','mental']
  ];
  function factorRows(m){
    const a = profile(m,'p1'), b = profile(m,'p2');
    return FACTORS.map(([label,key]) => {
      const av = ix(a,key), bv = ix(b,key);
      if (av == null || bv == null) return null;
      const diff = av - bv, d = Math.abs(diff);
      let text = 'bardzo podobnie';
      if (d >= 8) text = `wyraźna przewaga ${diff > 0 ? m.p1 : m.p2}`;
      else if (d >= 3) text = `lekka przewaga ${diff > 0 ? m.p1 : m.p2}`;
      return {label,text,diff:d};
    }).filter(Boolean).sort((x,y)=>y.diff-x.diff).slice(0,3);
  }

  function humanHtml(m){
    const data = pi(m), mu = data.matchup || {}, v = verdict(m);
    const factors = factorRows(m);
    return `<section class="pi888-human" data-pi888-human>
      <header>
        <div><span>🧬 PLAYER INTELLIGENCE · PO LUDZKU</span><b>${esc(v.title)}</b><small>${esc(v.text)}</small></div>
        <em>${esc(v.q)}</em>
      </header>
      <div class="pi888-chips">
        <span><small>Wniosek</small><b>${v.side ? esc(v.side) : 'BRAK PRZEWAGI'}</b></span>
        <span><small>Nawierzchnia</small><b>${esc(surfaceName(data.surface || m.surface))}</b></span>
        <span><small>Format</small><b>${esc(formatName(mu))}</b></span>
      </div>
      <div class="pi888-why">
        <b>Dlaczego?</b>
        ${factors.length ? factors.map(x=>`<div><span>${esc(x.label)}</span><strong>${esc(x.text)}</strong></div>`).join('') : '<p>Za mało danych, żeby sensownie rozbić przewagę na elementy.</p>'}
      </div>
      <p class="pi888-explain"><b>SHADOW</b> = ten moduł jeszcze nie zmienia końcowego sygnału ani generatora. Opisuje profil zawodników i pomaga ocenić, czy inne modele mają dodatkowe wsparcie.</p>
    </section>`;
  }

  function humanizeDetail(m){
    if (!m) return;
    const screen = document.querySelector('.p751-detail-screen');
    const tech = screen?.querySelector('section[data-pi851-detail]');
    if (!screen || !tech || screen.querySelector('[data-pi888-human]')) return;

    tech.insertAdjacentHTML('beforebegin', humanHtml(m));
    const wrap = document.createElement('details');
    wrap.className = 'pi888-advanced';
    const summary = document.createElement('summary');
    summary.innerHTML = '<b>Zaawansowane dane</b><span>indeksy, L5/L10/L20, edge, hold, return</span><i>⌄</i>';
    tech.parentNode.insertBefore(wrap, tech);
    wrap.appendChild(summary);
    wrap.appendChild(tech);
  }

  function humanizeCards(){
    document.querySelectorAll('.pi851-card-strip').forEach(card => {
      if (card.dataset.pi888 === '1') return;
      const host = card.closest('[data-p751-open]');
      const m = host && findMatch(host.getAttribute('data-p751-open'));
      if (!m) return;
      const v = verdict(m);
      card.dataset.pi888 = '1';
      card.innerHTML = `<div class="pi888-card-head"><span>🧬 Profil zawodników</span><em>${esc(v.q)}</em></div><b>${esc(v.title)}</b><small>${esc(v.text)}</small>`;
    });
  }

  const style = document.createElement('style');
  style.id = 'pi888-human-style';
  style.textContent = `
    .pi888-card-head{display:flex;align-items:center;justify-content:space-between;gap:.5rem}.pi888-card-head span{font-size:.67rem;font-weight:800;letter-spacing:.06em;color:#68e7ff}.pi888-card-head em{font-size:.61rem;font-style:normal;color:#baff67}.pi851-card-strip[data-pi888="1"]>b{display:block;margin-top:.3rem;color:#effbff;font-size:.82rem}.pi851-card-strip[data-pi888="1"]>small{display:block;margin-top:.18rem;color:#91aab5;line-height:1.4}
    .pi888-human{margin:.75rem 1rem .55rem;padding:.9rem;border:1px solid rgba(87,221,248,.28);border-radius:17px;background:linear-gradient(145deg,rgba(4,31,43,.98),rgba(3,18,28,.98));box-shadow:0 10px 26px rgba(0,0,0,.16)}
    .pi888-human header{display:flex;justify-content:space-between;align-items:flex-start;gap:.8rem}.pi888-human header>div{display:flex;flex-direction:column;gap:.18rem}.pi888-human header span{font-size:.68rem;font-weight:900;letter-spacing:.07em;color:#68e6ff}.pi888-human header b{font-size:1.08rem;color:#f2fcff}.pi888-human header small{color:#9bb2bc;line-height:1.45}.pi888-human header em{white-space:nowrap;font-style:normal;font-size:.64rem;padding:.24rem .48rem;border-radius:999px;color:#baff65;border:1px solid rgba(180,255,98,.2);background:rgba(180,255,98,.06)}
    .pi888-chips{display:grid;grid-template-columns:repeat(3,1fr);gap:.45rem;margin-top:.7rem}.pi888-chips span{padding:.55rem .62rem;border-radius:11px;background:rgba(67,193,220,.07);border:1px solid rgba(67,193,220,.11)}.pi888-chips small{display:block;color:#718d99;font-size:.59rem}.pi888-chips b{display:block;margin-top:.12rem;color:#e8faff;font-size:.72rem}
    .pi888-why{margin-top:.75rem;padding-top:.65rem;border-top:1px solid rgba(93,190,211,.12)}.pi888-why>b{color:#eafaff}.pi888-why>div{display:grid;grid-template-columns:.7fr 1.3fr;gap:.5rem;padding:.38rem 0;border-bottom:1px solid rgba(255,255,255,.04)}.pi888-why span{color:#75929e;font-size:.68rem}.pi888-why strong{color:#dff6fc;font-size:.69rem;font-weight:700}.pi888-why p{color:#839da8;font-size:.68rem}.pi888-explain{margin:.68rem 0 0;color:#819ba6;font-size:.67rem;line-height:1.5}.pi888-explain b{color:#ffd18f}
    .pi888-advanced{margin:.45rem 1rem 1rem;border:1px solid rgba(75,178,201,.13);border-radius:13px;overflow:hidden;background:rgba(3,17,26,.58)}.pi888-advanced>summary{display:flex;align-items:center;gap:.45rem;padding:.65rem .75rem;cursor:pointer}.pi888-advanced>summary b{color:#dff7fd;font-size:.74rem}.pi888-advanced>summary span{color:#6f8995;font-size:.62rem}.pi888-advanced>summary i{margin-left:auto;font-style:normal;color:#71909d}.pi888-advanced[open]>summary i{transform:rotate(180deg)}.pi888-advanced .pi851-detail{margin:0;border:0;border-top:1px solid rgba(75,178,201,.1);border-radius:0;background:transparent}.pi888-advanced .pi851-detail-head{display:none}
    @media(max-width:720px){.pi888-human{margin:.6rem .55rem .45rem;padding:.72rem}.pi888-human header{flex-direction:column}.pi888-chips{grid-template-columns:1fr}.pi888-why>div{grid-template-columns:.65fr 1.35fr}.pi888-advanced{margin:.4rem .55rem .85rem}}
  `;
  document.head.appendChild(style);

  try {
    if (typeof renderMatches === 'function' && !renderMatches.__pi888human) {
      const base = renderMatches;
      renderMatches = function(){ const out = base.apply(this, arguments); humanizeCards(); return out; };
      renderMatches.__pi888human = true;
    }
  } catch {}

  document.addEventListener('click', e => {
    const open = e.target.closest?.('[data-p751-open]');
    if (!open) return;
    const raw = open.getAttribute('data-p751-open');
    requestAnimationFrame(() => requestAnimationFrame(() => humanizeDetail(findMatch(raw))));
  });

  humanizeCards();
  window.TENIS_AI_PLAYER_HUMAN_V888 = Object.freeze({version:'v8.8.8', humanizeCards, humanizeDetail});
})();
